"""Rebinding a role -- G2 of the gap plan, `R18`, `R28`, `C12`.

The panel said "no cash account is bound" and offered no door. This is the door,
and what is proved about it is mostly about time: a rebinding is **history, not
overwrite**. The binding in force is closed on the day the new one starts, so a
posting dated before that day keeps resolving to the account it was made with and
a posting dated on or after it reaches the new one. Nothing already posted moves
(`R10`) -- and that is asserted on the ledger, through the engine, not on the
binding table.

The refusals are the other half. A role outside the catalogue is a typo; an
account no posting may use is a binding that would fail later; an account of
another class moves a meaning the plan fixed; a start on or before the current
binding's start rewrites history. Each has a code (`C10`), and each is proved
over HTTP as well as at the service, because the code is what the screen reads.

**Under the application role, like every test in this suite** (`T1`). The HTTP
tests go through the real chain -- host, session, middleware -- and another
tenant's company answers 404 on both routes, never 403 (IZ-04).
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

import pytest
from django.test import Client

from evidenta.accounting.coa.models import CompanyAccount
from evidenta.accounting.ledger.models import JournalLine
from evidenta.accounting.posting.formula import RoleFormula, bind_roles
from evidenta.accounting.posting.invariants import Origin
from evidenta.accounting.posting.services.formulas import post_formulas
from evidenta.accounting.slots.models import AccountRoleBinding
from evidenta.accounting.slots.services.binding import (
    COMPANY_SOURCE,
    AccountClassMismatchError,
    RebindingBeforeCurrentError,
    RoleAccountNotPostableError,
    UnknownRoleError,
    install_default_bindings,
    rebind_role,
    resolve_role,
    role_overview,
)
from evidenta.platform.api.lookup import NotFoundError
from evidenta.platform.audit.models import AuditEvent
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.test_account_roles import scene  # noqa: F401
from tests.isolation.test_coa_api import HOST_A, mfa_key, signed_in  # noqa: F401
from tests.isolation.test_ledger import seed_period
from tests.isolation.test_manual_entry import seed_template as seed_numbering

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

#: The day the defaults are installed -- the same day `test_account_roles` uses.
INSTALLED = date(2026, 3, 15)
#: The day the company moves its till to its own analytic.
REBOUND = date(2026, 6, 1)

ROLE = "CASA_MDL"
#: The company's own analytic under the plan's 2411 -- level five, which is
#: where an entity's own accounts begin (the catalogue says so). Not a code of
#: the plan and not a claim about its content.
OWN_TILL = "24111"
OWN_TILL_BLOCKED = "24112"

BASE = "/api/v1/accounting/slots"
MDL = "MDL"


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="rebind")


def seed_account(
    seed: Callable[..., None],
    tenant: uuid.UUID,
    company: uuid.UUID,
    code: str,
    *,
    blocked: bool = False,
) -> uuid.UUID:
    account_id = uuid.uuid4()
    seed(
        "INSERT INTO company_account (id, tenant_id, company_id, account_code,"
        " parent_id, origin, template_account_id, name_ro, account_class,"
        " normal_balance, allows_subaccounts, currency_tracking, quantity_tracking,"
        " required_dimensions, is_blocked, valid_from, valid_to, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, NULL, 'company', NULL, %s, 'asset', 'debit',"
        " false, false, false, '{}'::text[], %s, '2020-01-01', NULL, now(), now())",
        [account_id, tenant, company, code, f"Casa proprie {code}", blocked],
    )
    return account_id


@pytest.fixture
def bound(
    seed: Callable[..., None],
    context: TenantContext,
    scene: dict[str, uuid.UUID],  # noqa: F811
) -> dict[str, uuid.UUID]:
    """The role-complete company of `test_account_roles`, bound, plus two accounts
    of its own under the till: one usable, one blocked."""
    with tenant_context(context):
        install_default_bindings(
            tenant_id=scene["tenant"], company_id=scene["company"], on_date=INSTALLED
        )
    return {
        **scene,
        "own_till": seed_account(seed, scene["tenant"], scene["company"], OWN_TILL),
        "blocked_till": seed_account(
            seed, scene["tenant"], scene["company"], OWN_TILL_BLOCKED, blocked=True
        ),
    }


def code_of(account_id: uuid.UUID) -> str:
    return str(CompanyAccount.objects.get(id=account_id).account_code)


def by_code(company: uuid.UUID, code: str) -> uuid.UUID:
    return uuid.UUID(str(CompanyAccount.objects.get(company_id=company, account_code=code).id))


# --- history, not overwrite ----------------------------------------------------


def test_a_rebinding_closes_the_old_binding_where_the_new_one_starts(
    context: TenantContext, bound: dict[str, uuid.UUID]
) -> None:
    """Two rows afterwards, meeting at one day, and the day belongs to the new one."""
    with tenant_context(context):
        new = rebind_role(
            company_id=bound["company"],
            role=ROLE,
            account_id=bound["own_till"],
            valid_from=REBOUND,
        )
        rows = list(
            AccountRoleBinding.objects.filter(company_id=bound["company"], role=ROLE).order_by(
                "valid_from"
            )
        )

        assert [row.id for row in rows] == [rows[0].id, new.id]
        assert rows[0].valid_from == INSTALLED
        assert rows[0].valid_to == REBOUND
        assert new.valid_from == REBOUND
        assert new.valid_to is None
        assert new.source == COMPANY_SOURCE

        assert code_of(resolve_role(bound["company"], ROLE, REBOUND - date.resolution)) == "2411"
        assert code_of(resolve_role(bound["company"], ROLE, REBOUND)) == OWN_TILL


def test_the_rebinding_is_audited_with_both_accounts(
    context: TenantContext, bound: dict[str, uuid.UUID]
) -> None:
    """Who moved the till, when, from what to what -- the question asked months
    later, when a cash report changed shape."""
    with tenant_context(context):
        new = rebind_role(
            company_id=bound["company"],
            role=ROLE,
            account_id=bound["own_till"],
            valid_from=REBOUND,
        )
        event = AuditEvent.objects.get(action="slots.role_rebound", entity_id=new.id)

        assert event.entity_type == "account_role_binding"
        assert event.company_id == bound["company"]
        assert event.old_value is not None
        assert event.old_value["account_code"] == "2411"
        assert event.new_value == {
            "role": ROLE,
            "account_id": str(bound["own_till"]),
            "account_code": OWN_TILL,
            "valid_from": REBOUND.isoformat(),
        }


def seed_event_on(
    seed: Callable[..., None],
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    user_id: uuid.UUID,
    on: date,
) -> uuid.UUID:
    """A pending event dated `on` -- `test_ledger.seed_event` fixes its date, and
    this test needs one on each side of the rebinding."""
    event_id = uuid.uuid4()
    seed(
        "INSERT INTO accounting_event (id, tenant_id, company_id, event_type, event_version,"
        " source_module, source_document_type, source_document_id, occurred_at,"
        " accounting_date, idempotency_key, payload, capability_snapshot, status,"
        " actor_user_id, request_id, created_at)"
        " VALUES (%s, %s, %s, 'fixture.event', 1, 'manual', 'fixture', %s, %s,"
        " %s, %s, '{}', '{}', 'pending', %s, 'rebind', now())",
        [
            event_id,
            tenant_id,
            company_id,
            uuid.uuid4(),
            datetime.now(UTC),
            on,
            f"key-{event_id}",
            user_id,
        ],
    )
    return event_id


def post_through_the_till(
    seed: Callable[..., None], bound: dict[str, uuid.UUID], on: date
) -> uuid.UUID:
    """One formula naming roles, bound at `on` and posted at `on` -- the way every
    handler reaches an account (ADR-036 section 5.1)."""
    event = seed_event_on(seed, bound["tenant"], bound["company"], bound["user"], on)
    formulas = bind_roles(
        bound["company"],
        on,
        [
            RoleFormula(
                debit_role=ROLE,
                credit_role="VENIT_SERVICII",
                amount=Decimal("100.0000"),
                currency=MDL,
                amount_currency=Decimal("100.0000"),
                exchange_rate=Decimal(1),
                rate_date=on,
                document_date=on,
            )
        ],
    )
    result = post_formulas(
        tenant_id=bound["tenant"],
        company_id=bound["company"],
        accounting_date=on,
        functional_currency=MDL,
        accounting_event_id=event,
        origin=Origin(module="manual", document_type="fixture", document_id=uuid.uuid4()),
        rule_ref="fixture.rebinding.v1",
        description="Incasare prin casa",
        request_id="rebind",
        actor_user_id=bound["user"],
        formulas=formulas,
    )
    return result.journal_entry_id


def debit_account_of(entry_id: uuid.UUID) -> uuid.UUID:
    line = JournalLine.objects.get(journal_entry_id=entry_id, debit__gt=0)
    return uuid.UUID(str(line.account_id))


def test_postings_after_the_date_reach_the_new_account_and_earlier_ones_stay(
    context: TenantContext, bound: dict[str, uuid.UUID], seed: Callable[..., None]
) -> None:
    """`C12`, and the criterion the gap plan names for G2.

    A receipt posted in May goes to 2411. The till is moved to the company's own
    analytic from 1 June. A receipt posted in June goes to the analytic -- and
    the May entry, re-read, still names 2411. The rebinding decided what a
    *future* resolution answers; it did not, and could not, touch a line
    already in the ledger.
    """
    year_id, _ = seed_period(
        seed, bound["tenant"], bound["company"], start="2026-05-01", end="2026-05-31", period_no=5
    )
    seed_period(
        seed,
        bound["tenant"],
        bound["company"],
        start="2026-06-01",
        end="2026-06-30",
        period_no=6,
        year_id=year_id,
    )
    seed_numbering(seed, bound["tenant"], bound["company"])

    with tenant_context(context):
        before = post_through_the_till(seed, bound, date(2026, 5, 20))
        assert debit_account_of(before) == by_code(bound["company"], "2411")

        rebind_role(
            company_id=bound["company"],
            role=ROLE,
            account_id=bound["own_till"],
            valid_from=REBOUND,
        )

        after = post_through_the_till(seed, bound, date(2026, 6, 10))
        assert debit_account_of(after) == bound["own_till"]

        # Re-read, not remembered: the May entry as the ledger holds it now.
        assert debit_account_of(before) == by_code(bound["company"], "2411")
        assert JournalLine.objects.filter(journal_entry_id=before).count() == 2


def test_an_unbound_role_can_be_bound_from_scratch(
    context: TenantContext,
    scene: dict[str, uuid.UUID],  # noqa: F811
    seed: Callable[..., None],
) -> None:
    """The panel's case: nothing bound, one role needed. No current binding to
    close, so any start date is history that begins here."""
    own = seed_account(seed, scene["tenant"], scene["company"], OWN_TILL)
    with tenant_context(context):
        assert AccountRoleBinding.objects.filter(company_id=scene["company"]).count() == 0
        rebind_role(company_id=scene["company"], role=ROLE, account_id=own, valid_from=INSTALLED)
        assert resolve_role(scene["company"], ROLE, INSTALLED) == own


def test_the_overview_names_the_plan_code_beside_an_empty_binding(
    context: TenantContext,
    scene: dict[str, uuid.UUID],  # noqa: F811
) -> None:
    """The screen exists for the empty row, so the empty row has to say what the
    plan would put there."""
    with tenant_context(context):
        rows = role_overview(scene["company"], INSTALLED)
        till = next(row for row in rows if row["role"] == ROLE)

    assert len(rows) == 53
    assert till["default_code"] == "2411"
    assert till["account_id"] is None
    assert till["account_code"] is None


# --- the refusals --------------------------------------------------------------


def test_an_unknown_role_is_a_typo(context: TenantContext, bound: dict[str, uuid.UUID]) -> None:
    with tenant_context(context), pytest.raises(UnknownRoleError) as refusal:
        rebind_role(
            company_id=bound["company"],
            role="CASA_MDL_",
            account_id=bound["own_till"],
            valid_from=REBOUND,
        )
    assert refusal.value.code == "slots.role_unknown"


def test_an_account_of_another_class_is_refused(
    context: TenantContext, bound: dict[str, uuid.UUID]
) -> None:
    """The till is class 2 in the plan. A company may not decide it is a
    liability -- the balance sheet is what gets read."""
    with tenant_context(context):
        liability = by_code(bound["company"], "5211")
        with pytest.raises(AccountClassMismatchError) as refusal:
            rebind_role(
                company_id=bound["company"], role=ROLE, account_id=liability, valid_from=REBOUND
            )
        assert refusal.value.code == "slots.account_class_mismatch"
        assert code_of(resolve_role(bound["company"], ROLE, REBOUND)) == "2411"


def test_a_blocked_account_is_refused(context: TenantContext, bound: dict[str, uuid.UUID]) -> None:
    """A binding to an account no posting may use fails at the first posting,
    on a day chosen by a transaction. Refused now instead."""
    with tenant_context(context), pytest.raises(RoleAccountNotPostableError) as refusal:
        rebind_role(
            company_id=bound["company"],
            role=ROLE,
            account_id=bound["blocked_till"],
            valid_from=REBOUND,
        )
    assert refusal.value.code == "slots.account_not_postable"


def test_an_account_that_does_not_exist_is_the_same_refusal(
    context: TenantContext, bound: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context), pytest.raises(RoleAccountNotPostableError):
        rebind_role(
            company_id=bound["company"], role=ROLE, account_id=uuid.uuid4(), valid_from=REBOUND
        )


@pytest.mark.parametrize("start", [INSTALLED, date(2026, 1, 1)])
def test_a_start_on_or_before_the_current_binding_is_refused(
    context: TenantContext, bound: dict[str, uuid.UUID], start: date
) -> None:
    """On the same day as well as before it: a same-day rebinding would leave two
    answers for that day's postings, and a CHECK refuses the closed row anyway."""
    with tenant_context(context):
        with pytest.raises(RebindingBeforeCurrentError) as refusal:
            rebind_role(
                company_id=bound["company"],
                role=ROLE,
                account_id=bound["own_till"],
                valid_from=start,
            )
        assert refusal.value.code == "slots.rebinding_before_current"
        bindings = AccountRoleBinding.objects.filter(company_id=bound["company"], role=ROLE)
        assert bindings.count() == 1


def test_another_tenants_company_is_not_found(
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
    seed: Callable[..., None],
) -> None:
    """IZ-04 at the service: a 404 that says nothing, and no row written."""
    other = company_of(world["tenant_b"], "1002600001003", "Beta Roluri")
    grant_company(world["tenant_b"], other, world["user_b"], world["user_b"])
    own = seed_account(seed, world["tenant_b"], other, OWN_TILL)

    context_a = TenantContext(
        tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="rebind-a"
    )
    with tenant_context(context_a), pytest.raises(NotFoundError):
        rebind_role(company_id=other, role=ROLE, account_id=own, valid_from=REBOUND)

    context_b = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="rebind-b"
    )
    with tenant_context(context_b):
        assert AccountRoleBinding.objects.filter(company_id=other).count() == 0


# --- over HTTP -----------------------------------------------------------------


def get(client: Client, path: str) -> Any:
    return client.get(path, headers={"host": HOST_A})


def put(client: Client, path: str, body: dict[str, Any]) -> Any:
    return client.put(
        path,
        data=json.dumps(body, default=str),
        content_type="application/json",
        headers={"host": HOST_A},
    )


def test_the_overview_reads_over_http_with_the_plan_code_and_the_account(
    signed_in: Client,  # noqa: F811
    bound: dict[str, uuid.UUID],
) -> None:
    response = get(signed_in, f"{BASE}/companies/{bound['company']}/role-bindings?on={INSTALLED}")
    assert response.status_code == 200, response.content
    rows = response.json()
    till = next(row for row in rows if row["role"] == ROLE)

    assert len(rows) == 53
    assert till["default_code"] == "2411"
    assert till["account_code"] == "2411"
    assert till["name_ro"] == "Cont 2411"
    assert till["valid_from"] == INSTALLED.isoformat()
    assert till["source"]


def test_a_rebinding_over_http_changes_what_a_later_date_reads(
    signed_in: Client,  # noqa: F811
    bound: dict[str, uuid.UUID],
) -> None:
    response = put(
        signed_in,
        f"{BASE}/companies/{bound['company']}/role-bindings/{ROLE}",
        {"account_id": str(bound["own_till"]), "valid_from": REBOUND.isoformat()},
    )
    assert response.status_code == 200, response.content
    body = response.json()
    assert body["account_code"] == OWN_TILL
    assert body["valid_from"] == REBOUND.isoformat()
    assert body["valid_to"] is None
    assert body["source"] == COMPANY_SOURCE

    day_before = (REBOUND - date.resolution).isoformat()
    before = get(signed_in, f"{BASE}/companies/{bound['company']}/role-bindings?on={day_before}")
    after = get(signed_in, f"{BASE}/companies/{bound['company']}/role-bindings?on={REBOUND}")
    assert next(r for r in before.json() if r["role"] == ROLE)["account_code"] == "2411"
    assert next(r for r in after.json() if r["role"] == ROLE)["account_code"] == OWN_TILL


@pytest.mark.parametrize(
    ("role", "account", "start", "status", "code"),
    [
        ("CASA_MDL_", "own_till", REBOUND, 422, "slots.role_unknown"),
        ("CASA_MDL", "blocked_till", REBOUND, 409, "slots.account_not_postable"),
        ("CASA_MDL", "own_till", INSTALLED, 409, "slots.rebinding_before_current"),
    ],
)
def test_the_refusals_travel_with_their_codes(
    signed_in: Client,  # noqa: F811
    bound: dict[str, uuid.UUID],
    role: str,
    account: str,
    start: date,
    status: int,
    code: str,
) -> None:
    response = put(
        signed_in,
        f"{BASE}/companies/{bound['company']}/role-bindings/{role}",
        {"account_id": str(bound[account]), "valid_from": start.isoformat()},
    )
    assert response.status_code == status, response.content
    assert response.json()["code"] == code


def test_a_class_mismatch_travels_with_its_code(
    signed_in: Client,  # noqa: F811
    context: TenantContext,
    bound: dict[str, uuid.UUID],
) -> None:
    with tenant_context(context):
        liability = by_code(bound["company"], "5211")
    response = put(
        signed_in,
        f"{BASE}/companies/{bound['company']}/role-bindings/{ROLE}",
        {"account_id": str(liability), "valid_from": REBOUND.isoformat()},
    )
    assert response.status_code == 409, response.content
    assert response.json()["code"] == "slots.account_class_mismatch"


def test_a_bad_date_is_a_code_not_a_field_error(
    signed_in: Client,  # noqa: F811
    bound: dict[str, uuid.UUID],
) -> None:
    response = get(signed_in, f"{BASE}/companies/{bound['company']}/role-bindings?on=yesterday")
    assert response.status_code == 400
    assert response.json()["code"] == "slots.invalid_date"


def test_another_tenants_company_answers_404_on_both_routes(
    signed_in: Client,  # noqa: F811
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
    seed: Callable[..., None],
) -> None:
    """IZ-04 over HTTP: the read and the write, and neither says the company exists."""
    other = company_of(world["tenant_b"], "1002600001004", "Beta Roluri HTTP")
    grant_company(world["tenant_b"], other, world["user_b"], world["user_b"])
    own = seed_account(seed, world["tenant_b"], other, OWN_TILL)

    read = get(signed_in, f"{BASE}/companies/{other}/role-bindings?on={INSTALLED}")
    assert read.status_code == 404, read.content
    assert read.json()["code"] == "api.not_found"

    write = put(
        signed_in,
        f"{BASE}/companies/{other}/role-bindings/{ROLE}",
        {"account_id": str(own), "valid_from": REBOUND.isoformat()},
    )
    assert write.status_code == 404, write.content
    assert write.json()["code"] == "api.not_found"

    context_b = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="rebind-b"
    )
    with tenant_context(context_b):
        assert AccountRoleBinding.objects.filter(company_id=other).count() == 0
