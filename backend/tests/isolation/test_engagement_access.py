"""The second access path: a firm acting under an engagement.

These are the cases T2 calls mandatory and easy to forget -- expired, revoked,
suspended, not yet accepted, borrowed firm identity. Each one has a way of
looking like it works.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from django.db import connection

from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


def acting_for_firm(tenant_id: uuid.UUID, user_id: uuid.UUID, firm_id: uuid.UUID) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id, user_id=user_id, request_id="test", actor_firm_id=firm_id
    )


def visible_tenants() -> list[str]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT subdomain FROM tenant")
        return [row[0] for row in cursor.fetchall()]


def test_active_engagement_grants_access(
    firm_world: dict[str, uuid.UUID], engage: Callable[..., uuid.UUID]
) -> None:
    """IZ-10."""
    engage(firm_world["firm"], firm_world["tenant_b"], firm_world["user_f"])
    with tenant_context(
        acting_for_firm(firm_world["tenant_b"], firm_world["user_f"], firm_world["firm"])
    ):
        assert visible_tenants() == ["beta"]


def test_expired_engagement_grants_nothing(
    firm_world: dict[str, uuid.UUID], engage: Callable[..., uuid.UUID]
) -> None:
    """IZ-11 -- and no job has run.

    ``status`` is still 'active'; only ``valid_to`` has passed. Access stops
    because the predicate evaluates the dates, not because a scheduler moved the
    row to 'expired'. A job that fails to run must not leave access open.
    """
    engage(
        firm_world["firm"],
        firm_world["tenant_b"],
        firm_world["user_f"],
        valid_to="2024-01-01",
    )
    with tenant_context(
        acting_for_firm(firm_world["tenant_b"], firm_world["user_f"], firm_world["firm"])
    ):
        assert visible_tenants() == []


def test_future_engagement_grants_nothing(
    firm_world: dict[str, uuid.UUID], engage: Callable[..., uuid.UUID]
) -> None:
    """IZ-15. Signed, accepted, and not yet in force."""
    engage(
        firm_world["firm"],
        firm_world["tenant_b"],
        firm_world["user_f"],
        valid_from="2099-01-01",
    )
    with tenant_context(
        acting_for_firm(firm_world["tenant_b"], firm_world["user_f"], firm_world["firm"])
    ):
        assert visible_tenants() == []


@pytest.mark.parametrize("status", ["revoked", "suspended", "invited"])
def test_only_active_engagements_grant_access(
    firm_world: dict[str, uuid.UUID], engage: Callable[..., uuid.UUID], status: str
) -> None:
    """IZ-12, IZ-13, IZ-14 -- revoked, suspended, and never accepted."""
    engage(
        firm_world["firm"],
        firm_world["tenant_b"],
        firm_world["user_f"],
        status=status,
    )
    with tenant_context(
        acting_for_firm(firm_world["tenant_b"], firm_world["user_f"], firm_world["firm"])
    ):
        assert visible_tenants() == []


def test_engagement_over_another_tenant_grants_nothing(
    firm_world: dict[str, uuid.UUID], engage: Callable[..., uuid.UUID]
) -> None:
    """IZ-17. The firm holds an engagement -- over someone else."""
    engage(firm_world["firm"], firm_world["tenant_b"], firm_world["user_f"])
    with tenant_context(
        acting_for_firm(firm_world["tenant_a"], firm_world["user_f"], firm_world["firm"])
    ):
        assert visible_tenants() == []


def test_borrowing_a_firm_identity_grants_nothing(
    firm_world: dict[str, uuid.UUID], engage: Callable[..., uuid.UUID]
) -> None:
    """IZ-18. Setting a session variable is not becoming a firm.

    The predicate checks that the caller is an active member of the firm's own
    tenant. Without that check, anyone could claim to act for any firm by setting
    one GUC -- and the session variable is set by the application, which is the
    thing RLS is meant to be independent of.
    """
    engage(firm_world["firm"], firm_world["tenant_b"], firm_world["user_f"])
    with tenant_context(
        acting_for_firm(firm_world["tenant_b"], firm_world["user_a"], firm_world["firm"])
    ):
        assert visible_tenants() == []


def test_client_can_see_the_firm_holding_its_engagement(
    firm_world: dict[str, uuid.UUID], engage: Callable[..., uuid.UUID]
) -> None:
    """Both parties see the relationship -- the client must be able to answer
    "who keeps my books"."""
    engage(firm_world["firm"], firm_world["tenant_b"], firm_world["user_f"])
    with (
        tenant_context(
            TenantContext(
                tenant_id=firm_world["tenant_b"],
                user_id=firm_world["user_b"],
                request_id="test",
            )
        ),
        connection.cursor() as cursor,
    ):
        cursor.execute("SELECT count(*) FROM engagement")
        assert cursor.fetchone()[0] == 1


def test_two_firms_cannot_both_claim_a_module(
    firm_world: dict[str, uuid.UUID],
    engage: Callable[..., uuid.UUID],
    seed: Callable[..., None],
) -> None:
    """ADR-018: at most one live engagement per tenant may claim a module.

    Enforced by a partial unique index, not by a service check. A service check
    would be bypassed by the first bulk import or the first concurrent write, and
    the result would be two firms with access to the same salaries.
    """
    second_firm_tenant, second_firm = uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    seed(
        "INSERT INTO tenant (id, subdomain, legal_name, status, default_locale,"
        " created_at, updated_at)"
        " VALUES (%s, 'altafirma', 'Alta Firma SRL', 'active', 'ro', %s, %s)",
        [second_firm_tenant, now, now],
    )
    seed(
        "INSERT INTO firm (id, tenant_id, name, status, created_at, updated_at)"
        " VALUES (%s, %s, 'Alta Firma', 'active', %s, %s)",
        [second_firm, second_firm_tenant, now, now],
    )

    first = engage(firm_world["firm"], firm_world["tenant_b"], firm_world["user_f"])
    second = engage(second_firm, firm_world["tenant_b"], firm_world["user_f"])

    seed(
        "INSERT INTO engagement_module_scope (id, engagement_id, module_key,"
        " permission_level, client_tenant_id, is_live)"
        " VALUES (%s, %s, 'payroll', 'write', %s, true)",
        [uuid.uuid4(), first, firm_world["tenant_b"]],
    )
    with pytest.raises(Exception, match="engagement_module_scope_no_overlap"):
        seed(
            "INSERT INTO engagement_module_scope (id, engagement_id, module_key,"
            " permission_level, client_tenant_id, is_live)"
            " VALUES (%s, %s, 'payroll', 'write', %s, true)",
            [uuid.uuid4(), second, firm_world["tenant_b"]],
        )


def test_two_firms_may_hold_different_modules(
    firm_world: dict[str, uuid.UUID],
    engage: Callable[..., uuid.UUID],
    seed: Callable[..., None],
) -> None:
    """The point of ADR-018: one firm keeps the books, another runs payroll."""
    second_firm_tenant, second_firm = uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    seed(
        "INSERT INTO tenant (id, subdomain, legal_name, status, default_locale,"
        " created_at, updated_at)"
        " VALUES (%s, 'altafirma2', 'Alta Firma SRL', 'active', 'ro', %s, %s)",
        [second_firm_tenant, now, now],
    )
    seed(
        "INSERT INTO firm (id, tenant_id, name, status, created_at, updated_at)"
        " VALUES (%s, %s, 'Alta Firma', 'active', %s, %s)",
        [second_firm, second_firm_tenant, now, now],
    )
    first = engage(firm_world["firm"], firm_world["tenant_b"], firm_world["user_f"])
    second = engage(second_firm, firm_world["tenant_b"], firm_world["user_f"])

    for engagement_id, module in ((first, "accounting"), (second, "payroll")):
        seed(
            "INSERT INTO engagement_module_scope (id, engagement_id, module_key,"
            " permission_level, client_tenant_id, is_live)"
            " VALUES (%s, %s, %s, 'write', %s, true)",
            [uuid.uuid4(), engagement_id, module, firm_world["tenant_b"]],
        )


def test_an_unknown_module_key_is_refused(
    firm_world: dict[str, uuid.UUID],
    engage: Callable[..., uuid.UUID],
    seed: Callable[..., None],
) -> None:
    """ADR-019: a key written freely would produce a scope that refuses nothing."""
    engagement_id = engage(firm_world["firm"], firm_world["tenant_b"], firm_world["user_f"])
    with pytest.raises(Exception, match="engagement_module_scope_key_valid"):
        seed(
            "INSERT INTO engagement_module_scope (id, engagement_id, module_key,"
            " permission_level, client_tenant_id, is_live)"
            " VALUES (%s, %s, 'salarii', 'write', %s, true)",
            [uuid.uuid4(), engagement_id, firm_world["tenant_b"]],
        )


def test_revoking_an_engagement_frees_its_modules(
    firm_world: dict[str, uuid.UUID],
    engage: Callable[..., uuid.UUID],
    seed: Callable[..., None],
) -> None:
    """Revocation must free the module, or the client cannot appoint anyone else.

    Cutting access without releasing the relationship would leave `payroll`
    claimed by a dead engagement forever.
    """
    second_firm_tenant, second_firm = uuid.uuid4(), uuid.uuid4()
    now = datetime.now(UTC)
    seed(
        "INSERT INTO tenant (id, subdomain, legal_name, status, default_locale,"
        " created_at, updated_at)"
        " VALUES (%s, 'altafirma3', 'Alta Firma SRL', 'active', 'ro', %s, %s)",
        [second_firm_tenant, now, now],
    )
    seed(
        "INSERT INTO firm (id, tenant_id, name, status, created_at, updated_at)"
        " VALUES (%s, %s, 'Alta Firma', 'active', %s, %s)",
        [second_firm, second_firm_tenant, now, now],
    )
    first = engage(firm_world["firm"], firm_world["tenant_b"], firm_world["user_f"])
    second = engage(second_firm, firm_world["tenant_b"], firm_world["user_f"])
    seed(
        "INSERT INTO engagement_module_scope (id, engagement_id, module_key,"
        " permission_level, client_tenant_id, is_live)"
        " VALUES (%s, %s, 'payroll', 'write', %s, true)",
        [uuid.uuid4(), first, firm_world["tenant_b"]],
    )

    seed("UPDATE engagement SET status = 'revoked', revoked_at = now() WHERE id = %s", [first])

    # The module is free again: the second firm may now claim it.
    seed(
        "INSERT INTO engagement_module_scope (id, engagement_id, module_key,"
        " permission_level, client_tenant_id, is_live)"
        " VALUES (%s, %s, 'payroll', 'write', %s, true)",
        [uuid.uuid4(), second, firm_world["tenant_b"]],
    )
