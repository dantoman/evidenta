"""The tenant comes from the host, and from nowhere else.

Two halves. The first needs no database: extracting a label from a Host header is
string handling, and the cases that matter are the malformed ones. The second
needs the privileged resolver and real rows.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

import pytest
from django.http import HttpRequest
from django.test import RequestFactory

from evidenta.platform.rls.context import TenantContext, tenant_context
from evidenta.platform.rls.middleware import TenantResolutionError
from evidenta.platform.tenancy.middleware import SubdomainTenantResolver
from evidenta.platform.tenancy.subdomain import resolve_tenant, subdomain_of

BASE = "evidenta.md"


@pytest.mark.parametrize(
    ("host", "expected"),
    [
        ("alpha.evidenta.md", "alpha"),
        ("ALPHA.evidenta.md", "alpha"),
        ("alpha.evidenta.md:8000", "alpha"),
        ("alpha.evidenta.md.", "alpha"),
        # No label, or the base domain itself.
        ("evidenta.md", None),
        ("", None),
        # Someone else's domain that merely ends similarly.
        ("alpha.notevidenta.md", None),
        # Deeper nesting is not a tenant name.
        ("a.b.evidenta.md", None),
        # Reserved: a tenant called `api` would shadow the API host.
        ("api.evidenta.md", None),
        ("www.evidenta.md", None),
        # Malformed against the same pattern the database enforces.
        ("ab.evidenta.md", None),
        ("-alpha.evidenta.md", None),
        ("Alpha_Beta.evidenta.md", None),
    ],
)
def test_subdomain_extraction(host: str, expected: str | None) -> None:
    assert subdomain_of(host, BASE) == expected


def test_a_similar_looking_domain_is_not_a_suffix_match() -> None:
    """The check is on the dot-prefixed suffix, not on ``endswith``.

    ``notevidenta.md`` ends with ``evidenta.md``. A naive suffix test would hand
    a tenant label to whoever registers the neighbouring domain.
    """
    assert subdomain_of("alpha.notevidenta.md", BASE) is None


pytestmark_db = pytest.mark.django_db(databases=["default", "migration"])


@pytestmark_db
def test_resolver_finds_a_real_tenant(world: dict[str, uuid.UUID]) -> None:
    resolved = resolve_tenant("alpha")
    assert resolved is not None
    assert resolved.tenant_id == world["tenant_a"]
    assert resolved.status == "active"


@pytestmark_db
def test_resolver_returns_nothing_for_an_unknown_subdomain(
    world: dict[str, uuid.UUID],
) -> None:
    assert resolve_tenant("nimeni") is None


@pytestmark_db
def test_resolution_works_before_any_context_exists(
    world: dict[str, uuid.UUID],
) -> None:
    """The point of the privileged path.

    No tenant_context is open here. The ordinary policy on ``tenant`` could not
    answer -- it requires the very thing being resolved.
    """
    assert resolve_tenant("beta") is not None


@pytestmark_db
def test_full_resolution_produces_the_context(world: dict[str, uuid.UUID]) -> None:
    request = RequestFactory().get("/", headers={"host": "alpha.evidenta.md"})
    request.authenticated_user_id = world["user_a"]  # type: ignore[attr-defined]
    request.authenticated_tenant_id = world["tenant_a"]  # type: ignore[attr-defined]
    context = SubdomainTenantResolver(BASE)(request)
    # A tenant host yields a tenant context, never the console's (ADR-076).
    assert isinstance(context, TenantContext)
    assert context.tenant_id == world["tenant_a"]

    with tenant_context(context):
        pass  # the context is usable, which is the whole claim


@pytestmark_db
def test_unknown_and_inactive_tenants_are_indistinguishable(
    world: dict[str, uuid.UUID], seed: Callable[..., None]
) -> None:
    """IZ-37. Both answer the same, so the login page is not a directory."""
    seed("UPDATE tenant SET status = 'suspended' WHERE subdomain = 'beta'")
    resolver = SubdomainTenantResolver(BASE)

    messages = []
    for host in ("beta.evidenta.md", "nimeni.evidenta.md"):
        request = RequestFactory().get("/", headers={"host": host})
        request.authenticated_user_id = world["user_a"]  # type: ignore[attr-defined]
        with pytest.raises(TenantResolutionError) as caught:
            resolver(request)
        messages.append(str(caught.value))

    assert messages[0] == messages[1]


@pytestmark_db
@pytest.mark.parametrize(
    "make_request",
    [
        pytest.param(
            lambda tenant: RequestFactory().get(
                f"/?tenant_id={tenant}", headers={"host": "alpha.evidenta.md"}
            ),
            id="query-parameter",
        ),
        pytest.param(
            lambda tenant: RequestFactory().get(
                "/",
                headers={"host": "alpha.evidenta.md", "x-tenant-id": str(tenant)},
            ),
            id="header",
        ),
    ],
)
def test_a_client_stated_tenant_that_disagrees_is_refused(
    world: dict[str, uuid.UUID], make_request: Callable[[uuid.UUID], HttpRequest]
) -> None:
    """IZ-36.

    Ignoring it silently would be enough for isolation -- the context comes from
    the host either way. It is not enough for detection: a client sending a
    foreign tenant_id is broken or probing, and both are worth seeing.
    """
    request = make_request(world["tenant_b"])
    request.authenticated_user_id = world["user_a"]  # type: ignore[attr-defined]
    with pytest.raises(TenantResolutionError, match="disagrees"):
        SubdomainTenantResolver(BASE)(request)


@pytestmark_db
def test_a_matching_client_stated_tenant_is_accepted(
    world: dict[str, uuid.UUID],
) -> None:
    """Agreement is not an error -- only disagreement is."""
    request = RequestFactory().get(
        f"/?tenant_id={world['tenant_a']}", headers={"host": "alpha.evidenta.md"}
    )
    request.authenticated_user_id = world["user_a"]  # type: ignore[attr-defined]
    request.authenticated_tenant_id = world["tenant_a"]  # type: ignore[attr-defined]
    context = SubdomainTenantResolver(BASE)(request)
    assert isinstance(context, TenantContext)
    assert context.tenant_id == world["tenant_a"]


@pytestmark_db
def test_no_authenticated_user_is_refused(world: dict[str, uuid.UUID]) -> None:
    """Fail-closed. A resolver that defaulted to some user would work in
    development and be a hole in production."""
    request = RequestFactory().get("/", headers={"host": "alpha.evidenta.md"})
    with pytest.raises(TenantResolutionError, match="authenticated"):
        SubdomainTenantResolver(BASE)(request)


@pytestmark_db
def test_a_session_of_another_tenant_is_refused(world: dict[str, uuid.UUID]) -> None:
    """The identity is real; the tenant it was issued for is not this host's.

    RLS alone would answer with an empty result set -- correct, and
    indistinguishable from a tenant that has no data. The refusal names it.
    """
    request = RequestFactory().get("/", headers={"host": "alpha.evidenta.md"})
    request.authenticated_user_id = world["user_b"]  # type: ignore[attr-defined]
    request.authenticated_tenant_id = world["tenant_b"]  # type: ignore[attr-defined]
    with pytest.raises(TenantResolutionError) as caught:
        SubdomainTenantResolver(BASE)(request)
    assert caught.value.code == "auth.session_tenant_mismatch"
