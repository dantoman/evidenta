"""Commercial documents in the ledger -- ADR-073: the two invoices, and the money.

**The form is fixed and it is small**: a sale recognises revenue against a
receivable, for the document's total. What is not small is choosing *which*
receivable and *which* revenue, and both choices are carried on the fact rather
than derived -- ADR-073 §2, on the pattern ADR-057 fixed for settlement.

**Nothing here knows an account code** (`R15`, ADR-036 §5.1). The handler asks for
roles; `bind_roles` turns them into accounts through the company's own bindings at
the posting's date, or refuses with the binding's code.

**No VAT.** One treatment is registered, and it is the one for a sale without VAT.
The treatment with VAT cannot be registered yet: the engine selects on
capabilities, and the VAT status of a company is not one (`OD-83`, open). Adding a
second treatment before that is decided would mean choosing between them by
something the registry does not read.

**Goods and finished products are refused, with a code.** Their revenue is
recognised the same way, but the entry has a second half -- the stock leaving --
and that is F4. A handler posting only the first half would produce a month whose
margin equals its turnover: balanced, plausible, false.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from django.db import transaction

from evidenta.accounting.events.registry import (
    HANDLERS,
    EventType,
    HandlerVersion,
    register,
)
from evidenta.accounting.events.services.emission import emit
from evidenta.accounting.events.services.lifecycle import mark_failed, mark_posted
from evidenta.accounting.ledger.services.writing import entry_id_of_event
from evidenta.accounting.posting.formula import RoleFormula, bind_roles
from evidenta.accounting.posting.invariants import Origin
from evidenta.accounting.posting.resolution import selected_treatment
from evidenta.accounting.posting.services.formulas import post_formulas
from evidenta.platform.api.errors import ApiError
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

SALE_ROLES = (
    ROLE_CREANTE_TARA,
    ROLE_CREANTE_STRAINATATE,
    ROLE_VENIT_SERVICII,
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
    "currency",
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
class SalesInvoiceFact:
    """What the ledger needs to know about an issued invoice.

    A dataclass owned by `accounting`, not a row from `operations` -- the same
    seam `SettlementFact` draws, and for the same reason: a signature that named
    `SalesDocument` would make the shape of another module's table part of this
    one's contract.
    """

    document_id: uuid.UUID
    partner_id: uuid.UUID
    accounting_date: date
    document_date: date
    total: Decimal
    currency: str
    revenue_kind: str
    partner_resident: bool
    description: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "document_id": str(self.document_id),
            "partner_id": str(self.partner_id),
            "total": str(self.total),
            "currency": self.currency,
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

    total = _decimal(payload.get("total"), "total")
    if total <= 0:
        raise SalesPostingError(
            "a sale is posted for a positive total; a return is its own document"
        )

    currency = payload.get("currency")
    if currency != functional_currency:
        raise SalesPostingError(
            f"a sale in {currency!r} needs the exchange treatment; only "
            f"{functional_currency} is posted here so far"
        )

    return (
        RoleFormula(
            debit_role=ROLE_CREANTE_TARA if resident else ROLE_CREANTE_STRAINATATE,
            credit_role=REVENUE_ROLES[kind],
            amount=total,
            currency=functional_currency,
            amount_currency=total,
            exchange_rate=Decimal(1),
            rate_date=accounting_date,
            document_date=date.fromisoformat(str(payload["document_date"])),
            description="Venit din prestarea serviciilor",
        ),
    )


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

    total = _decimal(payload.get("total"), "total")
    if total <= 0:
        raise SalesPostingError(
            "a return is posted for a positive total; the direction is the "
            "document's nature, never the sign"
        )

    currency = payload.get("currency")
    if currency != functional_currency:
        raise SalesPostingError(
            f"a return in {currency!r} needs the exchange treatment; only "
            f"{functional_currency} is posted here so far"
        )

    return (
        RoleFormula(
            debit_role=ROLE_RETUR_REDUCERI,
            credit_role=ROLE_CREANTE_TARA if resident else ROLE_CREANTE_STRAINATATE,
            amount=total,
            currency=functional_currency,
            amount_currency=total,
            exchange_rate=Decimal(1),
            rate_date=accounting_date,
            document_date=date.fromisoformat(str(payload["document_date"])),
            description="Retur de la client",
        ),
    )


def _decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, Decimal):
        return value
    if isinstance(value, str):
        try:
            return Decimal(value)
        except ArithmeticError as error:
            raise SalesPostingError(f"{field} is {value!r}") from error
    raise SalesPostingError(f"{field} must be a Decimal or its string, never a float")


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
)

PURCHASE_PAYLOAD_FIELDS = (
    "document_id",
    "total",
    "currency",
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
    currency: str
    cost_destination: str
    partner_resident: bool
    description: str

    def as_payload(self) -> dict[str, Any]:
        return {
            "document_id": str(self.document_id),
            "partner_id": str(self.partner_id),
            "total": str(self.total),
            "currency": self.currency,
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
    """The pure treatment: one formula, the cost against the payable.

    **No VAT**, and for exactly the reason the sales half gives: the engine selects
    a treatment on capabilities, and a company's VAT status is not one (`OD-83`).
    A second treatment registered before that is decided would be chosen by
    something the registry does not read.

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

    total = _decimal(payload.get("total"), "total")
    if total <= 0:
        raise PurchasePostingError(
            "a purchase is posted for a positive total; a credit note is its own document"
        )

    currency = payload.get("currency")
    if currency != functional_currency:
        raise PurchasePostingError(
            f"a purchase in {currency!r} needs the exchange treatment; only "
            f"{functional_currency} is posted here so far"
        )

    return (
        RoleFormula(
            debit_role=COST_ROLES[destination],
            credit_role=ROLE_DATORII_TARA if resident else ROLE_DATORII_STRAINATATE,
            amount=total,
            currency=functional_currency,
            amount_currency=total,
            exchange_rate=Decimal(1),
            rate_date=accounting_date,
            document_date=date.fromisoformat(str(payload["document_date"])),
            # One description for four destinations: what happened is the same --
            # a service was received -- and what differs is the account it lands
            # on, which the line already says.
            description="Servicii primite de la furnizor",
        ),
    )


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
            )
    except (ApiError, NumberingError) as refusal:
        mark_failed(event.id, code=refusal.code, detail={"event_type": EVENT_PURCHASE})
        raise
    mark_posted(event.id)
    return PurchasePostingResult(
        event.id, result.journal_entry_id, result.formulas, posted_now=True
    )
