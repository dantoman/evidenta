"""Notifications -- F0.6.5, closing conflict X-9.

The module was marked F0 in the module map and in V2 section 10 and had no task
in section 6.1. What it has to prove here is narrow and specific:

* the engagement revocation notice reaches the client's members (Spec A 4.6);
* no notification carries another tenant's data;
* notifications are **personal** -- a firm's user with a live engagement reaches
  the client's data, which is what the engagement is for, and does not thereby
  read the client administrator's inbox.

The last one is the interesting boundary, and it is the one a wider policy would
have quietly crossed.
"""

from __future__ import annotations

import re
import uuid
from collections.abc import Callable
from pathlib import Path

import pytest
from django.db import transaction
from django.db.utils import InternalError, ProgrammingError

from evidenta.platform.engagement.services import revocation
from evidenta.platform.engagement.services.lifecycle import TenantSide
from evidenta.platform.notifications.messages import (
    CATALOGUE,
    UnknownMessageError,
    render,
)
from evidenta.platform.notifications.models import (
    Channel,
    DeliveryStatus,
    Notification,
    NotificationDelivery,
)
from evidenta.platform.notifications.services import dispatch
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="notif")


# --- The catalogue ------------------------------------------------------------


def test_no_message_names_another_tenant() -> None:
    """F0.6.5's second criterion, as a property of the catalogue rather than of
    any one call site.

    No message takes the accountant's name, so none can carry it. A message that
    later grew an `accountant_name` parameter would fail here -- which is the
    point: the name belongs to the other tenant, and a client user cannot read
    the `firm` row at all today (OD-51).
    """
    for key, message in CATALOGUE.items():
        assert "accountant_name" not in message.required_params, key
        assert "{accountant" not in message.body, key


def test_no_model_vocabulary_reaches_the_interface_strings() -> None:
    """C37, checked the way C37 says to check it -- by grepping the resource file.

    `tenant`, `firm`, `engagement` and `assignment` are model words. ADR-017 fixes
    the interface words they map to, and the two layers are joined by that map
    rather than aligned to each other. A message that said "engagement" would
    leak the schema into a sentence a client reads.
    """
    source = Path(__file__).resolve().parents[2] / ("evidenta/platform/notifications/messages.py")
    text = source.read_text(encoding="utf-8")
    # Only the string literals -- the module docstring names the forbidden terms
    # in order to forbid them.
    strings = " ".join(message.subject + " " + message.body for message in CATALOGUE.values())
    assert text  # the file is where the test thinks it is
    for term in ("tenant", "firm", "engagement", "assignment"):
        assert not re.search(rf"\b{term}\b", strings, re.IGNORECASE), term


def test_rendering_happens_at_read_time_from_a_key_and_parameters() -> None:
    subject, body = render("engagement.revoked", {})
    assert subject and body


def test_an_unknown_message_is_refused_at_dispatch(
    seed: Callable[..., None], context: TenantContext
) -> None:
    """Refused when it is sent, not when it is read.

    A notification nobody can render would otherwise be stored successfully and
    fail in the recipient's inbox, where nobody who can fix it will see it.
    """
    with tenant_context(context), pytest.raises(UnknownMessageError):
        dispatch.notify_tenant(tenant_id=context.tenant_id, type_key="engagement.exploded")


def test_a_missing_substitution_is_refused_at_dispatch(
    seed: Callable[..., None], context: TenantContext
) -> None:
    """No catalogue entry needs a substitution today -- every message is
    self-contained, because naming the other party would carry another tenant's
    data. The check still has to work, so it is proved against a message declared
    for the test rather than by weakening one that ships.
    """
    from evidenta.platform.notifications.messages import CATALOGUE, Message

    CATALOGUE["probe.needs_param"] = Message(subject="s", body="{x}", required_params=("x",))
    try:
        with tenant_context(context), pytest.raises(dispatch.MissingParameterError):
            dispatch.notify_tenant(tenant_id=context.tenant_id, type_key="probe.needs_param")
    finally:
        CATALOGUE.pop("probe.needs_param", None)


# --- Delivery -----------------------------------------------------------------


def test_a_tenant_notice_reaches_every_active_member(
    seed: Callable[..., None], world: dict[str, uuid.UUID], context: TenantContext
) -> None:
    with tenant_context(context):
        created = dispatch.notify_tenant(
            tenant_id=world["tenant_a"],
            type_key="engagement.revoked",
        )
        assert len(created) == 1
        inbox = list(Notification.objects.all())
        assert [n.recipient_user_id for n in inbox] == [world["user_a"]]
        assert inbox[0].params == {}


def test_the_in_app_channel_is_delivered_and_email_is_parked(
    seed: Callable[..., None], world: dict[str, uuid.UUID], context: TenantContext
) -> None:
    """OD-50, made visible instead of silent.

    The email channel has no transport: the sender runs without a user identity,
    which needs a privileged path of its own, and no provider is chosen. A row
    parked as `unavailable` is countable; a notification dropped on the floor is
    not.
    """
    with tenant_context(context):
        dispatch.notify_tenant(
            tenant_id=world["tenant_a"],
            type_key="engagement.revoked",
            channels=(Channel.IN_APP, Channel.EMAIL),
        )
        statuses = {d.channel: d.status for d in NotificationDelivery.objects.all()}
    assert statuses == {
        Channel.IN_APP: DeliveryStatus.SENT,
        Channel.EMAIL: DeliveryStatus.UNAVAILABLE,
    }


def test_revoking_an_engagement_notifies_the_client(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    firm_world: dict[str, uuid.UUID],
    engage: Callable[..., uuid.UUID],
) -> None:
    """Spec A section 4.6, end to end: the notice is part of the revocation.

    In the same transaction, deliberately. An access change that commits while
    its notice does not leaves people working against a system that has already
    changed under them.
    """
    engagement_id = engage(
        firm_id=firm_world["firm"],
        client_tenant_id=world["tenant_a"],
        invited_by=firm_world["user_f"],
        status="active",
    )
    ctx = TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="revoke")
    with tenant_context(ctx):
        revocation.revoke_engagement(
            engagement_id, world["user_a"], reason="test", actor_side=TenantSide.TENANT
        )
        inbox = list(Notification.objects.filter(type_key="engagement.revoked"))

    assert len(inbox) == 1
    assert inbox[0].recipient_user_id == world["user_a"]
    _, body = render(inbox[0].type_key, inbox[0].params)
    assert body


# --- Isolation ----------------------------------------------------------------


def test_notifications_of_another_tenant_are_invisible(
    seed: Callable[..., None], world: dict[str, uuid.UUID], context: TenantContext
) -> None:
    with tenant_context(context):
        dispatch.notify_tenant(
            tenant_id=world["tenant_a"],
            type_key="engagement.revoked",
        )

    other = TenantContext(tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="notif")
    with tenant_context(other):
        assert Notification.objects.count() == 0


def test_a_notification_cannot_be_sent_to_a_user_outside_the_tenant(
    seed: Callable[..., None], world: dict[str, uuid.UUID], context: TenantContext
) -> None:
    """The condition the privileged function exists for.

    Without it, anyone could deliver arbitrary text to any user in the
    installation, and the recipient would see it in an inbox carrying the
    product's name.
    """
    with (
        tenant_context(context),
        pytest.raises((InternalError, ProgrammingError)),
        transaction.atomic(),
    ):
        dispatch.notify(
            tenant_id=world["tenant_a"],
            recipient_user_ids=[world["user_b"]],
            type_key="engagement.revoked",
        )


def test_notifications_are_personal_not_tenant_wide(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    firm_world: dict[str, uuid.UUID],
    engage: Callable[..., uuid.UUID],
) -> None:
    """The boundary a wider policy would have crossed without anyone noticing.

    The firm's user has a live engagement, so they reach the client's data --
    that is what the engagement is for. The client administrator's own inbox is
    not part of it.
    """
    engage(
        firm_id=firm_world["firm"],
        client_tenant_id=world["tenant_a"],
        invited_by=firm_world["user_f"],
        status="active",
    )
    admin = TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="notif")
    with tenant_context(admin):
        dispatch.notify_tenant(
            tenant_id=world["tenant_a"],
            type_key="engagement.revoked",
        )
        assert Notification.objects.count() == 1

    firm_user = TenantContext(
        tenant_id=world["tenant_a"],
        user_id=firm_world["user_f"],
        request_id="notif",
        actor_firm_id=firm_world["firm"],
    )
    with tenant_context(firm_user):
        assert Notification.objects.count() == 0


def test_a_notification_cannot_be_created_without_a_context(
    seed: Callable[..., None], world: dict[str, uuid.UUID]
) -> None:
    """Refused by the database, not by the query guard -- which is the stronger
    of the two places.

    The privileged path names its `unguarded` reason, so the call does reach the
    server. What refuses it is `app.current_user_id()` inside
    `rls.has_tenant_access`, fail-closed: with no context it raises rather than
    returning NULL. A refusal that survives the application layer being wrong is
    worth more than one that depends on it being right.
    """
    with pytest.raises((RuntimeError, ProgrammingError)):
        dispatch.notify_tenant(
            tenant_id=world["tenant_a"],
            type_key="engagement.revoked",
        )
