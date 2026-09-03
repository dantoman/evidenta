"""Who may call into schema `rls` -- ADR-043, R5.

The defect this guards against did not look like a defect. Every migration that
creates a function in `rls` writes `REVOKE ALL ... FROM PUBLIC` after it, and
every one of those REVOKEs did nothing: the functions belong to `evidenta_rls`
(they are created under `SET LOCAL ROLE`), the REVOKE was issued afterwards by
`evidenta_owner`, and **a REVOKE from a non-owner is a WARNING, not an error**.
The SQL ran, the migration passed, and 23 of 25 functions -- including every
pre-context `auth_*` path and both engagement access paths -- stayed callable by
PUBLIC.

Nothing could have caught it: the schema guard checks tables and policies, the
suite rebuilds the database from scratch and so reproduces the same wrong state
faithfully every run. Hence this file, which asks the catalogue directly.

The second test is the one that matters in a year: the grant list is **declared
here**, so widening it is an edit somebody reads, not a side effect of adding a
function.

**This file is also the prevention, not only the check.** The obvious mechanism --
`ALTER DEFAULT PRIVILEGES ... REVOKE EXECUTE ON FUNCTIONS FROM PUBLIC` -- was
tried and measured, in both the bare form and the one that grants explicitly to
`evidenta_rls`, inside one transaction and across a commit. A function created
afterwards still comes out with the implicit ACL, PUBLIC included. So the
repair cannot defend itself in the schema; it is defended here, on a database
built from scratch every run.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from django.db import connections

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

#: Exactly what `evidenta_app` may execute in schema `rls`, and why. Derived by
#: measurement, not judgement: the functions called from Python
#: (`grep -r 'rls\.' backend/evidenta/`) united with those appearing in policy
#: expressions (`pg_policy`), because a policy is evaluated as the querying user.
#:
#: Adding a name here is a deliberate act. Everything absent is either a trigger
#: function -- PostgreSQL checks EXECUTE at CREATE TRIGGER, not at fire time, so
#: revoking costs nothing -- or an internal helper of another `rls` function,
#: which runs as `evidenta_rls` and needs no grant.
GRANTED_TO_APP = frozenset(
    {
        # Access predicates, named inside policies (R5).
        "has_tenant_access",
        "has_company_access",
        "can_see_engagement",
        # The path that precedes tenant context (ADR-026).
        "auth_lookup_user",
        "auth_mfa_methods",
        "auth_backup_codes",
        "auth_spend_backup_code",
        "resolve_session",
        "resolve_tenant_by_subdomain",
        # Privileged paths enumerated in Spec A section 6.2.
        "provision_engagement_company_access",
        # `P-9` (ADR-040): the application role cannot insert a company at all --
        # the policy wants an access row that wants the company.
        "provision_company",
        "revoke_engagement_company_access",
        # Notification dispatch, which runs with no user identity (OD-50).
        "create_notification",
        "create_notification_delivery",
        "notify_tenant_members",
        # The console's metadata reads (ADR-076 §4.3, ADR-092, Spec A §14):
        # staff-gated inside, refused under a tenant context. `console_caller_role`
        # is their internal guard and is deliberately absent -- it runs as
        # evidenta_rls from within the others.
        "console_tenants",
        "console_staff",
        "console_user_by_email",
        "console_privileged_log",
        "console_capabilities",
        "console_release_rings",
        "console_flag_overrides",
    }
)


@pytest.fixture
def cursor() -> Iterator[object]:
    """Read the catalogue through the migration connection, which owns nothing
    but may read `pg_proc` -- the application connection would be refused by the
    query guard for a query that touches no tenant data."""
    with connections["migration"].cursor() as handle:
        yield handle


def acl_rows(cursor: object) -> list[tuple[str, list[str]]]:
    cursor.execute(  # type: ignore[attr-defined]
        """
        SELECT p.proname,
               coalesce(array_agg(a.grantee ORDER BY a.grantee)
                        FILTER (WHERE a.grantee IS NOT NULL), '{}')
          FROM pg_proc p
          JOIN pg_namespace n ON n.oid = p.pronamespace
          LEFT JOIN LATERAL (
              SELECT split_part(item::text, '=', 1) AS grantee
                FROM unnest(coalesce(p.proacl, '{}')) AS item
          ) a ON true
         WHERE n.nspname = 'rls'
         GROUP BY p.proname
         ORDER BY p.proname
        """
    )
    return [(name, list(grantees)) for name, grantees in cursor.fetchall()]  # type: ignore[attr-defined]


def test_no_function_in_rls_is_executable_by_public(cursor: object) -> None:
    """An empty grantee in an ACL entry means PUBLIC.

    PUBLIC includes every role the cluster will ever have -- the application role
    today, and any reporting or read-only role somebody adds later without
    thinking about `rls` at all.
    """
    public = [name for name, grantees in acl_rows(cursor) if "" in grantees]
    assert public == [], (
        f"{len(public)} function(s) in schema rls are executable by PUBLIC: "
        f"{', '.join(public)}. A REVOKE issued by anyone other than the owner is "
        f"a warning, not an error -- issue it under SET LOCAL ROLE evidenta_rls."
    )


def test_the_application_may_execute_exactly_the_declared_set(cursor: object) -> None:
    """Both directions fail, and the second is the one that matters.

    An extra grant means a privileged path reachable from the application that
    nobody decided to expose. A missing one means the product is broken and the
    rest of the suite says so loudly -- so this half is really about the first.
    """
    granted = {name for name, grantees in acl_rows(cursor) if "evidenta_app" in grantees}
    assert granted == GRANTED_TO_APP, (
        f"granted but not declared: {sorted(granted - GRANTED_TO_APP)}; "
        f"declared but not granted: {sorted(GRANTED_TO_APP - granted)}"
    )


def test_the_guard_can_fail(cursor: object) -> None:
    """A guard nobody has seen refuse is a guard nobody knows the shape of.

    Grants PUBLIC back on one function, inside the test transaction, and checks
    that the first test would have caught it.
    """
    cursor.execute("SET LOCAL ROLE evidenta_rls")  # type: ignore[attr-defined]
    cursor.execute(  # type: ignore[attr-defined]
        "GRANT EXECUTE ON FUNCTION rls.has_tenant_access(uuid) TO PUBLIC"
    )
    cursor.execute("RESET ROLE")  # type: ignore[attr-defined]

    public = [name for name, grantees in acl_rows(cursor) if "" in grantees]
    assert public == ["has_tenant_access"]
