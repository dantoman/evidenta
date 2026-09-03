"""Commercial documents in the ledger -- ADR-073: the two invoices, and the money.

**The form is fixed and it is small**: a sale recognises revenue against a
receivable, for the document's total. What is not small is choosing *which*
receivable and *which* revenue, and both choices are carried on the fact rather
than derived -- ADR-073 §2, on the pattern ADR-057 fixed for settlement.

**Nothing here knows an account code** (`R15`, ADR-036 §5.1). The handler asks for
roles; `bind_roles` turns them into accounts through the company's own bindings at
the posting's date, or refuses with the binding's code.

**VAT, since ADR-089, and still one treatment per event.** The fact carries the
document's net, its VAT and the VAT split by rate; the handler posts the net
against revenue or cost and each VAT share against the VAT account, with the
rate stamped on the formula (ADR-048). What is *not* here is a second treatment
selected by the company's fiscal status: how a dated status reaches handler
selection is `OD-130`, deferred to the third case, and this -- the second -- takes
the reversible form instead. The status decides upstream: whether a sale may
carry VAT at all is the document layer's refusal on the document's date, and
whether a purchase's VAT is deductible is a discriminator on the fact, derived by
the purchases module from the status on the accounting date and checked here
against the stamp `emit` wrote (ADR-088). A handler reads amounts and booleans;
it never asks who the company is.

**Goods and finished products are refused, with a code.** Their revenue is
recognised the same way, but the entry has a second half -- the stock leaving --
and that is F4. A handler posting only the first half would produce a month whose
margin equals its turnover: balanced, plausible, false.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from django.db import transaction

from evidenta.accounting.currency.money import rounding_for
from evidenta.accounting.events.registry import (
    HANDLERS,
    EventType,
    HandlerVersion,
    register,
)
from evidenta.accounting.events.services.emission import emit
from evidenta.accounting.events.services.lifecycle import mark_failed, mark_posted
from evidenta.accounting.ledger.services.writing import ParameterStamp, entry_id_of_event
from evidenta.accounting.posting.formula import RoleFormula, bind_roles
from evidenta.accounting.posting.invariants import Origin
from evidenta.accounting.posting.resolution import selected_treatment
from evidenta.accounting.posting.services.formulas import post_formulas
from evidenta.fiscal.parameters.services.resolution import resolve_parameter
from evidenta.fiscal.parameters.services.scales import AMOUNT_SCALE_KEY, amount_scale
from evidenta.platform.api.errors import ApiError
from evidenta.platform.documents.services.lines import VatSlice
from evidenta.platform.numbering.services.allocation import NumberingError

SOURCE_MODULE = "sales"
SOURCE_DOCUMENT_TYPE = "sales.document"

EVENT_SALE = "sales.invoice_issued"
HANDLER_SALE = "sales.invoice_issued.v1"

ROLE_CREANTE_TARA = "CREANTE_COMERCIALE_TARA"
ROLE_CREANTE_STRAINATATE = "CREANTE_COMERCIALE_STRAINATATE"
ROLE_VENIT_SERVICII = "VENIT_SERVICII"
ROLE_VENIT_MARFURI = "VENIT_MARFURI"
ROLE_VENIT_PRODUSE = "VENIT_PRODUSE"

#: 5344, „Datorii privind taxa pe valoarea adăugată" -- the VAT collected on a
#: sale, and reduced by a return. In the catalogue since ADR-048; asked for
#: since ADR-089.
ROLE_TVA_COLECTATA = "TVA_COLECTATA"

SALE_ROLES = (
    ROLE_CREANTE_TARA,
    ROLE_CREANTE_STRAINATATE,
    ROLE_VENIT_SERVICII,
    ROLE_TVA_COLECTATA,
)

EVENT_RETURN = "sales.return_issued"
HANDLER_RETURN = "sales.return_issued.v1"

#: 7128, „Returnări și reduceri" -- ADR-073 §7. A **distribution expense**, not a
#: reversal of revenue: the standard's chart puts the return in class 712 beside
#: the other costs of selling, and posting it as negative revenue would flatter
#: turnover in a way the trial balance cannot show.
ROLE_RETUR_REDUCERI = "RETUR_REDUCERI"

RETURN_ROLES = (
    ROLE_CREANTE_TARA,
    ROLE_CREANTE_STRAINATATE,
    ROLE_RETUR_REDUCERI,
    ROLE_TVA_COLECTATA,
)

#: What is sold, and the role that recognises it. Enumerated in code: the value
#: selects which role is asked for, which is posting form (`R28`).
REVENUE_ROLES = {
    "services": ROLE_VENIT_SERVICII,
    "goods": ROLE_VENIT_MARFURI,
    "products": ROLE_VENIT_PRODUSE,
}

#: The two that need the other half of the entry, and therefore F4.
NEEDS_INVENTORY = ("goods", "products")

PAYLOAD_FIELDS = (
    "document_id",
    "total",
    "net",
    "vat",
    "vat_by_rate",
    "currency",
    "exchange_rate",
    "rate_date",
    "revenue_kind",
    "partner_resident",
    "partner_id",
)


class SalesPostingError(ApiError):
    code = "sales.posting_payload_invalid"
    status = 422


class SalesDiscriminatorMissingError(ApiError):
    """The fact does not say which receivable or which revenue this is.

    Its own code, because the fix is different: something upstream has to *decide*,
    and a default here would decide for it -- in the direction that looks harmless.
    """

    code = "sales.discriminator_missing"
    status = 422


class CostSideRequiresInventoryError(ApiError):
    """Revenue from goods without the stock leaving the books is half an entry.

    Refused rather than half-posted (ADR-073 §3). The refusal names inventory so
    the reader knows this is a sequencing fact, not a defect.
    """

    code = "sales.cost_side_requires_inventory"
    status = 409


@dataclass(frozen=True, slots=True)
class VatShare:
    """The part of a document's VAT that was calculated at one rate.

    ``rate_key`` is the parameter the rate was resolved under (`R18`), and may be
    absent for a document whose amounts arrived from elsewhere -- a rate without
    a key is an import, a key without a rate is nothing. The share becomes one
    formula against the VAT account, with the rate stamped on it (ADR-048), so
    the ledger of 5344 can be read by rate without going back to the documents.
    """

    rate_key: str | None
    rate: Decimal
    net: Decimal
    vat: Decimal

    def as_payload(self) -> dict[str, Any]:
        return {
            "rate_key": self.rate_key,
            "rate": str(self.rate),
            "net": str(self.net),
            "vat": str(self.vat),
        }


def vat_shares(slices: Iterable[VatSlice]) -> tuple[VatShare, ...]:
    """Fold the document core's per-regime slices into per-rate shares.

    Two exempt regimes at zero are one share of zero; two taxable regimes that
    happen to resolve through the same key at the same rate are one share. The
    ledger cares about the rate, the register about the regime, and the fact
    carries what the ledger consumes.
    """
    folded: dict[tuple[str | None, Decimal], VatShare] = {}
    for piece in slices:
        key = (piece.vat_rate_key, piece.vat_rate)
        current = folded.get(key)
        folded[key] = VatShare(
            rate_key=piece.vat_rate_key,
            rate=piece.vat_rate,
            net=(current.net if current else Decimal(0)) + piece.net,
            vat=(current.vat if current else Decimal(0)) + piece.vat,
        )
    return tuple(folded.values())


@dataclass(frozen=True, slots=True)
class SalesInvoiceFact:
    """What the ledger needs to know about an issued invoice.

    A dataclass owned by `accounting`, not a row from `operations` -- the same
    seam `SettlementFact` draws, and for the same reason: a signature that named
    `SalesDocument` would make the shape of another module's table part of this
    one's contract.

    ``total`` is ``net + vat`` and all three are carried rather than two derived:
    the handler checks the identity, and a fact that only stated two of them
    would let a rounding on the way in pass as a document that adds up.
    """

    document_id: uuid.UUID
    partner_id: uuid.UUID
    accounting_date: date
    document_date: date
    total: Decimal
    net: Decimal
    vat: Decimal
    currency: str
    revenue_kind: str
    partner_resident: bool
    description: str
    vat_by_rate: tuple[VatShare, ...] = ()
    #: The header's rate and the day it was taken for (ADR-039 section 3.2,
    #: ADR-097): exactly 1 and unused in the functional currency; on a document
    #: in another currency the amounts above are in that currency and the
    #: handler derives the lei from them, once, at the scale in force.
    exchange_rate: Decimal = Decimal(1)
    rate_date: date | None = None

    def as_payload(self) -> dict[str, Any]:
        return {
            "document_id": str(self.document_id),
            "partner_id": str(self.partner_id),
            "total": str(self.total),
            "net": str(self.net),
            "vat": str(self.vat),
            "vat_by_rate": [share.as_payload() for share in self.vat_by_rate],
            "currency": self.currency,
            "exchange_rate": str(self.exchange_rate),
            "rate_date": str(self.rate_date or self.document_date),
            "revenue_kind": self.revenue_kind,
            "partner_resident": self.partner_resident,
            "document_date": str(self.document_date),
        }


@dataclass(frozen=True, slots=True)
class SalesPostingResult:
    accounting_event_id: uuid.UUID
    journal_entry_id: uuid.UUID | None
    formulas: int
    posted_now: bool


def recognise_sale(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    accounting_date: date,
    functional_currency: str,
    payload: dict[str, Any],
) -> tuple[RoleFormula, ...]:
    """The pure treatment: one formula, receivable against revenue.

    Pure in the sense the registry needs -- it reads the payload and returns
    formulas, touching no table. What it does not do is decide anything the fact
    did not say: an absent discriminator is a refusal here, not a choice.
    """
    del tenant_id, company_id

    kind = payload.get("revenue_kind")
    if kind not in REVENUE_ROLES:
        raise SalesDiscriminatorMissingError(
            f"revenue_kind is {kind!r}; a sale says what it sells, because that is "
            f"what selects the revenue account"
        )
    if kind in NEEDS_INVENTORY:
        raise CostSideRequiresInventoryError(
            f"a sale of {kind} recognises revenue and takes stock off the books; the "
            f"second half needs inventory, which is not built. Refused rather than "
            f"posted half, which would make the margin equal the turnover"
        )

    resident = payload.get("partner_resident")
    if not isinstance(resident, bool):
        raise SalesDiscriminatorMissingError(
            "the invoice does not say whether the counterparty is a resident; the "
            "receivable account differs, and `partner` carries no residence, so it "
            "is asked for rather than assumed (ADR-073 §2)"
        )

    net, shares = _amounts(payload, SalesPostingError)
    if net <= 0:
        raise SalesPostingError("a sale is posted for a positive net; a return is its own document")

    money = _conversion(payload, functional_currency, accounting_date, SalesPostingError)

    receivable = ROLE_CREANTE_TARA if resident else ROLE_CREANTE_STRAINATATE
    document_date = date.fromisoformat(str(payload["document_date"]))
    formulas = [
        RoleFormula(
            debit_role=receivable,
            credit_role=REVENUE_ROLES[kind],
            amount=money.functional(net),
            currency=money.currency,
            amount_currency=net,
            exchange_rate=money.rate,
            rate_date=money.rate_date,
            document_date=document_date,
            description="Venit din prestarea serviciilor",
        )
    ]
    # One formula per rate, the receivable growing by each: the customer owes
    # the total, the revenue is the net, and the difference is owed onward to
    # the budget through 5344. The rate rides on the formula (ADR-048). On a
    # document in another currency the VAT is the document's share in that
    # currency, turned into lei at the header's rate like the net (ADR-097).
    for share in shares:
        if share.vat == 0:
            continue
        formulas.append(
            RoleFormula(
                debit_role=receivable,
                credit_role=ROLE_TVA_COLECTATA,
                amount=money.functional(share.vat),
                currency=money.currency,
                amount_currency=share.vat,
                exchange_rate=money.rate,
                rate_date=money.rate_date,
                document_date=document_date,
                vat_rate=share.rate,
                vat_rate_key=share.rate_key,
                description="TVA aferentă livrării",
            )
        )
    return tuple(formulas)


def recognise_return(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    accounting_date: date,
    functional_currency: str,
    payload: dict[str, Any],
) -> tuple[RoleFormula, ...]:
    """A return: the receivable comes down against a distribution expense.

    **Not the sale's entry with the signs swapped**, and the difference is what
    ends up in the profit and loss account. `7128` sits in class 712 with the
    other costs of selling; crediting revenue instead would leave turnover
    understated by exactly the returns, which no total in the trial balance
    disagrees with.

    The same discriminators as a sale, refused the same way -- and goods and
    products are refused for the same reason once more: a return puts stock back
    on the books, and that half is F4.
    """
    del tenant_id, company_id

    kind = payload.get("revenue_kind")
    if kind not in REVENUE_ROLES:
        raise SalesDiscriminatorMissingError(
            f"revenue_kind is {kind!r}; a return says what came back, because a "
            f"return of goods has a stock half and a return of services has none"
        )
    if kind in NEEDS_INVENTORY:
        raise CostSideRequiresInventoryError(
            f"a return of {kind} puts stock back on the books; the second half needs "
            f"inventory, which is not built"
        )

    resident = payload.get("partner_resident")
    if not isinstance(resident, bool):
        raise SalesDiscriminatorMissingError(
            "the return does not say whether the counterparty is a resident; the "
            "receivable it reduces differs by that (ADR-073 §2)"
        )

    net, shares = _amounts(payload, SalesPostingError)
    if net <= 0:
        raise SalesPostingError(
            "a return is posted for a positive net; the direction is the "
            "document's nature, never the sign"
        )

    money = _conversion(payload, functional_currency, accounting_date, SalesPostingError)

    receivable = ROLE_CREANTE_TARA if resident else ROLE_CREANTE_STRAINATATE
    document_date = date.fromisoformat(str(payload["document_date"]))
    formulas = [
        RoleFormula(
            debit_role=ROLE_RETUR_REDUCERI,
            credit_role=receivable,
            amount=money.functional(net),
            currency=money.currency,
            amount_currency=net,
            exchange_rate=money.rate,
            rate_date=money.rate_date,
            document_date=document_date,
            description="Retur de la client",
        )
    ]
    # The VAT collected on the delivery comes back down: 5344 is debited, the
    # receivable credited, one formula per rate like the sale it answers.
    for share in shares:
        if share.vat == 0:
            continue
        formulas.append(
            RoleFormula(
                debit_role=ROLE_TVA_COLECTATA,
                credit_role=receivable,
                amount=money.functional(share.vat),
                currency=money.currency,
                amount_currency=share.vat,
                exchange_rate=money.rate,
                rate_date=money.rate_date,
                document_date=document_date,
                vat_rate=share.rate,
                vat_rate_key=share.rate_key,
                description="TVA aferentă returului",
            )
        )
    return tuple(formulas)


@dataclass(frozen=True, slots=True)
class _Conversion:
    """How the amounts of one document become lei -- Spec B section 7.1.

    In the functional currency the rate is exactly 1 and ``functional`` is the
    identity, so a lei document is not a special case. In another currency the
    header's rate multiplies each amount and the product is reduced **once** to
    the scale in force on the accounting date, with the rounding rule of that
    date (`R17`, `R18`, ADR-037) -- the derivation `currency.money.convert`
    states, done here per formula because each formula is its own line.
    """

    currency: str
    rate: Decimal
    rate_date: date
    quantize: Callable[[Decimal], Decimal] | None

    def functional(self, amount_currency: Decimal) -> Decimal:
        if self.quantize is None:
            return amount_currency
        return self.quantize(amount_currency * self.rate)


def _conversion(
    payload: dict[str, Any], functional_currency: str, accounting_date: date, error: type[ApiError]
) -> _Conversion:
    """Read the header's currency and rate off the fact, refusing a rate that is
    not one. ``rate_date`` is the day the rate was taken for (ADR-039 section
    3.2); on a lei document it is the accounting date, as it always was."""
    currency = str(payload.get("currency"))
    if currency == functional_currency:
        return _Conversion(currency, Decimal(1), accounting_date, None)
    rate = _decimal(payload.get("exchange_rate"), "exchange_rate", error)
    if rate <= 0:
        raise error(f"exchange_rate {rate} erases or inverts the amount")
    raw_date = payload.get("rate_date") or payload.get("document_date")
    try:
        rate_date = date.fromisoformat(str(raw_date))
    except ValueError:
        raise error(f"rate_date {raw_date!r} is not a date") from None
    rule = rounding_for(accounting_date)
    scale = amount_scale(accounting_date)
    return _Conversion(currency, rate, rate_date, lambda value: rule.quantize(value, scale))


def _scale_stamps(
    fact_currency: str, functional_currency: str, on: date
) -> tuple[ParameterStamp, ...]:
    """The stamp a converted document carries (ADR-047): the lei amounts are
    derived, and the scale they were reduced to is what they stood on. A lei
    document derives nothing and stamps nothing, as before."""
    if fact_currency == functional_currency:
        return ()
    row = resolve_parameter(AMOUNT_SCALE_KEY, on)
    return (
        ParameterStamp(
            parameter_id=uuid.UUID(str(row.pk)),
            parameter_key=AMOUNT_SCALE_KEY,
            effective_date=on,
            confidence=row.source_confidence,
            resolved_at=datetime.now(UTC),
        ),
    )


def _decimal(value: Any, field: str, error: type[ApiError] = SalesPostingError) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, str):
        try:
            return Decimal(value)
        except ArithmeticError as failure:
            raise error(f"{field} is {value!r}") from failure
    raise error(f"{field} must be a Decimal or its string, never a float")


def _amounts(
    payload: dict[str, Any], error: type[ApiError]
) -> tuple[Decimal, tuple[VatShare, ...]]:
    """The net and the VAT shares, checked against each other and against the total.

    Three identities, refused rather than repaired: ``total = net + vat``, the
    shares add up to ``vat``, and the shares' nets add up to ``net``. A fact that
    failed any of them was assembled from two different readings of one document,
    and posting the one that balances would hide which.
    """
    total = _decimal(payload.get("total"), "total", error)
    net = _decimal(payload.get("net"), "net", error)
    vat = _decimal(payload.get("vat"), "vat", error)
    if vat < 0:
        raise error("VAT is not negative; a return is its own document")
    if net + vat != total:
        raise error(f"total {total} is not net {net} plus VAT {vat}")

    raw = payload.get("vat_by_rate")
    if not isinstance(raw, list):
        raise error("vat_by_rate is missing; a document with VAT says at which rates")
    shares: list[VatShare] = []
    for item in raw:
        if not isinstance(item, dict):
            raise error("a VAT share is a mapping of rate_key, rate, net and vat")
        rate_key = item.get("rate_key")
        if rate_key is not None and not isinstance(rate_key, str):
            raise error(f"rate_key is {rate_key!r}, not a parameter key")
        rate = _decimal(item.get("rate"), "rate", error)
        share_net = _decimal(item.get("net"), "net", error)
        share_vat = _decimal(item.get("vat"), "vat", error)
        if rate < 0 or share_net < 0 or share_vat < 0:
            raise error("a VAT share carries no negative figure")
        if share_vat > 0 and rate == 0:
            raise error(f"a VAT of {share_vat} at a rate of zero is a share that cannot exist")
        shares.append(VatShare(rate_key=rate_key, rate=rate, net=share_net, vat=share_vat))
    if sum((share.vat for share in shares), Decimal(0)) != vat:
        raise error(f"the VAT shares do not add up to the document's VAT {vat}")
    if sum((share.net for share in shares), Decimal(0)) != net:
        raise error(f"the VAT shares' nets do not add up to the document's net {net}")
    return net, tuple(shares)


HANDLERS[HANDLER_SALE] = recognise_sale

register(
    EventType(
        name=EVENT_SALE,
        payload_fields=PAYLOAD_FIELDS,
        account_roles=SALE_ROLES,
        handlers=(HandlerVersion(implementation_ref=HANDLER_SALE, valid_from=date.min),),
        description="An issued sales invoice: revenue recognised against the receivable.",
    )
)

HANDLERS[HANDLER_RETURN] = recognise_return

register(
    EventType(
        name=EVENT_RETURN,
        payload_fields=PAYLOAD_FIELDS,
        account_roles=RETURN_ROLES,
        handlers=(HandlerVersion(implementation_ref=HANDLER_RETURN, valid_from=date.min),),
        description="An issued credit note: the receivable reduced against returns.",
    )
)


SOURCE_MODULE_PURCHASE = "purchases"
SOURCE_DOCUMENT_TYPE_PURCHASE = "purchases.document"

EVENT_PURCHASE = "purchases.invoice_recorded"
HANDLER_PURCHASE = "purchases.invoice_recorded.v1"

ROLE_DATORII_TARA = "DATORII_COMERCIALE_TARA"
ROLE_DATORII_STRAINATATE = "DATORII_COMERCIALE_STRAINATATE"
ROLE_CHELTUIELI_ADMINISTRATIVE = "CHELTUIELI_SERVICII_ADMINISTRATIVE"
ROLE_ALTE_CHELTUIELI_DISTRIBUIRE = "ALTE_CHELTUIELI_DISTRIBUIRE"
ROLE_PRODUCTIE_DE_BAZA = "PRODUCTIE_DE_BAZA"
ROLE_COSTURI_INDIRECTE = "COSTURI_INDIRECTE_PRODUCTIE"

#: 2252, „Creanțe ale bugetului privind taxa pe valoarea adăugată" -- the VAT a
#: registered buyer may deduct. A buyer that is not registered bears the VAT as
#: part of the cost, and this role is not asked for.
ROLE_TVA_DEDUCTIBILA = "TVA_DEDUCTIBILA"

#: Where the cost lands, and the role that carries it -- ADR-073 §4, verbatim.
#:
#: The destination selects **which role is asked for**; it never conditions which
#: account a role binds to. Two of the four roles were added with ADR-073; the two
#: production ones already existed, which is why there are two new roles here and
#: not four.
COST_ROLES = {
    "administrative": ROLE_CHELTUIELI_ADMINISTRATIVE,
    "commercial": ROLE_ALTE_CHELTUIELI_DISTRIBUIRE,
    "production_direct": ROLE_PRODUCTIE_DE_BAZA,
    "production_indirect": ROLE_COSTURI_INDIRECTE,
}

PURCHASE_ROLES = (
    ROLE_DATORII_TARA,
    ROLE_DATORII_STRAINATATE,
    *COST_ROLES.values(),
    ROLE_TVA_DEDUCTIBILA,
)

PURCHASE_PAYLOAD_FIELDS = (
    "document_id",
    "total",
    "net",
    "vat",
    "vat_by_rate",
    "vat_deductible",
    "currency",
    "exchange_rate",
    "rate_date",
    "cost_destination",
    "partner_resident",
    "partner_id",
)


class PurchasePostingError(ApiError):
    code = "purchases.posting_payload_invalid"
    status = 422


class PurchaseDiscriminatorMissingError(ApiError):
    """The fact does not say where the cost lands, or whose debt this is."""

    code = "purchases.discriminator_missing"
    status = 422


class PurchaseVatStatusMismatchError(ApiError):
    """The fact claims a deductibility the stamp on the event contradicts.

    The purchases module derives `vat_deductible` from the company's status on
    the accounting date; `emit` stamps that same status on the event (ADR-088).
    The two are one fact read twice, and a disagreement means one reading is
    wrong -- refused, because posting either would put a number in 2252 or in
    cost that the other reading says is not there.
    """

    code = "purchases.vat_status_mismatch"
    status = 409


@dataclass(frozen=True, slots=True)
class PurchaseInvoiceFact:
    """What the ledger needs to know about a recorded supplier invoice.

    The mirror of `SalesInvoiceFact`, and owned by `accounting` for the same
    reason: a signature naming `PurchaseDocument` would make another module's
    table part of this one's contract.
    """

    document_id: uuid.UUID
    partner_id: uuid.UUID
    accounting_date: date
    document_date: date
    total: Decimal
    net: Decimal
    vat: Decimal
    currency: str
    cost_destination: str
    partner_resident: bool
    #: Whether *we* may deduct the VAT the supplier charged: true for a company
    #: registered on the accounting date, false otherwise. A discriminator on the
    #: fact, on the pattern of `partner_resident` (ADR-073 §2) -- derived by the
    #: purchases module from the dated status, never assumed here, and checked
    #: at posting against the stamp the event carries.
    vat_deductible: bool
    description: str
    vat_by_rate: tuple[VatShare, ...] = ()
    #: As on the sale: the header's rate and its day, 1 and unused in lei.
    exchange_rate: Decimal = Decimal(1)
    rate_date: date | None = None

    def as_payload(self) -> dict[str, Any]:
        return {
            "document_id": str(self.document_id),
            "partner_id": str(self.partner_id),
            "total": str(self.total),
            "net": str(self.net),
            "vat": str(self.vat),
            "vat_by_rate": [share.as_payload() for share in self.vat_by_rate],
            "vat_deductible": self.vat_deductible,
            "currency": self.currency,
            "exchange_rate": str(self.exchange_rate),
            "rate_date": str(self.rate_date or self.document_date),
            "cost_destination": self.cost_destination,
            "partner_resident": self.partner_resident,
            "document_date": str(self.document_date),
        }


def recognise_purchase(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    accounting_date: date,
    functional_currency: str,
    payload: dict[str, Any],
) -> tuple[RoleFormula, ...]:
    """The pure treatment: the cost against the payable, and the VAT where it belongs.

    **Deductible or borne, and the fact says which.** A registered buyer takes the
    VAT to 2252, one formula per rate; a buyer that is not registered has no
    right of deduction, and the VAT the supplier charged is part of what the
    service cost -- one formula, for the total, to the cost account. The boolean
    is read, never inferred from the amounts: an invoice with VAT on it says
    nothing about whether *we* may deduct it.

    **Stock cannot be bought through here**, and that is structural rather than a
    refusal with a code: none of the four destinations is an asset, so goods for
    resale and materials -- whose entry has a second half in F4 -- have no value to
    travel under.
    """
    del tenant_id, company_id

    destination = payload.get("cost_destination")
    if destination not in COST_ROLES:
        raise PurchaseDiscriminatorMissingError(
            f"cost_destination is {destination!r}; a purchase says where the cost "
            f"lands, because that is what selects the expense account"
        )

    resident = payload.get("partner_resident")
    if not isinstance(resident, bool):
        raise PurchaseDiscriminatorMissingError(
            "the invoice does not say whether the supplier is a resident; the "
            "payable account differs, and `partner` carries no residence, so it "
            "is asked for rather than assumed (ADR-073 §2)"
        )

    deductible = payload.get("vat_deductible")
    if not isinstance(deductible, bool):
        raise PurchaseDiscriminatorMissingError(
            "the invoice does not say whether its VAT is deductible; that follows "
            "from the company's registration on the accounting date, which the "
            "purchases module reads and this handler does not (ADR-089)"
        )

    net, shares = _amounts(payload, PurchasePostingError)
    total = _decimal(payload.get("total"), "total", PurchasePostingError)
    if net <= 0:
        raise PurchasePostingError(
            "a purchase is posted for a positive net; a credit note is its own document"
        )

    money = _conversion(payload, functional_currency, accounting_date, PurchasePostingError)

    payable = ROLE_DATORII_TARA if resident else ROLE_DATORII_STRAINATATE
    document_date = date.fromisoformat(str(payload["document_date"]))
    # One description for four destinations: what happened is the same -- a
    # service was received -- and what differs is the account it lands on, which
    # the line already says.
    description = "Servicii primite de la furnizor"

    if not deductible:
        # No right of deduction: the VAT is what the service cost, and it lands
        # with the rest of the cost. One formula for the total, no rate stamped
        # -- the rate belongs to a VAT formula, and there is none.
        return (
            RoleFormula(
                debit_role=COST_ROLES[destination],
                credit_role=payable,
                amount=money.functional(total),
                currency=money.currency,
                amount_currency=total,
                exchange_rate=money.rate,
                rate_date=money.rate_date,
                document_date=document_date,
                description=description,
            ),
        )

    formulas = [
        RoleFormula(
            debit_role=COST_ROLES[destination],
            credit_role=payable,
            amount=money.functional(net),
            currency=money.currency,
            amount_currency=net,
            exchange_rate=money.rate,
            rate_date=money.rate_date,
            document_date=document_date,
            description=description,
        )
    ]
    for share in shares:
        if share.vat == 0:
            continue
        formulas.append(
            RoleFormula(
                debit_role=ROLE_TVA_DEDUCTIBILA,
                credit_role=payable,
                amount=money.functional(share.vat),
                currency=money.currency,
                amount_currency=share.vat,
                exchange_rate=money.rate,
                rate_date=money.rate_date,
                document_date=document_date,
                vat_rate=share.rate,
                vat_rate_key=share.rate_key,
                description="TVA deductibilă",
            )
        )
    return tuple(formulas)


HANDLERS[HANDLER_PURCHASE] = recognise_purchase

register(
    EventType(
        name=EVENT_PURCHASE,
        payload_fields=PURCHASE_PAYLOAD_FIELDS,
        account_roles=PURCHASE_ROLES,
        handlers=(HandlerVersion(implementation_ref=HANDLER_PURCHASE, valid_from=date.min),),
        description="A recorded supplier invoice: the cost taken against the payable.",
    )
)


SOURCE_MODULE_TREASURY = "treasury"
SOURCE_DOCUMENT_TYPE_RECEIPT = "treasury.receipt"
SOURCE_DOCUMENT_TYPE_PAYMENT = "treasury.payment"

EVENT_RECEIPT = "treasury.receipt_recorded"
EVENT_PAYMENT = "treasury.payment_recorded"
HANDLER_RECEIPT = "treasury.receipt_recorded.v1"
HANDLER_PAYMENT = "treasury.payment_recorded.v1"

ROLE_CASA_MDL = "CASA_MDL"
ROLE_CONT_CURENT_MDL = "CONT_CURENT_MDL"

#: Where the money actually moved -- ADR-073 §5. The treasury account is the
#: **instrument's**, not the document's: the same receipt against the same invoice
#: lands in the till or in the bank account depending on where it was handed over,
#: and nothing on the invoice knows which.
#:
#: The currency accounts exist in the catalogue and are absent here: a receipt in
#: another currency opens the exchange differences, which have their own handler
#: (ADR-057) and their own step.
TREASURY_ROLES = {
    "cash": ROLE_CASA_MDL,
    "bank": ROLE_CONT_CURENT_MDL,
}

TREASURY_PAYLOAD_FIELDS = (
    "document_id",
    "amount",
    "currency",
    "treasury_account",
    "partner_resident",
    "partner_id",
)

RECEIPT_ROLES = (
    *TREASURY_ROLES.values(),
    ROLE_CREANTE_TARA,
    ROLE_CREANTE_STRAINATATE,
)

PAYMENT_ROLES = (
    *TREASURY_ROLES.values(),
    ROLE_DATORII_TARA,
    ROLE_DATORII_STRAINATATE,
)


class TreasuryPostingError(ApiError):
    code = "treasury.posting_payload_invalid"
    status = 422


class TreasuryDiscriminatorMissingError(ApiError):
    """The fact does not say where the money moved, or whose account it clears."""

    code = "treasury.discriminator_missing"
    status = 422


@dataclass(frozen=True, slots=True)
class TreasuryFact:
    """Money in or out, as the ledger needs it.

    One dataclass for both directions: what differs is which side the treasury
    role sits on, and that is the handler's business, not the fact's.
    """

    document_id: uuid.UUID
    partner_id: uuid.UUID
    accounting_date: date
    document_date: date
    amount: Decimal
    currency: str
    treasury_account: str
    partner_resident: bool
    description: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "document_id": str(self.document_id),
            "partner_id": str(self.partner_id),
            "amount": str(self.amount),
            "currency": self.currency,
            "treasury_account": self.treasury_account,
            "partner_resident": self.partner_resident,
            "document_date": str(self.document_date),
        }


@dataclass(frozen=True, slots=True)
class TreasuryPostingResult:
    accounting_event_id: uuid.UUID
    journal_entry_id: uuid.UUID | None
    formulas: int
    posted_now: bool


def _treasury_common(
    payload: dict[str, Any], functional_currency: str
) -> tuple[str, bool, Decimal]:
    """The three facts both directions need, refused rather than assumed."""
    where = payload.get("treasury_account")
    if where not in TREASURY_ROLES:
        raise TreasuryDiscriminatorMissingError(
            f"treasury_account is {where!r}; the money went somewhere, and which "
            f"account it landed in is a property of the instrument, not of the document"
        )

    resident = payload.get("partner_resident")
    if not isinstance(resident, bool):
        raise TreasuryDiscriminatorMissingError(
            "the document does not say whether the counterparty is a resident; the "
            "receivable it reduces differs by that, and `partner` carries no residence"
        )

    amount = _decimal(payload.get("amount"), "amount")
    if amount <= 0:
        raise TreasuryPostingError(
            "money moves in a positive amount; the direction is the document's "
            "type, never the sign -- a negative receipt and a payment would be the "
            "same row written two ways"
        )

    currency = payload.get("currency")
    if currency != functional_currency:
        raise TreasuryPostingError(
            f"a movement in {currency!r} needs the exchange treatment; only "
            f"{functional_currency} is posted here so far"
        )
    return str(where), resident, amount


def recognise_receipt(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    accounting_date: date,
    functional_currency: str,
    payload: dict[str, Any],
) -> tuple[RoleFormula, ...]:
    """Money in: the treasury account against the receivable.

    **Which receivable is not asked**, and that is ADR-073 §5 rather than an
    omission: the posting is the same whichever invoice the money answers. Saying
    *which one* is settlement, with its own handler and its own step -- and a link
    written here would be half of it, which reports would start reading.
    """
    del tenant_id, company_id
    where, resident, amount = _treasury_common(payload, functional_currency)

    return (
        RoleFormula(
            debit_role=TREASURY_ROLES[where],
            credit_role=ROLE_CREANTE_TARA if resident else ROLE_CREANTE_STRAINATATE,
            amount=amount,
            currency=functional_currency,
            amount_currency=amount,
            exchange_rate=Decimal(1),
            rate_date=accounting_date,
            document_date=date.fromisoformat(str(payload["document_date"])),
            description="Încasare de la client",
        ),
    )


def recognise_payment(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    accounting_date: date,
    functional_currency: str,
    payload: dict[str, Any],
) -> tuple[RoleFormula, ...]:
    """Money out: the payable against the treasury account. The mirror, exactly."""
    del tenant_id, company_id
    where, resident, amount = _treasury_common(payload, functional_currency)

    return (
        RoleFormula(
            debit_role=ROLE_DATORII_TARA if resident else ROLE_DATORII_STRAINATATE,
            credit_role=TREASURY_ROLES[where],
            amount=amount,
            currency=functional_currency,
            amount_currency=amount,
            exchange_rate=Decimal(1),
            rate_date=accounting_date,
            document_date=date.fromisoformat(str(payload["document_date"])),
            description="Plată către furnizor",
        ),
    )


HANDLERS[HANDLER_RECEIPT] = recognise_receipt
HANDLERS[HANDLER_PAYMENT] = recognise_payment

register(
    EventType(
        name=EVENT_RECEIPT,
        payload_fields=TREASURY_PAYLOAD_FIELDS,
        account_roles=RECEIPT_ROLES,
        handlers=(HandlerVersion(implementation_ref=HANDLER_RECEIPT, valid_from=date.min),),
        description="Money received: the treasury account against the receivable.",
    )
)

register(
    EventType(
        name=EVENT_PAYMENT,
        payload_fields=TREASURY_PAYLOAD_FIELDS,
        account_roles=PAYMENT_ROLES,
        handlers=(HandlerVersion(implementation_ref=HANDLER_PAYMENT, valid_from=date.min),),
        description="Money paid: the payable against the treasury account.",
    )
)


def post_treasury_movement(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    functional_currency: str,
    fact: TreasuryFact,
    direction: str,
    actor_user_id: uuid.UUID,
    request_id: str,
    capability_snapshot: dict[str, Any],
    occurred_at: datetime | None = None,
) -> TreasuryPostingResult:
    """One orchestration for both directions -- the event type is the difference.

    Two event types and one function, rather than two of each: the emit-select-
    bind-post-mark sequence is identical, and a second copy of it would be a
    second place for the idempotency key to be written differently.
    """
    if direction not in ("receipt", "payment"):
        raise TreasuryPostingError(f"direction is {direction!r}")
    event_type = EVENT_RECEIPT if direction == "receipt" else EVENT_PAYMENT
    document_type = (
        SOURCE_DOCUMENT_TYPE_RECEIPT if direction == "receipt" else SOURCE_DOCUMENT_TYPE_PAYMENT
    )

    event, created = emit(
        tenant_id=tenant_id,
        company_id=company_id,
        event_type=event_type,
        source_module=SOURCE_MODULE_TREASURY,
        source_document_type=document_type,
        source_document_id=fact.document_id,
        occurred_at=occurred_at or datetime.now(UTC),
        accounting_date=fact.accounting_date,
        idempotency_key=f"{event_type}:{fact.document_id}",
        payload=fact.as_payload(),
        capability_snapshot=capability_snapshot,
        actor_user_id=actor_user_id,
        request_id=request_id,
    )
    if not created:
        posted = entry_id_of_event(event.id)
        if posted is not None or event.status == "posted":
            return TreasuryPostingResult(event.id, posted, 0, posted_now=False)

    treatment = selected_treatment(event_type, fact.accounting_date, capability_snapshot)
    produced = treatment.handler(
        tenant_id=tenant_id,
        company_id=company_id,
        accounting_date=fact.accounting_date,
        functional_currency=functional_currency,
        payload=event.payload,
    )
    formulas: Sequence[RoleFormula] = tuple(produced)

    try:
        with transaction.atomic():
            bound = bind_roles(company_id, fact.accounting_date, formulas)
            result = post_formulas(
                tenant_id=tenant_id,
                company_id=company_id,
                accounting_date=fact.accounting_date,
                functional_currency=functional_currency,
                accounting_event_id=event.id,
                origin=Origin(
                    module=SOURCE_MODULE_TREASURY,
                    document_type=document_type,
                    document_id=fact.document_id,
                ),
                rule_ref=treatment.ref,
                description=fact.description,
                request_id=request_id,
                actor_user_id=actor_user_id,
                formulas=bound,
            )
    except (ApiError, NumberingError) as refusal:
        mark_failed(event.id, code=refusal.code, detail={"event_type": event_type})
        raise
    mark_posted(event.id)
    return TreasuryPostingResult(
        event.id, result.journal_entry_id, result.formulas, posted_now=True
    )


#: The nature of a sales document, and the event it becomes. Enumerated, because
#: which fact a document *is* is posting form (`R28`): a delivery recognises
#: revenue, a return reduces the receivable against a distribution expense, and
#: the advance has no treatment registered at all (ADR-073 §6 -- posting only its
#: first half would leave a balance of advances nothing could ever clear).
EVENT_BY_NATURE = {
    "delivery": EVENT_SALE,
    "return": EVENT_RETURN,
}


def post_sales_invoice(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    functional_currency: str,
    fact: SalesInvoiceFact,
    nature: str,
    actor_user_id: uuid.UUID,
    request_id: str,
    capability_snapshot: dict[str, Any],
    occurred_at: datetime | None = None,
) -> SalesPostingResult:
    """Record the document as an event and post it -- the shape every family uses.

    Emit under an idempotency key (`R19`, on the event and not on the endpoint);
    select the treatment by date and profile (`R17`, `R26`); run the pure handler;
    bind the roles; post; mark. A second call with the same document returns the
    first result rather than a second entry.

    ``nature`` picks the event, and an unknown one is refused rather than treated
    as a delivery: an advance posted as a delivery would recognise revenue that
    has not been earned.
    """
    event_type = EVENT_BY_NATURE.get(nature)
    if event_type is None:
        raise SalesPostingError(
            f"nature {nature!r} has no posting treatment; {sorted(EVENT_BY_NATURE)} do"
        )
    event, created = emit(
        tenant_id=tenant_id,
        company_id=company_id,
        event_type=event_type,
        source_module=SOURCE_MODULE,
        source_document_type=SOURCE_DOCUMENT_TYPE,
        source_document_id=fact.document_id,
        occurred_at=occurred_at or datetime.now(UTC),
        accounting_date=fact.accounting_date,
        # ADR-073 §8: the document's identity plus the event type. Not the
        # transition -- a document reaches `posted` once, and a re-posting after a
        # reversal is a different event, not the same key with a suffix.
        idempotency_key=f"{event_type}:{fact.document_id}",
        payload=fact.as_payload(),
        capability_snapshot=capability_snapshot,
        actor_user_id=actor_user_id,
        request_id=request_id,
    )
    if not created:
        posted = entry_id_of_event(event.id)
        if posted is not None or event.status == "posted":
            return SalesPostingResult(event.id, posted, 0, posted_now=False)

    treatment = selected_treatment(event_type, fact.accounting_date, capability_snapshot)
    produced = treatment.handler(
        tenant_id=tenant_id,
        company_id=company_id,
        accounting_date=fact.accounting_date,
        functional_currency=functional_currency,
        payload=event.payload,
    )
    formulas: Sequence[RoleFormula] = tuple(produced)

    try:
        with transaction.atomic():
            bound = bind_roles(company_id, fact.accounting_date, formulas)
            result = post_formulas(
                tenant_id=tenant_id,
                company_id=company_id,
                accounting_date=fact.accounting_date,
                functional_currency=functional_currency,
                accounting_event_id=event.id,
                origin=Origin(
                    module=SOURCE_MODULE,
                    document_type=SOURCE_DOCUMENT_TYPE,
                    document_id=fact.document_id,
                ),
                rule_ref=treatment.ref,
                description=fact.description,
                request_id=request_id,
                actor_user_id=actor_user_id,
                formulas=bound,
                parameter_stamps=_scale_stamps(
                    fact.currency, functional_currency, fact.accounting_date
                ),
            )
    except (ApiError, NumberingError) as refusal:
        mark_failed(event.id, code=refusal.code, detail={"event_type": event_type})
        raise
    mark_posted(event.id)
    return SalesPostingResult(event.id, result.journal_entry_id, result.formulas, posted_now=True)


@dataclass(frozen=True, slots=True)
class PurchasePostingResult:
    accounting_event_id: uuid.UUID
    journal_entry_id: uuid.UUID | None
    formulas: int
    posted_now: bool


def post_purchase_invoice(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    functional_currency: str,
    fact: PurchaseInvoiceFact,
    actor_user_id: uuid.UUID,
    request_id: str,
    capability_snapshot: dict[str, Any],
    occurred_at: datetime | None = None,
) -> PurchasePostingResult:
    """The same shape as the sales half, one direction over.

    Emit under an idempotency key (`R19`, on the event and not on the endpoint);
    select the treatment by date and profile (`R17`, `R26`); run the pure handler;
    bind the roles; post; mark. A second call with the same document returns the
    first result rather than a second entry.

    **The key is the document's identity plus the event type**, ADR-073 §8 -- not
    the supplier's number. Their number deduplicates *documents* (`R20`, the
    constraint on `purchase_document`); this deduplicates *postings*. Two
    questions, two mechanisms, and collapsing them would make a retry after a
    timeout look like the same invoice arriving twice.
    """
    event, created = emit(
        tenant_id=tenant_id,
        company_id=company_id,
        event_type=EVENT_PURCHASE,
        source_module=SOURCE_MODULE_PURCHASE,
        source_document_type=SOURCE_DOCUMENT_TYPE_PURCHASE,
        source_document_id=fact.document_id,
        occurred_at=occurred_at or datetime.now(UTC),
        accounting_date=fact.accounting_date,
        idempotency_key=f"{EVENT_PURCHASE}:{fact.document_id}",
        payload=fact.as_payload(),
        capability_snapshot=capability_snapshot,
        actor_user_id=actor_user_id,
        request_id=request_id,
    )
    if not created:
        posted = entry_id_of_event(event.id)
        if posted is not None or event.status == "posted":
            return PurchasePostingResult(event.id, posted, 0, posted_now=False)

    # The fact's deductibility against the stamp `emit` just wrote from the same
    # date (ADR-088). Not a selection -- the handler still reads the fact -- but
    # a check that the fact was read from the status the event records, so a
    # recalculation (`R18`) and an audit see one answer, not two.
    stamp = event.tax_status_snapshot
    if isinstance(stamp, dict):
        registered = stamp.get("vat", {}).get("registered")
        if isinstance(registered, bool) and registered != fact.vat_deductible:
            raise PurchaseVatStatusMismatchError(
                f"the fact says vat_deductible={fact.vat_deductible} and the event's "
                f"stamp says registered={registered} on {fact.accounting_date}; one of "
                f"them read the status wrong, and neither is posted"
            )

    treatment = selected_treatment(EVENT_PURCHASE, fact.accounting_date, capability_snapshot)
    produced = treatment.handler(
        tenant_id=tenant_id,
        company_id=company_id,
        accounting_date=fact.accounting_date,
        functional_currency=functional_currency,
        payload=event.payload,
    )
    formulas: Sequence[RoleFormula] = tuple(produced)

    try:
        with transaction.atomic():
            bound = bind_roles(company_id, fact.accounting_date, formulas)
            result = post_formulas(
                tenant_id=tenant_id,
                company_id=company_id,
                accounting_date=fact.accounting_date,
                functional_currency=functional_currency,
                accounting_event_id=event.id,
                origin=Origin(
                    module=SOURCE_MODULE_PURCHASE,
                    document_type=SOURCE_DOCUMENT_TYPE_PURCHASE,
                    document_id=fact.document_id,
                ),
                rule_ref=treatment.ref,
                description=fact.description,
                request_id=request_id,
                actor_user_id=actor_user_id,
                formulas=bound,
                parameter_stamps=_scale_stamps(
                    fact.currency, functional_currency, fact.accounting_date
                ),
            )
    except (ApiError, NumberingError) as refusal:
        mark_failed(event.id, code=refusal.code, detail={"event_type": EVENT_PURCHASE})
        raise
    mark_posted(event.id)
    return PurchasePostingResult(
        event.id, result.journal_entry_id, result.formulas, posted_now=True
    )
