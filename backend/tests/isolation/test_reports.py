"""The accounting reports of F1.8 -- read from the ledger, totalled by the server.

What is asserted is arithmetic and shape, never treatment: the account ledger
shows one row per document with its correspondence and a running balance; the
general ledger buckets by the company's months and explains each turnover by
correspondent, naming the part it cannot; the chess-board sums every pair; the
drill-down reaches the origin. Fixture accounts throughout (`FIXTURE-*`), fixture
correspondences, nothing declared as SNC.

**Under the application role, like every test in this suite** (T1): the reports
read through the same policies a request does, and the last test proves another
tenant's ledger is absent from them, not forbidden.
"""

from __future__ import annotations

import csv
import io
import json
import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from typing import Any

import pyotp
import pytest
from django.contrib.auth.hashers import make_password
from django.test import Client

from evidenta.accounting.ledger.errors import LedgerAccountNotFoundError
from evidenta.accounting.ledger.services import export
from evidenta.accounting.ledger.services.account_ledger import account_ledger
from evidenta.accounting.ledger.services.correspondence import correspondence
from evidenta.accounting.ledger.services.detail import entry_detail
from evidenta.accounting.ledger.services.general_ledger import general_ledger
from evidenta.accounting.ledger.services.trial_balance import trial_balance
from evidenta.accounting.posting.formula import DimensionValue
from evidenta.accounting.posting.services.manual import post_manual_entry
from evidenta.platform.identity.models import User
from evidenta.platform.identity.services.authentication import (
    confirm_totp,
    enrol_totp,
    generate_secret_key,
)
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.test_formulas import MDL, POSTING, RULE, SNAPSHOT, formula, post, seed_account
from tests.isolation.test_ledger import seed_period
from tests.isolation.test_manual_entry import seed_template as seed_numbering

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

PASSWORD = "o-parola-suficient-de-lunga"
HOST = {"host": "alpha.evidenta.localhost"}


@pytest.fixture(autouse=True)
def mfa_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MFA_SECRET_KEY", generate_secret_key())


@pytest.fixture
def signed_in(world: dict[str, uuid.UUID]) -> Client:
    """A client holding a real session cookie for tenant A -- the route
    `test_coa_api` takes, second factor included."""
    setup = TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="setup")
    with tenant_context(setup):
        User.objects.filter(pk=world["user_a"]).update(password_hash=make_password(PASSWORD))
        enrolment = enrol_totp(world["user_a"], label="phone")
        secret = str(pyotp.parse_uri(enrolment.provisioning_uri).secret)  # type: ignore[union-attr]
        confirm_totp(enrolment.method_id, pyotp.TOTP(secret).now())

    client = Client()
    response = client.post(
        "/api/v1/auth/login",
        data=json.dumps(
            {"email": "a@example.md", "password": PASSWORD, "totp_code": pyotp.TOTP(secret).now()}
        ),
        content_type="application/json",
        headers=HOST,
    )
    assert response.status_code == 200, response.content
    return client


JANUARY = (date(2026, 1, 1), date(2026, 1, 31))
FEBRUARY = (date(2026, 2, 1), date(2026, 2, 28))
QUARTER = (date(2026, 1, 1), date(2026, 3, 31))


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="reports")


@pytest.fixture
def scene(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> dict[str, Any]:
    """One company, three months of one exercise, a numbering template, accounts."""
    tenant = world["tenant_a"]
    company = company_of(tenant, "1002600001101", "Alpha Rapoarte")
    grant_company(tenant, company, world["user_a"], world["user_a"])
    year, january = seed_period(seed, tenant, company)
    _, february = seed_period(
        seed, tenant, company, start="2026-02-01", end="2026-02-28", period_no=2, year_id=year
    )
    _, march = seed_period(
        seed, tenant, company, start="2026-03-01", end="2026-03-31", period_no=3, year_id=year
    )
    seed_numbering(seed, tenant, company)
    return {
        "tenant": tenant,
        "company": company,
        "user": world["user_a"],
        "periods": {"january": january, "february": february, "march": march},
        "receivable": seed_account(
            seed, tenant, company, "FIXTURE-R", slots=("partner",), requires=("partner",)
        ),
        "revenue": seed_account(seed, tenant, company, "FIXTURE-V"),
        "vat": seed_account(seed, tenant, company, "FIXTURE-T"),
        "bank": seed_account(seed, tenant, company, "FIXTURE-B"),
        "partner": uuid.uuid4(),
    }


def sales(
    scene: dict[str, Any], seed: Callable[..., None], net: str, vat: str, on: date
) -> uuid.UUID:
    """A delivery: receivable against revenue and VAT, dated `on`."""
    partner = DimensionValue("partner", scene["partner"])
    return post(
        scene,
        [
            formula(
                scene["receivable"],
                scene["revenue"],
                net,
                dimensions=[partner],
                rate_date=on,
                document_date=on,
            ),
            formula(
                scene["receivable"],
                scene["vat"],
                vat,
                dimensions=[partner],
                vat_rate="20",
                rate_date=on,
                document_date=on,
            ),
        ],
        seed,
        accounting_date=on,
    )


def receipt(scene: dict[str, Any], seed: Callable[..., None], amount: str, on: date) -> uuid.UUID:
    """The customer pays: bank against receivable."""
    partner = DimensionValue("partner", scene["partner"])
    return post(
        scene,
        [
            formula(
                scene["bank"],
                scene["receivable"],
                amount,
                dimensions=[partner],
                rate_date=on,
                document_date=on,
            )
        ],
        seed,
        accounting_date=on,
    )


# --- fișa contului -------------------------------------------------------------


def test_the_account_ledger_shows_one_row_per_document_with_its_correspondence(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    """Two formulas of one invoice are one row on 221 (ADR-053 §3.1), showing both
    counterparts; the payment is a second row; the balance runs after each."""
    with tenant_context(context):
        invoice = sales(scene, seed, "100", "20", date(2026, 1, 10))
        payment = receipt(scene, seed, "50", date(2026, 1, 20))
        ledger = account_ledger(scene["company"], scene["receivable"], *JANUARY)

    assert ledger.account_code == "FIXTURE-R"
    assert ledger.opening == Decimal(0)
    assert [(row.journal_entry_id, row.debit, row.credit, row.balance) for row in ledger.rows] == [
        (invoice, Decimal("120.0000"), Decimal(0), Decimal("120.0000")),
        (payment, Decimal(0), Decimal("50.0000"), Decimal("70.0000")),
    ]
    first = ledger.rows[0]
    assert first.has_formulas
    assert [(c.account_code, c.debit, c.credit) for c in first.correspondents] == [
        ("FIXTURE-T", Decimal("20.0000"), Decimal(0)),
        ("FIXTURE-V", Decimal("100.0000"), Decimal(0)),
    ]
    assert [(c.account_code, c.debit, c.credit) for c in ledger.rows[1].correspondents] == [
        ("FIXTURE-B", Decimal(0), Decimal("50.0000"))
    ]
    assert (ledger.total_debit, ledger.total_credit, ledger.closing) == (
        Decimal("120.0000"),
        Decimal("50.0000"),
        Decimal("70.0000"),
    )
    assert not ledger.truncated


def test_the_opening_balance_is_everything_before_the_window(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    with tenant_context(context):
        sales(scene, seed, "100", "20", date(2026, 1, 10))
        february_payment = receipt(scene, seed, "30", date(2026, 2, 5))
        ledger = account_ledger(scene["company"], scene["receivable"], *FEBRUARY)

    assert ledger.opening == Decimal("120.0000")
    assert [row.journal_entry_id for row in ledger.rows] == [february_payment]
    assert ledger.rows[0].balance == Decimal("90.0000")
    assert ledger.closing == Decimal("90.0000")


def test_a_lines_only_entry_is_a_row_without_correspondence(
    context: TenantContext, scene: dict[str, Any]
) -> None:
    """The manual note writes no formulas (ADR-048 §4). Its row is there, with
    the amount and `has_formulas = False` -- not invented from the lines."""
    payload = {
        "description": "Nota manuala",
        "lines": [
            {"account_id": str(scene["bank"]), "debit": "7", "credit": "0"},
            {"account_id": str(scene["vat"]), "debit": "0", "credit": "7"},
        ],
    }
    with tenant_context(context):
        result = post_manual_entry(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            accounting_date=POSTING,
            functional_currency=MDL,
            note_id=uuid.uuid4(),
            payload=payload,
            idempotency_key="report-note",
            actor_user_id=scene["user"],
            request_id="reports",
            capability_snapshot=SNAPSHOT,
        )
        ledger = account_ledger(scene["company"], scene["bank"], *JANUARY)

    (row,) = ledger.rows
    assert row.journal_entry_id == result.journal_entry_id
    assert row.debit == Decimal("7.0000") and not row.has_formulas and row.correspondents == ()


def test_an_account_this_context_cannot_see_is_refused_not_emptied(
    context: TenantContext, scene: dict[str, Any]
) -> None:
    with tenant_context(context), pytest.raises(LedgerAccountNotFoundError) as excinfo:
        account_ledger(scene["company"], uuid.uuid4(), *JANUARY)
    assert excinfo.value.code == "ledger.account_not_found"


# --- Cartea Mare -----------------------------------------------------------------


def test_the_general_ledger_buckets_by_the_companys_months_and_explains_each_turnover(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    with tenant_context(context):
        sales(scene, seed, "100", "20", date(2026, 1, 10))
        sales(scene, seed, "200", "40", date(2026, 1, 25))
        receipt(scene, seed, "50", date(2026, 2, 5))
        ledger = general_ledger(scene["company"], scene["receivable"], *QUARTER)

    assert [m.period_no for m in ledger.months] == [1, 2]
    january, february = ledger.months
    assert (january.opening, january.debit, january.credit, january.closing) == (
        Decimal(0),
        Decimal("360.0000"),
        Decimal(0),
        Decimal("360.0000"),
    )
    assert [(t.account_code, t.amount) for t in january.debit_by] == [
        ("FIXTURE-T", Decimal("60.0000")),
        ("FIXTURE-V", Decimal("300.0000")),
    ]
    assert january.credit_by == () and january.debit_unassigned == Decimal(0)
    assert (february.opening, february.credit, february.closing) == (
        Decimal("360.0000"),
        Decimal("50.0000"),
        Decimal("310.0000"),
    )
    assert [(t.account_code, t.amount) for t in february.credit_by] == [
        ("FIXTURE-B", Decimal("50.0000"))
    ]
    assert (ledger.total_debit, ledger.total_credit, ledger.closing) == (
        Decimal("360.0000"),
        Decimal("50.0000"),
        Decimal("310.0000"),
    )


def test_the_general_ledger_names_the_turnover_no_formula_explains(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    """A month with a formula entry and a lines-only note: the note's turnover is
    in the month's total and reported as unassigned, never spread on a counterpart."""
    payload = {
        "description": "Nota manuala",
        "lines": [
            {"account_id": str(scene["bank"]), "debit": "7", "credit": "0"},
            {"account_id": str(scene["vat"]), "debit": "0", "credit": "7"},
        ],
    }
    with tenant_context(context):
        receipt(scene, seed, "50", date(2026, 1, 20))
        post_manual_entry(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            accounting_date=POSTING,
            functional_currency=MDL,
            note_id=uuid.uuid4(),
            payload=payload,
            idempotency_key="report-note-2",
            actor_user_id=scene["user"],
            request_id="reports",
            capability_snapshot=SNAPSHOT,
        )
        ledger = general_ledger(scene["company"], scene["bank"], *JANUARY)

    (january,) = ledger.months
    assert january.debit == Decimal("57.0000")
    assert [(t.account_code, t.amount) for t in january.debit_by] == [
        ("FIXTURE-R", Decimal("50.0000"))
    ]
    assert january.debit_unassigned == Decimal("7.0000")


# --- rulaje pe corespondențe ---------------------------------------------------------


def test_the_chess_board_sums_every_pair_and_names_what_it_cannot_see(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    payload = {
        "description": "Nota manuala",
        "lines": [
            {"account_id": str(scene["bank"]), "debit": "7", "credit": "0"},
            {"account_id": str(scene["vat"]), "debit": "0", "credit": "7"},
        ],
    }
    with tenant_context(context):
        sales(scene, seed, "100", "20", date(2026, 1, 10))
        sales(scene, seed, "200", "40", date(2026, 1, 25))
        receipt(scene, seed, "50", date(2026, 1, 28))
        post_manual_entry(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            accounting_date=POSTING,
            functional_currency=MDL,
            note_id=uuid.uuid4(),
            payload=payload,
            idempotency_key="report-note-3",
            actor_user_id=scene["user"],
            request_id="reports",
            capability_snapshot=SNAPSHOT,
        )
        report = correspondence(scene["company"], *JANUARY)

    assert [(c.debit_code, c.credit_code, c.amount) for c in report.cells] == [
        ("FIXTURE-B", "FIXTURE-R", Decimal("50.0000")),
        ("FIXTURE-R", "FIXTURE-T", Decimal("60.0000")),
        ("FIXTURE-R", "FIXTURE-V", Decimal("300.0000")),
    ]
    assert [(t.account_code, t.amount) for t in report.debit_totals] == [
        ("FIXTURE-B", Decimal("50.0000")),
        ("FIXTURE-R", Decimal("360.0000")),
    ]
    assert report.total == Decimal("410.0000")
    assert report.lines_total == Decimal("417.0000")
    assert report.unassigned == Decimal("7.0000")


# --- drill-down ----------------------------------------------------------------------


def test_the_drill_down_reaches_the_formulas_the_stamps_and_the_origin(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    with tenant_context(context):
        invoice = sales(scene, seed, "100", "20", date(2026, 1, 10))
        detail = entry_detail(invoice)
        assert entry_detail(uuid.uuid4()) is None

    assert detail is not None
    assert detail.rule_ref == RULE
    assert detail.fiscal_effective_date == date(2026, 1, 10)
    assert detail.chart is None  # fixture accounts, no template
    assert [(f.debit_code, f.credit_code, f.amount, f.vat_rate) for f in detail.formulas] == [
        ("FIXTURE-R", "FIXTURE-V", Decimal("100.0000"), None),
        ("FIXTURE-R", "FIXTURE-T", Decimal("20.0000"), Decimal("20.0000")),
    ]
    assert detail.formulas[0].slots == (("partner", scene["partner"]),)
    assert [(line.account_code, line.debit, line.credit) for line in detail.lines] == [
        ("FIXTURE-R", Decimal("100.0000"), Decimal(0)),
        ("FIXTURE-V", Decimal(0), Decimal("100.0000")),
        ("FIXTURE-R", Decimal("20.0000"), Decimal(0)),
        ("FIXTURE-T", Decimal(0), Decimal("20.0000")),
    ]
    assert detail.lines[0].dimensions == (("partner", scene["partner"]),)
    assert detail.origin is not None
    assert (detail.origin.source_module, detail.origin.source_document_type) == (
        "manual",
        "fixture",
    )


# --- the export is the same result, written out ----------------------------------------


def test_the_csv_is_the_same_figures_the_screen_shows(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    """C20: produced from the dataclass the screen was rendered from, so the two
    cannot diverge; C38: Romanian conventions -- decimal comma, dd.mm.yyyy --
    whatever the interface language."""
    with tenant_context(context):
        sales(scene, seed, "100.5", "20.1", date(2026, 1, 10))
        ledger = account_ledger(scene["company"], scene["receivable"], *JANUARY)
        balance = trial_balance(scene["company"], *JANUARY)

    body = export.account_ledger_csv(ledger)
    assert body.startswith("﻿".encode())
    rows = list(csv.reader(io.StringIO(body.decode("utf-8-sig")), delimiter=";"))
    assert rows[0] == [
        "Data",
        "Număr",
        "Data documentului",
        "Descriere",
        "Cont corespondent",
        "Debit",
        "Credit",
        "Sold",
    ]
    assert rows[1][3:] == ["Sold inițial", "", "", "", "0,00"]
    assert rows[2][0] == "10.01.2026"
    assert rows[2][4:] == ["FIXTURE-T, FIXTURE-V", "120,60", "0,00", "120,60"]
    assert rows[-1][3:] == ["Sold final", "", "", "", "120,60"]

    balance_rows = list(
        csv.reader(
            io.StringIO(export.trial_balance_csv(balance).decode("utf-8-sig")), delimiter=";"
        )
    )
    assert balance_rows[-1][0] == "Total"
    assert balance_rows[-1][3] == balance_rows[-1][4] == "120,60"


# --- over HTTP -------------------------------------------------------------------------


def test_the_endpoints_answer_json_and_csv_from_one_service(
    context: TenantContext,
    scene: dict[str, Any],
    seed: Callable[..., None],
    signed_in: Client,
) -> None:
    with tenant_context(context):
        sales(scene, seed, "100", "20", date(2026, 1, 10))

    base = f"/api/v1/accounting/ledger/companies/{scene['company']}"
    account = f"{base}/accounts/{scene['receivable']}"
    window = "?from=2026-01-01&to=2026-01-31"

    ledger = signed_in.get(f"{account}/ledger{window}", headers=HOST).json()
    assert ledger["closing"] == "120.0000" and len(ledger["rows"]) == 1
    assert ledger["rows"][0]["correspondents"][0]["account_code"] == "FIXTURE-T"

    general = signed_in.get(f"{account}/general-ledger{window}", headers=HOST).json()
    assert general["months"][0]["debit_by"][1] == {
        "account_id": str(scene["revenue"]),
        "account_code": "FIXTURE-V",
        "amount": "100.0000",
    }

    chess = signed_in.get(f"{base}/correspondence{window}", headers=HOST).json()
    assert chess["total"] == "120.0000" and chess["unassigned"] == "0.0000"

    entry_id = ledger["rows"][0]["journal_entry_id"]
    detail = signed_in.get(f"/api/v1/accounting/ledger/entries/{entry_id}", headers=HOST).json()
    assert detail["rule_ref"] == RULE and len(detail["formulas"]) == 2

    exported = signed_in.get(f"{account}/ledger{window}&export=csv", headers=HOST)
    assert exported.status_code == 200
    assert exported["Content-Type"].startswith("text/csv")
    assert exported["Content-Disposition"].startswith('attachment; filename="fisa-cont-FIXTURE-R-')
    assert b"120,00" in exported.content

    refused = signed_in.get(f"{base}/correspondence{window}&export=xlsx", headers=HOST)
    assert refused.status_code == 400 and refused.json()["code"] == "ledger.unknown_format"

    missing = signed_in.get(f"/api/v1/accounting/ledger/entries/{uuid.uuid4()}", headers=HOST)
    assert missing.status_code == 404 and missing.json()["code"] == "api.not_found"


# --- isolation -------------------------------------------------------------------------


def test_another_tenants_ledger_is_absent_from_every_report(
    context: TenantContext,
    scene: dict[str, Any],
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
) -> None:
    with tenant_context(context):
        invoice = sales(scene, seed, "100", "20", date(2026, 1, 10))

    other = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="reports"
    )
    with tenant_context(other):
        with pytest.raises(LedgerAccountNotFoundError):
            account_ledger(scene["company"], scene["receivable"], *JANUARY)
        with pytest.raises(LedgerAccountNotFoundError):
            general_ledger(scene["company"], scene["receivable"], *JANUARY)
        assert correspondence(scene["company"], *JANUARY).cells == ()
        assert entry_detail(invoice) is None


# --- reversals and closing entries read like any other document -------------------------


def test_a_reversal_reads_as_the_opposite_side_against_the_same_counterpart_and_is_linked(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    """The mirror swaps accounts, never signs (R10): on 221 the storno is a credit
    against the same counterparts, and both rows carry their R14 link."""
    from django.db import connection

    from evidenta.accounting.ledger.services.reversal import reverse_entry
    from tests.isolation.test_ledger import seed_event

    with tenant_context(context):
        invoice = sales(scene, seed, "100", "20", date(2026, 1, 10))
        event = seed_event(seed, scene["tenant"], scene["company"], scene["user"])
        with connection.cursor() as cursor:
            cursor.execute("SET CONSTRAINTS ALL DEFERRED")
        storno = reverse_entry(
            invoice,
            accounting_event_id=event,
            period_id=scene["periods"]["january"],
            accounting_date=date(2026, 1, 20),
            entry_number="NC-STORNO",
            request_id="reports",
            rule_ref="fixture.reversal.v1",
        )
        ledger = account_ledger(scene["company"], scene["receivable"], *JANUARY)
        chess = correspondence(scene["company"], *JANUARY)
        detail = entry_detail(storno.id)
        general = general_ledger(scene["company"], scene["receivable"], *JANUARY)

    original, mirror = ledger.rows
    assert (original.debit, original.credit) == (Decimal("120.0000"), Decimal(0))
    assert (mirror.debit, mirror.credit) == (Decimal(0), Decimal("120.0000"))
    assert mirror.entry_type == "reversal"
    assert [(c.account_code, c.debit, c.credit) for c in mirror.correspondents] == [
        ("FIXTURE-T", Decimal(0), Decimal("20.0000")),
        ("FIXTURE-V", Decimal(0), Decimal("100.0000")),
    ]
    assert original.reversed_by_entry_id == storno.id and original.reverses_entry_id is None
    assert mirror.reverses_entry_id == invoice and mirror.reversed_by_entry_id is None
    assert ledger.closing == Decimal(0)
    # The chess-board carries the pair in both directions, not netted.
    assert [(c.debit_code, c.credit_code, c.amount) for c in chess.cells] == [
        ("FIXTURE-R", "FIXTURE-T", Decimal("20.0000")),
        ("FIXTURE-R", "FIXTURE-V", Decimal("100.0000")),
        ("FIXTURE-T", "FIXTURE-R", Decimal("20.0000")),
        ("FIXTURE-V", "FIXTURE-R", Decimal("100.0000")),
    ]
    assert detail is not None and detail.reverses_entry_id == invoice
    # Cartea Mare: the same two counterparts on both sides of the month, and a
    # month that closes where it opened.
    (january,) = general.months
    assert [(t.account_code, t.amount) for t in january.debit_by] == [
        ("FIXTURE-T", Decimal("20.0000")),
        ("FIXTURE-V", Decimal("100.0000")),
    ]
    assert [(t.account_code, t.amount) for t in january.credit_by] == [
        ("FIXTURE-T", Decimal("20.0000")),
        ("FIXTURE-V", Decimal("100.0000")),
    ]
    assert january.closing == january.opening == Decimal(0)


def test_a_closing_entry_is_a_document_row_like_any_other(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    """ADR-053: the year-end chain posts through formulas with entry_type
    'closing' and reads with full correspondence -- no special case."""
    from evidenta.accounting.posting.invariants import Origin
    from evidenta.accounting.posting.services.formulas import post_formulas
    from tests.isolation.test_ledger import seed_event

    with tenant_context(context):
        sales(scene, seed, "100", "20", date(2026, 1, 10))
        event = seed_event(seed, scene["tenant"], scene["company"], scene["user"])
        closing = post_formulas(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            accounting_date=date(2026, 1, 31),
            functional_currency=MDL,
            accounting_event_id=event,
            origin=Origin(module="periods", document_type="fixture", document_id=uuid.uuid4()),
            rule_ref="fixture.closing.v1",
            description="Închidere de fixture",
            request_id="reports",
            actor_user_id=scene["user"],
            entry_type="closing",
            formulas=[
                formula(
                    scene["revenue"],
                    scene["vat"],
                    "100",
                    rate_date=date(2026, 1, 31),
                    document_date=date(2026, 1, 31),
                )
            ],
        )
        ledger = account_ledger(scene["company"], scene["revenue"], *JANUARY)
        general = general_ledger(scene["company"], scene["revenue"], *JANUARY)
        chess = correspondence(scene["company"], *JANUARY)
        detail = entry_detail(closing.journal_entry_id)

    assert detail is not None and detail.entry_type == "closing"
    assert [(f.debit_code, f.credit_code) for f in detail.formulas] == [("FIXTURE-V", "FIXTURE-T")]
    assert ("FIXTURE-V", "FIXTURE-T", Decimal("100.0000")) in [
        (c.debit_code, c.credit_code, c.amount) for c in chess.cells
    ]
    assert [(row.entry_type, row.debit, row.credit) for row in ledger.rows] == [
        ("standard", Decimal(0), Decimal("100.0000")),
        ("closing", Decimal("100.0000"), Decimal(0)),
    ]
    assert ledger.rows[1].journal_entry_id == closing.journal_entry_id
    assert ledger.rows[1].correspondents[0].account_code == "FIXTURE-T"
    assert ledger.closing == Decimal(0)
    (january,) = general.months
    assert [(t.account_code, t.amount) for t in january.debit_by] == [
        ("FIXTURE-T", Decimal("100.0000"))
    ]
    assert [(t.account_code, t.amount) for t in january.credit_by] == [
        ("FIXTURE-R", Decimal("100.0000"))
    ]


def test_the_general_ledger_reads_whole_months_whatever_the_window_edges(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    """A window that starts on the 15th still reads January whole, on both the
    turnover and the correspondence side -- and says so in its own dates."""
    with tenant_context(context):
        sales(scene, seed, "100", "20", date(2026, 1, 10))
        receipt(scene, seed, "50", date(2026, 1, 20))
        ledger = general_ledger(
            scene["company"], scene["receivable"], date(2026, 1, 15), date(2026, 2, 10)
        )

    assert (ledger.start_date, ledger.end_date) == (date(2026, 1, 1), date(2026, 1, 31))
    (january,) = ledger.months
    assert (january.debit, january.credit) == (Decimal("120.0000"), Decimal("50.0000"))
    assert sum((t.amount for t in january.debit_by), Decimal(0)) == january.debit
    assert sum((t.amount for t in january.credit_by), Decimal(0)) == january.credit


# --- ADR-059: what the register refuses on its own -----------------------------------------


def test_the_register_refuses_a_line_dated_off_its_entry_and_a_third_decimal(
    context: TenantContext, scene: dict[str, Any], seed: Callable[..., None]
) -> None:
    """Both barriers past the engine: the trigger on the line's date and the CHECK
    on the amount's scale, met by a writer that skipped the engine."""
    from django.db import IntegrityError, transaction

    from evidenta.accounting.ledger.models import JournalEntry, JournalLine
    from tests.isolation.test_ledger import seed_event

    with tenant_context(context):
        event = seed_event(seed, scene["tenant"], scene["company"], scene["user"])
        entry = JournalEntry.objects.create(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            entry_number="NC-BARRIER",
            accounting_date=POSTING,
            period_id=scene["periods"]["january"],
            accounting_event_id=event,
            description="Probe",
            request_id="reports",
        )
        common = dict(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            journal_entry=entry,
            account_id=scene["bank"],
            currency=MDL,
            exchange_rate=Decimal(1),
            document_date=POSTING,
            rate_date=POSTING,
        )
        with (
            pytest.raises(IntegrityError, match="carries the posting date of its entry"),
            transaction.atomic(),
        ):
            JournalLine.objects.create(
                line_number=1,
                accounting_date=date(2026, 1, 20),
                debit=Decimal("1"),
                credit=Decimal(0),
                amount_currency=Decimal("1"),
                **common,
            )
        with pytest.raises(IntegrityError, match="journal_line_amount_scale"), transaction.atomic():
            JournalLine.objects.create(
                line_number=1,
                accounting_date=POSTING,
                debit=Decimal("1.005"),
                credit=Decimal(0),
                amount_currency=Decimal("1.005"),
                **common,
            )
