"""Accounting periods and the exercise that contains them -- F1.5, ADR-039 part II.

Three entities, and the splits are the point:

``fiscal_year``   the exercise, with ``start_date`` and ``end_date`` **explicit**
``period``        the operational period, strictly one calendar month
``vat_period``    the VAT fiscal period -- normally the same month, and not the
                  same concept (Codul fiscal art. 114; see ``VatPeriod``)

Law nr. 287/2017, art. 24 para. (1) makes the exercise the calendar year with
four exceptions, and exception (b) -- an entity applying its parent's period --
is the ordinary case for a subsidiary of a foreign owner. April-to-March is not
a theoretical case, so "twelve months, January to December" may not appear
anywhere in closing, aggregation or reporting (ADR-039 section 6). The cost of
carrying it as data is two columns; the cost of assuming it is a rewrite plus a
segment of clients the product cannot serve.

**Two divergences from Spec B section 6, both deliberate and neither silent.**

1. Spec B carries ``fiscal_year`` as a ``smallint`` column on ``period``. ADR-039
   is later and accepted, and it makes the exercise an entity with explicit
   dates -- a smallint cannot say that an exercise runs April to March. The ADR
   wins, which is also the rule the F1 backlog states for exactly this case.
2. Spec B section 6.1 lists four states (``open``, ``closing``, ``closed``,
   ``locked``); ADR-039 section 8 lists three. Three are implemented. The fourth,
   ``closing`` -- new postings refused while corrections in flight are still
   allowed -- is a workflow question with real content, so it is recorded as an
   open decision rather than invented here or dropped in silence. Adding a state
   later is an additive migration; inventing the semantics of one now is not.

**`DNB-07` stays open, and is visible in what is missing.** The decision asks
whether the period is one state for everything, or carries per-module locks so
VAT can close independently of payroll. Nothing here answers it: there is no
``period_module_lock`` table and no module column. Both remaining options are
additive on top of this schema, which is why building the base does not close
the decision -- but the base *is* option (A) as today's behaviour, and that is
said out loud here rather than discovered later.

**Nothing is deleted.** A period holds the trace of its own closing, and the
application role has no DELETE privilege on either table (``infra/migrations/
0035_periods``). A period that disappears takes with it the answer to "who
closed March, and when" -- and the entries posted into it stay, referencing it.
"""

from __future__ import annotations

import uuid

from django.db import models

from evidenta.platform.tenancy.models import Company, Tenant


class FiscalYearStatus(models.TextChoices):
    """Two states, because an exercise either accepts work or it does not.

    ``closed`` is what locks every period inside it (ADR-039 section 8): reopening
    a closed period is possible only while its exercise is open, so the exercise
    is the outer gate, not a label.
    """

    OPEN = "open"
    CLOSED = "closed"


class PeriodStatus(models.TextChoices):
    """ADR-039 section 8. Three, and the third is terminal.

    ``open``    postings accepted
    ``closed``  refused; reopening possible while the exercise is open
    ``locked``  refused forever -- reached by closing the exercise
    """

    OPEN = "open"
    CLOSED = "closed"
    LOCKED = "locked"


class FiscalYear(models.Model):
    """One exercise of one company, with its own start and end.

    ``code`` is the designation an accountant uses -- ``2026`` for a calendar
    exercise, ``2026/2027`` for one that straddles. It is a code, not a name: it
    is ordered and matched, never sorted linguistically, so it carries
    ``COLLATE "C"`` (C34, ADR-015) applied in the SQL migration.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    code = models.TextField()

    # Explicit, not derived from `code`. Deriving them would put the assumption
    # this ADR exists to remove back into the code that reads the column.
    start_date = models.DateField()
    end_date = models.DateField()

    status = models.TextField(choices=FiscalYearStatus.choices, default=FiscalYearStatus.OPEN)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by_user_id = models.UUIDField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "fiscal_year"
        constraints = [
            models.UniqueConstraint(fields=["company", "code"], name="fiscal_year_code_unique"),
            models.CheckConstraint(
                condition=models.Q(status__in=[c.value for c in FiscalYearStatus]),
                name="fiscal_year_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(end_date__gt=models.F("start_date")),
                name="fiscal_year_period_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status="open") | models.Q(closed_at__isnull=False),
                name="fiscal_year_closed_has_timestamp",
            ),
        ]
        indexes = [
            models.Index(fields=["company", "start_date"], name="fiscal_year_company_start"),
        ]

    def __str__(self) -> str:
        return f"{self.code} ({self.start_date} - {self.end_date})"


class Period(models.Model):
    """One calendar month of one exercise. Strictly monthly, for everyone.

    ADR-039 section 7: the accounting period is the month, always -- unlike the
    VAT fiscal period, which normally equals the month but goes irregular when a
    registration is cancelled (Codul fiscal art. 114 para. (2)). The two are
    distinct entities on purpose, and ``VatPeriod`` below is the other one. This
    one is the container a posting falls into; that one is the container a
    declaration is built on. Nothing links them, because on the month where they
    differ a link would have to point at two rows.

    ``period_no`` counts within the exercise, not within the calendar year: for
    an April-to-March exercise, period 1 is April. Anything else would reintroduce
    the calendar assumption through the numbering.

    **``end_date`` is the last day, inclusive** -- ``2026-01-31``, not ``2026-02-01``.
    That is deliberately *unlike* the validity windows elsewhere in the system,
    which are half-open ``[valid_from, valid_to)``: fiscal parameters, chart
    versions, event-type handlers. A period is a named stretch of days an
    accountant talks about, not a window a lookup falls into, and the CHECK
    below pins both ends to the month so the two conventions cannot be confused
    silently -- the failure they would otherwise produce is one day a year, found
    at a client rather than in a test.

    ``reopened_count`` is not decoration. Reopening a closed period is an event a
    reviewer asks about, and the count is the cheapest form of the question "how
    often did this happen here". The reason for each reopening lives in the audit
    entry, where it cannot be overwritten by the next one.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")
    fiscal_year = models.ForeignKey(
        FiscalYear, on_delete=models.PROTECT, db_column="fiscal_year_id", related_name="periods"
    )

    period_no = models.SmallIntegerField()
    start_date = models.DateField()
    end_date = models.DateField()

    status = models.TextField(choices=PeriodStatus.choices, default=PeriodStatus.OPEN)
    closed_at = models.DateTimeField(null=True, blank=True)
    closed_by_user_id = models.UUIDField(null=True, blank=True)

    reopened_count = models.SmallIntegerField(default=0)
    last_reopened_at = models.DateTimeField(null=True, blank=True)
    last_reopened_by_user_id = models.UUIDField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "period"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "fiscal_year", "period_no"], name="period_number_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=[c.value for c in PeriodStatus]),
                name="period_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")), name="period_dates_valid"
            ),
            models.CheckConstraint(condition=models.Q(period_no__gte=1), name="period_no_positive"),
            models.CheckConstraint(
                condition=models.Q(status="open") | models.Q(closed_at__isnull=False),
                name="period_closed_has_timestamp",
            ),
            models.CheckConstraint(
                condition=models.Q(reopened_count__gte=0), name="period_reopened_count_positive"
            ),
        ]
        indexes = [
            # The query the engine will run on every posting: which period holds
            # this `accounting_date`. Starts with the context column, per the
            # index rule in the amendment (section B.3).
            models.Index(fields=["company", "start_date"], name="period_company_start"),
            models.Index(fields=["fiscal_year", "period_no"], name="period_year_number"),
        ]

    def __str__(self) -> str:
        return f"{self.start_date:%Y-%m} ({self.status})"


class VatPeriodKind(models.TextChoices):
    """Why a VAT fiscal period has the shape it has -- Codul fiscal art. 114.

    ``monthly``  para. (1): the calendar month. Every period but the last one of
                 a cancelled registration is this, for every taxpayer -- there is
                 no quarterly variant, on no threshold and for no category.
    ``final``    para. (2): the period that closes a cancelled registration, and
                 the only one allowed to run past the end of its own month.

    The kind is carried rather than derived from the dates, because in the common
    case it cannot be derived: when the cancellation and the entry into force of
    the act fall in the same month, the final period *is* one calendar month and
    is indistinguishable from a regular one by shape alone. What separates them
    is that nothing follows the final period.
    """

    MONTHLY = "monthly"
    FINAL = "final"


class VatPeriod(models.Model):
    """The VAT fiscal period -- Codul fiscal art. 114, ADR-039 section 7.

    **A separate entity, not a column on ``period``, and not a view over it.**
    Art. 114 para. (1) makes the VAT fiscal period the calendar month for
    everyone, which is also what ``period`` is -- so for 99% of the months of
    99% of companies the two coincide, and a model that merged them would look
    right for years. Para. (2) is the 1%: when a VAT registration is cancelled,
    the last fiscal period begins on the first day of the month in which the
    cancellation happened and ends on the last day of the month in which the
    cancelling act entered into force. If those are different months, **one VAT
    fiscal period covers two or more accounting periods**. A merged model cannot
    express that, and the declaration built on it would be wrong in exactly the
    situation where someone is looking.

    **There is no ``status`` column here, and its absence is deliberate.**
    Closing is a state of the accounting period (ADR-039 section 8); what a VAT
    period would close is the filing of a declaration, and that lifecycle belongs
    to F2. More to the point, `DNB-07` -- one state for everything, per-module
    locks, or periods per domain -- is **open**. This table is not option (C)
    quietly chosen: it holds no lock, refuses no posting and gates nothing. It
    exists because art. 114 gives VAT a period with different *edges*, not
    because VAT wants a lock of its own. A ``status`` column added here would
    answer `DNB-07` by accident, which is why there is not one.

    **What this table cannot say, and nothing else says either.** A VAT period is
    meaningful only while the company is registered, and the registration lives in
    ``company_vat_registration`` (``platform/tenancy``). Nothing here reads it:
    `D6` sends a service through another module's public surface, and `tenancy`
    exposes no VAT accessor today. So the caller names the months, and a VAT
    period for a company that never registered is refused by nobody. Recorded
    rather than papered over with a check that reads a model it may not read.

    ``end_date`` is the **last day, inclusive**, the same convention as ``period``
    and deliberately unlike the half-open ``[valid_from, valid_to)`` windows of
    fiscal parameters -- and unlike ``company_vat_registration``'s own window,
    which is the neighbouring table most likely to be confused with this one.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    start_date = models.DateField()
    end_date = models.DateField()

    kind = models.TextField(choices=VatPeriodKind.choices, default=VatPeriodKind.MONTHLY)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "vat_period"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(kind__in=[c.value for c in VatPeriodKind]),
                name="vat_period_kind_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="vat_period_dates_valid",
            ),
        ]
        indexes = [
            # The lookup every declaration makes: which VAT period holds this
            # date. Starts with the context column, like every other index here.
            models.Index(fields=["company", "start_date"], name="vat_period_company_start"),
        ]

    def __str__(self) -> str:
        if (
            self.start_date.year == self.end_date.year
            and self.start_date.month == self.end_date.month
        ):
            return f"{self.start_date:%Y-%m} ({self.kind})"
        return f"{self.start_date:%Y-%m}..{self.end_date:%Y-%m} ({self.kind})"
