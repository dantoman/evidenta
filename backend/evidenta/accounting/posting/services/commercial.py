"""Commercial documents in the ledger -- ADR-073, the `sales` half.

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


def post_sales_invoice(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    functional_currency: str,
    fact: SalesInvoiceFact,
    actor_user_id: uuid.UUID,
    request_id: str,
    capability_snapshot: dict[str, Any],
    occurred_at: datetime | None = None,
) -> SalesPostingResult:
    """Record the invoice as an event and post it -- the shape every family uses.

    Emit under an idempotency key (`R19`, on the event and not on the endpoint);
    select the treatment by date and profile (`R17`, `R26`); run the pure handler;
    bind the roles; post; mark. A second call with the same document returns the
    first result rather than a second entry.
    """
    event, created = emit(
        tenant_id=tenant_id,
        company_id=company_id,
        event_type=EVENT_SALE,
        source_module=SOURCE_MODULE,
        source_document_type=SOURCE_DOCUMENT_TYPE,
        source_document_id=fact.document_id,
        occurred_at=occurred_at or datetime.now(UTC),
        accounting_date=fact.accounting_date,
        # ADR-073 §8: the document's identity plus the event type. Not the
        # transition -- a document reaches `posted` once, and a re-posting after a
        # reversal is a different event, not the same key with a suffix.
        idempotency_key=f"{EVENT_SALE}:{fact.document_id}",
        payload=fact.as_payload(),
        capability_snapshot=capability_snapshot,
        actor_user_id=actor_user_id,
        request_id=request_id,
    )
    if not created:
        posted = entry_id_of_event(event.id)
        if posted is not None or event.status == "posted":
            return SalesPostingResult(event.id, posted, 0, posted_now=False)

    treatment = selected_treatment(EVENT_SALE, fact.accounting_date, capability_snapshot)
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
        mark_failed(event.id, code=refusal.code, detail={"event_type": EVENT_SALE})
        raise
    mark_posted(event.id)
    return SalesPostingResult(event.id, result.journal_entry_id, result.formulas, posted_now=True)
