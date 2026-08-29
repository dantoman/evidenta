"""Realised exchange and sum differences at settlement -- F1.4.4, case C4 of ADR-036 section 11.

The first computed handler, and the one chosen to go first because it is the
only one of the five that emits formulas **no document line asks for**: the
difference exists between two moments -- the day a receivable or payable was
recognised and the day it was settled -- not on any line of input. If the engine
can emit that, the other handlers are simpler cases.

**What the act fixes, and the handler follows** (SNC "Diferenţe de curs valutar
şi de sumă", in the wording in force from 01.01.2020 -- `c4-diferente-de-curs.md`):

* **Two notions, one arithmetic** (pct. 4, 17). A *diferență de curs valutar*
  arises on operations in foreign currency; a *diferență de sumă* arises between
  **residents** of the Republic of Moldova on contracts in foreign currency or in
  conventional units. The formula is the same; the **counterparty decides the
  account**, and the discriminator -- resident, and the contract's denomination
  -- is **required, never defaulted**. A default anywhere in it is where the next
  silent choice would live.
* **Three pairs of accounts, not two**, as roles (ADR-050 section 3.1):
  `6226/7224` exchange differences, `6227/7225` sum differences, `6127/7147` the
  spread between the BNM official rate and the bank's buy/sell rate -- which
  lands in the **operational** result, not the financial one. Confusing the third
  with the first gives a statement wrong by section with a correct total,
  invisible in the trial balance.
* **The contractual term decides whether anything happens** (pct. 19, 21). At the
  rate of the delivery date, or at a fixed rate, no difference arises: both
  sides recognise at the same rate. That branch is a **tested case**, not an
  omission. The term is on the document header (`document.rate_term`); its
  default, `payment_date`, is the act's own suppletive rule (pct. 6, 8).
* **Advances are excluded permanently** (pct. 11-12 as amended, pct. 23): the
  rate is fixed at payment and never recalculated.
* **Revaluation at the reporting date is not here.** Annex 1 of the standard is
  the authority on which balance-sheet lines revalue and has not been extracted.

**The handler is pure of the ledger** (ADR-036 section 5.1): it reads the
settlement fact from the payload and returns role formulas. It does read the
fiscal registry -- the amount scale and the rounding rule in force on the
settlement date (R17, R18) -- because a difference is a *derived* amount, the
first one this engine produces, and the rule that reduces it to two decimals is
versioned logic, not arithmetic. What it stood on is stamped on the entry
(ADR-047): this is the first handler that writes a parameter stamp.

**Which day's rate the header carries** (`DN-04`) is open and does not block:
at settlement the rate is the payment day's whatever the answer.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal, InvalidOperation
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
from evidenta.accounting.posting.formula import Formula, RoleFormula, bind_roles
from evidenta.accounting.posting.invariants import Origin, PostingRefusedError
from evidenta.accounting.posting.resolution import selected_treatment
from evidenta.accounting.posting.services.formulas import post_formulas
from evidenta.fiscal.parameters.services.resolution import resolve_parameter
from evidenta.fiscal.parameters.services.scales import AMOUNT_SCALE_KEY, amount_scale
from evidenta.platform.api.errors import ApiError
from evidenta.platform.numbering.services.allocation import NumberingError

EVENT_RECEIVABLE = "receivables.settlement_created"
EVENT_PAYABLE = "payables.settlement_created"
HANDLER_REF = "settlement.differences.v1"

#: `accounting_event.source_module`: a settlement is a payment, and payments
#: are the banking module's fact even before that module exists.
SOURCE_MODULE = "banking"
SOURCE_DOCUMENT_TYPE = "settlement"

RECEIVABLE = "receivable"
PAYABLE = "payable"

#: The vocabulary of `document.rate_term`, repeated as strings: this module does
#: not import `platform.documents` models (D6); the value travels in the payload.
PAYMENT_DATE = "payment_date"
DELIVERY_DATE = "delivery_date"
FIXED = "fixed"
RATE_TERMS = (PAYMENT_DATE, DELIVERY_DATE, FIXED)

FOREIGN_CURRENCY = "foreign_currency"
CONVENTIONAL_UNITS = "conventional_units"
DENOMINATIONS = (FOREIGN_CURRENCY, CONVENTIONAL_UNITS)

# Roles (ADR-050 section 3.1; catalogue `roles_snc_2020.csv`).
ROLE_CURS_FAVORABILA = "DIFERENTA_CURS_FAVORABILA"
ROLE_CURS_NEFAVORABILA = "DIFERENTA_CURS_NEFAVORABILA"
ROLE_SUMA_FAVORABILA = "DIFERENTA_SUMA_FAVORABILA"
ROLE_SUMA_NEFAVORABILA = "DIFERENTA_SUMA_NEFAVORABILA"
ROLE_ECART_FAVORABIL = "ECART_CURS_BANCA_FAVORABIL"
ROLE_ECART_NEFAVORABIL = "ECART_CURS_BANCA_NEFAVORABIL"
ROLE_CREANTE_TARA = "CREANTE_COMERCIALE_TARA"
ROLE_CREANTE_STRAINATATE = "CREANTE_COMERCIALE_STRAINATATE"
ROLE_DATORII_TARA = "DATORII_COMERCIALE_TARA"
ROLE_DATORII_STRAINATATE = "DATORII_COMERCIALE_STRAINATATE"
ROLE_CONT_MDL = "CONT_CURENT_MDL"

ALL_ROLES = (
    ROLE_CURS_FAVORABILA,
    ROLE_CURS_NEFAVORABILA,
    ROLE_SUMA_FAVORABILA,
    ROLE_SUMA_NEFAVORABILA,
    ROLE_ECART_FAVORABIL,
    ROLE_ECART_NEFAVORABIL,
    ROLE_CREANTE_TARA,
    ROLE_CREANTE_STRAINATATE,
    ROLE_DATORII_TARA,
    ROLE_DATORII_STRAINATATE,
    ROLE_CONT_MDL,
)

PAYLOAD_FIELDS = (
    "settlement_id",
    "document_id",
    "document_type",
    "side",
    "currency",
    "amount_currency",
    "issue_rate",
    "settlement_rate",
    "settlement_date",
    "rate_term",
    "partner_resident",
    "contract_denomination",
    "settles_advance",
)


class SettlementPayloadError(PostingRefusedError):
    """The fact is not one this handler can compute from. A caller bug, refused
    before any event exists."""

    code = "posting.settlement_payload_malformed"
    status = 400


class SettlementDiscriminatorMissingError(PostingRefusedError):
    """Resident or not, foreign currency or conventional units -- not stated.

    Refused rather than assumed. The discriminator chooses between two pairs of
    accounts that land in different lines of the statement; a default here would
    be the next silent choice, and it would look reasonable.
    """

    code = "posting.settlement_discriminator_missing"
    status = 400


class SettlementNotInCurrencyError(PostingRefusedError):
    """A settlement in the functional currency has no difference to record."""

    code = "posting.settlement_not_in_currency"
    status = 400


@dataclass(frozen=True, slots=True)
class SettlementFact:
    """What the caller states about one settlement. Every field is explicit."""

    settlement_id: uuid.UUID
    document_id: uuid.UUID
    document_type: str
    side: str
    currency: str
    amount_currency: Decimal
    issue_rate: Decimal
    settlement_rate: Decimal
    settlement_date: date
    rate_term: str
    partner_resident: bool
    contract_denomination: str
    settles_advance: bool
    #: The bank's actual buy/sell rate, when the settlement passed through a
    #: conversion. None when it did not -- absent, not zero.
    bank_rate: Decimal | None = None

    def as_payload(self) -> dict[str, Any]:
        return {
            "settlement_id": str(self.settlement_id),
            "document_id": str(self.document_id),
            "document_type": self.document_type,
            "side": self.side,
            "currency": self.currency,
            "amount_currency": str(self.amount_currency),
            "issue_rate": str(self.issue_rate),
            "settlement_rate": str(self.settlement_rate),
            "settlement_date": self.settlement_date.isoformat(),
            "rate_term": self.rate_term,
            "partner_resident": self.partner_resident,
            "contract_denomination": self.contract_denomination,
            "settles_advance": self.settles_advance,
            "bank_rate": None if self.bank_rate is None else str(self.bank_rate),
        }


@dataclass(frozen=True, slots=True)
class SettlementResult:
    accounting_event_id: uuid.UUID
    #: None when the fact produced no difference: the event is recorded and
    #: posted, and there is nothing in the ledger to point at (pct. 21, pct. 23).
    journal_entry_id: uuid.UUID | None
    formulas: int
    posted_now: bool


# --- the handler --------------------------------------------------------------------


def _decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool | float):
        raise SettlementPayloadError(f"{field} is {value!r}; amounts and rates travel exactly")
    try:
        return Decimal(value) if isinstance(value, int | Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise SettlementPayloadError(f"{field} is {value!r}, not a number") from None


def record_settlement_differences(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    accounting_date: date,
    functional_currency: str,
    payload: Mapping[str, Any],
) -> tuple[RoleFormula, ...]:
    """The difference the settlement realised, as role formulas -- or none.

    Signs. ``diff = amount_currency x (settlement_rate - issue_rate)``, reduced
    once to the amount scale in force on the settlement date. On a receivable a
    positive ``diff`` is favourable (more lei came in than were recognised):
    ``Dt receivable / Ct favourable``; negative is ``Dt unfavourable / Ct
    receivable``. On a payable the signs invert. The bank spread,
    ``amount_currency x (bank_rate - settlement_rate)``, is its own pair against
    the lei account -- operational result, not financial.
    """
    del tenant_id, company_id
    side = payload.get("side")
    if side not in (RECEIVABLE, PAYABLE):
        raise SettlementPayloadError(f"side is {side!r}, not receivable or payable")
    rate_term = payload.get("rate_term")
    if rate_term not in RATE_TERMS:
        raise SettlementPayloadError(f"rate_term is {rate_term!r}; pct. 19 names {RATE_TERMS}")
    resident = payload.get("partner_resident")
    denomination = payload.get("contract_denomination")
    if not isinstance(resident, bool) or denomination not in DENOMINATIONS:
        raise SettlementDiscriminatorMissingError(
            "the settlement does not say whether the counterparty is a resident and what "
            "the contract is denominated in (pct. 4, 17); the pair of accounts depends on "
            "it, and it is not assumed"
        )
    if payload.get("currency") == functional_currency:
        raise SettlementNotInCurrencyError(
            f"a settlement in {functional_currency} has no exchange or sum difference"
        )

    # pct. 21: at the delivery-date rate or a fixed one, both sides recognise at
    # the same rate and no difference exists. pct. 23: an advance keeps the rate
    # of its payment for good.
    if rate_term in (DELIVERY_DATE, FIXED) or payload.get("settles_advance") is True:
        return ()

    amount = _decimal(payload.get("amount_currency"), "amount_currency")
    issue_rate = _decimal(payload.get("issue_rate"), "issue_rate")
    settlement_rate = _decimal(payload.get("settlement_rate"), "settlement_rate")
    if amount <= 0 or issue_rate <= 0 or settlement_rate <= 0:
        raise SettlementPayloadError("amount and rates are positive; a sign belongs on the side")

    rule = rounding_for(accounting_date)
    scale = amount_scale(accounting_date)
    currency = str(payload.get("currency"))

    def formula(debit: str, credit: str, value: Decimal, text: str) -> RoleFormula:
        return RoleFormula(
            debit_role=debit,
            credit_role=credit,
            amount=value,
            currency=functional_currency,
            amount_currency=value,
            exchange_rate=Decimal(1),
            rate_date=accounting_date,
            document_date=accounting_date,
            description=text,
        )

    favourable, unfavourable = (
        (ROLE_SUMA_FAVORABILA, ROLE_SUMA_NEFAVORABILA)
        if resident
        else (ROLE_CURS_FAVORABILA, ROLE_CURS_NEFAVORABILA)
    )
    kind = "de sumă" if resident else "de curs valutar"
    if side == RECEIVABLE:
        partner = ROLE_CREANTE_TARA if resident else ROLE_CREANTE_STRAINATATE
    else:
        partner = ROLE_DATORII_TARA if resident else ROLE_DATORII_STRAINATATE

    out: list[RoleFormula] = []
    diff = rule.quantize(amount * (settlement_rate - issue_rate), scale)
    if diff != 0:
        gain = diff > 0 if side == RECEIVABLE else diff < 0
        magnitude = abs(diff)
        if gain:
            out.append(formula(partner, favourable, magnitude, f"Diferență favorabilă {kind}"))
        else:
            out.append(formula(unfavourable, partner, magnitude, f"Diferență nefavorabilă {kind}"))

    bank_rate = payload.get("bank_rate")
    if bank_rate is not None:
        spread = rule.quantize(amount * (_decimal(bank_rate, "bank_rate") - settlement_rate), scale)
        if spread != 0:
            # Selling currency (a receivable settled in it) at a better bank rate
            # is a gain; buying it (to settle a payable) at a higher bank rate is
            # a loss. The counterpart is the lei account the conversion touched.
            gain = spread > 0 if side == RECEIVABLE else spread < 0
            magnitude = abs(spread)
            text = "Ecart între cursul oficial al BNM și cursul băncii"
            if gain:
                out.append(formula(ROLE_CONT_MDL, ROLE_ECART_FAVORABIL, magnitude, text))
            else:
                out.append(formula(ROLE_ECART_NEFAVORABIL, ROLE_CONT_MDL, magnitude, text))
    del currency
    return tuple(out)


HANDLERS[HANDLER_REF] = record_settlement_differences

for _name, _text in (
    (EVENT_RECEIVABLE, "A receivable settled: the realised difference, if any, on the customer."),
    (EVENT_PAYABLE, "A payable settled: the realised difference, if any, on the supplier."),
):
    register(
        EventType(
            name=_name,
            payload_fields=PAYLOAD_FIELDS,
            account_roles=ALL_ROLES,
            handlers=(HandlerVersion(implementation_ref=HANDLER_REF, valid_from=date.min),),
            description=_text,
        )
    )


# --- the service --------------------------------------------------------------------


def _check(fact: SettlementFact, functional_currency: str) -> None:
    """The refusals that happen before an event exists -- caller bugs."""
    if fact.side not in (RECEIVABLE, PAYABLE):
        raise SettlementPayloadError(f"side is {fact.side!r}")
    if fact.rate_term not in RATE_TERMS:
        raise SettlementPayloadError(f"rate_term is {fact.rate_term!r}")
    if (
        not isinstance(fact.partner_resident, bool)
        or fact.contract_denomination not in DENOMINATIONS
    ):
        raise SettlementDiscriminatorMissingError(
            "the settlement does not say whether the counterparty is a resident and what "
            "the contract is denominated in (pct. 4, 17); refused, not assumed"
        )
    if fact.currency == functional_currency:
        raise SettlementNotInCurrencyError(
            f"a settlement in {functional_currency} has no exchange or sum difference"
        )
    for name, value in (
        ("amount_currency", fact.amount_currency),
        ("issue_rate", fact.issue_rate),
        ("settlement_rate", fact.settlement_rate),
    ):
        if not isinstance(value, Decimal):
            raise SettlementPayloadError(f"{name} must be Decimal, never float")
        if value <= 0:
            raise SettlementPayloadError(f"{name} is {value}; a sign belongs on the side")
    if fact.bank_rate is not None and (
        not isinstance(fact.bank_rate, Decimal) or fact.bank_rate <= 0
    ):
        raise SettlementPayloadError("bank_rate must be a positive Decimal, or absent")


def post_settlement_differences(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    functional_currency: str,
    fact: SettlementFact,
    actor_user_id: uuid.UUID,
    request_id: str,
    capability_snapshot: dict[str, Any],
    occurred_at: datetime | None = None,
) -> SettlementResult:
    """Record the settlement as an event and post the difference it realised.

    The shape of `services.manual` and `services.closing`: refuse the caller's
    bugs before an event exists; emit under an idempotency key; select the
    treatment by date and profile; run the pure handler; bind the roles; post;
    mark. When the handler returns nothing -- delivery-date or fixed rate, an
    advance, a difference that rounds to zero -- the event is posted with no
    entry: the settlement happened and produced no difference, which is a fact
    worth being able to point at.
    """
    _check(fact, functional_currency)
    event_type = EVENT_RECEIVABLE if fact.side == RECEIVABLE else EVENT_PAYABLE
    accounting_date = fact.settlement_date

    event, created = emit(
        tenant_id=tenant_id,
        company_id=company_id,
        event_type=event_type,
        source_module=SOURCE_MODULE,
        source_document_type=SOURCE_DOCUMENT_TYPE,
        source_document_id=fact.settlement_id,
        occurred_at=occurred_at or datetime.now(UTC),
        accounting_date=accounting_date,
        idempotency_key=f"{event_type}:{fact.settlement_id}",
        payload=fact.as_payload(),
        capability_snapshot=capability_snapshot,
        actor_user_id=actor_user_id,
        request_id=request_id,
    )
    if not created:
        settled = entry_id_of_event(event.id)
        if settled is not None or event.status == "posted":
            return SettlementResult(event.id, settled, 0, posted_now=False)

    treatment = selected_treatment(event_type, accounting_date, capability_snapshot)
    produced = treatment.handler(
        tenant_id=tenant_id,
        company_id=company_id,
        accounting_date=accounting_date,
        functional_currency=functional_currency,
        payload=event.payload,
    )
    if not all(isinstance(item, RoleFormula) for item in produced):
        raise SettlementPayloadError(
            f"the treatment registered for {event_type} returned something other than role formulas"
        )
    role_formulas: Sequence[RoleFormula] = tuple(produced)
    if not role_formulas:
        mark_posted(event.id)
        return SettlementResult(event.id, None, 0, posted_now=True)

    try:
        with transaction.atomic():
            bound: Sequence[Formula] = bind_roles(company_id, accounting_date, role_formulas)
            scale_row = resolve_parameter(AMOUNT_SCALE_KEY, accounting_date)
            stamp = ParameterStamp(
                parameter_id=uuid.UUID(str(scale_row.pk)),
                parameter_key=AMOUNT_SCALE_KEY,
                effective_date=accounting_date,
                confidence=scale_row.source_confidence,
                resolved_at=datetime.now(UTC),
            )
            result = post_formulas(
                tenant_id=tenant_id,
                company_id=company_id,
                accounting_date=accounting_date,
                functional_currency=functional_currency,
                accounting_event_id=event.id,
                origin=Origin(
                    module=SOURCE_MODULE,
                    document_type=SOURCE_DOCUMENT_TYPE,
                    document_id=fact.settlement_id,
                ),
                rule_ref=treatment.ref,
                description=(
                    "Diferențe de curs realizate la decontare"
                    if not fact.partner_resident
                    else "Diferențe de sumă realizate la decontare"
                ),
                request_id=request_id,
                actor_user_id=actor_user_id,
                formulas=bound,
                parameter_stamps=(stamp,),
            )
    except (ApiError, NumberingError) as refusal:
        mark_failed(event.id, code=refusal.code, detail={"event_type": event_type})
        raise
    mark_posted(event.id)
    return SettlementResult(event.id, result.journal_entry_id, result.formulas, posted_now=True)
