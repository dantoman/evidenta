"""What a company may do to its own chart -- Spec B section 2.4.

The table in that section is short and every row is a refusal somewhere:

    renaming        system accounts no, own subaccounts yes
    deletion        never, for either
    closing         ``valid_to``
    blocking        ``is_blocked``

Deletion has no function here. That is the refusal -- and it is not the only one:
the application role holds no DELETE privilege on ``company_account`` or
``company_chart`` (``infra/migrations/0033_coa``). A service-level check alone
would be bypassed by the 1C importer and by any data migration, which is exactly
where a chart gets mangled.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import date

from django.db import transaction

from evidenta.accounting.coa.dimensions import DIMENSION_KEYS
from evidenta.accounting.coa.errors import (
    AccountCodeTakenError,
    AccountNotFoundError,
    InvalidValidityWindowError,
    ParentAccountClosedError,
    SubaccountsNotAllowedError,
    SystemAccountImmutableError,
    UnknownDimensionError,
)
from evidenta.accounting.coa.models import AccountOrigin, CompanyAccount
from evidenta.fiscal.parameters.services.resolution import in_force
from evidenta.platform.audit.services.recording import record


def _account(account_id: uuid.UUID) -> CompanyAccount:
    """The account, or a refusal that does not say whose it is.

    RLS has already narrowed the table to this context, so "not found" covers
    both "no such account" and "not yours" -- IZ-04, and the only answer that
    does not leak the existence of another tenant's row.
    """
    account = CompanyAccount.objects.filter(id=account_id).first()
    if account is None:
        raise AccountNotFoundError(f"account {account_id} is not visible in this context")
    return account


def _audit(
    action: str,
    account: CompanyAccount,
    *,
    old: dict[str, object] | None = None,
    new: dict[str, object] | None = None,
) -> None:
    """Every change to a chart, recorded from the service that made it.

    Explicit rather than through a signal (C4). The question this answers is the
    one that gets asked months later, when a report changed shape: who blocked
    that account, and when. Row timestamps cannot answer it -- they say the row
    changed, not who changed it or what it was before.
    """
    record(
        action=action,
        entity_type="company_account",
        entity_id=account.id,
        company_id=account.company_id,
        old_value=old,
        new_value=new,
    )


def _check_dimensions(required: Sequence[str]) -> list[str]:
    unknown = sorted(set(required) - set(DIMENSION_KEYS))
    if unknown:
        raise UnknownDimensionError(
            f"{', '.join(unknown)} is not in the closed vocabulary of ADR-029; "
            f"an account requiring a dimension no journal line carries would "
            f"refuse every posting made to it"
        )
    return list(required)


@transaction.atomic
def create_subaccount(
    parent_id: uuid.UUID,
    account_code: str,
    name_ro: str,
    valid_from: date,
    *,
    currency_tracking: bool = False,
    quantity_tracking: bool = False,
    required_dimensions: Sequence[str] = (),
    allows_subaccounts: bool = False,
) -> CompanyAccount:
    """A subaccount of the company's own, under an account that permits them.

    ``account_class`` and ``normal_balance`` are **inherited, not passed**. A
    subaccount rolls up into its parent; one classified differently would make
    the roll-up mean nothing, and offering the caller the choice would only be
    offering them the mistake.

    No rule is imposed on the shape of the code beyond uniqueness within the
    company. Extending the parent's code is the usual practice, but "usual" is
    not a rule this repository can cite, and inventing one here would refuse
    charts that are already in use elsewhere.
    """
    parent = _account(parent_id)
    if not parent.allows_subaccounts:
        raise SubaccountsNotAllowedError(
            f"account {parent.account_code} does not allow subaccounts"
        )
    if parent.valid_to is not None and parent.valid_to <= valid_from:
        raise ParentAccountClosedError(
            f"account {parent.account_code} stops being valid on {parent.valid_to}, "
            f"before the subaccount would start on {valid_from}"
        )
    if valid_from < parent.valid_from:
        raise InvalidValidityWindowError(
            f"a subaccount cannot be valid from {valid_from}, before its parent "
            f"{parent.account_code} is ({parent.valid_from})"
        )
    if CompanyAccount.objects.filter(
        company_id=parent.company_id, account_code=account_code
    ).exists():
        raise AccountCodeTakenError(f"{account_code} already exists in this company's chart")

    account = CompanyAccount.objects.create(
        tenant_id=parent.tenant_id,
        company_id=parent.company_id,
        account_code=account_code,
        parent=parent,
        origin=AccountOrigin.COMPANY,
        template_account=None,
        name_ro=name_ro,
        account_class=parent.account_class,
        normal_balance=parent.normal_balance,
        allows_subaccounts=allows_subaccounts,
        currency_tracking=currency_tracking,
        quantity_tracking=quantity_tracking,
        required_dimensions=_check_dimensions(required_dimensions),
        valid_from=valid_from,
    )
    _audit("coa.subaccount_created", account, new={"account_code": account_code, "name": name_ro})
    return account


@transaction.atomic
def rename_account(account_id: uuid.UUID, name_ro: str) -> CompanyAccount:
    """Rename a company's own subaccount. System accounts are refused.

    A system account carries the name from the act that published it, and the
    same name has to read the same way in every company's register. Renaming one
    locally would produce a trial balance whose line is unrecognisable against
    anybody else's -- and the propagation policy (`OD-03`) would then have to
    decide whether a central rename overwrites it, which is a question nobody
    should have to answer.
    """
    account = _account(account_id)
    if account.origin == AccountOrigin.SYSTEM:
        raise SystemAccountImmutableError(
            f"{account.account_code} comes from the template and is maintained centrally"
        )
    previous = account.name_ro
    account.name_ro = name_ro
    account.save(update_fields=["name_ro", "updated_at"])
    _audit("coa.account_renamed", account, old={"name": previous}, new={"name": name_ro})
    return account


@transaction.atomic
def set_blocked(account_id: uuid.UUID, blocked: bool) -> CompanyAccount:
    """Forbid or re-allow postings, without touching history.

    Allowed on system accounts too: a company that does not use an account of the
    published chart is making a decision about its own bookkeeping, not about
    what the account is.
    """
    account = _account(account_id)
    previous = account.is_blocked
    account.is_blocked = blocked
    account.save(update_fields=["is_blocked", "updated_at"])
    _audit(
        "coa.account_blocked" if blocked else "coa.account_unblocked",
        account,
        old={"is_blocked": previous},
        new={"is_blocked": blocked},
    )
    return account


@transaction.atomic
def close_account(account_id: uuid.UUID, valid_to: date) -> CompanyAccount:
    """Stop an account from being valid, from a date. Never a deletion.

    The half-open window is ``[valid_from, valid_to)``, so the account is valid up
    to but not including ``valid_to`` -- the same convention the fiscal resolver
    uses, and the reason ``in_force`` is imported rather than reimplemented.
    """
    account = _account(account_id)
    if valid_to <= account.valid_from:
        raise InvalidValidityWindowError(
            f"{account.account_code} is valid from {account.valid_from}; it cannot "
            f"stop on {valid_to}"
        )
    previous = account.valid_to
    account.valid_to = valid_to
    account.save(update_fields=["valid_to", "updated_at"])
    _audit(
        "coa.account_closed",
        account,
        old={"valid_to": previous.isoformat() if previous else None},
        new={"valid_to": valid_to.isoformat()},
    )
    return account


def postable_accounts(company_id: uuid.UUID, on_date: date) -> list[CompanyAccount]:
    """Accounts a posting dated ``on_date`` may use.

    The date is a parameter and the clock is never read. A resolver that could
    fall back to "today" would answer a recalculation of a closed period with
    this year's chart -- silently, and looking correct.
    """
    rows = in_force(CompanyAccount.objects.filter(company_id=company_id, is_blocked=False), on_date)
    return list(rows.order_by("account_code"))
