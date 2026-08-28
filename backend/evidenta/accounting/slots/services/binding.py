"""Installing a company's role bindings, and resolving one at posting.

``resolve_role`` is the only way a handler reaches an account. It refuses rather
than falling back: an unbound role means the company's chart cannot express what
the treatment needs, and posting anyway would put the amount somewhere plausible
and wrong. A wrong account balances just as well as a right one, which is why
this failure has to be loud at the moment it happens.
"""

from __future__ import annotations

import uuid
from datetime import date

from django.db.models import Q

from evidenta.accounting.coa.services.accounts import postable_accounts
from evidenta.accounting.slots.catalogue import DEFAULTS, ROLES
from evidenta.accounting.slots.models import AccountRoleBinding
from evidenta.platform.api.errors import ApiError


class UnknownRoleError(ApiError):
    """A role outside the catalogue. Refused before anything is written."""

    code = "slots.role_unknown"
    status = 422


class RoleNotBoundError(ApiError):
    """The company has no account for this role on this date.

    Not a default and not a guess: the treatment needs an account the chart does
    not offer, and the person who can answer that is an accountant.
    """

    code = "slots.role_not_bound"
    status = 409


class RoleAccountMissingError(ApiError):
    """The mapping names a subaccount this company's chart does not contain."""

    code = "slots.role_account_missing"
    status = 409


def resolve_role(company_id: uuid.UUID, role: str, on_date: date) -> uuid.UUID:
    """The account this role means for this company on this date.

    The date is the posting's, never today (`R17`, `R18`): recalculating March in
    June has to reach the account March reached.
    """
    if role not in ROLES:
        raise UnknownRoleError(
            f"{role!r} is not an account role. The catalogue is code, so this is a "
            f"typo rather than a missing configuration"
        )
    binding = (
        AccountRoleBinding.objects.filter(company_id=company_id, role=role, valid_from__lte=on_date)
        .filter(Q(valid_to__isnull=True) | Q(valid_to__gt=on_date))
        .first()
    )
    if binding is None:
        raise RoleNotBoundError(
            f"company {company_id} has no account bound to {role} on {on_date}. "
            f"Posting would have to pick one, and a wrong account balances exactly "
            f"as well as a right one"
        )
    return uuid.UUID(str(binding.account_id))


def install_default_bindings(
    *, tenant_id: uuid.UUID, company_id: uuid.UUID, on_date: date
) -> list[AccountRoleBinding]:
    """Bind every role to the account the plan imposes for it.

    The plan fixes all four levels, so there is one correct answer per role and
    no configurable default to choose. What this does is make that answer
    explicit and dated for a company, so that resolution is a lookup rather than
    a rule compiled into the engine.

    Refuses loudly on a missing account instead of skipping the role: a partially
    bound company posts correctly until the day it meets the role nobody
    installed, and that day is chosen by the transaction, not by anybody.
    """
    # Through `coa`'s own service, not through its models (`D6`). It also
    # answers the right question: a role has to bind to an account a posting may
    # actually use, so blocked and out-of-force accounts are excluded here rather
    # than discovered at the first posting that needs them.
    accounts = {account.account_code: account for account in postable_accounts(company_id, on_date)}

    missing = sorted({default.account_code for default in DEFAULTS} - set(accounts))
    if missing:
        raise RoleAccountMissingError(
            f"company {company_id} has no account for {', '.join(missing)} on "
            f"{on_date}; the role mapping names subaccounts of the general plan, "
            f"so a chart without them is not the plan"
        )

    existing = set(
        AccountRoleBinding.objects.filter(company_id=company_id).values_list("role", flat=True)
    )
    return AccountRoleBinding.objects.bulk_create(
        [
            AccountRoleBinding(
                tenant_id=tenant_id,
                company_id=company_id,
                role=default.role,
                account=accounts[default.account_code],
                valid_from=max(default.valid_from, on_date),
                source=default.source,
            )
            for default in DEFAULTS
            if default.role not in existing
        ]
    )


def bindings_of(company_id: uuid.UUID, on_date: date) -> list[dict[str, object]]:
    """What every role resolves to, for a screen or for an audit."""
    rows = (
        AccountRoleBinding.objects.filter(company_id=company_id, valid_from__lte=on_date)
        .filter(Q(valid_to__isnull=True) | Q(valid_to__gt=on_date))
        .select_related("account")
        .order_by("role")
    )
    return [
        {
            "role": row.role,
            "account_id": str(row.account_id),
            "account_code": row.account.account_code,
            "name_ro": row.account.name_ro,
            "valid_from": row.valid_from.isoformat(),
            "source": row.source,
        }
        for row in rows
    ]
