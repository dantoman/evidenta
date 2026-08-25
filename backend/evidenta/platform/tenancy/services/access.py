"""What `tenancy` answers for other modules about access.

`D6` sends services through a module's public surface rather than its models, and
this is that surface for the one question other modules actually ask: may the
current context see this tenant at all.

The answer is not computed here. It is asked of the database, because the
database is where the rule lives.
"""

from __future__ import annotations

import uuid

from evidenta.platform.tenancy.models import Company, Tenant


def tenant_visible_in_context(tenant_id: uuid.UUID) -> bool:
    """Whether the tenant row is visible under the context currently set.

    ``Tenant`` carries the policy ``id = app.current_tenant_id() AND
    rls.has_tenant_access(id)``, so asking whether the row is visible asks the
    database the same question every later query will ask -- through membership
    for a member, through the engagement for a firm's user. Re-implementing that
    test in the caller would be a second copy of the access rule, free to drift
    from the one that actually guards the data.

    Requires a context to be set; without one the query guard refuses before this
    returns anything, which is the intended failure and not an edge case.
    """
    return Tenant.objects.filter(pk=tenant_id).exists()


def company_visible_in_context(company_id: uuid.UUID) -> bool:
    """Whether the company row is visible under the context currently set.

    The companion of ``tenant_visible_in_context``, and the same argument: the
    policy on ``company`` requires the tenant in context *and*
    ``rls.has_company_access(id)``, so asking whether the row is visible asks the
    database exactly what every later query will ask.

    It answers one question and returns a boolean, deliberately. A helper that
    returned the row would hand another module ``Company`` itself, and the
    caller would start reading fields off it -- which is the coupling `D6` is
    about, arriving through a service instead of an import.
    """
    return Company.objects.filter(pk=company_id).exists()
