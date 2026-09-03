"""Foreign currency, end to end -- ADR-097 (`F2.A9`, `OD-127`, `A10`).

Four things, in the order the money moves:

1. **The rates door** writes under the reference-data role, leaves a row in
   `privileged_access_log`, is idempotent on the day, and refuses a changed
   value rather than overwriting the rate an entry may stand on.
2. **An invoice in EUR** posts the receivable in EUR with the lei derived once
   at the official rate of the invoice's date -- exact figures, the four
   elements of Spec B section 7.1 on the line, the scale stamped (`C12`).
3. **Settling it in lei** at another rate posts the realised difference on the
   pair the counterparty selects (ADR-057): exchange for a non-resident, sum for
   a resident in conventional units. The 1000 x (19.6234 - 19.5000) = 123.40 of
   ADR-057, reached through the allocation instead of a hand-built fact.
4. **The revaluation** restates the open half at the reporting date's rate,
   posts nothing the second time, and -- the `A10` criterion -- the settlement
   after it measures its difference from the revalued rate, not the invoice's
   (SNC pct. 15, Example 3). The receivable closes at exactly zero.

Then the negative one: another tenant sees none of it (IZ).

The rates are fixtures, not published values (the ones ADR-057 uses). Under the
application role (`T1`); the door test also uses the reference-data connection,
which is what it is about.
"""

from __future__ import annotations

import io
import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError

from evidenta.accounting.currency.models import ExchangeRate, Revaluation, RevaluationItem
from evidenta.accounting.currency.services.rates import RateNotFoundError, rate_on
from evidenta.accounting.currency.services.revaluation import (
    list_revaluations,
    revalue_monetary_items,
)
from evidenta.accounting.ledger.models import (
    EntryParameterStamp,
    JournalEntry,
    JournalFormula,
    JournalLine,
)
from evidenta.accounting.posting.services.commercial import (
    ROLE_CASA_MDL,
    ROLE_CREANTE_STRAINATATE,
    ROLE_CREANTE_TARA,
    ROLE_VENIT_SERVICII,
)
from evidenta.accounting.posting.services.settlement import (
    ROLE_CURS_FAVORABILA,
    ROLE_CURS_NEFAVORABILA,
    ROLE_SUMA_FAVORABILA,
    ROLE_SUMA_NEFAVORABILA,
)
from evidenta.accounting.slots.models import AccountRoleBinding
from evidenta.operations.sales.services.documents import open_sale
from evidenta.operations.sales.services.issuing import issue_and_post
from evidenta.operations.settlements.models import Settlement
from evidenta.operations.settlements.services.allocation import allocate, outstanding
from evidenta.operations.settlements.services.balances import open_documents
from evidenta.operations.treasury.services.documents import open_receipt
from evidenta.operations.treasury.services.recording import record_and_post
from evidenta.platform.audit.models import PrivilegedAccessLog
from evidenta.platform.audit.services.privileged import REFDATA_ALIAS
from evidenta.platform.documents.errors import ContractDenominationRequiredError
from evidenta.platform.documents.services.lifecycle import get_document
from evidenta.platform.documents.services.lines import LineInput, replace_lines
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.test_formulas import seed_account
from tests.isolation.test_ledger import seed_period
from tests.isolation.test_line_rounding import direction, scale, source  # noqa: F401
from tests.isolation.test_manual_entry import seed_template as seed_numbering

pytestmark = pytest.mark.django_db(databases=["default", "migration", "refdata"])

SAMPLE = Path(__file__).resolve().parents[2] / (
    "evidenta/accounting/currency/data/sample_rates.csv"
)

ISSUED = date(2026, 1, 20)
SETTLED = date(2026, 1, 25)
REPORTED = date(2026, 1, 31)
SETTLED_LATER = date(2026, 2, 10)

#: The fixture rates of ADR-057, plus one for the reporting date and one for the
#: settlement after it. Values, not published rates.
RATES = (
    ("EUR", ISSUED, "19.5000"),
    ("EUR", SETTLED, "19.6234"),
    ("EUR", REPORTED, "19.7000"),
    ("EUR", SETTLED_LATER, "19.8000"),
)

SNAPSHOT: dict[str, Any] = {"version": 1, "on": "2026-01-01", "activated": [], "usable": []}

ROLE_ACCOUNT_CODES = {
    ROLE_CREANTE_TARA: "2211",
    ROLE_CREANTE_STRAINATATE: "2212",
    ROLE_VENIT_SERVICII: "6111",
    ROLE_CASA_MDL: "2411",
    ROLE_CURS_FAVORABILA: "6226",
    ROLE_CURS_NEFAVORABILA: "7224",
    ROLE_SUMA_FAVORABILA: "6227",
    ROLE_SUMA_NEFAVORABILA: "7225",
}


# --- 1. the door ---------------------------------------------------------------------


def _log_rows() -> list[PrivilegedAccessLog]:
    return list(
        PrivilegedAccessLog.objects.using(REFDATA_ALIAS)
        .filter(path_code="P-3", actor="test:fx")
        .order_by("id")
    )


def _load(path: Path) -> str:
    out = io.StringIO()
    call_command("load_exchange_rates", str(path), actor="test:fx", stdout=out)
    return out.getvalue()


def test_the_door_writes_under_the_reference_role_once_and_refuses_a_change(
    tmp_path: Path,
) -> None:
    before = len(_log_rows())

    output = _load(SAMPLE)
    rows = ExchangeRate.objects.using(REFDATA_ALIAS).filter(currency="EUR").order_by("rate_date")
    assert [(r.rate_date, r.rate) for r in rows] == [
        (ISSUED, Decimal("19.50000000")),
        (SETTLED, Decimal("19.62340000")),
        (REPORTED, Decimal("19.70000000")),
        (SETTLED_LATER, Decimal("19.80000000")),
    ]
    assert "6 cursuri noi" in output
    logged = _log_rows()
    assert len(logged) == before + 1
    assert logged[-1].payload == {
        "file": "sample_rates.csv",
        "rows": 6,
        "created": 6,
        "unchanged": 0,
    }

    # Idempotent on the day: the same file again writes nothing and says so,
    # and still leaves its row -- a run that wrote nothing is still a run.
    assert "0 cursuri noi, 6 neschimbate" in _load(SAMPLE)
    assert len(_log_rows()) == before + 2

    # A different value for a day already there is refused, not overwritten:
    # an entry posted at 19.5000 must still stand on 19.5000 tomorrow.
    changed = tmp_path / "changed.csv"
    changed.write_text(
        "currency,rate_date,rate,rate_type,source\nEUR,2026-01-20,19.6000,bnm_official,test\n",
        encoding="utf-8",
    )
    with pytest.raises(CommandError, match=r"already 19\.50000000"):
        _load(changed)
    assert ExchangeRate.objects.using(REFDATA_ALIAS).get(
        currency="EUR", rate_date=ISSUED, rate_type="bnm_official"
    ).rate == Decimal("19.50000000")
    # The refused run left no row claiming it happened.
    assert len(_log_rows()) == before + 2


def test_a_day_without_a_rate_is_refused_not_carried_forward(
    world: dict[str, uuid.UUID],
) -> None:
    """ADR-039 section 3.2: which rate applies on a day with none published is a
    decision, and `rate_on` does not take it. Under a context, like every read
    on the application connection -- the table is global, the guard is not."""
    context = TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="fx")
    with tenant_context(context), pytest.raises(RateNotFoundError):
        rate_on("EUR", date(2026, 1, 21))


# --- the world -----------------------------------------------------------------------


@pytest.fixture
def fx_world(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
    source: uuid.UUID,  # noqa: F811 -- the fiscal act fixture, imported to be found
) -> dict[str, Any]:
    """A company with January and February open, the eight roles bound, one
    customer, and the fixture rates in the global table.

    The rates go in through the seed connection rather than the door, for the
    reason the fixture docstring in `conftest.py` gives about the seed: the test
    transaction on the application connection cannot see what the reference
    connection's transaction wrote. The door is proved above, on its own.
    """
    tenant = world["tenant_a"]
    company = company_of(tenant, "1002600000921", "Alpha Valută")
    grant_company(tenant, company, world["user_a"], world["user_a"])
    year, _ = seed_period(seed, tenant, company)
    seed_period(
        seed, tenant, company, start="2026-02-01", end="2026-02-28", period_no=2, year_id=year
    )
    seed_numbering(seed, tenant, company)
    for document_type in ("sales.document", "treasury.receipt"):
        seed_numbering(seed, tenant, company, document_type=document_type)
    scale(seed, world, "accounting.amount_scale", 2)
    direction(seed, world, "half_up")
    for currency, on, rate in RATES:
        seed(
            "INSERT INTO exchange_rate (id, currency, rate_date, rate, rate_type, source,"
            " created_at) VALUES (%s, %s, %s, %s, 'bnm_official', 'fixture', now())"
            " ON CONFLICT (currency, rate_date, rate_type) DO NOTHING",
            [uuid.uuid4(), currency, on, Decimal(rate)],
        )

    context = TenantContext(tenant_id=tenant, user_id=world["user_a"], request_id="fx")
    accounts = {
        role: seed_account(seed, tenant, company, code) for role, code in ROLE_ACCOUNT_CODES.items()
    }
    partner_id = uuid.uuid4()
    seed(
        "INSERT INTO partner (id, tenant_id, kind, legal_name, is_customer, is_supplier,"
        " is_active, created_at, updated_at)"
        " VALUES (%s, %s, 'legal_entity', 'Client Export SRL', true, false, true, now(), now())",
        [partner_id, tenant],
    )
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
    return {
        "tenant": tenant,
        "company": company,
        "user": world["user_a"],
        "partner": partner_id,
        "context": context,
        "accounts": accounts,
        "other": TenantContext(
            tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="fx-other"
        ),
    }


def an_invoice(
    world: dict[str, Any],
    *,
    amount: str = "1000.00",
    resident: bool = False,
    denomination: str | None = "foreign_currency",
    currency: str | None = "EUR",
    on: date = ISSUED,
) -> uuid.UUID:
    document_id = open_sale(
        company_id=world["company"],
        partner_id=world["partner"],
        document_date=on,
        revenue_kind="services",
        partner_resident=resident,
        currency=currency,
        contract_denomination=denomination,
    )
    replace_lines(
        document_id,
        [
            LineInput(
                description="Servicii de consultanță",
                quantity=Decimal("1"),
                unit_price=Decimal(amount),
                net_amount=Decimal(amount),
                vat_amount=Decimal("0"),
                total_amount=Decimal(amount),
                vat_regime_code="fara_tva",
                vat_rate=Decimal("0"),
            )
        ],
    )
    issue_and_post(
        document_id=document_id,
        actor_user_id=world["user"],
        request_id="invoice",
        capability_snapshot=SNAPSHOT,
    )
    return document_id


def a_receipt(world: dict[str, Any], *, amount: str, on: date = SETTLED) -> uuid.UUID:
    document_id = open_receipt(
        company_id=world["company"],
        partner_id=world["partner"],
        document_date=on,
        amount=Decimal(amount),
        treasury_account="cash",
        partner_resident=False,
    )
    record_and_post(
        document_id=document_id,
        actor_user_id=world["user"],
        request_id="receipt",
        capability_snapshot=SNAPSHOT,
    )
    return document_id


def settle(world: dict[str, Any], invoice: uuid.UUID, receipt: uuid.UUID, amount: str) -> Any:
    return allocate(
        settled_document_id=invoice,
        movement_document_id=receipt,
        amount=Decimal(amount),
        actor_user_id=world["user"],
        request_id="settle",
        capability_snapshot=SNAPSHOT,
    )


def revalue(world: dict[str, Any], as_of: date = REPORTED) -> Any:
    return revalue_monetary_items(
        tenant_id=world["tenant"],
        company_id=world["company"],
        as_of=as_of,
        actor_user_id=world["user"],
        request_id="revalue",
        capability_snapshot=SNAPSHOT,
    )


def correspondences(entry_id: uuid.UUID) -> list[tuple[uuid.UUID, uuid.UUID, Decimal]]:
    return [
        (f.debit_account_id, f.credit_account_id, f.amount)
        for f in JournalFormula.objects.filter(journal_entry_id=entry_id).order_by("id")
    ]


def balance_of(account_id: uuid.UUID) -> Decimal:
    lines = JournalLine.objects.filter(account_id=account_id)
    return sum((line.debit - line.credit for line in lines), Decimal(0))


# --- 2. the invoice ------------------------------------------------------------------


def test_a_eur_invoice_posts_the_receivable_in_currency_at_the_rate_of_its_day(
    fx_world: dict[str, Any],
) -> None:
    """1000 EUR at 19.5000 is 19,500.00 lei on 2212 -- with all four elements of
    Spec B section 7.1 on the line and the scale stamped on the entry."""
    a = fx_world["accounts"]
    with tenant_context(fx_world["context"]):
        invoice = an_invoice(fx_world)
        document = get_document(invoice)
        assert document.exchange_rate == Decimal("19.50000000")
        assert document.contract_denomination == "foreign_currency"

        entry = JournalEntry.objects.get(accounting_event__source_document_id=invoice)
        assert correspondences(entry.id) == [
            (a[ROLE_CREANTE_STRAINATATE], a[ROLE_VENIT_SERVICII], Decimal("19500.0000"))
        ]
        receivable = JournalLine.objects.get(
            journal_entry_id=entry.id, account_id=a[ROLE_CREANTE_STRAINATATE]
        )
        assert (receivable.debit, receivable.currency, receivable.amount_currency) == (
            Decimal("19500.0000"),
            "EUR",
            Decimal("1000.0000"),
        )
        assert receivable.exchange_rate == Decimal("19.50000000")
        assert receivable.rate_date == ISSUED
        assert [
            s.parameter_key for s in EntryParameterStamp.objects.filter(journal_entry_id=entry.id)
        ] == ["accounting.amount_scale"]

        # What is open is 1000 EUR, in EUR.
        (item,) = open_documents(fx_world["company"])
        assert (item.currency, item.outstanding) == ("EUR", Decimal("1000.0000"))


def test_a_document_in_currency_says_its_denomination_and_has_a_rate_for_its_day(
    fx_world: dict[str, Any],
) -> None:
    with tenant_context(fx_world["context"]):
        with pytest.raises(ContractDenominationRequiredError):
            open_sale(
                company_id=fx_world["company"],
                partner_id=fx_world["partner"],
                document_date=ISSUED,
                revenue_kind="services",
                partner_resident=False,
                currency="EUR",
            )
        # No rate published on the 21st: refused, not the 20th's carried over.
        with pytest.raises(RateNotFoundError):
            open_sale(
                company_id=fx_world["company"],
                partner_id=fx_world["partner"],
                document_date=date(2026, 1, 21),
                revenue_kind="services",
                partner_resident=False,
                currency="EUR",
                contract_denomination="foreign_currency",
            )


# --- 3. the settlement ---------------------------------------------------------------


def test_settling_in_lei_at_another_rate_posts_the_realised_exchange_difference(
    fx_world: dict[str, Any],
) -> None:
    """19,623.40 lei on the 25th are 1000 EUR at 19.6234; 1000 x (19.6234 - 19.5000)
    = 123.40 lands on 2212 / 6226 -- the receivable closes at zero, in both currencies."""
    a = fx_world["accounts"]
    with tenant_context(fx_world["context"]):
        invoice = an_invoice(fx_world)
        receipt = a_receipt(fx_world, amount="19623.40")

        result = settle(fx_world, invoice, receipt, "19623.40")

        assert (result.currency, result.amount_currency) == ("EUR", Decimal("1000.00"))
        assert result.outstanding_after == Decimal("0.0000")
        assert result.journal_entry_id is not None
        assert correspondences(result.journal_entry_id) == [
            (a[ROLE_CREANTE_STRAINATATE], a[ROLE_CURS_FAVORABILA], Decimal("123.4000"))
        ]
        row = Settlement.objects.get(pk=result.settlement_id)
        assert (row.currency, row.amount_currency, row.settlement_rate) == (
            "EUR",
            Decimal("1000.0000"),
            Decimal("19.62340000"),
        )
        assert row.amount == Decimal("19623.4000")
        assert outstanding(invoice) == Decimal("0.0000")
        assert balance_of(a[ROLE_CREANTE_STRAINATATE]) == Decimal("0.0000")


def test_a_resident_in_conventional_units_settled_in_lei_hits_the_sum_pair(
    fx_world: dict[str, Any],
) -> None:
    """Same arithmetic, other accounts: 2211 / 6227 (SNC pct. 17, 20) -- and at
    the reporting date nothing is restated (pct. 22)."""
    a = fx_world["accounts"]
    with tenant_context(fx_world["context"]):
        invoice = an_invoice(fx_world, resident=True, denomination="conventional_units")
        receipt = a_receipt(fx_world, amount="19623.40")
        result = settle(fx_world, invoice, receipt, "19623.40")
        assert correspondences(result.journal_entry_id) == [
            (a[ROLE_CREANTE_TARA], a[ROLE_SUMA_FAVORABILA], Decimal("123.4000"))
        ]

        # A second, still open, conventional-units invoice: out of the perimeter.
        an_invoice(fx_world, resident=True, denomination="conventional_units", amount="400.00")
        revaluation = revalue(fx_world)
        assert revaluation.posted_now is True
        assert revaluation.revaluation.journal_entry_id is None
        assert revaluation.revaluation.items == ()


# --- 4. the revaluation --------------------------------------------------------------


def test_the_open_half_is_restated_once_and_the_next_settlement_starts_from_there(
    fx_world: dict[str, Any],
) -> None:
    """The `A10` criterion, in one story.

    1000 EUR at 19.5000. Half settled on the 25th at 19.6234 (61.70 realised).
    On the 31st the open 500 EUR are restated from 19.5000 to 19.7000: 100.00
    unrealised, one entry, the partner on the formula. A second run posts
    nothing. On 10 February the other half is settled at 19.8000: the realised
    difference is 500 x (19.8000 - 19.7000) = 50.00 -- measured from the
    revalued rate, not 150.00 from the invoice's (SNC pct. 15, Example 3). And
    2212 closes at exactly zero.
    """
    a = fx_world["accounts"]
    with tenant_context(fx_world["context"]):
        invoice = an_invoice(fx_world)
        first = settle(fx_world, invoice, a_receipt(fx_world, amount="9811.70"), "9811.70")
        assert correspondences(first.journal_entry_id) == [
            (a[ROLE_CREANTE_STRAINATATE], a[ROLE_CURS_FAVORABILA], Decimal("61.7000"))
        ]
        assert outstanding(invoice) == Decimal("500.0000")

        entries_before = JournalEntry.objects.count()
        result = revalue(fx_world)
        assert result.posted_now is True
        view = result.revaluation
        assert view.journal_entry_id is not None
        assert correspondences(view.journal_entry_id) == [
            (a[ROLE_CREANTE_STRAINATATE], a[ROLE_CURS_FAVORABILA], Decimal("100.0000"))
        ]
        entry = JournalEntry.objects.get(pk=view.journal_entry_id)
        assert entry.accounting_date == REPORTED
        assert entry.rule_ref == "revaluation.monetary_items.v1"
        assert [
            s.parameter_key for s in EntryParameterStamp.objects.filter(journal_entry_id=entry.id)
        ] == ["accounting.amount_scale"]
        (item,) = view.items
        assert (item.amount_currency, item.rate_before, item.rate_after, item.difference) == (
            Decimal("500.0000"),
            Decimal("19.50000000"),
            Decimal("19.70000000"),
            Decimal("100.0000"),
        )
        assert Revaluation.objects.count() == 1 and RevaluationItem.objects.count() == 1

        # The second run: the same revaluation, nothing new in the ledger.
        again = revalue(fx_world)
        assert again.posted_now is False
        assert again.revaluation.id == view.id
        assert JournalEntry.objects.count() == entries_before + 1
        assert Revaluation.objects.count() == 1

        # The rest, in February, from the revalued base.
        second = settle(
            fx_world, invoice, a_receipt(fx_world, amount="9900.00", on=SETTLED_LATER), "9900.00"
        )
        assert second.amount_currency == Decimal("500.00")
        assert correspondences(second.journal_entry_id) == [
            (a[ROLE_CREANTE_STRAINATATE], a[ROLE_CURS_FAVORABILA], Decimal("50.0000"))
        ]
        assert outstanding(invoice) == Decimal("0.0000")
        assert balance_of(a[ROLE_CREANTE_STRAINATATE]) == Decimal("0.0000")
        assert open_documents(fx_world["company"]) == ()


# --- IZ ------------------------------------------------------------------------------


def test_another_tenant_sees_nothing_of_it(fx_world: dict[str, Any]) -> None:
    with tenant_context(fx_world["context"]):
        invoice = an_invoice(fx_world)
        settle(fx_world, invoice, a_receipt(fx_world, amount="9811.70"), "9811.70")
        revalue(fx_world)
        assert Settlement.objects.count() == 1
        assert Revaluation.objects.count() == 1

    with tenant_context(fx_world["other"]):
        assert Settlement.objects.count() == 0
        assert Revaluation.objects.count() == 0
        assert RevaluationItem.objects.count() == 0
        assert list_revaluations(fx_world["company"]) == ()
        # The rate is global, and the same for everyone (Spec B section 7.2).
        assert rate_on("EUR", ISSUED) == Decimal("19.50000000")


def test_a_rate_without_a_source_is_refused(tmp_path: Path) -> None:
    """R15: reference data names where it was read. A bulletin rate with no bulletin
    is not loaded -- refused at the door, before the reference role writes anything."""
    path = tmp_path / "no-source.csv"
    path.write_text(
        "currency,rate_date,rate,rate_type,source\nEUR,2026-03-15,19.5000,bnm_official,\n",
        encoding="utf-8",
    )
    with pytest.raises(CommandError, match="source"):
        _load(path)
    assert not (
        ExchangeRate.objects.using(REFDATA_ALIAS)
        .filter(currency="EUR", rate_date=date(2026, 3, 15))
        .exists()
    )
