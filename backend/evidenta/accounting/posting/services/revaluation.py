"""Unrealised exchange differences at the reporting date -- `A10`, Spec B section 7.3.

The second computed handler after C4 (ADR-057), and its mirror in time: C4
records the difference realised when a balance is settled; this one records the
difference that exists on a balance **not yet settled**, at the rate of the day
the statements are drawn up.

**What the act fixes, and the handler follows** (SNC "Diferenţe de curs valutar
şi de sumă", wording in force from 01.01.2020 -- OMF 48/2019;
`f2-x2-snc-situatii-financiare-si-diferente-de-curs.md` section 8-9):

* **The third moment** (pct. 6 sub 3): the lei equivalent is determined at the
  official rate on the date of the financial statements. Pct. 13 lets the entity
  do it with another periodicity -- monthly is what this product's period is.
* **Monetary items only** (pct. 11): cash, receivables and payables in foreign
  currency, **except advances given and received** (excluded since 01.01.2020;
  the 2013 wording included them -- the handler is registered from 2020-01-01
  for that reason, and a date before it has no treatment rather than a wrong
  one, `R17`). Non-monetary items keep the rate of initial recognition (pct. 12).
* **Contracts between residents are not recalculated** (pct. 22): a sum
  difference arises only at settlement. So the perimeter is the balances whose
  counterparty is not a resident -- the same discriminator ADR-057 uses to pick
  the pair of accounts, read the other way round.
* **Direction** (pct. 9-10, Annex 1): a receivable whose rate rose is a
  favourable difference -- *majorare concomitentă a creanţelor şi veniturilor
  curente* -- `Dt` receivable / `Ct` 6226; whose rate fell, `Dt` 7224 / `Ct`
  receivable. A payable inverts: a rate that rose is *majorare concomitentă a
  cheltuielilor şi datoriilor curente*, `Dt` 7224 / `Ct` payable.
* **The next difference is measured from the revalued rate** (pct. 15, Example
  3): after this entry the balance is carried at ``closing_rate``. That is why
  each item names the rate it was *carried* at, not the rate of the invoice --
  the caller resolves it, and the handler computes against what it is given.

**The handler is pure of the ledger** (ADR-036 section 5.1): the open balances
arrive in the payload, computed by the module that owns them, and the handler
returns role formulas. It reads the fiscal registry for the scale and rounding
in force on the reporting date, like C4, because the difference is a derived
amount; what it stood on is stamped on the entry (ADR-047).

**One entry per company and date**, all items in it, each formula carrying the
partner as a dimension so a chart that declares the partner on the receivable
keeps it (ADR-048 `place`). Idempotent on `(company, as_of)` through the event's
key; a second run returns the first entry.
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
from evidenta.accounting.posting.formula import DimensionValue, Formula, RoleFormula, bind_roles
from evidenta.accounting.posting.invariants import Origin, PostingRefusedError
from evidenta.accounting.posting.resolution import selected_treatment
from evidenta.accounting.posting.services.formulas import post_formulas
from evidenta.fiscal.parameters.services.resolution import resolve_parameter
from evidenta.fiscal.parameters.services.scales import AMOUNT_SCALE_KEY, amount_scale
from evidenta.platform.api.errors import ApiError
from evidenta.platform.numbering.services.allocation import NumberingError

EVENT_TYPE = "accounting.revaluation_calculated"
HANDLER_REF = "revaluation.monetary_items.v1"

#: The wording in force: OMF 48/2019 rewrote pct. 11-12 with effect from
#: 01.01.2020, moving advances out of the monetary items. A revaluation dated
#: before that falls under the 2013 wording, which this build does not
#: implement -- so it has no treatment, which is a refusal, not a guess.
VALID_FROM = date(2020, 1, 1)

#: `accounting_event.source_module`: the currency module's own act, the way the
#: closing is the period module's (`SourceModule.CURRENCY`).
SOURCE_MODULE = "currency"
SOURCE_DOCUMENT_TYPE = "revaluation"

RECEIVABLE = "receivable"
PAYABLE = "payable"
PARTNER_DIMENSION = "partner"

ROLE_CURS_FAVORABILA = "DIFERENTA_CURS_FAVORABILA"
ROLE_CURS_NEFAVORABILA = "DIFERENTA_CURS_NEFAVORABILA"
ROLE_CREANTE_STRAINATATE = "CREANTE_COMERCIALE_STRAINATATE"
ROLE_DATORII_STRAINATATE = "DATORII_COMERCIALE_STRAINATATE"

ALL_ROLES = (
    ROLE_CURS_FAVORABILA,
    ROLE_CURS_NEFAVORABILA,
    ROLE_CREANTE_STRAINATATE,
    ROLE_DATORII_STRAINATATE,
)

PAYLOAD_FIELDS = ("as_of", "items")
ITEM_FIELDS = (
    "document_id",
    "document_type",
    "side",
    "partner_id",
    "currency",
    "amount_currency",
    "carrying_rate",
    "closing_rate",
)


class RevaluationPayloadError(PostingRefusedError):
    """An item the handler cannot compute from -- a caller bug, refused before
    any event exists."""

    code = "posting.revaluation_payload_malformed"
    status = 400


class RevaluationNotInCurrencyError(PostingRefusedError):
    """A balance in the functional currency has nothing to revalue."""

    code = "posting.revaluation_not_in_currency"
    status = 400


@dataclass(frozen=True, slots=True)
class RevaluedItem:
    """One open balance, with the rate it is carried at and the closing rate."""

    document_id: uuid.UUID
    document_type: str
    side: str
    partner_id: uuid.UUID
    currency: str
    amount_currency: Decimal
    carrying_rate: Decimal
    closing_rate: Decimal

    def as_payload(self) -> dict[str, Any]:
        return {
            "document_id": str(self.document_id),
            "document_type": self.document_type,
            "side": self.side,
            "partner_id": str(self.partner_id),
            "currency": self.currency,
            "amount_currency": str(self.amount_currency),
            "carrying_rate": str(self.carrying_rate),
            "closing_rate": str(self.closing_rate),
        }


@dataclass(frozen=True, slots=True)
class RevaluationPostingResult:
    accounting_event_id: uuid.UUID
    #: None when nothing differed: the event is posted, and there is no entry.
    journal_entry_id: uuid.UUID | None
    formulas: int
    posted_now: bool


def revaluation_difference(
    amount_currency: Decimal, carrying_rate: Decimal, closing_rate: Decimal, on: date
) -> Decimal:
    """``amount x (closing - carrying)``, reduced once to the scale in force on ``on``.

    The one place the arithmetic lives: the handler uses it to post and the
    revaluation service uses it to record what each item came to, so the row and
    the entry cannot disagree by a rounding.
    """
    return rounding_for(on).quantize(
        amount_currency * (closing_rate - carrying_rate), amount_scale(on)
    )


# --- the handler --------------------------------------------------------------------


def _decimal(value: Any, field: str) -> Decimal:
    if isinstance(value, bool | float):
        raise RevaluationPayloadError(f"{field} is {value!r}; amounts and rates travel exactly")
    try:
        return Decimal(value) if isinstance(value, int | Decimal) else Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        raise RevaluationPayloadError(f"{field} is {value!r}, not a number") from None


def _uuid(value: Any, field: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(value))
    except (ValueError, TypeError, AttributeError):
        raise RevaluationPayloadError(f"{field} is {value!r}, not an identifier") from None


def revalue_monetary_items(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    accounting_date: date,
    functional_currency: str,
    payload: Mapping[str, Any],
) -> tuple[RoleFormula, ...]:
    """The unrealised difference on each open balance, as role formulas.

    Reads the items from the payload and nothing else. An item whose difference
    rounds to zero produces no formula; a payload whose items all do produces no
    entry, and the event records that the revaluation ran and found nothing.
    """
    del tenant_id, company_id
    items = payload.get("items")
    if not isinstance(items, list):
        raise RevaluationPayloadError("items is not a list; a revaluation names what it revalues")

    out: list[RoleFormula] = []
    for raw in items:
        if not isinstance(raw, Mapping):
            raise RevaluationPayloadError("an item is a mapping of the eight fields")
        missing = [field for field in ITEM_FIELDS if field not in raw]
        if missing:
            raise RevaluationPayloadError(f"an item lacks {', '.join(missing)}")
        side = raw["side"]
        if side not in (RECEIVABLE, PAYABLE):
            raise RevaluationPayloadError(f"side is {side!r}, not receivable or payable")
        currency = str(raw["currency"])
        if currency == functional_currency:
            raise RevaluationNotInCurrencyError(
                f"a balance in {functional_currency} has no exchange difference"
            )
        amount = _decimal(raw["amount_currency"], "amount_currency")
        carrying = _decimal(raw["carrying_rate"], "carrying_rate")
        closing = _decimal(raw["closing_rate"], "closing_rate")
        if amount <= 0 or carrying <= 0 or closing <= 0:
            raise RevaluationPayloadError(
                "amount and rates are positive; a sign belongs on the side"
            )
        partner_id = _uuid(raw["partner_id"], "partner_id")

        diff = revaluation_difference(amount, carrying, closing, accounting_date)
        if diff == 0:
            continue
        # pct. 9-10: on a receivable a rise in the rate is favourable; on a payable
        # a rise is unfavourable, because more lei are now owed.
        balance = ROLE_CREANTE_STRAINATATE if side == RECEIVABLE else ROLE_DATORII_STRAINATATE
        gain = diff > 0 if side == RECEIVABLE else diff < 0
        what = "creanței" if side == RECEIVABLE else "datoriei"
        text = f"Reevaluarea {what} în {currency} la cursul de {closing}"
        common: dict[str, Any] = {
            "amount": abs(diff),
            "currency": functional_currency,
            "amount_currency": abs(diff),
            "exchange_rate": Decimal(1),
            "rate_date": accounting_date,
            "document_date": accounting_date,
            "dimensions": (DimensionValue(PARTNER_DIMENSION, partner_id),),
            "description": text,
        }
        if gain:
            out.append(RoleFormula(debit_role=balance, credit_role=ROLE_CURS_FAVORABILA, **common))
        else:
            out.append(
                RoleFormula(debit_role=ROLE_CURS_NEFAVORABILA, credit_role=balance, **common)
            )
    return tuple(out)


HANDLERS[HANDLER_REF] = revalue_monetary_items

register(
    EventType(
        name=EVENT_TYPE,
        payload_fields=PAYLOAD_FIELDS,
        account_roles=ALL_ROLES,
        handlers=(HandlerVersion(implementation_ref=HANDLER_REF, valid_from=VALID_FROM),),
        description=(
            "The monetary items in foreign currency restated at the official rate of the "
            "reporting date: the unrealised exchange differences (SNC pct. 11, 14)."
        ),
    )
)


# --- the service --------------------------------------------------------------------


def _check(items: Sequence[RevaluedItem], functional_currency: str) -> None:
    """The refusals that happen before an event exists -- caller bugs."""
    for item in items:
        if item.side not in (RECEIVABLE, PAYABLE):
            raise RevaluationPayloadError(f"side is {item.side!r}")
        if item.currency == functional_currency:
            raise RevaluationNotInCurrencyError(
                f"a balance in {functional_currency} has no exchange difference"
            )
        for name, value in (
            ("amount_currency", item.amount_currency),
            ("carrying_rate", item.carrying_rate),
            ("closing_rate", item.closing_rate),
        ):
            if not isinstance(value, Decimal):
                raise RevaluationPayloadError(f"{name} must be Decimal, never float")
            if value <= 0:
                raise RevaluationPayloadError(f"{name} is {value}; a sign belongs on the side")


def post_revaluation(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    revaluation_id: uuid.UUID,
    as_of: date,
    functional_currency: str,
    items: Sequence[RevaluedItem],
    actor_user_id: uuid.UUID,
    request_id: str,
    capability_snapshot: dict[str, Any],
    occurred_at: datetime | None = None,
) -> RevaluationPostingResult:
    """Record the revaluation as an event and post what it found.

    The shape of `settlement.post_settlement_differences`: refuse the caller's
    bugs before an event exists; emit under the key of the company and the date;
    select the treatment by date and profile; run the pure handler; bind the
    roles; stamp the scale; post; mark. ``revaluation_id`` is the source document
    of the event (`R13`): the row the currency module writes beside the entry,
    which lists the balances the entry stands on.
    """
    _check(items, functional_currency)
    event, created = emit(
        tenant_id=tenant_id,
        company_id=company_id,
        event_type=EVENT_TYPE,
        source_module=SOURCE_MODULE,
        source_document_type=SOURCE_DOCUMENT_TYPE,
        source_document_id=revaluation_id,
        occurred_at=occurred_at or datetime.now(UTC),
        accounting_date=as_of,
        idempotency_key=f"{EVENT_TYPE}:{company_id}:{as_of.isoformat()}",
        payload={"as_of": as_of.isoformat(), "items": [item.as_payload() for item in items]},
        capability_snapshot=capability_snapshot,
        actor_user_id=actor_user_id,
        request_id=request_id,
    )
    if not created:
        posted = entry_id_of_event(event.id)
        if posted is not None or event.status == "posted":
            return RevaluationPostingResult(event.id, posted, 0, posted_now=False)

    try:
        treatment = selected_treatment(EVENT_TYPE, as_of, capability_snapshot)
        produced = treatment.handler(
            tenant_id=tenant_id,
            company_id=company_id,
            accounting_date=as_of,
            functional_currency=functional_currency,
            payload=event.payload,
        )
    except ApiError as refusal:
        mark_failed(event.id, code=refusal.code, detail={"event_type": EVENT_TYPE})
        raise
    role_formulas: Sequence[RoleFormula] = tuple(produced)
    if not role_formulas:
        mark_posted(event.id)
        return RevaluationPostingResult(event.id, None, 0, posted_now=True)

    try:
        with transaction.atomic():
            bound: Sequence[Formula] = bind_roles(company_id, as_of, role_formulas)
            scale_row = resolve_parameter(AMOUNT_SCALE_KEY, as_of)
            stamp = ParameterStamp(
                parameter_id=uuid.UUID(str(scale_row.pk)),
                parameter_key=AMOUNT_SCALE_KEY,
                effective_date=as_of,
                confidence=scale_row.source_confidence,
                resolved_at=datetime.now(UTC),
            )
            result = post_formulas(
                tenant_id=tenant_id,
                company_id=company_id,
                accounting_date=as_of,
                functional_currency=functional_currency,
                accounting_event_id=event.id,
                origin=Origin(
                    module=SOURCE_MODULE,
                    document_type=SOURCE_DOCUMENT_TYPE,
                    document_id=revaluation_id,
                ),
                rule_ref=treatment.ref,
                description=(f"Reevaluarea elementelor monetare în valută la {as_of:%d.%m.%Y}"),
                request_id=request_id,
                actor_user_id=actor_user_id,
                formulas=bound,
                parameter_stamps=(stamp,),
            )
    except (ApiError, NumberingError) as refusal:
        mark_failed(event.id, code=refusal.code, detail={"event_type": EVENT_TYPE})
        raise
    mark_posted(event.id)
    return RevaluationPostingResult(
        event.id, result.journal_entry_id, result.formulas, posted_now=True
    )
