"""The fiscal invoice as a printed document -- `C22`, ADR-095.

**The form is OMF nr. 118 din 28.08.2017, anexa nr. 1**, read in `V1`
(`docs/_input/cercetare/v1-factura-fiscala-omf-118-2017.md`). What that reading
gives, this module reproduces verbatim: the eight columns of the goods table
(10.1 to 10.8) with the act's own headings, the line arithmetic the Instruction
(anexa nr. 2) prescribes -- 10.5 is the product of 10.3 and 10.4, 10.7 the product
of 10.5 and 10.6, 10.8 the sum of 10.5 and 10.7 (pct. 15, 17, 18) -- and the
document total as the sum of the columns (pct. 23, 24). The amounts are not
recomputed here: the lines already hold them, derived once by the versioned
rounding rule, and the totals come from the same addition the register shows
(`C19`, `C20`).

**What the reading did not cover is convention, and is marked as such** in the
code below: the labels of the party blocks, the signature lines, the word for a
return. Columns 10.9 to 10.12 (packaging, places, gross mass) are not printed --
nothing in the document core carries them. The per-page total of row 11 is not
produced; a one-page invoice has row 11 equal to row 12, and a longer one shows
row 12 only.

**Only the legal names** (`C39`, ADR-034): the partner's `legal_name` through the
directory's own reader, the company's through `company_heading`. The internal
name exists for lists and search and does not reach a document.

**A draft is refused.** It has no number, and a form without one is not the
document; the stable code is `sales.not_printable` (`C10`). A cancelled document
is refused for the opposite reason: it keeps its number and is not to be handed
to anyone.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from evidenta.fiscal.parameters.services.scales import amount_scale
from evidenta.masterdata.partners.services.directory import (
    partner_in_context,
    vat_registration_on,
)
from evidenta.operations.sales.models import SaleNature, SalesDocument
from evidenta.platform.api.errors import ApiError
from evidenta.platform.documents.errors import DocumentNotFoundError
from evidenta.platform.documents.formatting import date_ro
from evidenta.platform.documents.printing import (
    Column,
    Columns,
    Field,
    Fields,
    PrintableDocument,
    Section,
    Signatures,
    Table,
    Text,
    file_name_of,
    render,
)
from evidenta.platform.documents.services.lifecycle import get_document
from evidenta.platform.documents.services.lines import lines_of, totals_of, vat_breakdown
from evidenta.platform.tenancy.services.companies import company_heading
from evidenta.platform.tenancy.services.tax_status import tax_status_at


class SaleNotPrintableError(ApiError):
    code = "sales.not_printable"
    status = 409


#: The document core's states in which the form exists: numbered, and not
#: withdrawn. Written as the core's values rather than imported from its models,
#: which this layer may not hold (`D6`).
PRINTABLE_STATES = frozenset({"confirmed", "posted"})

#: The document's own words. Fixed, in Romanian, never from the interface
#: resource files (`C33`, ADR-033). The column headings are the act's (anexa nr.
#: 1, columns 10.1 to 10.8); everything else is platform convention.
TITLE = "Factura fiscală"
RETURN_NOTE = (
    "Document de retur (notă de credit): sumele de mai sus reduc creanța facturii pe care o "
    "corectează."
)
SELLER = "Furnizor"
BUYER = "Cumpărător/beneficiar"
ABSENT = "—"


def columns_for(scale: int) -> tuple[Column, ...]:
    """The eight columns of annex 1, with money at the scale in force on the document's date.

    Not a module constant: the decimals of an amount are `accounting.amount_scale`,
    a dated fiscal parameter (R15, ADR-037 section 3.2), and a `2` written here
    would be that parameter compiled into code -- correct until the day it moves,
    then silently re-rounding every earlier invoice reprinted (R18).
    """
    return (
        Column(
            "10.1 Denumirea mărfurilor/activelor, serviciilor și codul poziției tarifare al "
            "mărfii/activului",
            weight=8,
        ),
        Column("10.2 Unitatea de măsură", weight=2),
        Column("10.3 Cantitatea mărfurilor/activelor, volumul serviciilor", "right", 3, None),
        Column("10.4 Preț unitar fără TVA, lei", "right", 3, None, min_places=scale),
        Column("10.5 Valoarea totală fără TVA, lei", "right", 3, scale),
        Column("10.6 Cota TVA, %", "right", 2, None),
        Column("10.7 Suma totală a TVA, lei", "right", 3, scale),
        Column("10.8 Valoarea mărfurilor/activelor, serviciilor, lei", "right", 3, scale),
    )


TOTAL_ROW = "12. TOTAL (pe factura fiscală)"


def invoice_printable(document_id: uuid.UUID) -> PrintableDocument:
    """The invoice as the value the pipeline prints. Absent and not-visible are
    one answer, 404 (IZ-04); unnumbered is 409 with its own code."""
    document = get_document(document_id)
    sale = (
        SalesDocument.objects.filter(document_id=document_id)
        .values_list("nature", flat=True)
        .first()
    )
    if sale is None:
        raise DocumentNotFoundError(f"document {document_id} is not a sale visible in this context")
    if document.state not in PRINTABLE_STATES or not document.formatted_number:
        raise SaleNotPrintableError(
            f"document {document_id} is {document.state}; only a validated or posted "
            f"invoice has a number to print"
        )

    seller = company_heading(document.company_id)
    seller_vat = tax_status_at(document.company_id, document.document_date)["vat"]
    seller_block = Fields(
        SELLER,
        (
            Field("Denumirea", seller.legal_name),
            Field("IDNO", seller.idno),
            Field("Codul TVA", seller_vat.get("code") or ABSENT),
        ),
    )
    buyer_block = Fields(BUYER, _buyer(document.partner_id, document.document_date))

    # The rate per treatment, read off the lines the way the posting reads it:
    # one rate per regime on a document priced on one date.
    rates = {piece.vat_regime_code: piece.vat_rate for piece in vat_breakdown(document_id)}
    rows = tuple(
        (
            line.description,
            "",  # 10.2: the sales line carries no unit yet; the column is the form's.
            line.quantity,
            line.unit_price,
            line.net_amount,
            rates.get(line.vat_regime_code, Decimal(0)),
            line.vat_amount,
            line.total_amount,
        )
        for line in lines_of(document_id)
    )
    totals = totals_of(document_id)
    table = Table(
        columns_for(amount_scale(document.document_date)),
        rows,
        footer=((TOTAL_ROW, "", "", "", totals.net, "", totals.vat, totals.total),),
    )

    sections: list[Section] = [
        Fields(
            None,
            (
                Field("Seria și numărul", document.formatted_number),
                Field("Data", document.document_date),
            ),
        ),
        Columns(seller_block, buyer_block),
        table,
    ]
    if sale == SaleNature.RETURN:
        sections.append(Text(RETURN_NOTE, "note"))
    sections.append(Signatures((f"{SELLER} (semnătura)", f"{BUYER} (semnătura)")))

    return PrintableDocument(
        title=TITLE,
        subtitle=f"Nr. {document.formatted_number} din {date_ro(document.document_date)}",
        sections=tuple(sections),
        file_name=file_name_of("factura", document.formatted_number),
        # The form is a turned sheet: eight columns do not fit an upright one.
        landscape=True,
    )


def invoice_pdf(document_id: uuid.UUID) -> bytes:
    return render(invoice_printable(document_id))


def _buyer(partner_id: uuid.UUID | None, on: object) -> tuple[Field, ...]:
    """The counterparty as the directory names it on the document's date.

    `legal_name`, never `internal_name` (`C39`). The VAT code is the registration
    in force on the document's date, not today's (ADR-044): the document records
    what was true when it was issued.
    """
    if partner_id is None:
        return (Field("Denumirea", ABSENT),)
    partner = partner_in_context(partner_id)
    registration = vat_registration_on(partner_id, on)  # type: ignore[arg-type]
    identifier = partner.get("idno") or partner.get("idnp") or ABSENT
    return (
        Field("Denumirea", str(partner["legal_name"])),
        Field("IDNO", str(identifier)),
        Field("Codul TVA", registration.vat_code if registration is not None else ABSENT),
    )
