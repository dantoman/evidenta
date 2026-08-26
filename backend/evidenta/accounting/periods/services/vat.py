"""The VAT fiscal period -- F1.5.3, ADR-039 section 7, Codul fiscal art. 114.

Two concepts, and this module exists so they cannot be one:

    period       the accounting period -- exactly one calendar month, for
                 everyone, always. It decides which container a posting falls in.
    vat_period   the VAT fiscal period -- the calendar month too, for everyone,
                 with **one** exception named in law. It decides which declaration
                 a turnover falls in.

Art. 114 para. (1): the VAT fiscal period is the calendar month. There is no
quarterly variant -- not on a threshold, not for a category.

Art. 114 para. (2): when a registration is cancelled, the last fiscal period
begins on the first day of the month **in which the cancellation happened** and
ends on the last day of the month **in which the cancelling act entered into
force**. Two dates, two months, one period. When those months differ, a single
VAT fiscal period spans several accounting periods -- and that is the whole
reason the two are separate tables. Merged, the cancellation case is not merely
awkward to report: it is inexpressible, and the 99% of months where the two
coincide would keep the mistake invisible for years.

**What this module refuses to invent.**

* *Filing deadlines.* Art. 115 puts the declaration and the payment at the 25th
  of the following month, and an earlier version of the same article said "the
  last day of the month". ADR-039 section 7.1 draws the consequence: the
  reporting calendar is a **fiscal parameter** with ``valid_from`` / ``valid_to``
  and a source (R15), not a constant. ``fiscal_parameter`` exists since F0.8 and
  is empty (`OD-22` lists reporting deadlines among the values still owed), so
  there is no deadline function here. A number written from memory into the code
  that tells a taxpayer when to pay is the defect R15 exists to prevent.
* *Rates and thresholds.* None appear here; a VAT period has none.
* *The first period of a mid-month registration.* ADR-039 section 7 quotes
  para. (2) for the last period and says nothing about the first. So this module
  takes **months**, not registration dates: the caller names the month the
  sequence starts in, and a start that is not the first of a month is refused
  rather than silently rounded. If the answer turns out to be a partial first
  period, the schema has to change -- which is visible now instead of buried in
  a rounding rule here.

**What this module cannot check, and nothing else checks either.** A VAT period
is meaningful only while the company is registered, and the registration lives in
``company_vat_registration``, in ``platform/tenancy``. `D6` sends a service
through another module's public surface, and `tenancy` publishes no VAT accessor
(``services/access.py`` answers visibility and nothing else). So the dates come
from the caller, and nothing here refuses a VAT period for a company that never
registered -- nor a fresh monthly period after a final one, which is legitimate
after re-registration and indistinguishable from a mistake without that table.
Stated here rather than answered with a query this module may not make.
"""

from __future__ import annotations

import uuid
from datetime import date

from django.db import transaction

from evidenta.accounting.periods.errors import (
    CompanyNotVisibleError,
    InvalidVatPeriodWindowError,
    VatPeriodNotFoundError,
    VatPeriodOverlapsError,
    VatRegistrationAlreadyClosedError,
)
from evidenta.accounting.periods.models import VatPeriod, VatPeriodKind
from evidenta.accounting.periods.services.months import (
    first_day_of_month,
    first_day_of_next_month,
    last_day_of_month,
)
from evidenta.platform.audit.services.recording import record
from evidenta.platform.rls.context import MissingTenantContextError, current_context
from evidenta.platform.tenancy.services.access import company_visible_in_context


def _context_tenant() -> uuid.UUID:
    context = current_context()
    if context is None:
        raise MissingTenantContextError("a VAT fiscal period needs a tenant context")
    return context.tenant_id


def _require_visible(company_id: uuid.UUID) -> None:
    """Asked of ``tenancy``, not read off ``Company`` -- `D6` through a service."""
    if not company_visible_in_context(company_id):
        raise CompanyNotVisibleError(f"company {company_id} is not visible in this context")


def _overlapping(company_id: uuid.UUID, start: date, end: date) -> list[VatPeriod]:
    return list(
        VatPeriod.objects.filter(
            company_id=company_id, start_date__lte=end, end_date__gte=start
        ).order_by("start_date")
    )


@transaction.atomic
def open_vat_periods(company_id: uuid.UUID, first_month: date, through: date) -> list[VatPeriod]:
    """One VAT fiscal period per calendar month, from ``first_month`` through ``through``.

    Both arguments name a **month**: ``first_month`` must be the first day of one
    and ``through`` the last day of one. Refusing anything else is not tidiness --
    art. 114 para. (1) knows only whole calendar months, and rounding a date to a
    month here would hide the one question the law does not answer (see the module
    docstring: a registration that takes effect on the 15th).

    Generated in one call rather than typed one by one, for the same reason the
    exercise generates its own months: nobody types a February, so nobody types
    the wrong number of days into one.

    Deliberately **not** idempotent over an existing range. A second call that
    silently skipped the months it found would make "the periods are already
    there" and "the periods were just created" indistinguishable, and the caller
    that most wants to know the difference is the one recovering from a failure.
    """
    tenant_id = _context_tenant()
    _require_visible(company_id)

    if first_month != first_day_of_month(first_month):
        raise InvalidVatPeriodWindowError(
            f"a VAT fiscal period starts on the first of a month; {first_month} does not "
            f"(Codul fiscal art. 114 alin. (1))"
        )
    if through != last_day_of_month(through):
        raise InvalidVatPeriodWindowError(
            f"a VAT fiscal period ends on the last day of a month; {through} does not "
            f"(Codul fiscal art. 114 alin. (1))"
        )
    if through < first_month:
        raise InvalidVatPeriodWindowError(f"{first_month} to {through} ends before it starts")

    existing = _overlapping(company_id, first_month, through)
    if existing:
        clash = existing[0]
        raise VatPeriodOverlapsError(
            f"{first_month} to {through} overlaps the VAT fiscal period "
            f"{clash.start_date} to {clash.end_date}; two periods over one day is "
            f"two declarations for one day"
        )

    periods = []
    month_start = first_month
    while month_start <= through:
        periods.append(
            VatPeriod(
                tenant_id=tenant_id,
                company_id=company_id,
                start_date=month_start,
                end_date=last_day_of_month(month_start),
                kind=VatPeriodKind.MONTHLY,
            )
        )
        month_start = first_day_of_next_month(month_start)
    VatPeriod.objects.bulk_create(periods)

    record(
        action="vat_period.opened",
        entity_type="vat_period",
        company_id=company_id,
        new_value={
            "first_month": first_month.isoformat(),
            "through": through.isoformat(),
            "periods": len(periods),
        },
    )
    return periods


@transaction.atomic
def close_vat_registration(
    company_id: uuid.UUID, cancelled_on: date, act_in_force_on: date
) -> VatPeriod:
    """The last VAT fiscal period of a cancelled registration -- art. 114 para. (2).

    ``cancelled_on``     the day the cancellation happened
    ``act_in_force_on``  the day the cancelling act entered into force

    Both are ordinary days, not months: the article derives the month edges from
    them, and a caller that had to round them first would be doing the derivation
    the law describes. The resulting period runs from the first day of the month
    of ``cancelled_on`` to the last day of the month of ``act_in_force_on`` --
    **longer than a calendar month whenever those months differ**, which is the
    case no merged model can express.

    If the month of cancellation already has its monthly period -- the normal
    situation, since the month was running when the act arrived -- that row is
    extended in place and becomes the final one. Extending rather than adding
    keeps the declaration already attached to that month attached to the period
    that now ends later, instead of leaving two rows disputing March.
    """
    tenant_id = _context_tenant()
    _require_visible(company_id)

    if act_in_force_on < cancelled_on:
        raise InvalidVatPeriodWindowError(
            f"the cancelling act cannot enter into force ({act_in_force_on}) before the "
            f"cancellation happened ({cancelled_on})"
        )

    start = first_day_of_month(cancelled_on)
    end = last_day_of_month(act_in_force_on)

    existing = _overlapping(company_id, start, end)
    already_final = [period for period in existing if period.kind == VatPeriodKind.FINAL]
    if already_final:
        final = already_final[0]
        raise VatRegistrationAlreadyClosedError(
            f"the VAT registration is already closed by the final period "
            f"{final.start_date} to {final.end_date}; recording the cancellation twice "
            f"would move the end of a fiscal period that has already been declared on"
        )

    surplus = [period for period in existing if period.start_date != start]
    if surplus:
        clash = surplus[0]
        raise VatPeriodOverlapsError(
            f"the final period {start} to {end} would swallow the VAT fiscal period "
            f"{clash.start_date} to {clash.end_date}; those months already carry a "
            f"period of their own, and merging them is not something this service "
            f"decides on its own"
        )

    if existing:
        final = existing[0]
        old = {"start_date": final.start_date.isoformat(), "end_date": final.end_date.isoformat()}
        final.end_date = end
        final.kind = VatPeriodKind.FINAL
        final.save(update_fields=["end_date", "kind", "updated_at"])
    else:
        old = {}
        final = VatPeriod.objects.create(
            tenant_id=tenant_id,
            company_id=company_id,
            start_date=start,
            end_date=end,
            kind=VatPeriodKind.FINAL,
        )

    record(
        action="vat_registration.closed",
        entity_type="vat_period",
        entity_id=final.id,
        company_id=company_id,
        old_value=old or None,
        new_value={
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "kind": VatPeriodKind.FINAL.value,
            "cancelled_on": cancelled_on.isoformat(),
            "act_in_force_on": act_in_force_on.isoformat(),
        },
    )
    return final


def vat_period_for(company_id: uuid.UUID, day: date) -> VatPeriod:
    """The VAT fiscal period covering ``day``, or a loud refusal.

    The counterpart of ``resolution.period_for``, and deliberately a different
    function with a different error code. A company can have an open accounting
    period for a month and no VAT period for it at all -- it is simply not
    registered -- and answering that with ``periods.period_not_found`` would send
    the caller to open an exercise that is already open.

    Never invents a period. Same argument as the accounting one: a declaration
    that created its own container would decide, unreviewed, which months a
    cancelled registration still covers.
    """
    period = VatPeriod.objects.filter(
        company_id=company_id, start_date__lte=day, end_date__gte=day
    ).first()
    if period is None:
        raise VatPeriodNotFoundError(
            f"no VAT fiscal period covers {day} for company {company_id}; "
            f"the company is not registered for VAT over that day, or the periods "
            f"have not been opened"
        )
    return period
