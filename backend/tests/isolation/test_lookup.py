"""IZ-04 -- a resource of another tenant answers 404, never 403.

    "UA cere prin API o resursă a lui B, după `id` -> 404, nu 403 --
     existența nu se dezvăluie."

The distinction is not politeness. "This exists and is not yours", repeated over
a range of identifiers, is an enumeration oracle: a competitor holding a client
list learns which of them keep their books here, and one tenant can measure
another's volume by probing. 404 says nothing at all.

The convenient part is that RLS produces the right answer without being asked --
which is also the part worth a test, because it means nobody had to remember.
"""

from __future__ import annotations

import uuid

import pytest

from evidenta.platform.api.lookup import NotFoundError, get_or_404
from evidenta.platform.notifications.models import Notification
from evidenta.platform.notifications.services import dispatch
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


def test_a_resource_of_another_tenant_is_not_found_rather_than_forbidden(
    seed: object, world: dict[str, uuid.UUID]
) -> None:
    """An existing row and an identifier never issued must be indistinguishable.

    Asserting on both is the point. Testing only the cross-tenant row would pass
    on an implementation that answered 404 for it and 403 for nothing at all --
    or that answered differently in some other way a caller could measure.
    """
    owner = TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="iz04")
    with tenant_context(owner):
        created = dispatch.notify_tenant(tenant_id=world["tenant_a"], type_key="engagement.revoked")
        assert get_or_404(Notification.objects.all(), pk=created[0])

    stranger = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="iz04"
    )
    with tenant_context(stranger):
        with pytest.raises(NotFoundError) as existing:
            get_or_404(Notification.objects.all(), pk=created[0])
        with pytest.raises(NotFoundError) as never_issued:
            get_or_404(Notification.objects.all(), pk=uuid.uuid4())

    assert existing.value.code == never_issued.value.code == "api.not_found"
    assert existing.value.status == never_issued.value.status == 404
    assert str(existing.value) == str(never_issued.value)


def test_the_owner_still_reads_their_own_row(seed: object, world: dict[str, uuid.UUID]) -> None:
    """The control. Without it, a lookup that refused everything would pass the
    test above -- 404 for all callers is indistinguishable in exactly the way the
    rule asks for, and useless.
    """
    owner = TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="iz04")
    with tenant_context(owner):
        created = dispatch.notify_tenant(tenant_id=world["tenant_a"], type_key="engagement.revoked")
        found = get_or_404(Notification.objects.all(), pk=created[0])
    assert found.id == created[0]
