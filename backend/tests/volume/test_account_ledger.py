"""The account ledger at volume -- ADR-053 §3.2, §3.3, under the application role.

The scenario the ADR sets the target on: the "Mare" company, one busy account,
one month, rows aggregated per document. Two things are measured, and both are
printed with the environment beside them rather than asserted at the default
scale, where nothing is slow:

* the plan of the read `account_ledger` makes reaches its rows through
  `journal_line_account_idx` -- the index ADR-053 §4 names -- and not through a
  scan of the company's whole ledger;
* how long the busiest month takes, wall clock, through the service, with RLS
  active. At the opt-in scale (`EVIDENTA_VOLUME_ROWS`) the proposed threshold of
  one second (ADR-053 §3.3, proposed, not decided) is asserted.

The rows go in as the model says they arrive: N documents over a year, each one
entry with two lines and one formula, spread over twelve open months, a handful
of accounts with one that takes every debit. Inserted through `generate_series`
under `evidenta_app` so the policies are evaluated per row -- a benchmark on rows
the owner wrote would be a benchmark of a database we do not run.
"""

from __future__ import annotations

import os
import re
import time
import uuid
from collections.abc import Callable
from datetime import date

import pytest
from django.db import connection

from evidenta.accounting.ledger.services.account_ledger import AccountLedger, account_ledger
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.test_ledger import seed_period

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

DEFAULT_DOCUMENTS = 2_000
DOCUMENTS = int(os.environ.get("EVIDENTA_VOLUME_ROWS", DEFAULT_DOCUMENTS))

#: ADR-053 §3.3, the account ledger row: proposed by the implementing session,
#: to be confirmed by the owner. Asserted only at the opt-in scale.
PROPOSED_SECONDS = 1.0


def generate_ledger(
    seed: Callable[..., None],
    tenant: uuid.UUID,
    company: uuid.UUID,
    user: uuid.UUID,
    documents: int,
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    """`documents` posted entries over 2026, two lines and one formula each.

    Returns the busy account (debited on every entry) and the credit accounts.
    """
    year, _ = seed_period(seed, tenant, company)
    for number, month in enumerate(range(2, 13), start=2):
        last = date(2026, month + 1, 1) if month < 12 else date(2027, 1, 1)
        seed_period(
            seed,
            tenant,
            company,
            start=f"2026-{month:02d}-01",
            end=str(date.fromordinal(last.toordinal() - 1)),
            period_no=number,
            year_id=year,
        )

    busy = uuid.uuid4()
    credits = [uuid.uuid4() for _ in range(5)]
    for account_id, code in ((busy, "VOL-D"), *((c, f"VOL-C{i}") for i, c in enumerate(credits))):
        seed(
            "INSERT INTO company_account (id, tenant_id, company_id, account_code, parent_id,"
            " origin, template_account_id, name_ro, account_class, normal_balance,"
            " allows_subaccounts, currency_tracking, quantity_tracking, required_dimensions,"
            " is_blocked, valid_from, valid_to, created_at, updated_at)"
            " VALUES (%s, %s, %s, %s, NULL, 'company', NULL, %s, 'asset', 'debit', false,"
            " false, false, '{}'::text[], false, '2020-01-01', NULL, now(), now())",
            [account_id, tenant, company, code, f"Cont de volum {code}"],
        )

    with connection.cursor() as cursor:
        # One event per document, then the entry, its two lines and its formula
        # -- four statements over generate_series, policies evaluated per row.
        cursor.execute(
            """
            INSERT INTO accounting_event (id, tenant_id, company_id, event_type, event_version,
                source_module, source_document_type, source_document_id, occurred_at,
                accounting_date, idempotency_key, payload, capability_snapshot, status,
                posted_at, actor_user_id, request_id, created_at)
            SELECT gen_random_uuid(), app.current_tenant_id(), %(company)s, 'fixture.event', 1,
                   'manual', 'fixture', gen_random_uuid(), now(),
                   DATE '2026-01-01' + ((i * 364) / %(n)s)::int,
                   'volume-' || i, '{}', '{}', 'posted', now(), %(user)s, 'volume', now()
              FROM generate_series(1, %(n)s) AS i
            """,
            {"company": company, "n": documents, "user": user},
        )
        cursor.execute(
            """
            INSERT INTO journal_entry (id, tenant_id, company_id, entry_number, accounting_date,
                period_id, entry_type, accounting_event_id, status, posted_at, posted_by_user_id,
                description, total_debit, total_credit, request_id, rule_ref,
                fiscal_effective_date, created_at, updated_at)
            SELECT gen_random_uuid(), e.tenant_id, e.company_id, 'VOL-' || e.idempotency_key,
                   e.accounting_date, p.id, 'standard', e.id, 'posted', now(), %(user)s,
                   'Document de volum', 0, 0, 'volume', 'fixture.volume.v1',
                   e.accounting_date, now(), now()
              FROM accounting_event e
              JOIN period p ON p.company_id = e.company_id
                           AND e.accounting_date BETWEEN p.start_date AND p.end_date
             WHERE e.company_id = %(company)s AND e.request_id = 'volume'
            """,
            {"company": company, "user": user},
        )
        cursor.execute(
            """
            INSERT INTO journal_line (tenant_id, company_id, accounting_date, document_date,
                rate_date, journal_entry_id, line_number, account_id, debit, credit, currency,
                amount_currency, exchange_rate)
            SELECT j.tenant_id, j.company_id, j.accounting_date, j.accounting_date,
                   j.accounting_date, j.id, side.n, CASE WHEN side.n = 1 THEN %(busy)s
                        ELSE (%(credits)s::uuid[])[1 + (abs(hashtext(j.id::text)) %% 5)] END,
                   CASE WHEN side.n = 1 THEN 100 ELSE 0 END,
                   CASE WHEN side.n = 1 THEN 0 ELSE 100 END,
                   'MDL', 100, 1
              FROM journal_entry j, (VALUES (1), (2)) AS side(n)
             WHERE j.company_id = %(company)s AND j.request_id = 'volume'
            """,
            {"company": company, "busy": busy, "credits": credits},
        )
        cursor.execute(
            """
            INSERT INTO journal_formula (tenant_id, company_id, accounting_date, journal_entry_id,
                formula_number, debit_account_id, credit_account_id, amount, currency,
                amount_currency, exchange_rate, rate_date, document_date)
            SELECT j.tenant_id, j.company_id, j.accounting_date, j.id, 1, %(busy)s,
                   (%(credits)s::uuid[])[1 + (abs(hashtext(j.id::text)) %% 5)], 100, 'MDL', 100, 1,
                   j.accounting_date, j.accounting_date
              FROM journal_entry j
             WHERE j.company_id = %(company)s AND j.request_id = 'volume'
            """,
            {"company": company, "busy": busy, "credits": credits},
        )
        cursor.execute("ANALYZE journal_line")
        cursor.execute("ANALYZE journal_formula")
    return busy, credits


def _read_a_month(
    seed: Callable[..., None],
    tenant: uuid.UUID,
    company: uuid.UUID,
    user: uuid.UUID,
    context: TenantContext,
) -> tuple[uuid.UUID, AccountLedger, str, float]:
    """Seed the year, read March of the busy account, explain the query behind it."""
    with tenant_context(context):
        busy, _ = generate_ledger(seed, tenant, company, user, DOCUMENTS)

        started = time.perf_counter()
        ledger = account_ledger(company, busy, date(2026, 3, 1), date(2026, 3, 31))
        elapsed = time.perf_counter() - started

        with connection.cursor() as cursor:
            cursor.execute(
                """
                EXPLAIN (ANALYZE, FORMAT TEXT)
                SELECT journal_entry_id, sum(debit), sum(credit)
                  FROM journal_line
                 WHERE company_id = %s AND account_id = %s
                   AND accounting_date BETWEEN %s AND %s
                 GROUP BY journal_entry_id
                """,
                [company, busy, date(2026, 3, 1), date(2026, 3, 31)],
            )
            plan = "\n".join(row[0] for row in cursor.fetchall())
    return busy, ledger, plan, elapsed


def test_the_account_ledger_reads_a_month_through_its_index(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> None:
    tenant, user = world["tenant_a"], world["user_a"]
    company = company_of(tenant, "1002600009901", "Volum SRL")
    grant_company(tenant, company, user, user)
    context = TenantContext(tenant_id=tenant, user_id=user, request_id="volume")

    # The seeded lines live in this test's transaction and roll back at the end.
    # Autovacuum's own ANALYZE sees none of them -- committed, the table is empty
    # -- and if it lands between the ANALYZE in `generate_ledger` and the EXPLAIN,
    # the planner costs the query for an empty table and opens whichever index is
    # cheapest. Seen once in a full run after the corpus arrived (its rolled-back
    # postings make autovacuum visit `journal_line` more often). Off for the
    # window, back on after: the measurement is of the index, not of the race.
    seed("ALTER TABLE journal_line SET (autovacuum_enabled = false)")
    seed("ALTER TABLE journal_formula SET (autovacuum_enabled = false)")
    try:
        _, ledger, plan, elapsed = _read_a_month(seed, tenant, company, user, context)
    finally:
        seed("ALTER TABLE journal_line RESET (autovacuum_enabled)")
        seed("ALTER TABLE journal_formula RESET (autovacuum_enabled)")

    assert ledger.rows, "the busiest account has a month with no documents?"
    assert all(row.has_formulas for row in ledger.rows)
    assert ledger.closing == ledger.opening + ledger.total_debit - ledger.total_credit
    assert "journal_line_account_idx" in plan, f"the month is not read through its index\n{plan}"
    touched = max(
        (float(m) for m in re.findall(r"actual time=[\d.]+\.\.[\d.]+ rows=([\d.]+)", plan)),
        default=0.0,
    )
    print(
        f"\n  fișa contului: {len(ledger.rows)} documents in March of {DOCUMENTS:,}, "
        f"{elapsed * 1000:.1f}ms through the service under evidenta_app; "
        f"largest plan node read {touched:,.0f} rows"
    )
    if DOCUMENTS > DEFAULT_DOCUMENTS:
        assert elapsed <= PROPOSED_SECONDS, (
            f"ADR-053 §3.3 proposes {PROPOSED_SECONDS}s for one month of the busiest "
            f"account; measured {elapsed:.2f}s at {DOCUMENTS:,} documents"
        )
