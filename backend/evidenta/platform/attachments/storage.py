"""The storage contract -- written, with no provider chosen.

`OD-52` is open: bucket per tenant or prefix per tenant, how URLs are signed and
for how long, the size and type limits, whether files are scanned, and what
happens to objects when a tenant reaches `archived`. None of that is decided
here, and none of it is guessed.

What *is* decided, because it holds whichever way OD-52 lands:

* **the object key is derived, never supplied** -- `object_key` below;
* **the key carries tenant and company first**, so any layout preserves the
  isolation boundary and a bucket policy written later has something to stand on;
* **an unconfigured deployment refuses** rather than silently doing nothing. Same
  shape as the tenant resolver: `RLS_CONTEXT_RESOLVER` unset means refuse-all,
  because a storage backend that quietly accepted uploads and dropped them would
  be discovered by a client who cannot find their invoice.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Protocol

from django.conf import settings
from django.utils.module_loading import import_string


class StorageNotConfiguredError(RuntimeError):
    """No storage backend is configured, and there is no safe default.

    Refusing is the whole point. The alternative -- a local-filesystem default --
    would work in development, pass every test, and lose files in production
    behind a load balancer.
    """


class AttachmentStorage(Protocol):
    """What a backend has to provide. Deliberately four methods.

    `signed_url` takes the key and nothing about the caller: authorisation
    happened before, in the database, when the caller could see the metadata row
    at all. A backend that re-derived permission from the key would be a second
    copy of the access rule.
    """

    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    def signed_url(self, key: str, *, expires_in: int) -> str: ...

    def delete(self, key: str) -> None: ...

    def exists(self, key: str) -> bool: ...


class RefusingStorage:
    """The default. Every call raises, naming OD-52."""

    def _refuse(self) -> None:
        raise StorageNotConfiguredError(
            "no attachment storage backend is configured. ATTACHMENT_STORAGE is "
            "unset and there is no default: OD-52 has not chosen a provider, and "
            "a filesystem fallback would pass every test and lose files in "
            "production."
        )

    def put(self, key: str, data: bytes, content_type: str) -> None:
        self._refuse()

    def signed_url(self, key: str, *, expires_in: int) -> str:
        self._refuse()
        raise AssertionError("unreachable")

    def delete(self, key: str) -> None:
        self._refuse()

    def exists(self, key: str) -> bool:
        self._refuse()
        raise AssertionError("unreachable")


def get_storage() -> AttachmentStorage:
    dotted = getattr(settings, "ATTACHMENT_STORAGE", None)
    if not dotted:
        return RefusingStorage()
    factory = import_string(dotted)
    storage: AttachmentStorage = factory()
    return storage


def object_key(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    attachment_id: uuid.UUID,
    uploaded_at: datetime,
) -> str:
    """The key for one object. Derived from identifiers only.

    The original filename does not appear. A filename that reaches a path is how
    directory traversal gets written, and a server-generated `attachment_id`
    makes the key unguessable -- which matters for whatever URL-signing scheme
    OD-52 settles on.

    Tenant and company lead, before the decision on bucket-per-tenant versus
    prefix-per-tenant, so that either choice preserves the boundary.
    """
    return f"{tenant_id}/{company_id}/{uploaded_at:%Y/%m}/{attachment_id}"
