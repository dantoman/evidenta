"""The VAT fiscal period -- F1.5.3, under the application role.

Everything runs inside ``tenant_context``, on the application connection (T1).

**The suite is built around the one month where the two concepts come apart.**
Art. 114 para. (1) makes the VAT fiscal period the calendar month, which is also
what an accounting period is, so a suite that only exercised ordinary months
would pass just as happily against a model that had merged them -- and would keep
passing until a client cancelled a registration. So the central test is
para. (2): a cancellation in March whose act enters into force in April produces
**one** VAT fiscal period covering **two** accounting periods, and both answers
are asserted side by side.

Service-level and database-level assertions are mixed on purpose, as in
``test_periods.py``: where a rule exists in both places both are tested, because
the reason the rule is in the database is that the service is not the only way in.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date

import pytest
from django.db import connection, transaction
from django.db.utils import IntegrityError, ProgrammingError

from evidenta.accounting.periods.errors import (
    CompanyNotVisibleError,
    InvalidVatPeriodWindowError,
    PeriodNotFoundError,
    VatPeriodNotFoundError,
    VatPeriodOverlapsError,
    VatRegistrationAlreadyClosedError,
)
from evidenta.accounting.periods.models import PeriodStatus, VatPeriod, VatPeriodKind
from evidenta.accounting.periods.services.opening import open_fiscal_year
from evidenta.accounting.periods.services.resolution import period_for
from evidenta.accounting.periods.services.vat import (
    close_vat_registration,
    open_vat_periods,
    vat_period_for,
)
from evidenta.platform.audit.models import AuditEvent
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="vat")


@pytest.fixture
def company(
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> uuid.UUID:
    company_id = company_of(world["tenant_a"], "1002600000201", "Alpha TVA")
    grant_company(world["tenant_a"], company_id, world["user_a"], world["user_a"])
    return company_id


def open_2026(company_id: uuid.UUID) -> list[VatPeriod]:
    return open_vat_periods(company_id, date(2026, 1, 1), date(2026, 12, 31))


# --- art. 114 para. (1): the month, for everyone ----------------------------


def test_the_vat_period_is_the_calendar_month(context: TenantContext, company: uuid.UUID) -> None:
    """No quarterly variant -- not on a threshold, not for a category."""
    with tenant_context(context):
        periods = open_2026(company)

        assert len(periods) == 12
        assert periods[0].start_date == date(2026, 1, 1)
        assert periods[0].end_date == date(2026, 1, 31)
        assert all(p.kind == VatPeriodKind.MONTHLY for p in periods)

        # February 2026 has 28 days. Generated, not typed.
        assert (periods[1].start_date, periods[1].end_date) == (date(2026, 2, 1), date(2026, 2, 28))


def test_a_window_that_is_not_whole_months_is_refused(
    context: TenantContext, company: uuid.UUID
) -> None:
    """Art. 114 speaks only in whole calendar months, in both paragraphs.

    Rounding a mid-month date here would quietly answer a question the article
    does not: what the first fiscal period of a registration that takes effect
    on the 15th looks like. Refusing keeps the question visible.
    """
    with tenant_context(context):
        with pytest.raises(InvalidVatPeriodWindowError):
            open_vat_periods(company, date(2026, 1, 15), date(2026, 12, 31))
        with pytest.raises(InvalidVatPeriodWindowError):
            open_vat_periods(company, date(2026, 1, 1), date(2026, 12, 15))
        with pytest.raises(InvalidVatPeriodWindowError):
            open_vat_periods(company, date(2026, 5, 1), date(2026, 3, 31))


def test_two_vat_periods_may_not_cover_one_day(context: TenantContext, company: uuid.UUID) -> None:
    with tenant_context(context):
        open_2026(company)
        with pytest.raises(VatPeriodOverlapsError):
            open_vat_periods(company, date(2026, 6, 1), date(2027, 5, 31))


def test_the_database_refuses_an_overlap_the_service_never_saw(
    context: TenantContext, company: uuid.UUID
) -> None:
    """The path the 1C importer and any data migration take."""
    with tenant_context(context):
        open_2026(company)

        with pytest.raises(IntegrityError, match="vat_period_no_overlap"), transaction.atomic():
            VatPeriod.objects.create(
                tenant_id=context.tenant_id,
                company_id=company,
                start_date=date(2026, 6, 1),
                end_date=date(2026, 6, 30),
            )


def test_the_database_refuses_a_monthly_period_longer_than_its_month(
    context: TenantContext, company: uuid.UUID
) -> None:
    """Only the final period of art. 114 para. (2) may exceed a month.

    Without this CHECK, an import could give one company a "month" of two months
    and the difference would surface in a declaration, not at write time.
    """
    with (
        tenant_context(context),
        pytest.raises(IntegrityError, match="vat_period_monthly_is_one_month"),
        transaction.atomic(),
    ):
        VatPeriod.objects.create(
            tenant_id=context.tenant_id,
            company_id=company,
            start_date=date(2026, 3, 1),
            end_date=date(2026, 4, 30),
            kind=VatPeriodKind.MONTHLY,
        )


def test_the_database_refuses_a_period_that_does_not_sit_on_month_edges(
    context: TenantContext, company: uuid.UUID
) -> None:
    with tenant_context(context):
        with (
            pytest.raises(IntegrityError, match="vat_period_starts_a_month"),
            transaction.atomic(),
        ):
            VatPeriod.objects.create(
                tenant_id=context.tenant_id,
                company_id=company,
                start_date=date(2026, 3, 15),
                end_date=date(2026, 3, 31),
            )

        with (
            pytest.raises(IntegrityError, match="vat_period_ends_a_month"),
            transaction.atomic(),
        ):
            VatPeriod.objects.create(
                tenant_id=context.tenant_id,
                company_id=company,
                start_date=date(2026, 3, 1),
                end_date=date(2026, 3, 20),
            )


# --- art. 114 para. (2): the case the two concepts exist for -----------------


def test_the_last_period_of_a_cancelled_registration_exceeds_a_calendar_month(
    context: TenantContext, company: uuid.UUID
) -> None:
    """**This is the test F1.5.3 exists for.**

    Cancellation happens on 10 March; the cancelling act enters into force on
    5 April. Art. 114 para. (2): the last fiscal period begins on the first day
    of the month of the cancellation and ends on the last day of the month in
    which the act entered into force -- 1 March to 30 April, a single VAT fiscal
    period covering two accounting periods.

    Asserted next to the accounting periods for the same months, because the
    claim being tested is not "the dates are these" but "the two concepts are
    not the same concept".
    """
    with tenant_context(context):
        open_fiscal_year(company, "2026", date(2026, 1, 1), date(2026, 12, 31))
        open_vat_periods(company, date(2026, 1, 1), date(2026, 3, 31))

        final = close_vat_registration(company, date(2026, 3, 10), date(2026, 4, 5))

        assert final.kind == VatPeriodKind.FINAL
        assert final.start_date == date(2026, 3, 1)
        assert final.end_date == date(2026, 4, 30)

        # One VAT period over both months...
        assert vat_period_for(company, date(2026, 3, 10)).id == final.id
        assert vat_period_for(company, date(2026, 4, 5)).id == final.id
        assert vat_period_for(company, date(2026, 4, 30)).id == final.id

        # ...while the accounting periods stay strictly monthly, and are two.
        march = period_for(company, date(2026, 3, 10))
        april = period_for(company, date(2026, 4, 5))
        assert march.id != april.id
        assert (march.start_date, march.end_date) == (date(2026, 3, 1), date(2026, 3, 31))
        assert (april.start_date, april.end_date) == (date(2026, 4, 1), date(2026, 4, 30))
        assert march.status == PeriodStatus.OPEN


def test_the_final_period_extends_the_month_that_was_already_running(
    context: TenantContext, company: uuid.UUID
) -> None:
    """The normal sequence: March's period exists when the act arrives.

    Extending the row rather than adding a second one keeps whatever is already
    attached to March attached to the period that now ends in April, instead of
    leaving two rows disputing the month.
    """
    with tenant_context(context):
        opened = open_vat_periods(company, date(2026, 1, 1), date(2026, 3, 31))
        march_id = opened[2].id

        final = close_vat_registration(company, date(2026, 3, 10), date(2026, 4, 5))

        assert final.id == march_id
        assert VatPeriod.objects.filter(company_id=company).count() == 3


def test_a_cancellation_inside_one_month_still_produces_a_final_period(
    context: TenantContext, company: uuid.UUID
) -> None:
    """The 99% case, and the reason ``kind`` is stored rather than derived.

    Cancellation and entry into force in the same month give a final period that
    is exactly one calendar month -- identical in shape to any other month. What
    separates it is that nothing follows it, and that cannot be read off the
    dates.
    """
    with tenant_context(context):
        open_vat_periods(company, date(2026, 1, 1), date(2026, 3, 31))

        final = close_vat_registration(company, date(2026, 3, 5), date(2026, 3, 20))

        assert final.kind == VatPeriodKind.FINAL
        assert (final.start_date, final.end_date) == (date(2026, 3, 1), date(2026, 3, 31))


def test_the_final_period_is_created_when_the_month_had_none(
    context: TenantContext, company: uuid.UUID
) -> None:
    with tenant_context(context):
        final = close_vat_registration(company, date(2026, 3, 10), date(2026, 5, 4))

        assert (final.start_date, final.end_date) == (date(2026, 3, 1), date(2026, 5, 31))
        assert VatPeriod.objects.filter(company_id=company).count() == 1


def test_an_act_in_force_before_the_cancellation_is_refused(
    context: TenantContext, company: uuid.UUID
) -> None:
    with tenant_context(context), pytest.raises(InvalidVatPeriodWindowError):
        close_vat_registration(company, date(2026, 4, 5), date(2026, 3, 10))


def test_closing_twice_is_refused_with_its_own_code(
    context: TenantContext, company: uuid.UUID
) -> None:
    """Recording the cancellation twice would move the end of a declared period."""
    with tenant_context(context):
        close_vat_registration(company, date(2026, 3, 10), date(2026, 4, 5))

        with pytest.raises(VatRegistrationAlreadyClosedError):
            close_vat_registration(company, date(2026, 3, 10), date(2026, 5, 4))


def test_a_final_period_never_swallows_months_that_already_have_one(
    context: TenantContext, company: uuid.UUID
) -> None:
    """April already carries its own period, so March cannot grow over it.

    A different code from the double-close: this one is fixed by naming
    different months, and the periods in the way are not this service's to
    remove -- the application role has no DELETE on the table.
    """
    with tenant_context(context):
        open_2026(company)

        with pytest.raises(VatPeriodOverlapsError):
            close_vat_registration(company, date(2026, 3, 10), date(2026, 4, 5))


def test_a_final_period_is_not_revised_in_place_by_a_direct_update(
    context: TenantContext, company: uuid.UUID
) -> None:
    """The trigger, not the service -- the path an importer takes.

    A refusal that lives only in Python is one the 1C importer and every data
    migration walk past, and moving the end of the last fiscal period a taxpayer
    has already declared on is exactly what must not happen quietly.
    """
    with tenant_context(context):
        final = close_vat_registration(company, date(2026, 3, 10), date(2026, 4, 5))

        with pytest.raises(ProgrammingError, match="not revised in place"), transaction.atomic():
            VatPeriod.objects.filter(id=final.id).update(end_date=date(2026, 5, 31))

        with pytest.raises(ProgrammingError, match="not revised in place"), transaction.atomic():
            VatPeriod.objects.filter(id=final.id).update(kind=VatPeriodKind.MONTHLY)


# --- the two calendars are independent --------------------------------------


def test_a_vat_period_exists_without_an_accounting_period(
    context: TenantContext, company: uuid.UUID
) -> None:
    """No exercise is open, and the VAT periods are still there.

    They answer different questions of different tables, and neither generates
    the other. A VAT period that required an open exercise would make the
    declaration depend on whether somebody had opened the books.
    """
    with tenant_context(context):
        open_2026(company)

        assert vat_period_for(company, date(2026, 7, 15)).start_date == date(2026, 7, 1)
        with pytest.raises(PeriodNotFoundError):
            period_for(company, date(2026, 7, 15))


def test_an_accounting_period_exists_without_a_vat_period(
    context: TenantContext, company: uuid.UUID
) -> None:
    """A company that is not registered for VAT keeps books all the same.

    And the refusal has its own code: answering with `periods.period_not_found`
    would send the caller to open an exercise that is already open.
    """
    with tenant_context(context):
        open_fiscal_year(company, "2026", date(2026, 1, 1), date(2026, 12, 31))

        assert period_for(company, date(2026, 7, 15)).start_date == date(2026, 7, 1)
        with pytest.raises(VatPeriodNotFoundError):
            vat_period_for(company, date(2026, 7, 15))


def test_closing_a_registration_records_both_dates_in_the_audit(
    context: TenantContext, company: uuid.UUID
) -> None:
    """Both dates, because the period cannot be reconstructed from one of them.

    The month edges are derived; what art. 114 para. (2) actually names is the
    day of the cancellation and the day the act entered into force.
    """
    with tenant_context(context):
        final = close_vat_registration(company, date(2026, 3, 10), date(2026, 4, 5))

        entry = AuditEvent.objects.filter(
            action="vat_registration.closed", entity_id=final.id
        ).first()
        assert entry is not None
        assert entry.new_value is not None
        assert entry.new_value["cancelled_on"] == "2026-03-10"
        assert entry.new_value["act_in_force_on"] == "2026-04-05"


# --- isolation and what cannot be undone ------------------------------------


def test_vat_periods_of_another_tenant_are_invisible(
    context: TenantContext, company: uuid.UUID, world: dict[str, uuid.UUID]
) -> None:
    """IZ-01 for this table: absent, not forbidden."""
    with tenant_context(context):
        open_2026(company)

    other = TenantContext(tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="vat")
    with tenant_context(other):
        assert VatPeriod.objects.count() == 0
        with pytest.raises(VatPeriodNotFoundError):
            vat_period_for(company, date(2026, 7, 15))


def test_a_company_outside_the_context_is_refused(
    context: TenantContext,
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
) -> None:
    """Asked of `tenancy` through its service, not read off ``Company`` (D6)."""
    foreign = company_of(world["tenant_b"], "1002600000202", "Beta TVA")
    with tenant_context(context), pytest.raises(CompanyNotVisibleError):
        open_vat_periods(foreign, date(2026, 1, 1), date(2026, 3, 31))


def test_a_vat_period_cannot_be_deleted(context: TenantContext, company: uuid.UUID) -> None:
    """A missing privilege, not a convention in a service.

    A deleted VAT period takes with it the boundary a filed declaration was
    built on.
    """
    with tenant_context(context):
        open_2026(company)
        period = vat_period_for(company, date(2026, 7, 15))

        with (
            pytest.raises(ProgrammingError, match="permission denied"),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute("DELETE FROM vat_period WHERE id = %s", [period.id])
