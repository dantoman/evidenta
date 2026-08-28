"""Refusals from the chart of accounts, each with a stable code -- C10.

Codes are the contract, messages are for the human reading the log. Every one of
them is a refusal a caller can reasonably branch on: an account code already
taken is a form error, a system account being immutable is not.

They subclass ``ApiError`` so the middleware renders them with their code even
when they surface through a plain Django view -- C10 is a guarantee about the
API, not about DRF.
"""

from __future__ import annotations

from evidenta.platform.api.errors import ApiError


class ChartAlreadyInstantiatedError(ApiError):
    """A company has exactly one chart. A second would be a second answer."""

    code = "coa.chart_already_instantiated"
    status = 409


class TemplateNotPublishedError(ApiError):
    """A draft or superseded version is not something to build a company on."""

    code = "coa.template_not_published"
    status = 400


class CompanyNotVisibleError(ApiError):
    """The company does not exist, or this context cannot reach it.

    One code for both, deliberately: distinguishing them would tell a caller
    whether a company id exists in another tenant -- IZ-04, the convention that
    an inaccessible row is absent, never forbidden.
    """

    code = "coa.company_not_visible"
    status = 404


class AccountNotFoundError(ApiError):
    code = "coa.account_not_found"
    status = 404


class SubaccountsNotAllowedError(ApiError):
    """The parent account does not allow subaccounts -- Spec B section 2.4."""

    code = "coa.subaccounts_not_allowed"
    status = 400


class ParentAccountClosedError(ApiError):
    """A subaccount cannot start after its parent has stopped being valid."""

    code = "coa.parent_account_closed"
    status = 400


class AccountCodeTakenError(ApiError):
    code = "coa.account_code_taken"
    status = 409


class SystemAccountImmutableError(ApiError):
    """System accounts are maintained centrally, not renamed per company.

    Blocking one and closing one are still allowed: those are the company's own
    decisions about its own bookkeeping, and neither changes what the account
    *is*.
    """

    code = "coa.system_account_immutable"
    status = 400


class UnknownDimensionError(ApiError):
    """A dimension outside the closed vocabulary -- ADR-029.

    Refused in the service and again by a CHECK, because a required dimension no
    column carries is a requirement the posting engine can never satisfy: every
    posting to that account would be refused, and the cause would be looked for
    in the posting.
    """

    code = "coa.unknown_dimension"
    status = 400


class InvalidValidityWindowError(ApiError):
    code = "coa.invalid_validity_window"
    status = 400


class TooManyDimensionSlotsError(ApiError):
    """More typed slots than an account carries -- ADR-048.

    Four is the limit, and it is a column count on the largest tables in the
    system, not a preference: a fifth slot is a migration on the register.
    """

    code = "coa.too_many_dimension_slots"
    status = 400


class DuplicateDimensionSlotError(ApiError):
    """One dimension named in two positions. A value would have two homes."""

    code = "coa.duplicate_dimension_slot"
    status = 400


class RequiredDimensionNotCarriedError(ApiError):
    """A required dimension that is not one of the declared slots.

    Refused in the service and again by a CHECK
    (``*_required_within_slots``): an account that demanded an axis it does not
    carry would refuse every posting made to it, and the cause would be looked
    for in the posting.
    """

    code = "coa.required_dimension_not_carried"
    status = 400


class TemplateDeclarationNarrowedError(ApiError):
    """A company tried to drop a slot or a requirement the template imposes.

    The template's declaration is the plan's (ADR-048): a company may **extend**
    a system account with its own analytics -- layer 2 of ADR-036 -- and may not
    remove what the plan declared, for the same reason it cannot rename the
    account.
    """

    code = "coa.template_declaration_narrowed"
    status = 400
