"""Realised exchange and sum differences at settlement -- C4 of ADR-036 section 11, ADR-057.

Shape, not treatment: which pair of accounts the discriminator selects, which
side the difference lands on, that the delivery-date and fixed-rate terms and an
advance produce no posting at all (pct. 21, 23), that the bank spread is a third
pair against the lei account, that the derived amount is reduced once at the
scale in force and the parameter is stamped, and that the discriminator is
refused rather than assumed. Accounts are fixtures bound to the roles by name;
no chart code appears. The rates and amounts are test values.

Under the application role (T1).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pytest

from evidenta.accounting.events.models import AccountingEvent
from evidenta.accounting.ledger.models import EntryParameterStamp, JournalEntry, JournalFormula
from evidenta.accounting.posting.services.settlement import (
    CONVENTIONAL_UNITS,
    DELIVERY_DATE,
    EVENT_PAYABLE,
    EVENT_RECEIVABLE,
    FIXED,
    FOREIGN_CURRENCY,
    HANDLER_REF,
    PAYABLE,
    PAYMENT_DATE,
    RECEIVABLE,
    ROLE_CONT_MDL,
    ROLE_CREANTE_STRAINATATE,
    ROLE_CREANTE_TARA,
    ROLE_CURS_FAVORABILA,
    ROLE_CURS_NEFAVORABILA,
    ROLE_DATORII_STRAINATATE,
    ROLE_DATORII_TARA,
    ROLE_ECART_FAVORABIL,
    ROLE_ECART_NEFAVORABIL,
    ROLE_SUMA_FAVORABILA,
    ROLE_SUMA_NEFAVORABILA,
    SettlementDiscriminatorMissingError,
    SettlementFact,
    SettlementNotInCurrencyError,
    post_settlement_differences,
)
from evidenta.accounting.slots.models import AccountRoleBinding
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.test_formulas import seed_account
from tests.isolation.test_ledger import seed_period
from tests.isolation.test_line_rounding import direction, scale, source  # noqa: F401
from tests.isolation.test_manual_entry import seed_template as seed_numbering

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

MDL = "MDL"
SETTLED = date(2026, 1, 20)
SNAPSHOT: dict[str, Any] = {"version": 1, "on": "2026-01-01", "activated": [], "usable": []}


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="c4")


@pytest.fixture
def scene(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
    context: TenantContext,
    source: uuid.UUID,  # noqa: F811 -- the fiscal act fixture, imported to be found
) -> dict[str, Any]:
    """A company, an open January, a numbering template, the conventions (two
    decimals, half_up), and one fixture account per role the handler names."""
    tenant = world["tenant_a"]
    company = company_of(tenant, "1002600000903", "Alpha Decontare")
    grant_company(tenant, company, world["user_a"], world["user_a"])
    seed_period(seed, tenant, company)
    seed_numbering(seed, tenant, company)
    scale(seed, world, "accounting.amount_scale", 2)
    direction(seed, world, "half_up")
    roles = (
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
    accounts = {
        role: seed_account(seed, tenant, company, f"FIX-{i}") for i, role in enumerate(roles)
    }
    with tenant_context(context):
        for role, account in accounts.items():
            AccountRoleBinding.objects.create(
                tenant_id=tenant,
                company_id=company,
                role=role,
                account_id=account,
                valid_from=date(2026, 1, 1),
                source="fixture",
            )
    return {"tenant": tenant, "company": company, "user": world["user_a"], "accounts": accounts}


def fact(**overrides: Any) -> SettlementFact:
    base: dict[str, Any] = {
        "settlement_id": uuid.uuid4(),
        "document_id": uuid.uuid4(),
        "document_type": "sales.document",
        "side": RECEIVABLE,
        "currency": "EUR",
        "amount_currency": Decimal("1000"),
        "issue_rate": Decimal("19.5000"),
        "settlement_rate": Decimal("19.6234"),
        "settlement_date": SETTLED,
        "rate_term": PAYMENT_DATE,
        "partner_resident": False,
        "contract_denomination": FOREIGN_CURRENCY,
        "settles_advance": False,
    }
    base.update(overrides)
    return SettlementFact(**base)


def settle(scene: dict[str, Any], the_fact: SettlementFact) -> Any:
    return post_settlement_differences(
        tenant_id=scene["tenant"],
        company_id=scene["company"],
        functional_currency=MDL,
        fact=the_fact,
        actor_user_id=scene["user"],
        request_id="c4",
        capability_snapshot=SNAPSHOT,
    )


def correspondences(entry_id: uuid.UUID) -> list[tuple[uuid.UUID, uuid.UUID, Decimal]]:
    return [
        (f.debit_account_id, f.credit_account_id, f.amount)
        for f in JournalFormula.objects.filter(journal_entry_id=entry_id).order_by("id")
    ]


# --- the pairs -----------------------------------------------------------------------


def test_a_receivable_from_abroad_settled_higher_is_a_favourable_exchange_difference(
    scene: dict[str, Any], context: TenantContext
) -> None:
    """1000 x (19.6234 - 19.5000) = 123.40, once, at two decimals -- and stamped."""
    a = scene["accounts"]
    with tenant_context(context):
        result = settle(scene, fact())
        assert result.journal_entry_id is not None
        assert correspondences(result.journal_entry_id) == [
            (a[ROLE_CREANTE_STRAINATATE], a[ROLE_CURS_FAVORABILA], Decimal("123.4000"))
        ]
        entry = JournalEntry.objects.get(pk=result.journal_entry_id)
        assert entry.rule_ref == HANDLER_REF and entry.accounting_date == SETTLED
        stamps = list(EntryParameterStamp.objects.filter(journal_entry_id=entry.id))
        assert [s.parameter_key for s in stamps] == ["accounting.amount_scale"]
        event = AccountingEvent.objects.get(pk=result.accounting_event_id)
        assert event.event_type == EVENT_RECEIVABLE and event.status == "posted"


def test_a_receivable_settled_lower_is_an_unfavourable_exchange_difference(
    scene: dict[str, Any], context: TenantContext
) -> None:
    a = scene["accounts"]
    with tenant_context(context):
        result = settle(scene, fact(settlement_rate=Decimal("19.4000")))
        assert correspondences(result.journal_entry_id) == [
            (a[ROLE_CURS_NEFAVORABILA], a[ROLE_CREANTE_STRAINATATE], Decimal("100.0000"))
        ]


def test_between_residents_it_is_a_sum_difference_on_the_other_pair(
    scene: dict[str, Any], context: TenantContext
) -> None:
    """Same arithmetic, other accounts: the counterparty decides (pct. 4, 17)."""
    a = scene["accounts"]
    with tenant_context(context):
        result = settle(
            scene, fact(partner_resident=True, contract_denomination=CONVENTIONAL_UNITS)
        )
        assert correspondences(result.journal_entry_id) == [
            (a[ROLE_CREANTE_TARA], a[ROLE_SUMA_FAVORABILA], Decimal("123.4000"))
        ]
        result = settle(
            scene,
            fact(
                partner_resident=True,
                contract_denomination=CONVENTIONAL_UNITS,
                settlement_rate=Decimal("19.4000"),
            ),
        )
        assert correspondences(result.journal_entry_id) == [
            (a[ROLE_SUMA_NEFAVORABILA], a[ROLE_CREANTE_TARA], Decimal("100.0000"))
        ]


def test_on_a_payable_the_signs_invert(scene: dict[str, Any], context: TenantContext) -> None:
    a = scene["accounts"]
    with tenant_context(context):
        up = settle(scene, fact(side=PAYABLE))
        assert correspondences(up.journal_entry_id) == [
            (a[ROLE_CURS_NEFAVORABILA], a[ROLE_DATORII_STRAINATATE], Decimal("123.4000"))
        ]
        assert AccountingEvent.objects.get(pk=up.accounting_event_id).event_type == EVENT_PAYABLE
        down = settle(scene, fact(side=PAYABLE, settlement_rate=Decimal("19.4000")))
        assert correspondences(down.journal_entry_id) == [
            (a[ROLE_DATORII_STRAINATATE], a[ROLE_CURS_FAVORABILA], Decimal("100.0000"))
        ]
        resident = settle(
            scene, fact(side=PAYABLE, partner_resident=True, contract_denomination=FOREIGN_CURRENCY)
        )
        assert correspondences(resident.journal_entry_id) == [
            (a[ROLE_SUMA_NEFAVORABILA], a[ROLE_DATORII_TARA], Decimal("123.4000"))
        ]


def test_the_bank_spread_is_the_third_pair_against_the_lei_account(
    scene: dict[str, Any], context: TenantContext
) -> None:
    """Sold to the bank below the official rate: 1000 x (19.6000 - 19.6234) = -23.40,
    a loss in the operational result, beside the financial difference."""
    a = scene["accounts"]
    with tenant_context(context):
        result = settle(scene, fact(bank_rate=Decimal("19.6000")))
        assert correspondences(result.journal_entry_id) == [
            (a[ROLE_CREANTE_STRAINATATE], a[ROLE_CURS_FAVORABILA], Decimal("123.4000")),
            (a[ROLE_ECART_NEFAVORABIL], a[ROLE_CONT_MDL], Decimal("23.4000")),
        ]
        better = settle(scene, fact(bank_rate=Decimal("19.7000")))
        assert correspondences(better.journal_entry_id)[-1] == (
            a[ROLE_CONT_MDL],
            a[ROLE_ECART_FAVORABIL],
            Decimal("76.6000"),
        )


# --- the branches with nothing to post ---------------------------------------------


@pytest.mark.parametrize("term", [DELIVERY_DATE, FIXED])
def test_at_the_delivery_or_a_fixed_rate_no_difference_arises(
    scene: dict[str, Any], context: TenantContext, term: str
) -> None:
    """pct. 21 -- both sides recognise at the same rate. A case, not an omission."""
    with tenant_context(context):
        result = settle(scene, fact(rate_term=term))
        assert result.journal_entry_id is None and result.formulas == 0
        event = AccountingEvent.objects.get(pk=result.accounting_event_id)
        assert event.status == "posted"
        assert not JournalEntry.objects.filter(accounting_event_id=event.id).exists()


def test_an_advance_keeps_its_rate_for_good(scene: dict[str, Any], context: TenantContext) -> None:
    with tenant_context(context):
        result = settle(scene, fact(settles_advance=True))
        assert result.journal_entry_id is None


def test_a_difference_that_rounds_to_nothing_posts_nothing(
    scene: dict[str, Any], context: TenantContext
) -> None:
    """1 x 0.0040 = 0.004 -> 0.00 at two decimals: no zero line (invariant 5)."""
    with tenant_context(context):
        result = settle(
            scene,
            fact(amount_currency=Decimal("1"), settlement_rate=Decimal("19.5040")),
        )
        assert result.journal_entry_id is None


# --- what is refused, and when -------------------------------------------------------


def test_the_discriminator_is_refused_not_assumed(
    scene: dict[str, Any], context: TenantContext
) -> None:
    with tenant_context(context):
        with pytest.raises(SettlementDiscriminatorMissingError):
            settle(scene, fact(contract_denomination="mdl"))
        with pytest.raises(SettlementDiscriminatorMissingError):
            settle(scene, fact(partner_resident=None))  # type: ignore[arg-type]
        # Refused before any event exists: a caller bug, not a failed posting.
        assert not AccountingEvent.objects.filter(event_type=EVENT_RECEIVABLE).exists()


def test_a_settlement_in_the_functional_currency_has_nothing_to_record(
    scene: dict[str, Any], context: TenantContext
) -> None:
    with tenant_context(context), pytest.raises(SettlementNotInCurrencyError):
        settle(scene, fact(currency=MDL))


def test_the_same_settlement_twice_posts_once(
    scene: dict[str, Any], context: TenantContext
) -> None:
    the_fact = fact(settlement_id=uuid.UUID(int=7))
    with tenant_context(context):
        first = settle(scene, the_fact)
        second = settle(scene, the_fact)
        assert first.journal_entry_id == second.journal_entry_id
        assert first.posted_now and not second.posted_now
