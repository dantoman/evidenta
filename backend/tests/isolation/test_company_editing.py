"""Editing and closing a company -- ADR-083, under the application role (`T1`).

Two of these tests are about the feature. The rest are about the three things the
ADR had to measure before the feature could be honest:

* a company-scoped key is held through ``company_access``, never through a
  membership -- so it opens one company and not its neighbour;
* ``closed`` now means something, and what it means is enforced by the posting
  gate rather than by a screen (`R12`'s neighbour);
* what production actually writes into ``company_access.role_id`` is a
  **tenant-level** role, which no company-scoped key can ever hang off. That one
  is written as a test rather than as a claim, because the fixtures model the
  intended world and production models another -- which is exactly why nothing
  caught it.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest

from evidenta.accounting.periods.errors import CompanyNotPostableError, PeriodNotFoundError
from evidenta.accounting.periods.services.resolution import assert_postable
from evidenta.platform.identity.models import CompanyAccess, Role, RoleLevel
from evidenta.platform.identity.services import roles as role_service
from evidenta.platform.rls.context import TenantContext, tenant_context
from evidenta.platform.tenancy.models import Company, CompanyStatus
from evidenta.platform.tenancy.services.companies import (
    CompanyFieldNotEditableError,
    CompanyPermissionDeniedError,
    close_company,
    update_company,
)
from evidenta.platform.tenancy.services.provisioning import (
    CompanyProvisioningRefusedError,
    provision_company,
)
from tests.isolation.conftest import role_id

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


def as_user(tenant_id: uuid.UUID, user_id: uuid.UUID) -> TenantContext:
    return TenantContext(tenant_id=tenant_id, user_id=user_id, request_id="test")


@pytest.fixture
def owned(
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> dict[str, uuid.UUID]:
    """One company of tenant A, reachable by user A through a company-level role.

    ``grant_company`` writes ``company_admin`` -- the shape ``CompanyAccess``
    documents. ``create_system_roles`` then fills both system roles with the
    permissions of their level, which is what the product does when a tenant is
    created.
    """
    ids = dict(world)
    ids["company"] = company_of(ids["tenant_a"], "1000000000001", "Alpha Unu SRL")
    grant_company(ids["tenant_a"], ids["company"], ids["user_a"], ids["user_a"])
    with tenant_context(as_user(ids["tenant_a"], ids["user_a"])):
        role_service.create_system_roles(ids["tenant_a"])
    return ids


def test_the_key_on_this_company_corrects_it(owned: dict[str, uuid.UUID]) -> None:
    with tenant_context(as_user(owned["tenant_a"], owned["user_a"])):
        update_company(owned["company"], legal_name="Alpha Unu SRL corectat", caem_code="4711")
        stored = Company.objects.get(pk=owned["company"])

    assert stored.legal_name == "Alpha Unu SRL corectat"
    assert stored.caem_code == "4711"


def test_a_role_without_the_key_cannot_edit(owned: dict[str, uuid.UUID]) -> None:
    """Reaching a company and being allowed to change it are different questions.

    The company stays visible throughout -- a firm's user with access to the
    books but no key over the company card is the ordinary case, not an edge.
    """
    with tenant_context(as_user(owned["tenant_a"], owned["user_a"])):
        bare = Role.objects.create(
            tenant_id=owned["tenant_a"],
            key="doar_citire",
            name="Doar citire",
            level=RoleLevel.COMPANY,
        )
        CompanyAccess.objects.filter(company_id=owned["company"]).update(role=bare)

        assert Company.objects.filter(pk=owned["company"]).exists()
        with pytest.raises(CompanyPermissionDeniedError):
            update_company(owned["company"], legal_name="schimbat")


def test_the_key_does_not_travel_to_the_next_company(
    owned: dict[str, uuid.UUID], company_of: Callable[..., uuid.UUID]
) -> None:
    """ADR-083 section 1: company scope, so a holding can be narrow.

    The second company belongs to the same tenant and has no access row, so it is
    invisible -- and the refusal says *not visible*, never *not permitted*: a 403
    on a row the caller cannot see would confirm the id exists (IZ-04).
    """
    from evidenta.platform.tenancy.services.companies import CompanyNotVisibleError

    second = company_of(owned["tenant_a"], "1000000000002", "Alpha Doi SRL")
    with (
        tenant_context(as_user(owned["tenant_a"], owned["user_a"])),
        pytest.raises(CompanyNotVisibleError),
    ):
        update_company(second, legal_name="schimbat")


def test_a_field_with_consequences_is_refused_by_name(owned: dict[str, uuid.UUID]) -> None:
    """`idno` has left on issued documents; the API does not take it back.

    Refused rather than silently dropped: a screen that sent it and got 200 would
    believe it had changed something.
    """
    with (
        tenant_context(as_user(owned["tenant_a"], owned["user_a"])),
        pytest.raises(CompanyFieldNotEditableError),
    ):
        update_company(owned["company"], idno="1000000000009")


def test_editing_does_not_carry_closing(owned: dict[str, uuid.UUID]) -> None:
    """The whole point of two keys, in one test.

    A role holding `company.edit` and not `company.close` corrects the card and
    cannot stop the company receiving postings.
    """
    with tenant_context(as_user(owned["tenant_a"], owned["user_a"])):
        editor = Role.objects.create(
            tenant_id=owned["tenant_a"],
            key="editor",
            name="Editor",
            level=RoleLevel.COMPANY,
        )
        role_service.grant_permission(editor, "company.edit", owned["user_a"])
        CompanyAccess.objects.filter(company_id=owned["company"]).update(role=editor)

        update_company(owned["company"], short_name="Alpha")
        with pytest.raises(CompanyPermissionDeniedError):
            close_company(owned["company"], reason="greseala")


def test_closing_is_recorded_and_repeatable(owned: dict[str, uuid.UUID]) -> None:
    with tenant_context(as_user(owned["tenant_a"], owned["user_a"])):
        closed = close_company(owned["company"], reason="a incetat activitatea")
        again = close_company(owned["company"], reason="a incetat activitatea")

    assert closed.status == CompanyStatus.CLOSED
    assert again.status == CompanyStatus.CLOSED


def test_a_closed_company_is_refused_by_the_engine(owned: dict[str, uuid.UUID]) -> None:
    """`closed` stops being decorative -- ADR-083 section 2.3.

    The company has no periods at all, and that is what makes the test say
    something: an active company answers `period_not_found`, a closed one is
    refused before the calendar is consulted. Same call, two different reasons,
    and the codes tell them apart.
    """
    with tenant_context(as_user(owned["tenant_a"], owned["user_a"])):
        with pytest.raises(PeriodNotFoundError):
            assert_postable(owned["company"], date(2026, 3, 15))

        close_company(owned["company"], reason="a incetat activitatea")

        with pytest.raises(CompanyNotPostableError):
            assert_postable(owned["company"], date(2026, 3, 15))


def test_provisioning_writes_a_role_a_company_key_can_hang_off(
    world: dict[str, uuid.UUID],
) -> None:
    """The repair of `OD-124`, asserted where the defect used to be -- ADR-084.

    **What this test said until 31.08**, and it passed: `rls.provision_company`
    copied the creator's *membership* role -- tenant-level -- into
    ``company_access.role_id``. `role_permission` binds a permission's scope to
    the role's level, so no company-scoped key could hang off the rows the product
    actually created. `company.revoke_access` had been unholdable since F0.3.3 for
    exactly that reason, and nothing said so: the fixtures wrote ``company_admin``,
    which is what `CompanyAccess` documents, so every test agreed with the model
    and disagreed with production.

    Now the function looks the role up instead of copying one, and this asserts
    the level -- not the key. A future company-level system role under another name
    would still satisfy what the permission machinery needs.
    """
    tenant = world["tenant_a"]
    context = as_user(tenant, world["user_a"])
    with tenant_context(context):
        role_service.create_system_roles(tenant)
        company = provision_company(idno="1002600000913", legal_name="Alpha Provizionată")

        access = CompanyAccess.objects.get(company_id=company.id, user_id=world["user_a"])
        granted = Role.objects.get(pk=access.role_id)

        assert granted.level == RoleLevel.COMPANY
        # And the key it opens, which is the whole point of the level.
        assert role_service.has_company_permission(world["user_a"], company.id, "company.edit")


def test_provisioning_refuses_a_tenant_without_the_company_role(
    seed: Callable[..., None],
) -> None:
    """Loud, rather than falling back to the membership role.

    The tenant is built the way the damaged ones actually are -- with ``owner``
    and **without** ``company_admin`` -- which is the state measured on `alpha`
    before `repair_system_roles` existed. It cannot be reached by deleting the
    role: a system role refuses deletion, and the trigger says so. It is reached
    by never having created it, which is how the real ones got there.

    Falling back to the membership role here would restore `OD-124` silently, and
    only on damaged tenants -- which is where nobody looks.
    """
    now = datetime.now(UTC)
    tenant = uuid.uuid4()
    user = uuid.uuid4()
    seed(
        "INSERT INTO tenant (id, subdomain, legal_name, status, default_locale,"
        " created_at, updated_at)"
        " VALUES (%s, 'fararol', 'Fara Rol SRL', 'active', 'ro', %s, %s)",
        [tenant, now, now],
    )
    seed(
        'INSERT INTO "user" (id, email, full_name, mfa_enabled, locale, is_active,'
        " created_at, updated_at)"
        " VALUES (%s, 'fararol@example.md', 'F', false, 'ro', true, %s, %s)",
        [user, now, now],
    )
    seed(
        "INSERT INTO role (id, tenant_id, key, name, level, is_system,"
        " created_at, updated_at)"
        " VALUES (%s, %s, 'owner', 'owner', 'tenant', true, %s, %s)",
        [role_id(tenant, "owner"), tenant, now, now],
    )
    seed(
        "INSERT INTO membership (id, tenant_id, user_id, role_id, status, invited_at,"
        " accepted_at, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, 'active', %s, %s, %s, %s)",
        [uuid.uuid4(), tenant, user, role_id(tenant, "owner"), now, now, now, now],
    )

    with (
        tenant_context(as_user(tenant, user)),
        pytest.raises(CompanyProvisioningRefusedError),
    ):
        provision_company(idno="1002600000914", legal_name="Alpha Fara Rol")


def test_a_tenant_level_role_on_an_access_row_still_holds_no_company_key(
    owned: dict[str, uuid.UUID],
) -> None:
    """The mechanism the fix relies on, kept under test on its own.

    ADR-084 repairs *which role gets written*; it does not change what a
    tenant-level role can hold. If that ever stopped being true, the fix would be
    unnecessary and this file would be measuring nothing.
    """
    with tenant_context(as_user(owned["tenant_a"], owned["user_a"])):
        tenant_level = Role.objects.get(tenant_id=owned["tenant_a"], key="owner")
        assert tenant_level.level == RoleLevel.TENANT
        CompanyAccess.objects.filter(company_id=owned["company"]).update(role=tenant_level)

        assert not role_service.has_company_permission(
            owned["user_a"], owned["company"], "company.edit"
        )
        with pytest.raises(CompanyPermissionDeniedError):
            update_company(owned["company"], legal_name="schimbat")
