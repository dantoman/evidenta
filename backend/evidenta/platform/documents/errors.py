"""Stable refusal codes for the document layer -- C10.

The code is the contract; the message is for the human reading the log. A client
branching on wording breaks the day the wording improves, and improving wording
is the cheapest change in the product.

Every code is prefixed `documents.` and every one of them is a **refusal a user
can act on**. Failures nobody can act on stay exceptions and reach the error
tracker, which is where an unexpected failure belongs.
"""

from __future__ import annotations

from evidenta.platform.api.errors import ApiError


class DocumentNotFoundError(ApiError):
    """Absent, or not visible in this context. Never 403 -- IZ-04."""

    code = "documents.not_found"
    status = 404


class DocumentNotEditableError(ApiError):
    """The document is past draft, and a validated document is frozen.

    The database refuses the write too, through a trigger. This is the stable
    code, not the guarantee: a bulk import or a data migration never reaches this
    class and still cannot rewrite a validated document.
    """

    code = "documents.not_editable"
    status = 409


class InvalidTransitionError(ApiError):
    """A move the state machine does not contain."""

    code = "documents.invalid_transition"
    status = 409


class CancellationReasonRequiredError(ApiError):
    """Cancelling without saying why. The register has to account for what was
    voided, not fall silent about it."""

    code = "documents.cancellation_reason_required"
    status = 400


class CancelAfterPostingError(ApiError):
    """Cancellation is allowed only before the accounting effect exists.

    After it, the correction is a reversal and a re-entry -- `R10`. This layer
    does not post, so today the state is unreachable; the refusal is written now
    because the transition that makes it reachable must not have to add it.
    """

    code = "documents.cancel_after_posting"
    status = 409


class PartnerRequiredError(ApiError):
    code = "documents.partner_required"
    status = 400


class NoLinesError(ApiError):
    code = "documents.no_lines"
    status = 400


class LineAmountsInconsistentError(ApiError):
    """`total` is not `net + vat`. Exact addition, so this is arithmetic, not
    rounding -- the one identity this layer is entitled to enforce."""

    code = "documents.line_amounts_inconsistent"
    status = 422


class VatRegimeRequiredError(ApiError):
    """A position with no VAT treatment. Not the same as a zero rate: exempt and
    zero-rated both carry 0 and a declaration that cannot tell them apart is
    filed wrong."""

    code = "documents.vat_regime_required"
    status = 400


class CurrencyMismatchError(ApiError):
    """A rate of exactly 1 is the only rate an amount already in the company's
    functional currency can carry, and a foreign currency needs one that is not
    invented here."""

    code = "documents.currency_mismatch"
    status = 400


class ExchangeRateRequiredError(ApiError):
    """A document in a foreign currency with no rate supplied.

    Not resolved for the caller: art. 97 alin. (6) names a date that is neither
    the document's nor the posting's, and that question is open (ADR-039,
    `DN-04`). Choosing a date here would close it from the least entitled layer.
    """

    code = "documents.exchange_rate_required"
    status = 400


class SourceNotConvertibleError(ApiError):
    """The registry does not list this target among the source type's outcomes."""

    code = "documents.source_not_convertible"
    status = 409


class SourceNotValidatedError(ApiError):
    """A draft is not a commitment, so nothing converts from one and nothing
    reverses one -- a draft is deleted instead."""

    code = "documents.source_not_validated"
    status = 409


class AlreadyConvertedError(ApiError):
    code = "documents.already_converted"
    status = 409


class AlreadyReversedError(ApiError):
    code = "documents.already_reversed"
    status = 409


class ReversalReasonRequiredError(ApiError):
    code = "documents.reversal_reason_required"
    status = 400


class ExternalNumberNotAllowedError(ApiError):
    """A document numbered by this system cannot also carry one issued elsewhere."""

    code = "documents.external_number_not_allowed"
    status = 400


class RateTermUnknownError(ApiError):
    """The contractual term on the rate is not one of the three pct. 19 names.

    At the payment date, at the delivery date, or fixed by the parties -- and no
    fourth. A term outside the vocabulary is refused rather than stored: the
    handler that reads it at settlement (ADR-057) decides on it whether any
    difference exists at all.
    """

    code = "documents.rate_term_unknown"
    status = 400


class ContractDenominationRequiredError(ApiError):
    """A document in another currency without saying what the contract is
    denominated in -- foreign currency or conventional units (ADR-057 §2.2).

    Refused rather than defaulted: the value selects the pair of accounts a
    settlement difference lands on and whether the balance is revalued at the
    reporting date, and a default would be the silent choice that looks
    reasonable.
    """

    code = "documents.contract_denomination_required"
    status = 422


class ContractDenominationInvalidError(ApiError):
    """A denomination on a document in the functional currency, or one outside
    the two values the standard names. A contract in lei has no denomination."""

    code = "documents.contract_denomination_invalid"
    status = 422
