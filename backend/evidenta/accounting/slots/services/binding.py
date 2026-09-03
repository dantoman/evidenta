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
from typing import Any

from django.db import transaction
from django.db.models import Q

from evidenta.accounting.coa.services.accounts import declare_dimension_slots, postable_accounts
from evidenta.accounting.slots.catalogue import DEFAULTS, ROLES, RoleDefault
from evidenta.accounting.slots.models import AccountRoleBinding
from evidenta.platform.api.errors import ApiError
from evidenta.platform.api.lookup import NotFoundError
from evidenta.platform.audit.services.recording import record
from evidenta.platform.tenancy.services.access import company_visible_in_context

#: What a binding made from the screen says about where it came from. The
#: defaults cite the plan; a departure from it cites the company, because the
#: company is who can defend it at an inspection.
COMPANY_SOURCE = "company"


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


class RoleAccountNotPostableError(ApiError):
    """The account chosen for a role cannot receive a posting on the date.

    Absent from the chart, closed by then, or blocked -- the same three cases
    `postable_accounts` excludes, and the same reason: a binding that names an
    account no posting may use is a binding that fails at the first posting,
    which is the moment chosen by a transaction rather than by anybody.
    """

    code = "slots.account_not_postable"
    status = 409


class AccountClassMismatchError(ApiError):
    """The account is in another class than the one the plan imposes for the role.

    A role names a meaning -- receivables, VAT collected, the till -- and the
    plan fixes which class that meaning lives in. A company may keep its own
    analytic under that class; it may not decide that the till is a liability.
    Refused rather than accepted with a warning, because a warning is what gets
    clicked past and the balance sheet is what gets read.
    """

    code = "slots.account_class_mismatch"
    status = 409


class RebindingBeforeCurrentError(ApiError):
    """The new binding would start on or before the one already in force starts.

    History, not overwrite: a rebinding closes the current binding on the date
    the new one starts, so the postings made before that date keep resolving to
    the account they resolved to (`R18`). A start date at or before the current
    one would have to rewrite that history, and a binding dated the same day
    would leave two answers for the postings of that day.
    """

    code = "slots.rebinding_before_current"
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
    _declare_role_slots(accounts)
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


def role_overview(company_id: uuid.UUID, on_date: date) -> list[dict[str, object]]:
    """Every role of the catalogue, with what it resolves to on the date -- or nothing.

    The screen's shape rather than the audit's: a role the company has not
    bound is a row here, with the account the plan imposes beside the empty
    binding, because the screen exists precisely for the row that is empty.
    `bindings_of` says what *is* bound; this says what *should* be.
    """
    bound = {str(row["role"]): row for row in bindings_of(company_id, on_date)}
    overview: list[dict[str, object]] = []
    for default in sorted(DEFAULTS, key=lambda d: d.role):
        binding = bound.get(default.role)
        overview.append(
            {
                "role": default.role,
                "default_code": default.account_code,
                "dimension_slots": list(default.dimension_slots),
                "account_id": binding["account_id"] if binding else None,
                "account_code": binding["account_code"] if binding else None,
                "name_ro": binding["name_ro"] if binding else None,
                "valid_from": binding["valid_from"] if binding else None,
                "source": binding["source"] if binding else None,
            }
        )
    return overview


@transaction.atomic
def rebind_role(
    *, company_id: uuid.UUID, role: str, account_id: uuid.UUID, valid_from: date
) -> AccountRoleBinding:
    """Bind a role to another account of the company, from a date.

    History, never overwrite. The binding in force is closed on ``valid_from``
    (half-open, so the day itself belongs to the new one) and a new binding
    opens there with the company as its source. A posting dated before that day
    keeps resolving to the old account and a posting dated on or after it
    reaches the new one -- nothing already posted moves (`R10`, `R18`), and the
    ledger is not consulted here because it has nothing to say: the binding
    decides what a *future* resolution answers, not what a past one did.

    Four refusals, each with its own code, in the order a person can act on
    them: an unknown role is a typo; a company this context cannot see is a
    404 that says nothing (IZ-04); an account no posting may use on the date is
    a binding that would fail later; an account of another class is a meaning
    the plan does not allow the company to move; a start on or before the
    current binding's start would rewrite history.
    """
    default = _default_of(role)
    if not company_visible_in_context(company_id):
        raise NotFoundError(f"company {company_id} is not visible in this context")

    account = next(
        (row for row in postable_accounts(company_id, valid_from) if row.id == account_id), None
    )
    if account is None:
        raise RoleAccountNotPostableError(
            f"account {account_id} cannot receive a posting for company {company_id} "
            f"on {valid_from}: it is absent from the chart, not yet or no longer "
            f"valid, or blocked. A role bound to it would fail at the first posting"
        )
    if _class_of(account.account_code) != _class_of(default.account_code):
        raise AccountClassMismatchError(
            f"{role} means an account of class {_class_of(default.account_code)} "
            f"({default.account_code} in the plan); {account.account_code} is in "
            f"class {_class_of(account.account_code)}. A company keeps its own "
            f"analytic under the class the plan fixes, it does not move the meaning"
        )

    current = (
        AccountRoleBinding.objects.filter(company_id=company_id, role=role)
        .order_by("-valid_from")
        .select_related("account")
        .first()
    )
    old: dict[str, Any] | None = None
    if current is not None:
        if valid_from <= current.valid_from:
            raise RebindingBeforeCurrentError(
                f"{role} is bound to {current.account.account_code} from "
                f"{current.valid_from}; a new binding has to start after that day. "
                f"The postings before it keep the account they were made with"
            )
        old = {
            "account_id": str(current.account_id),
            "account_code": current.account.account_code,
            "valid_from": current.valid_from.isoformat(),
            "valid_to": current.valid_to.isoformat() if current.valid_to else None,
        }
        if current.valid_to is None or current.valid_to > valid_from:
            current.valid_to = valid_from
            current.save(update_fields=["valid_to", "updated_at"])

    _declare_slots_for(default, account)
    binding = AccountRoleBinding.objects.create(
        tenant_id=account.tenant_id,
        company_id=company_id,
        role=role,
        account=account,
        valid_from=valid_from,
        source=COMPANY_SOURCE,
    )
    record(
        action="slots.role_rebound",
        entity_type="account_role_binding",
        entity_id=binding.id,
        company_id=company_id,
        old_value=old,
        new_value={
            "role": role,
            "account_id": str(account.id),
            "account_code": account.account_code,
            "valid_from": valid_from.isoformat(),
        },
    )
    return binding


def _default_of(role: str) -> RoleDefault:
    """The catalogue's row for the role, or the refusal `resolve_role` gives."""
    for default in DEFAULTS:
        if default.role == role:
            return default
    raise UnknownRoleError(
        f"{role!r} is not an account role. The catalogue is code, so this is a "
        f"typo rather than a missing configuration"
    )


def _class_of(account_code: str) -> str:
    """The class of an account, which the plan writes as the first digit of its code."""
    return account_code[:1]


def _declare_role_slots(accounts: dict[str, Any]) -> None:
    """Make every account a role names carry the dimensions that role's postings set.

    ADR-065 section 8.4: without `employee` declared on 5311 and the two
    personnel-cost accounts, the value reaches no formula however many slots
    exist -- the entry balances and the person is gone. The catalogue says which
    roles need which slots; this extends the account's declaration and never
    narrows it, and a second run changes nothing.
    """
    for default in DEFAULTS:
        if default.dimension_slots:
            _declare_slots_for(default, accounts[default.account_code])


def _declare_slots_for(default: RoleDefault, account: Any) -> None:
    """One role, one account: extend the declaration, never narrow it.

    Shared by the installation and by a rebinding, because the rebinding is
    exactly where the case of ADR-065 section 8.4 comes back: a company that
    moves its salary liability to its own analytic has moved it to an account
    that declares nothing, and the employee would vanish from the next run.
    """
    if not default.dimension_slots:
        return
    declared = account.declared_slots()
    missing = [slot for slot in default.dimension_slots if slot not in declared]
    if missing:
        declare_dimension_slots(account.id, [*declared, *missing])
