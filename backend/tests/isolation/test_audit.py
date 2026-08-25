"""The audit trail: append-only, attributable, and enumerable.

Three properties, each of which fails differently if it is only a convention.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

import pytest
from django.db import connection, transaction
from django.db.utils import ProgrammingError

from evidenta.platform.audit.models import AuditEvent
from evidenta.platform.audit.services.enumeration import effects_in_interval, history_of
from evidenta.platform.audit.services.recording import (
    MissingAuditContextError,
    record,
)
from evidenta.platform.engagement.services.lifecycle import TenantSide, accept, invite
from evidenta.platform.engagement.services.revocation import revoke_engagement
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


@pytest.fixture
def as_client(firm_world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(
        tenant_id=firm_world["tenant_b"],
        user_id=firm_world["user_b"],
        request_id="req-1",
    )


def test_recording_requires_a_context(firm_world: dict[str, uuid.UUID]) -> None:
    """An entry whose actor cannot be attributed is not evidence of anything."""
    with pytest.raises(MissingAuditContextError):
        record(action="test.thing", entity_type="thing")


def test_the_actor_comes_from_the_context_not_the_caller(
    as_client: TenantContext,
) -> None:
    with tenant_context(as_client):
        event = record(action="test.thing", entity_type="thing")
        assert event.actor_user_id == as_client.user_id
        assert event.request_id == as_client.request_id


def test_audit_cannot_be_updated_or_deleted(as_client: TenantContext) -> None:
    """Append-only enforced by grants, not by convention.

    Whoever can delete the row that incriminates them deletes the evidence too.
    The application role simply has no UPDATE or DELETE on this table.
    """
    with tenant_context(as_client):
        event = record(action="test.thing", entity_type="thing")

    for statement, params in (
        ("UPDATE audit_event SET action = 'changed' WHERE id = %s", [event.id]),
        ("DELETE FROM audit_event WHERE id = %s", [event.id]),
    ):
        with (
            tenant_context(as_client),
            pytest.raises(ProgrammingError, match="permission denied"),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute(statement, params)


def test_an_entry_cannot_be_attributed_to_someone_else(
    firm_world: dict[str, uuid.UUID], as_client: TenantContext
) -> None:
    """The insert policy requires actor_user_id = current_user_id().

    Without it, a user could write an audit entry blaming a colleague -- which is
    precisely the forgery the audit exists to prevent.
    """
    with (
        tenant_context(as_client),
        pytest.raises(ProgrammingError, match="row-level security"),
        transaction.atomic(),
        connection.cursor() as cursor,
    ):
        cursor.execute(
            "INSERT INTO audit_event (tenant_id, occurred_at, actor_user_id,"
            " request_id, action, entity_type, source)"
            " VALUES (%s, now(), %s, 'forged', 'test.forged', 'thing', 'web')",
            [firm_world["tenant_b"], firm_world["user_f"]],
        )


def test_audit_is_scoped_to_the_tenant(
    firm_world: dict[str, uuid.UUID], as_client: TenantContext
) -> None:
    with tenant_context(as_client):
        record(action="test.b", entity_type="thing")

    other = TenantContext(
        tenant_id=firm_world["tenant_a"],
        user_id=firm_world["user_a"],
        request_id="req-2",
    )
    with tenant_context(other):
        assert AuditEvent.objects.count() == 0


def test_a_firm_acting_under_engagement_is_recorded_as_such(
    firm_world: dict[str, uuid.UUID], engage: Callable[..., uuid.UUID]
) -> None:
    """The column that makes "who had access in March 2027" answerable.

    Without actor_firm_id the actor is a user id with no relationship, and after
    the firm is gone there is nothing to reconstruct it from.
    """
    engage(firm_world["firm"], firm_world["tenant_b"], firm_world["user_f"])
    acting = TenantContext(
        tenant_id=firm_world["tenant_b"],
        user_id=firm_world["user_f"],
        request_id="req-firm",
        actor_firm_id=firm_world["firm"],
    )
    with tenant_context(acting):
        event = record(action="test.by_firm", entity_type="thing")
        assert event.actor_firm_id == firm_world["firm"]


def test_revocation_records_itself(
    firm_world: dict[str, uuid.UUID], as_client: TenantContext
) -> None:
    """The gap left open at F0.3.4, now closed."""
    with tenant_context(as_client):
        engagement = invite(
            firm_id=firm_world["firm"],
            client_tenant_id=firm_world["tenant_b"],
            invited_by_user_id=firm_world["user_f"],
            initiated_by=TenantSide.FIRM,
            valid_from=date(2020, 1, 1),
        )
        accept(engagement.id, firm_world["user_b"], TenantSide.TENANT)
        revoke_engagement(engagement.id, firm_world["user_b"], reason="test")

        actions = [event.action for event in history_of("engagement", engagement.id)]
    assert actions == ["engagement.accepted", "engagement.revoked"]


def test_effects_group_by_the_act_that_caused_them(
    firm_world: dict[str, uuid.UUID], as_client: TenantContext
) -> None:
    """Spec A 9.3: reversing half an act is worse than reversing none of it.

    The grouping is what turns "undo Monday" from an impossible restore into an
    enumerable set -- which is the only thing that makes refusing the restore an
    honest answer rather than a shrug.
    """
    now = datetime.now(UTC)
    with tenant_context(as_client):
        record(action="test.one", entity_type="thing")
        record(action="test.two", entity_type="thing")

    second = TenantContext(
        tenant_id=as_client.tenant_id,
        user_id=as_client.user_id,
        request_id="req-2",
    )
    with tenant_context(second):
        record(action="test.three", entity_type="thing")

    with tenant_context(as_client):
        groups = effects_in_interval(now - timedelta(minutes=1), now + timedelta(minutes=1))

    assert [group.request_id for group in groups] == ["req-1", "req-2"]
    assert [len(group.events) for group in groups] == [2, 1]


def test_a_transfer_is_recorded_as_one_act(
    firm_world: dict[str, uuid.UUID], as_client: TenantContext, seed: Callable[..., None]
) -> None:
    """Two rows, one request_id.

    Grouped by the act, a transfer reads as a transfer. Grouped by nothing, it
    reads as two unrelated status changes that happened to land in the same
    second -- and reversing one without the other leaves the client with no
    accountant at all.
    """
    from evidenta.platform.engagement.services.lifecycle import transfer

    now = datetime.now(UTC)
    second_tenant, second_firm = uuid.uuid4(), uuid.uuid4()
    seed(
        "INSERT INTO tenant (id, subdomain, legal_name, status, default_locale,"
        " created_at, updated_at)"
        " VALUES (%s, 'firmaurm', 'Firma Urmatoare SRL', 'active', 'ro', %s, %s)",
        [second_tenant, now, now],
    )
    seed(
        "INSERT INTO firm (id, tenant_id, name, status, created_at, updated_at)"
        " VALUES (%s, %s, 'Firma Urmatoare', 'active', %s, %s)",
        [second_firm, second_tenant, now, now],
    )

    with tenant_context(as_client):
        outgoing = invite(
            firm_id=firm_world["firm"],
            client_tenant_id=firm_world["tenant_b"],
            invited_by_user_id=firm_world["user_f"],
            initiated_by=TenantSide.FIRM,
            valid_from=date(2020, 1, 1),
        )
        accept(outgoing.id, firm_world["user_b"], TenantSide.TENANT)
        incoming = invite(
            firm_id=second_firm,
            client_tenant_id=firm_world["tenant_b"],
            invited_by_user_id=firm_world["user_b"],
            initiated_by=TenantSide.TENANT,
            valid_from=date(2020, 1, 1),
        )
        transfer(
            outgoing_engagement_id=outgoing.id,
            incoming_engagement_id=incoming.id,
            accepted_by_user_id=firm_world["user_b"],
        )

        groups = effects_in_interval(now - timedelta(minutes=1), now + timedelta(minutes=1))

    transfer_actions = {
        event.action for group in groups for event in group.events if "transferred" in event.action
    }
    assert transfer_actions == {
        "engagement.transferred_out",
        "engagement.transferred_in",
    }
    # Both in the same group: one act.
    assert len(groups) == 1
