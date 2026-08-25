"""Company access: membership is not enough, and revocation cascades.

Two claims that look obvious and are not. A tenant may hold several companies and
a user may be entitled to one of them -- so belonging to the tenant cannot be the
same as reaching every company under it. And access granted through an engagement
must not outlive the engagement, which is a property of the revocation path, not
of good intentions.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

import pytest
from django.db import connection, transaction
from django.db.utils import ProgrammingError

from evidenta.platform.engagement.services.revocation import (
    RevocationError,
    revoke_engagement,
)
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


def member(tenant_id: uuid.UUID, user_id: uuid.UUID) -> TenantContext:
    return TenantContext(tenant_id=tenant_id, user_id=user_id, request_id="test")


def visible_companies() -> list[str]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT legal_name FROM company ORDER BY legal_name")
        return [row[0] for row in cursor.fetchall()]


def test_membership_alone_does_not_reach_a_company(
    world: dict[str, uuid.UUID], company_of: Callable[..., uuid.UUID]
) -> None:
    """The claim worth testing: belonging to the tenant is not access."""
    company_of(world["tenant_a"], "1002600000001", "Alpha Trading")
    with tenant_context(member(world["tenant_a"], world["user_a"])):
        assert visible_companies() == []


def test_company_access_reaches_exactly_one_company(
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> None:
    granted = company_of(world["tenant_a"], "1002600000001", "Alpha Trading")
    company_of(world["tenant_a"], "1002600000002", "Alpha Logistics")
    grant_company(world["tenant_a"], granted, world["user_a"], world["user_a"])

    with tenant_context(member(world["tenant_a"], world["user_a"])):
        assert visible_companies() == ["Alpha Trading"]


def test_insert_into_another_tenant_is_refused(
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> None:
    """IZ-50. Without WITH CHECK this row would commit and then vanish."""
    granted = company_of(world["tenant_a"], "1002600000001", "Alpha Trading")
    grant_company(world["tenant_a"], granted, world["user_a"], world["user_a"])

    # The atomic() is a savepoint, and it is required: catching a database error
    # inside a transaction without one leaves the transaction aborted, and every
    # later statement fails with a message about the abort rather than about the
    # thing under test.
    with (
        tenant_context(member(world["tenant_a"], world["user_a"])),
        pytest.raises(ProgrammingError, match="row-level security"),
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "INSERT INTO company (id, tenant_id, idno, legal_name,"
            " functional_currency, fiscal_year_start_month,"
            " accounting_start_date, status, created_at, updated_at)"
            " VALUES (%s, %s, '1002600000009', 'Intrus SRL', 'MDL', 1,"
            " '2026-01-01', 'active', now(), now())",
            [uuid.uuid4(), world["tenant_b"]],
        )


def test_revocation_cascades_to_derived_company_access(
    firm_world: dict[str, uuid.UUID],
    engage: Callable[..., uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> None:
    """Access does not outlive the relationship that produced it.

    The firm's user reaches the client's company; after revocation, nothing --
    in the same transaction, without a job, and without the administrator ever
    being able to see the rows being revoked.
    """
    engagement_id = engage(firm_world["firm"], firm_world["tenant_b"], firm_world["user_f"])
    company_id = company_of(firm_world["tenant_b"], "1002600000010", "Beta Services")
    grant_company(
        firm_world["tenant_b"],
        company_id,
        firm_world["user_f"],
        firm_world["user_b"],
        via="engagement",
        engagement_id=engagement_id,
    )

    acting = TenantContext(
        tenant_id=firm_world["tenant_b"],
        user_id=firm_world["user_f"],
        request_id="test",
        actor_firm_id=firm_world["firm"],
    )
    with tenant_context(acting):
        assert visible_companies() == ["Beta Services"]

    # The client revokes. A tenant may revoke at any time, without motivation.
    with tenant_context(member(firm_world["tenant_b"], firm_world["user_b"])):
        result = revoke_engagement(engagement_id, firm_world["user_b"], reason="test")
    assert result.company_access_revoked == 1

    with tenant_context(acting):
        assert visible_companies() == []


def test_revoking_twice_is_refused(
    firm_world: dict[str, uuid.UUID], engage: Callable[..., uuid.UUID]
) -> None:
    """Revoked is terminal. Resuming means a new engagement, so history stays readable."""
    engagement_id = engage(firm_world["firm"], firm_world["tenant_b"], firm_world["user_f"])
    with tenant_context(member(firm_world["tenant_b"], firm_world["user_b"])):
        revoke_engagement(engagement_id, firm_world["user_b"])
        with pytest.raises(RevocationError):
            revoke_engagement(engagement_id, firm_world["user_b"])


def test_the_cascade_path_refuses_a_caller_without_rights(
    firm_world: dict[str, uuid.UUID], engage: Callable[..., uuid.UUID]
) -> None:
    """The privileged function is a path, not a hole.

    It checks the caller's right through the same predicate as the policy on
    ``engagement``. Without that check, knowing a uuid would be enough to strip
    anyone's access.
    """
    engagement_id = engage(firm_world["firm"], firm_world["tenant_b"], firm_world["user_f"])
    with (
        tenant_context(member(firm_world["tenant_a"], firm_world["user_a"])),
        pytest.raises(ProgrammingError, match="fara drept"),
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "SELECT rls.revoke_engagement_company_access(%s)",
            [str(engagement_id)],
        )
