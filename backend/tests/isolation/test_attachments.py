"""Attachments -- F0.6.3, ADR-030.

Two things under test, and they are different in kind.

The first is the boundary DN-16 settled: an attachment is **company-scoped**, so
an accountant with access to one company of a holding does not see another's.
That is the case ADR-030 turns on, and it is the one worth proving, because the
tenant-level version would look correct in every single-company test.

The second is that the storage backend **refuses** when unconfigured. OD-52 has
not chosen a provider, and the failure mode being guarded against is not an
exception -- it is a filesystem fallback that works in development, passes every
test, and loses files in production behind a load balancer.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime

import pytest
from django.db import transaction
from django.db.utils import IntegrityError, ProgrammingError

from evidenta.platform.attachments.models import Attachment
from evidenta.platform.attachments.storage import (
    RefusingStorage,
    StorageNotConfiguredError,
    get_storage,
    object_key,
)
from evidenta.platform.rls.context import TenantContext, tenant_context

from .conftest import role_id, seed_system_roles

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

CHECKSUM = "a" * 64


@pytest.fixture
def company(
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> uuid.UUID:
    company_id = company_of(world["tenant_a"], "1002600000001", "Alpha Trading")
    grant_company(world["tenant_a"], company_id, world["user_a"], world["user_a"])
    return company_id


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="attach")


def attach(company_id: uuid.UUID, tenant_id: uuid.UUID, user_id: uuid.UUID) -> Attachment:
    attachment_id = uuid.uuid4()
    now = datetime.now(UTC)
    return Attachment.objects.create(
        id=attachment_id,
        tenant_id=tenant_id,
        company_id=company_id,
        storage_key=object_key(
            tenant_id=tenant_id,
            company_id=company_id,
            attachment_id=attachment_id,
            uploaded_at=now,
        ),
        original_filename="factura.pdf",
        content_type="application/pdf",
        byte_size=1024,
        checksum_sha256=CHECKSUM,
        uploaded_by_user_id=user_id,
    )


# --- The boundary ADR-030 turns on -------------------------------------------


def test_an_attachment_is_visible_within_its_company(
    company: uuid.UUID, context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        created = attach(company, world["tenant_a"], world["user_a"])
        assert Attachment.objects.get(pk=created.pk).original_filename == "factura.pdf"


def test_an_accountant_of_one_company_does_not_see_anothers_attachments(
    seed: Callable[..., None],
    company: uuid.UUID,
    context: TenantContext,
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> None:
    """The case ADR-030 exists for, and the one a tenant-level model would fail.

    Both companies belong to the same tenant, so a tenant-scoped policy would
    show one company's attachments to anyone in the tenant. The second user here
    is a member of the tenant and was granted access to the *second* company
    only -- exactly the holding arrangement `company_access` exists for. An
    invoice PDF carries the partner's bank details, the commercial terms and the
    signatures, not just what the document row holds.

    Note it is a second **user**, not a narrowed context. `app.company_id`
    narrows and does not decide (ADR-004): the policy asks
    `rls.has_company_access`, which reads a grant, not a session variable. A test
    built on the context alone would prove nothing about access.
    """
    with tenant_context(context):
        created = attach(company, world["tenant_a"], world["user_a"])

    other_company = company_of(world["tenant_a"], "1002600000002", "Alpha Services")
    other_user = uuid.uuid4()
    now = datetime.now(UTC)
    seed_system_roles(seed, world["tenant_a"])
    seed(
        'INSERT INTO "user" (id, email, full_name, mfa_enabled, locale, is_active,'
        " created_at, updated_at)"
        " VALUES (%s, 'c@example.md', 'C', false, 'ro', true, %s, %s)",
        [other_user, now, now],
    )
    seed(
        "INSERT INTO membership (id, tenant_id, user_id, role_id, status, invited_at,"
        " accepted_at, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, 'active', %s, %s, %s, %s)",
        [
            uuid.uuid4(),
            world["tenant_a"],
            other_user,
            role_id(world["tenant_a"], "owner"),
            now,
            now,
            now,
            now,
        ],
    )
    grant_company(world["tenant_a"], other_company, other_user, world["user_a"])

    restricted = TenantContext(tenant_id=world["tenant_a"], user_id=other_user, request_id="attach")
    with tenant_context(restricted):
        assert not Attachment.objects.filter(pk=created.pk).exists()


def test_another_tenant_does_not_see_it(
    company: uuid.UUID, context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        created = attach(company, world["tenant_a"], world["user_a"])

    stranger = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="attach"
    )
    with tenant_context(stranger):
        assert not Attachment.objects.filter(pk=created.pk).exists()


def test_an_attachment_cannot_be_written_into_a_company_without_access(
    company: uuid.UUID,
    context: TenantContext,
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
) -> None:
    """`WITH CHECK`, not just `USING`. Without it a caller could file an
    attachment into a company they cannot read -- writing where you cannot see is
    the half of an access rule that is easiest to leave out.
    """
    other = company_of(world["tenant_a"], "1002600000003", "Alpha Logistics")
    with (
        tenant_context(context),
        pytest.raises((ProgrammingError, IntegrityError)),
        transaction.atomic(),
    ):
        attach(other, world["tenant_a"], world["user_a"])


# --- The key --------------------------------------------------------------


def test_the_key_is_derived_and_carries_tenant_and_company_first() -> None:
    """Before OD-52 chooses bucket-per-tenant or prefix-per-tenant, so that
    either choice preserves the boundary and a bucket policy has something to
    stand on.
    """
    tenant_id = uuid.uuid4()
    company_id = uuid.uuid4()
    attachment_id = uuid.uuid4()
    key = object_key(
        tenant_id=tenant_id,
        company_id=company_id,
        attachment_id=attachment_id,
        uploaded_at=datetime(2026, 3, 7, tzinfo=UTC),
    )
    assert key == f"{tenant_id}/{company_id}/2026/03/{attachment_id}"


def test_the_original_filename_never_reaches_the_key(
    company: uuid.UUID, context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    """A filename that reaches a path is how directory traversal gets written.

    The name is kept in a column so a download can return what the user
    recognises; it is not an input to the key.
    """
    with tenant_context(context):
        created = attach(company, world["tenant_a"], world["user_a"])
        created.original_filename = "../../etc/passwd"
        created.save(update_fields=["original_filename"])
        assert ".." not in created.storage_key


def test_two_rows_cannot_point_at_one_object(
    company: uuid.UUID, context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    """Deleting either would break the other."""
    with tenant_context(context):
        created = attach(company, world["tenant_a"], world["user_a"])
        with pytest.raises(IntegrityError), transaction.atomic():
            Attachment.objects.create(
                tenant_id=world["tenant_a"],
                company_id=company,
                storage_key=created.storage_key,
                original_filename="copie.pdf",
                content_type="application/pdf",
                byte_size=1,
                checksum_sha256=CHECKSUM,
                uploaded_by_user_id=world["user_a"],
            )


def test_a_malformed_checksum_is_refused(
    company: uuid.UUID, context: TenantContext, world: dict[str, uuid.UUID]
) -> None:
    """A checksum in the wrong shape compares unequal to a correct one, which
    reads as corruption on every download.
    """
    with (
        tenant_context(context),
        pytest.raises(IntegrityError),
        transaction.atomic(),
    ):
        attachment_id = uuid.uuid4()
        Attachment.objects.create(
            id=attachment_id,
            tenant_id=world["tenant_a"],
            company_id=company,
            storage_key=f"k/{attachment_id}",
            original_filename="x.pdf",
            content_type="application/pdf",
            byte_size=1,
            checksum_sha256="NOT-A-CHECKSUM",
            uploaded_by_user_id=world["user_a"],
        )


# --- Storage refuses when unconfigured ---------------------------------------


def test_an_unconfigured_backend_refuses_rather_than_falling_back() -> None:
    """The failure being guarded against is not an exception.

    It is a filesystem fallback: works in development, passes every test, and
    loses files in production behind a load balancer, where the next request
    reaches a different container.
    """
    storage = get_storage()
    assert isinstance(storage, RefusingStorage)
    for call in (
        lambda: storage.put("k", b"", "application/pdf"),
        lambda: storage.signed_url("k", expires_in=60),
        lambda: storage.delete("k"),
        lambda: storage.exists("k"),
    ):
        with pytest.raises(StorageNotConfiguredError):
            call()
