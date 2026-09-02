"""Writing the positions of a document.

Only on a draft. The trigger on `document_line` refuses everything else, so this
service is the readable half of a guarantee the database holds -- the same
division `journal_line` uses, and for the same reason: a bulk import and a data
migration never call a service.

**Nothing here computes an amount.** `net`, `vat` and `total` arrive as inputs
and are checked against the one identity that involves no rounding,
``total = net + vat``. Deriving `net` from quantity and price, or `vat` from the
rate, means reducing an exact product to a stored scale -- and *which* rounding
rule does that is versioned fiscal logic selected by the effective date (`R16`,
`R17`), open on three axes at once: where VAT is rounded (per line or per
document), in which direction at a tie, and to how many decimals (ADR-037
sections 3.1 to 3.3, `DNB-08`). A helper here that rounded would be that
decision, taken silently by the layer least entitled to take it.

So the contract is: whoever knows the rule computes; this layer stores what it
was given and refuses what cannot be true whatever the rule turns out to be.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from decimal import Decimal

from django.db import transaction
from django.db.models import Sum

from evidenta.platform.documents.errors import (
    DocumentNotEditableError,
    DocumentNotFoundError,
    LineAmountsInconsistentError,
    VatRegimeRequiredError,
)
from evidenta.platform.documents.models import EDITABLE_STATES, Document, DocumentLine


@dataclass(frozen=True, slots=True)
class LineInput:
    """One position, as the caller states it.

    Every monetary field is a `Decimal` and stays one. `float` is refused at
    construction rather than converted: it makes the same document total
    differently depending on the order the lines are added, and the failure shows
    up as a few bani nobody can attribute to anything.
    """

    description: str
    quantity: Decimal
    unit_price: Decimal

    #: The treatment, as a code from the fiscal nomenclature. Required: a
    #: position with no VAT treatment cannot be declared, and an empty string is
    #: not a treatment.
    vat_regime_code: str
    #: The rate as a percentage -- `20`, not `0.20` -- resolved from the
    #: nomenclature by date and copied here by the caller.
    vat_rate: Decimal

    net_amount: Decimal
    vat_amount: Decimal
    total_amount: Decimal

    item_id: uuid.UUID | None = None
    unit_id: uuid.UUID | None = None
    unit_code: str = ""
    discount_percent: Decimal | None = None
    discount_amount: Decimal = field(default=Decimal(0))
    vat_rate_key: str | None = None
    source_line_id: uuid.UUID | None = None

    def __post_init__(self) -> None:
        for name in (
            "quantity",
            "unit_price",
            "vat_rate",
            "net_amount",
            "vat_amount",
            "total_amount",
            "discount_amount",
        ):
            value = getattr(self, name)
            if not isinstance(value, Decimal):
                raise TypeError(
                    f"{name} must be Decimal, got {type(value).__name__}. "
                    f"Converting silently is how a float reaches a document total."
                )
        if self.discount_percent is not None and not isinstance(self.discount_percent, Decimal):
            raise TypeError("discount_percent must be Decimal, never float")
        if not self.vat_regime_code.strip():
            raise VatRegimeRequiredError(
                "a position needs a VAT treatment code. Exempt and zero-rated both "
                "carry a rate of 0 and are different facts; a declaration that "
                "cannot tell them apart is filed wrong."
            )
        if self.total_amount != self.net_amount + self.vat_amount:
            raise LineAmountsInconsistentError(
                f"total {self.total_amount} is not net {self.net_amount} plus VAT "
                f"{self.vat_amount}. This is exact addition, not rounding."
            )


def _document(document_id: uuid.UUID) -> Document:
    """The document, read under the policy. Absent, never forbidden (IZ-04)."""
    document = Document.objects.filter(id=document_id).first()
    if document is None:
        raise DocumentNotFoundError(f"document {document_id} is not visible in this context")
    return document


def assert_editable(document: Document) -> None:
    if document.state not in EDITABLE_STATES:
        raise DocumentNotEditableError(
            f"document {document.id} is {document.state} and its positions are "
            f"frozen; a correction is a reversal and a new document"
        )


@transaction.atomic
def replace_lines(document_id: uuid.UUID, lines: Sequence[LineInput]) -> list[DocumentLine]:
    """Set the document's positions to exactly this list, renumbered from 1.

    Replace rather than patch, because a draft's positions are edited as a block
    on every screen that shows them, and reconciling a partial update against
    `line_no` produces gaps and duplicates that the unique constraint then
    reports as an integrity error nobody can read.

    Takes the identifier rather than the row: this is a public service, and a
    module that had to hold a `Document` to call it would have to import the
    document core's models -- `D6`, the coupling the rule exists to stop.
    """
    document = _document(document_id)
    assert_editable(document)
    document.lines.all().delete()
    return [_write(document, line, position) for position, line in enumerate(lines, start=1)]


@transaction.atomic
def add_line(document_id: uuid.UUID, line: LineInput) -> DocumentLine:
    """Append one position after the last.

    The position is computed under the document's own row rather than read: two
    concurrent appends would otherwise choose the same `line_no`, and the unique
    constraint would refuse the second with an error about an index.
    """
    document = _document(document_id)
    assert_editable(document)
    Document.objects.select_for_update().get(pk=document.pk)
    last = document.lines.order_by("-line_no").values_list("line_no", flat=True).first()
    return _write(document, line, (last or 0) + 1)


def _write(document: Document, line: LineInput, position: int) -> DocumentLine:
    return DocumentLine.objects.create(
        tenant_id=document.tenant_id,
        company_id=document.company_id,
        document=document,
        line_no=position,
        item_id=line.item_id,
        description=line.description,
        quantity=line.quantity,
        unit_id=line.unit_id,
        unit_code=line.unit_code,
        unit_price=line.unit_price,
        discount_percent=line.discount_percent,
        discount_amount=line.discount_amount,
        net_amount=line.net_amount,
        vat_regime_code=line.vat_regime_code,
        vat_rate_key=line.vat_rate_key,
        vat_rate=line.vat_rate,
        vat_amount=line.vat_amount,
        total_amount=line.total_amount,
        source_line_id=line.source_line_id,
    )


def copy_lines(
    source: Document, target: Document, *, invert_signs: bool = False
) -> list[DocumentLine]:
    """Carry the positions of one document onto another, keeping the trail.

    Internal to the document core -- `reversal` and `conversion` call it with rows
    they have just built. Nothing outside the module holds a `Document`.

    Every copy records `source_line_id`, so a position on an invoice can be
    traced back to the proforma position it came from and a storno position to
    the one it undoes -- the documentary half of the navigation `R13` asks for.

    ``invert_signs`` flips the quantity and the four monetary amounts and leaves
    the unit price, the rate and the discount percentage alone: those describe
    *how* the position was priced, and a storno undoes the amount, not the price
    list. ``total = net + vat`` survives the flip because negating both sides of
    an addition is still an addition.
    """
    assert_editable(target)
    sign = Decimal(-1) if invert_signs else Decimal(1)
    copied: list[DocumentLine] = []
    for line in source.lines.order_by("line_no"):
        copied.append(
            DocumentLine.objects.create(
                tenant_id=target.tenant_id,
                company_id=target.company_id,
                document=target,
                line_no=line.line_no,
                item_id=line.item_id,
                description=line.description,
                quantity=line.quantity * sign,
                unit_id=line.unit_id,
                unit_code=line.unit_code,
                unit_price=line.unit_price,
                discount_percent=line.discount_percent,
                discount_amount=line.discount_amount * sign,
                net_amount=line.net_amount * sign,
                vat_regime_code=line.vat_regime_code,
                vat_rate_key=line.vat_rate_key,
                vat_rate=line.vat_rate,
                vat_amount=line.vat_amount * sign,
                total_amount=line.total_amount * sign,
                source_line=line,
            )
        )
    return copied


@dataclass(frozen=True, slots=True)
class DocumentTotals:
    """What the positions come to, added exactly.

    Addition only -- no rate is applied and nothing is rounded, so this is
    arithmetic rather than a VAT calculation. Whether the document's VAT is the
    sum of its lines or the rate applied to the total base is ADR-037 section
    3.1, open, and this function does not answer it: it reports the sum of what
    is stored.
    """

    net: Decimal
    vat: Decimal
    total: Decimal


def totals_of(document_id: uuid.UUID) -> DocumentTotals:
    net = Decimal(0)
    vat = Decimal(0)
    for line in DocumentLine.objects.filter(document_id=document_id):
        net += line.net_amount
        vat += line.vat_amount
    return DocumentTotals(net=net, vat=vat, total=net + vat)


@dataclass(frozen=True, slots=True)
class VatSlice:
    """The document's positions that share one VAT treatment, added exactly.

    Grouped by the regime **and** the rate it resolved to, because the two can
    part ways over time: the same regime code priced in March and in June may
    carry different rates, and a posting that stamps a rate on a formula (ADR-048)
    has to say which one.
    """

    vat_regime_code: str
    vat_rate_key: str | None
    vat_rate: Decimal
    net: Decimal
    vat: Decimal


def vat_breakdown(document_id: uuid.UUID) -> tuple[VatSlice, ...]:
    """`totals_of`, split by VAT treatment -- what a posting with VAT consumes.

    Addition only, like `totals_of`: the rate is read off the lines, never
    re-applied, so the slices add up to exactly what the lines carry. A document
    whose positions all share one treatment comes back as one slice; a document
    with no positions comes back empty.

    Ordered by rate, highest first, then by regime code -- a stable order so the
    formulas a handler derives from it are numbered the same way every time the
    same document is posted.
    """
    rows = (
        DocumentLine.objects.filter(document_id=document_id)
        .values("vat_regime_code", "vat_rate_key", "vat_rate")
        .annotate(net=Sum("net_amount"), vat=Sum("vat_amount"))
        .order_by("-vat_rate", "vat_regime_code")
    )
    return tuple(
        VatSlice(
            vat_regime_code=str(row["vat_regime_code"]),
            vat_rate_key=row["vat_rate_key"],
            vat_rate=Decimal(row["vat_rate"]),
            net=Decimal(row["net"]),
            vat=Decimal(row["vat"]),
        )
        for row in rows
    )


def totals_of_many(document_ids: Iterable[uuid.UUID]) -> dict[uuid.UUID, DocumentTotals]:
    """`totals_of` for a list: one grouped query instead of one per row.

    Every id asked for is in the result. A document with no positions comes back
    with zeros, exactly as `totals_of` reports it, because a list and the detail
    it opens into must show the same figure -- a row missing from the result
    would read as "unknown" where the truth is "nothing yet".

    The same arithmetic as `totals_of` and no more: the database adds what is
    stored, per document, and applies no rate.
    """
    ids = list(document_ids)
    zero = Decimal(0)
    totals = {document_id: DocumentTotals(net=zero, vat=zero, total=zero) for document_id in ids}
    summed = (
        DocumentLine.objects.filter(document_id__in=ids)
        .values("document_id")
        .annotate(net=Sum("net_amount"), vat=Sum("vat_amount"))
    )
    for row in summed:
        net = Decimal(row["net"])
        vat = Decimal(row["vat"])
        totals[row["document_id"]] = DocumentTotals(net=net, vat=vat, total=net + vat)
    return totals
