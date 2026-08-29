"""The reference-data role -- ADR-049, closes OD-67.

Four claims, each measured against the catalogue or by trying:

1. **The role is narrow.** No BYPASSRLS, no superuser, no membership in
   `evidenta_rls` or `evidenta_owner`, no table owned. Read from `pg_roles`, not
   from the bootstrap file: the file says what was intended, the catalogue says
   what happened.
2. **It writes reference tables and nothing else.** An INSERT into a global
   reference table succeeds; the same INSERT from the application role is
   refused; a SELECT on `company` or an INSERT into `journal_entry` under the
   role is a permission error, not an empty result -- there is no policy to make
   it empty, because there is no privilege to reach the policy.
3. **It cannot delete.** Reference data is versioned; the privilege is not
   granted, so the refusal happens before any policy.
4. **Every run leaves exactly one audit row, or none.** `privileged_run` writes
   `privileged_access_log` in the same transaction: a run that raises leaves no
   row claiming it happened. The row is invisible to the application role, and
   nobody can rewrite it -- the test administrator, which bypasses RLS, is
   refused by the trigger.

No real act, rate or account number appears here (`OD-22` is open); the acts are
fictitious and dated so, for the same reason as in `test_fiscal.py`.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Iterator
from datetime import UTC, date, datetime

import psycopg.errors
import pytest
from django.db import connections, transaction
from django.db.utils import ProgrammingError

from evidenta.platform.audit.models import PrivilegedAccessLog, PrivilegedPath
from evidenta.platform.audit.services.privileged import REFDATA_ALIAS, privileged_run
from evidenta.platform.legislation.models import NormativeAct, NormativeActPublication
from evidenta.platform.legislation.services.registry import Act, Publication, register_act
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration", "refdata"])

ROLE = "evidenta_refdata"


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="refdata")


@pytest.fixture
def refdata() -> Iterator[object]:
    with connections[REFDATA_ALIAS].cursor() as cursor:
        yield cursor


@pytest.fixture
def catalogue() -> Iterator[object]:
    """`pg_roles` and friends, read through the owner: the refdata connection
    could read them too, but the claim is about the role, not made by it."""
    with connections["migration"].cursor() as cursor:
        yield cursor


def _fictitious_act(suffix: str) -> Act:
    return Act(
        act_type="test",
        act_number=f"TEST-{suffix}/0000",
        act_date=date(2000, 1, 1),
        title=f"Act de test {suffix}",
        publications=(Publication(2000, "TEST 0", f"art. {suffix}"),),
    )


# --- 1. the role is narrow -----------------------------------------------------


def test_the_role_is_narrow(catalogue: object) -> None:
    catalogue.execute(  # type: ignore[attr-defined]
        """
        SELECT rolsuper, rolbypassrls, rolcreaterole, rolcreatedb, rolcanlogin,
               pg_has_role(rolname, 'evidenta_rls', 'USAGE'),
               pg_has_role(rolname, 'evidenta_owner', 'USAGE'),
               (SELECT count(*) FROM pg_class c JOIN pg_roles o ON o.oid = c.relowner
                 WHERE o.rolname = r.rolname AND c.relkind IN ('r', 'p')),
               has_schema_privilege(rolname, 'public', 'CREATE')
          FROM pg_roles r WHERE rolname = %s
        """,
        [ROLE],
    )
    row = catalogue.fetchone()  # type: ignore[attr-defined]
    assert row is not None, f"{ROLE} does not exist: 0004_refdata_role.sql did not run"
    (
        is_super,
        bypasses,
        can_create_role,
        can_create_db,
        can_login,
        in_rls,
        in_owner,
        owned,
        creates,
    ) = row
    assert not is_super
    assert not bypasses, "BYPASSRLS on the loading role would make every policy decorative for it"
    assert not can_create_role and not can_create_db
    assert can_login, "the loaders connect as it"
    assert not in_rls and not in_owner
    assert owned == 0, (
        "a role that owns a table has every privilege on it, and FORCE RLS is all that holds"
    )
    assert not creates


# --- 2. writes reference tables, and nothing else -------------------------------


def test_the_role_writes_a_reference_table(refdata: object) -> None:
    act = register_act(_fictitious_act("write"), using=REFDATA_ALIAS)
    assert NormativeAct.objects.using(REFDATA_ALIAS).filter(pk=act.pk).exists()
    assert NormativeActPublication.objects.using(REFDATA_ALIAS).filter(act=act).count() == 1


def test_registering_twice_records_once(refdata: object) -> None:
    first = register_act(_fictitious_act("twice"), using=REFDATA_ALIAS)
    second = register_act(_fictitious_act("twice"), using=REFDATA_ALIAS)
    assert first.pk == second.pk
    assert NormativeActPublication.objects.using(REFDATA_ALIAS).filter(act=first).count() == 1


def test_one_publication_is_shared_by_two_acts(refdata: object) -> None:
    """The fact that killed 'one more pair of columns' (OD-65)."""
    shared = Publication(2000, "TEST 1", "art. shared", published_at=date(2000, 1, 2))
    one = register_act(
        Act("test", "TEST-A/0000", date(2000, 1, 1), "A", publications=(shared,)),
        using=REFDATA_ALIAS,
    )
    two = register_act(
        Act("test", "TEST-B/0000", date(2000, 1, 1), "B", publications=(shared,)),
        using=REFDATA_ALIAS,
    )
    positions = {
        link.publication_id
        for link in NormativeActPublication.objects.using(REFDATA_ALIAS).filter(act__in=[one, two])
    }
    assert len(positions) == 1


def test_the_application_role_cannot_write_a_reference_table(context: TenantContext) -> None:
    """The privilege, not the policy: 0059 revokes it explicitly (OD-47)."""
    with tenant_context(context), pytest.raises(ProgrammingError), transaction.atomic():
        NormativeAct.objects.create(
            act_type="test", act_number="TEST-APP/0000", act_date=date(2000, 1, 1), title="x"
        )


@pytest.mark.parametrize(
    "statement",
    [
        "SELECT count(*) FROM company",
        "SELECT count(*) FROM tenant",
        "SELECT count(*) FROM journal_entry",
        "INSERT INTO company_dimension (id) VALUES (gen_random_uuid())",
    ],
)
def test_the_role_reaches_no_tenant_table(refdata: object, statement: str) -> None:
    """Permission denied -- not zero rows. A policy would make it empty; there is
    no privilege to reach a policy, which is the stronger refusal."""
    with pytest.raises(ProgrammingError) as excinfo, transaction.atomic(using=REFDATA_ALIAS):
        refdata.execute(statement)  # type: ignore[attr-defined]
    assert isinstance(excinfo.value.__cause__, psycopg.errors.InsufficientPrivilege)


# --- 3. no DELETE ----------------------------------------------------------------


def test_the_role_cannot_delete_reference_rows(refdata: object) -> None:
    act = register_act(_fictitious_act("keep"), using=REFDATA_ALIAS)
    with pytest.raises(ProgrammingError) as excinfo, transaction.atomic(using=REFDATA_ALIAS):
        refdata.execute("DELETE FROM normative_act WHERE id = %s", [act.pk])  # type: ignore[attr-defined]
    assert isinstance(excinfo.value.__cause__, psycopg.errors.InsufficientPrivilege)


# --- 4. one audit row per run, or none ------------------------------------------


def _log_rows(request_id: str) -> list[PrivilegedAccessLog]:
    return list(PrivilegedAccessLog.objects.using(REFDATA_ALIAS).filter(request_id=request_id))


def test_a_run_leaves_exactly_one_row(refdata: object) -> None:
    request_id = f"test:{uuid.uuid4()}"
    with privileged_run(
        PrivilegedPath.P4_FISCAL_RULES, actor="test:suite", request_id=request_id
    ) as run:
        register_act(_fictitious_act("logged"), using=REFDATA_ALIAS)
        run.payload["acts"] = 1

    rows = _log_rows(request_id)
    assert len(rows) == 1
    (row,) = rows
    assert row.path_code == "P-4"
    assert row.actor == "test:suite"
    assert row.payload == {"acts": 1}
    assert row.occurred_at <= datetime.now(tz=UTC)


def test_a_failed_run_leaves_no_row(refdata: object) -> None:
    request_id = f"test:{uuid.uuid4()}"
    with (
        pytest.raises(RuntimeError),
        privileged_run(PrivilegedPath.P4_FISCAL_RULES, actor="test:suite", request_id=request_id),
    ):
        register_act(_fictitious_act("aborted"), using=REFDATA_ALIAS)
        raise RuntimeError("the load blew up half way")

    assert _log_rows(request_id) == []
    assert (
        not NormativeAct.objects.using(REFDATA_ALIAS)
        .filter(act_number="TEST-aborted/0000")
        .exists()
    )


def test_an_unknown_path_is_refused_before_anything_runs() -> None:
    with pytest.raises(ValueError, match="not a privileged path"), privileged_run("P-99"):
        raise AssertionError("the body must not run")


def test_a_run_on_the_application_connection_is_refused(context: TenantContext) -> None:
    """`using` exists so this can be shown, not so it can be done."""
    with (
        tenant_context(context),
        pytest.raises(ProgrammingError),
        privileged_run(PrivilegedPath.P4_FISCAL_RULES, actor="test:suite", using="default"),
    ):
        pass


def test_the_application_role_cannot_read_the_log(context: TenantContext) -> None:
    """The log names tenants other than the caller's; reading it is a
    cross-tenant query outside the read-model layer (R7)."""
    with tenant_context(context), pytest.raises(ProgrammingError), transaction.atomic():
        list(PrivilegedAccessLog.objects.all()[:1])


def test_the_log_refuses_rewrite_even_for_the_administrator(
    seed: Callable[..., None],
) -> None:
    """Append-only by trigger, so it holds against a role that bypasses RLS."""
    request_id = f"test:{uuid.uuid4()}"
    seed(
        """
        INSERT INTO privileged_access_log
            (occurred_at, path_code, actor, request_id)
        VALUES (now(), 'P-4', 'test:admin', %s)
        """,
        [request_id],
    )
    with pytest.raises(Exception) as excinfo:
        seed(
            "UPDATE privileged_access_log SET actor = 'rewritten' WHERE request_id = %s",
            [request_id],
        )
    assert "append-only" in str(excinfo.value)
    with pytest.raises(Exception) as excinfo:
        seed("DELETE FROM privileged_access_log WHERE request_id = %s", [request_id])
    assert "append-only" in str(excinfo.value)
