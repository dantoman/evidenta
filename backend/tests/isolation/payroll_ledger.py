"""The ledger a payroll run needs once approval posts -- shared by the payroll tests.

Since the payroll posting, `approve()` emits `payroll.run_approved` and the engine
writes the entry in the same transaction. A test that approves a run therefore
needs what the engine needs: an open month for the accrual date, a numbering
template for the entry, the amount scale, one account per catalogue code, and the
roles bound through the real installer -- which is also what declares the
`employee` slot (ADR-065 section 8.4). Seeded here once, so three files do not
carry three drifting copies.

Not seeded here: the rounding direction. The payroll files insert their own
`accounting.money_rounding` version and the overlap EXCLUDE refuses a second.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date

from evidenta.accounting.slots.catalogue import DEFAULTS
from evidenta.accounting.slots.services.binding import install_default_bindings
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.test_ledger import seed_period
from tests.isolation.test_manual_entry import seed_template as seed_numbering

#: The fictitious act every convention row here stands on -- the same id
#: `test_line_rounding.source` uses, so the two can coexist in one test.
SCALE_SOURCE_ID = uuid.UUID("00000000-0000-0000-0000-00000000c0de")


def plan_account(
    seed: Callable[..., None], tenant: uuid.UUID, company: uuid.UUID, code: str
) -> uuid.UUID:
    """A company account carrying the plan's code, with no slot declared.

    No slot on purpose: the claim under test elsewhere is that the catalogue
    declares it when the roles are bound, so a fixture that declared it would
    prove nothing.
    """
    account_id = uuid.uuid4()
    liability = code.startswith("5")
    account_class, balance = ("liability", "credit") if liability else ("expense", "debit")
    seed(
        "INSERT INTO company_account (id, tenant_id, company_id, account_code,"
        " parent_id, origin, template_account_id, name_ro, account_class,"
        " normal_balance, allows_subaccounts, currency_tracking, quantity_tracking,"
        " required_dimensions, is_blocked, valid_from, valid_to, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, NULL, 'company', NULL, %s, %s, %s,"
        " false, false, false, '{}'::text[], false, '2020-01-01', NULL, now(), now())",
        [account_id, tenant, company, code, f"Cont {code}", account_class, balance],
    )
    return account_id


def seed_ledger_for_payroll(
    seed: Callable[..., None],
    *,
    tenant: uuid.UUID,
    company: uuid.UUID,
    user: uuid.UUID,
    period_start: str = "2026-03-01",
    period_end: str = "2026-03-31",
    period_no: int = 3,
) -> dict[str, uuid.UUID]:
    """Everything the posting engine asks of a company, for one open month.

    Returns the accounts by plan code, so a chain assertion can name them.
    """
    seed_period(seed, tenant, company, start=period_start, end=period_end, period_no=period_no)
    seed_numbering(seed, tenant, company)
    seed(
        "INSERT INTO fiscal_parameter_source (id, act_type, act_number, act_date,"
        " effective_from, created_at)"
        " VALUES (%s, 'test', 'X-SCALE', '2019-12-31', '2020-01-01', now())"
        " ON CONFLICT (id) DO NOTHING",
        [SCALE_SOURCE_ID],
    )
    seed(
        "INSERT INTO fiscal_parameter (id, parameter_key, scope, value_type, value,"
        " valid_from, margin_basis, margin_reference, source_id, status,"
        " approved_by_user_id, approved_at, source_confidence, created_at, updated_at)"
        " VALUES (%s, 'accounting.amount_scale', 'global', 'integer', '2'::jsonb,"
        " DATE '2020-01-01', 'platform_convention', 'ADR-037 §3.2', %s,"
        " 'active', %s, now(), 'confirmed', now(), now())",
        [uuid.uuid4(), SCALE_SOURCE_ID, user],
    )
    # Every code the catalogue names, so the installer binds every role: it
    # refuses a chart with a code missing rather than binding what it can.
    codes = sorted({default.account_code for default in DEFAULTS})
    accounts = {code: plan_account(seed, tenant, company, code) for code in codes}
    context = TenantContext(tenant_id=tenant, user_id=user, request_id="payroll-ledger")
    with tenant_context(context):
        install_default_bindings(tenant_id=tenant, company_id=company, on_date=date(2026, 1, 1))
    return accounts
