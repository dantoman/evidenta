"""The engagement state machine -- Spec A section 4.2.

The tests that matter here are the refusals. An allowed transition working is
table stakes; what the matrix is for is the transitions that must *not* happen,
and the actors who must not be able to trigger them.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest
from django.db import connection

from evidenta.platform.engagement.models import Engagement, EngagementStatus
from evidenta.platform.engagement.services.lifecycle import (
    IllegalTransitionError,
    TenantSide,
    accept,
    invite,
    mark_expired,
    resume,
    suspend,
    transfer,
)
from evidenta.platform.engagement.services.revocation import (
    RevocationError,
    revoke_engagement,
)
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


@pytest.fixture
def as_client(firm_world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(
        tenant_id=firm_world["tenant_b"],
        user_id=firm_world["user_b"],
        request_id="test",
    )


def new_invitation(
    firm_world: dict[str, uuid.UUID], initiated_by: str = TenantSide.FIRM
) -> Engagement:
    return invite(
        firm_id=firm_world["firm"],
        client_tenant_id=firm_world["tenant_b"],
        invited_by_user_id=firm_world["user_f"],
        initiated_by=initiated_by,
        valid_from=date(2020, 1, 1),
    )


def test_invitation_grants_nothing_until_accepted(
    firm_world: dict[str, uuid.UUID], as_client: TenantContext
) -> None:
    with tenant_context(as_client):
        engagement = new_invitation(firm_world)
        assert engagement.status == EngagementStatus.INVITED
        assert engagement.accepted_at is None


def test_the_inviting_side_cannot_also_accept(
    firm_world: dict[str, uuid.UUID], as_client: TenantContext
) -> None:
    """An invitation a firm both sends and accepts is not delegation.

    Without this the model could not tell later whether the client ever agreed.
    """
    with tenant_context(as_client):
        engagement = new_invitation(firm_world, initiated_by=TenantSide.FIRM)
        with pytest.raises(IllegalTransitionError) as caught:
            accept(engagement.id, firm_world["user_f"], TenantSide.FIRM)
    assert caught.value.code == "engagement.self_acceptance"


def test_the_other_side_accepts(firm_world: dict[str, uuid.UUID], as_client: TenantContext) -> None:
    with tenant_context(as_client):
        engagement = new_invitation(firm_world, initiated_by=TenantSide.FIRM)
        accepted = accept(engagement.id, firm_world["user_b"], TenantSide.TENANT)
    assert accepted.status == EngagementStatus.ACTIVE
    assert accepted.accepted_at is not None


def test_suspend_and_resume_keep_the_relationship(
    firm_world: dict[str, uuid.UUID], as_client: TenantContext
) -> None:
    """Suspension is reversible and needs no re-acceptance: nothing ended."""
    with tenant_context(as_client):
        engagement = new_invitation(firm_world)
        accept(engagement.id, firm_world["user_b"], TenantSide.TENANT)
        suspended = suspend(engagement.id, TenantSide.TENANT)
        assert suspended.status == EngagementStatus.SUSPENDED

        resumed = resume(engagement.id, TenantSide.TENANT)
        assert resumed.status == EngagementStatus.ACTIVE
        assert resumed.suspended_at is None


def test_a_firm_cannot_revoke_unilaterally(
    firm_world: dict[str, uuid.UUID], as_client: TenantContext
) -> None:
    """DN-14 has not decided whether it may, so it may not.

    Refusing is the fail-closed answer: a firm that cannot revoke is an
    inconvenience, a firm that revokes when it should not have is a client
    without an accountant on a filing deadline.
    """
    with tenant_context(as_client):
        engagement = new_invitation(firm_world)
        accept(engagement.id, firm_world["user_b"], TenantSide.TENANT)
        with pytest.raises(RevocationError, match="actor_not_allowed"):
            revoke_engagement(engagement.id, firm_world["user_f"], actor_side=TenantSide.FIRM)


def test_the_tenant_may_revoke_without_motivation(
    firm_world: dict[str, uuid.UUID], as_client: TenantContext
) -> None:
    """Follows from INV-7: the tenant owns the data."""
    with tenant_context(as_client):
        engagement = new_invitation(firm_world)
        accept(engagement.id, firm_world["user_b"], TenantSide.TENANT)
        result = revoke_engagement(engagement.id, firm_world["user_b"])
    assert result.engagement_id == engagement.id


@pytest.mark.parametrize(
    ("terminal", "attempt"),
    [
        (EngagementStatus.REVOKED, "suspend"),
        (EngagementStatus.REVOKED, "resume"),
        (EngagementStatus.EXPIRED, "resume"),
        (EngagementStatus.TRANSFERRED, "resume"),
    ],
)
def test_terminal_states_have_no_way_out(
    firm_world: dict[str, uuid.UUID],
    as_client: TenantContext,
    terminal: str,
    attempt: str,
) -> None:
    """Resuming a relationship means a new engagement.

    A row that went out and came back would make "who had access in March 2027"
    unanswerable -- which is the question the whole history exists to answer.

    The state is set through the ORM, inside the test's transaction. The `seed`
    fixture writes on a separate connection and would not see a row created here
    and never committed -- the UPDATE would match nothing and the test would pass
    against an engagement that is still active.
    """
    action = {"suspend": suspend, "resume": resume}[attempt]

    with tenant_context(as_client):
        engagement = new_invitation(firm_world)
        accept(engagement.id, firm_world["user_b"], TenantSide.TENANT)
        Engagement.objects.filter(pk=engagement.id).update(
            status=terminal, revoked_at=datetime.now(UTC)
        )

        with pytest.raises(IllegalTransitionError) as caught:
            action(engagement.id, TenantSide.TENANT)
    assert caught.value.code == "engagement.transition_not_allowed"


def test_transfer_is_succession_not_overlap(
    firm_world: dict[str, uuid.UUID], as_client: TenantContext, seed: Callable[..., None]
) -> None:
    """ADR-018 fixes this until DN-15 closes.

    The outgoing engagement releases its modules as the incoming one starts.
    Reversed, the non-overlap index would refuse the very transfer it exists to
    make orderly.
    """
    now = datetime.now(UTC)
    second_tenant, second_firm = uuid.uuid4(), uuid.uuid4()
    seed(
        "INSERT INTO tenant (id, subdomain, legal_name, status, default_locale,"
        " created_at, updated_at)"
        " VALUES (%s, 'firmanoua', 'Firma Noua SRL', 'active', 'ro', %s, %s)",
        [second_tenant, now, now],
    )
    seed(
        "INSERT INTO firm (id, tenant_id, name, status, created_at, updated_at)"
        " VALUES (%s, %s, 'Firma Noua', 'active', %s, %s)",
        [second_firm, second_tenant, now, now],
    )

    with tenant_context(as_client):
        outgoing = new_invitation(firm_world)
        accept(outgoing.id, firm_world["user_b"], TenantSide.TENANT)

        incoming = invite(
            firm_id=second_firm,
            client_tenant_id=firm_world["tenant_b"],
            invited_by_user_id=firm_world["user_b"],
            initiated_by=TenantSide.TENANT,
            valid_from=date(2020, 1, 1),
        )
        result = transfer(
            outgoing_engagement_id=outgoing.id,
            incoming_engagement_id=incoming.id,
            accepted_by_user_id=firm_world["user_b"],
        )

        assert result.status == EngagementStatus.ACTIVE
        outgoing.refresh_from_db()
        assert outgoing.status == EngagementStatus.TRANSFERRED
        assert outgoing.transferred_to_id == incoming.id


def test_expiry_is_cosmetic_not_the_security_mechanism(
    firm_world: dict[str, uuid.UUID], as_client: TenantContext
) -> None:
    """The job moves the label; the predicate already stopped the access.

    Asserted together on purpose: if someone ever makes access depend on the job,
    the second half of this test is what fails.
    """
    yesterday = date.today() - timedelta(days=1)

    with tenant_context(as_client):
        engagement = new_invitation(firm_world)
        accept(engagement.id, firm_world["user_b"], TenantSide.TENANT)
        Engagement.objects.filter(pk=engagement.id).update(valid_to=yesterday)

    # Access to the client's data is already gone, with the row still labelled
    # `active`. What is checked is reaching the *tenant*, not seeing the
    # engagement row: both parties keep seeing the relationship whatever its
    # validity, because the client must be able to answer "who kept my books in
    # 2026" long after the firm is gone.
    acting = TenantContext(
        tenant_id=firm_world["tenant_b"],
        user_id=firm_world["user_f"],
        request_id="test",
        actor_firm_id=firm_world["firm"],
    )
    with tenant_context(acting), connection.cursor() as cursor:
        cursor.execute("SELECT count(*) FROM tenant")
        assert cursor.fetchone()[0] == 0

    with tenant_context(as_client):
        expired = mark_expired(engagement.id)
        assert expired is not None
        assert expired.status == EngagementStatus.EXPIRED
