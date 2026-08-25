"""Restricted scope: the cases where an engagement exists and still says no.

T2 lists "engagement cu scope restrâns" as mandatory, and it is the one of the
four that had nothing behind it. The reason is worth stating, because the tests
below read very differently once it is known:

``covers_all_companies`` appeared **zero times** in all of ``infra/``. It was
written by the lifecycle service and read by nothing -- so an engagement declared
as covering every company covered, in fact, exactly the companies for which
somebody had already inserted a ``company_access`` row by hand. The column
promised a rule nobody enforced.

Enforcement sits at provisioning rather than in the predicate (owner's decision):
``rls.has_company_access`` is unchanged and access is still a row, not a
deduction. What changed is who writes the row -- see ``0032``.

One thing these tests do **not** show, and it would be easy to read them as if
they did: ``engagement_company_scope`` is still consulted by nothing. IZ-25 holds
because no row grants access to B2 and propagation declines to make one, not
because the scope table was read. The initial grant -- who serves this client at
all -- is ``OD-42``, still open.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

import pytest
from django.db import connection, transaction

from evidenta.platform.engagement.services.provisioning import provision_company_access
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


def acting_for_firm(tenant_id: uuid.UUID, user_id: uuid.UUID, firm_id: uuid.UUID) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id, user_id=user_id, request_id="test", actor_firm_id=firm_id
    )


def visible_companies() -> list[uuid.UUID]:
    with connection.cursor() as cursor:
        cursor.execute("SELECT id FROM company ORDER BY id")
        return [row[0] for row in cursor.fetchall()]


@pytest.fixture
def served(
    firm_world: dict[str, uuid.UUID],
    engage: Callable[..., uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> Callable[..., dict[str, uuid.UUID]]:
    """A firm serving tenant B, holding access to exactly one of its companies.

    The starting position for all three scenarios: company B1 exists and is
    served, and whether B2 becomes visible is what each test is about.
    """

    def make(*, covers_all_companies: bool) -> dict[str, uuid.UUID]:
        ids = dict(firm_world)
        ids["engagement"] = engage(
            ids["firm"],
            ids["tenant_b"],
            ids["user_f"],
            covers_all_companies=covers_all_companies,
        )
        ids["company_b1"] = company_of(ids["tenant_b"], "1000000000001", "Beta Unu SRL")
        grant_company(
            ids["tenant_b"],
            ids["company_b1"],
            ids["user_f"],
            ids["user_b"],
            via="engagement",
            engagement_id=ids["engagement"],
        )
        return ids

    return make


def test_a_company_outside_the_scope_is_not_visible(
    served: Callable[..., dict[str, uuid.UUID]], company_of: Callable[..., uuid.UUID]
) -> None:
    """IZ-25. The engagement is live, and B2 is still nobody's business.

    Note what is *not* the reason: the firm passes the tenant-level check, so it
    reads tenant B perfectly well. The refusal is one level down, at the company,
    and it comes from the absence of a grant.
    """
    ids = served(covers_all_companies=False)
    company_b2 = company_of(ids["tenant_b"], "1000000000002", "Beta Doi SRL")

    with tenant_context(acting_for_firm(ids["tenant_b"], ids["user_f"], ids["firm"])):
        visible = visible_companies()

    assert ids["company_b1"] in visible
    assert company_b2 not in visible


def test_a_company_created_later_is_not_granted_automatically(
    served: Callable[..., dict[str, uuid.UUID]], company_of: Callable[..., uuid.UUID]
) -> None:
    """IZ-26. Provisioning runs, and declines.

    The assertion that matters is the count. A provisioning that silently granted
    nothing because it was never called would satisfy the visibility check below
    just as well, and would break the day it started being called.
    """
    ids = served(covers_all_companies=False)
    company_b2 = company_of(ids["tenant_b"], "1000000000002", "Beta Doi SRL")

    with tenant_context(acting_for_firm(ids["tenant_b"], ids["user_f"], ids["firm"])):
        result = provision_company_access(company_b2)
        visible = visible_companies()

    assert result.access_granted == 0
    assert company_b2 not in visible


def test_a_company_created_later_is_granted_when_the_engagement_covers_all(
    served: Callable[..., dict[str, uuid.UUID]], company_of: Callable[..., uuid.UUID]
) -> None:
    """IZ-27. The same call, the other answer, and the column finally decides it."""
    ids = served(covers_all_companies=True)
    company_b2 = company_of(ids["tenant_b"], "1000000000002", "Beta Doi SRL")

    with tenant_context(acting_for_firm(ids["tenant_b"], ids["user_f"], ids["firm"])):
        result = provision_company_access(company_b2)
        visible = visible_companies()

    assert result.access_granted == 1
    assert company_b2 in visible


def test_provisioning_twice_grants_once(
    served: Callable[..., dict[str, uuid.UUID]], company_of: Callable[..., uuid.UUID]
) -> None:
    """Whatever ends up calling this will call it twice eventually.

    A retry, a resumed import, two screens racing. The second call must be a
    no-op rather than a constraint violation surfacing as a 500 on a screen that
    did nothing wrong.
    """
    ids = served(covers_all_companies=True)
    company_b2 = company_of(ids["tenant_b"], "1000000000002", "Beta Doi SRL")

    with tenant_context(acting_for_firm(ids["tenant_b"], ids["user_f"], ids["firm"])):
        first = provision_company_access(company_b2)
        second = provision_company_access(company_b2)

    assert (first.access_granted, second.access_granted) == (1, 0)


def test_provisioning_a_company_of_another_tenant_is_refused(
    served: Callable[..., dict[str, uuid.UUID]], company_of: Callable[..., uuid.UUID]
) -> None:
    """The safety condition, mirroring the one on revocation.

    Without it the function would be a way in rather than a way through: knowing
    a uuid would be enough to extend somebody else's grants. The firm serves
    tenant B and has no business with tenant A's companies.
    """
    ids = served(covers_all_companies=True)
    company_a = company_of(ids["tenant_a"], "1000000000003", "Alpha Unu SRL")

    with tenant_context(acting_for_firm(ids["tenant_b"], ids["user_f"], ids["firm"])):
        # The savepoint is not ceremony: the refusal aborts the transaction, and
        # without one the context manager's own exit query fails on the way out,
        # turning a clean refusal into an unrelated error.
        with pytest.raises(Exception, match="fara drept asupra tenantului"), transaction.atomic():
            provision_company_access(company_a)

        # Still usable afterwards, which is the point of refusing this way.
        assert ids["company_b1"] in visible_companies()
