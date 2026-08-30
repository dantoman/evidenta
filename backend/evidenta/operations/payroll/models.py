"""People, work relationships and the monthly timesheet -- ADR-065, ADR-067.

**The employee belongs to the company, not to the tenant** (ADR-065 section 4).
The legal employer is the company: it withholds, it files IPC, it answers for it.
A person working at two companies of the same tenant has two work relationships,
two withholdings and two declarations -- and exemptions are granted at one place
of work only (HG 697/2014 point 9), which is a property of the relationship, not
of the person.

**The contract is the head of a series, not a state** (ADR-067). Any change to
any clause of art. 49 para (1) of the Labour Code requires a signed amendment,
annexed to the contract and part of it. A contract overwritten in place cannot
show which clause was in force on a past date, nor that the change was consented
to -- and `R18` asks exactly that of every recalculation of a past month.

**The generating fact of the reporting is the employer's order, not the
contract.** The IRM19 instruction, point 2: the ten-working-day deadline runs
*"starting the day after the date indicated in the order"*, and point 3: the form
is filled in *"in accordance with the orders drawn up by the employer"*. So the
order's date and number are columns here, on entities that were being built
anyway -- ADR-067 section 2 draws that line explicitly.

**What is deliberately not here.** No calculated amount, no contribution, no
withholding: those are the payroll run, and a column anticipating them would be
that decision taken in the wrong place. No leave or medical certificate -- the
insured-risk events of IRM19 point 3 letter b) belong with the leave module. No
suspension code: the IRM19 classifier of employment relationships is a text this
repository does not hold, and inventing codes for it would produce declarations
that validate and are wrong.
"""

from __future__ import annotations

import uuid

from django.db import models

from evidenta.platform.tenancy.models import Company, Tenant


class TaxResidency(models.TextChoices):
    """Resident or not -- and no default.

    Residency decides the whole shape of the withholding, so a default would let
    the row arrive without anyone deciding, which is the pattern `source_confidence`
    already argues for in `fiscal`.
    """

    RESIDENT = "resident"
    NON_RESIDENT = "non_resident"


#: The points of annex 1 to Law 489/1999 whose payer column (a) names the
#: **employer**. 1.3 is the independently practising doctor and 1.6 to 1.9 are
#: individuals paying for themselves -- none of them is a category an employment
#: relationship can carry, so none of them is accepted here.
#:
#: **Closed at the employer's points, not at the annex's ten**, and the narrowing
#: is the honest half: what this module computes today is the general regime.
#: Widening it is a row in the register plus a migration, which is visible;
#: accepting a point no handler exists for is not.
EMPLOYER_CAS_POINTS = ("1.1", "1.2", "1.4", "1.5")


class Employee(models.Model):
    """A person, at the level of the company that employs them.

    **The identity is a constraint, not a sentence.** Residents are identified by
    IDNP; those without one by an identity document, whose type and number then
    carry the uniqueness. Exactly one of the two, enforced by a CHECK -- because
    the row for which the exception is made is precisely the row that would
    otherwise have no natural key at all, and the same person would be entered
    twice on re-hiring, with two streams of withholdings behind them.

    Collation follows `Company.idno` (`C34`, ADR-015): IDNP and the document
    number are **codes** and take `COLLATE "C"` in the migration's SQL; the names
    are **names** and keep the database collation. Without that, any report
    ordered by IDNP comes out sorted linguistically, silently.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    #: Two columns rather than one, because the declaration asks for two: IRM19
    #: col. 2 is *"the surname and given name of the individual, as in the
    #: identity document"*. ADR-065 section 4 says "the legal name"; splitting it
    #: is adding a field to an entity the ADR describes, not changing it.
    last_name = models.TextField()
    first_name = models.TextField()

    idnp = models.TextField(null=True, blank=True)
    identity_document_type = models.TextField(null=True, blank=True)
    identity_document_number = models.TextField(null=True, blank=True)

    tax_residency = models.TextField(choices=TaxResidency.choices)

    #: IRM19 col. 4 -- the personal social insurance code CNAS assigns. Nullable
    #: because it is assigned by an institution, not by us, and a person can be
    #: recorded before it comes back.
    social_insurance_code = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "employee"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(tax_residency__in=TaxResidency.values),
                name="employee_residency_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(idnp__isnull=False)
                    & models.Q(identity_document_type__isnull=True)
                    & models.Q(identity_document_number__isnull=True)
                )
                | (
                    models.Q(idnp__isnull=True)
                    & models.Q(identity_document_type__isnull=False)
                    & models.Q(identity_document_number__isnull=False)
                ),
                name="employee_exactly_one_identity",
            ),
            models.UniqueConstraint(
                fields=["company", "idnp"],
                condition=models.Q(idnp__isnull=False),
                name="employee_idnp_unique",
            ),
            models.UniqueConstraint(
                fields=["company", "identity_document_type", "identity_document_number"],
                condition=models.Q(idnp__isnull=True),
                name="employee_document_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "company", "last_name"], name="employee_name_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.last_name} {self.first_name}"


class EmploymentContract(models.Model):
    """The head of the series -- ADR-067.

    Carries the clauses as signed. What changed afterwards lives on
    `EmploymentContractAmendment`, one row per signed amendment; "which clause was
    in force on date D" is read by walking the series, never from a column here.

    **Three dates that are not each other**, and art. 49 keeps them apart:
    `signed_on` is when it was signed, `effective_from` is when it starts
    producing effects (letter d), and `hire_order_date` is the date on the
    employer's order -- from which the IRM19 deadline runs, not from either of
    the other two.

    **`relationship_type` is `NOT NULL` and has no default** (ADR-071 section
    4bis). A nullable domain would make *"no type"* expressible, and `NULL` would
    inevitably read as *"applies anywhere"* -- which is the value the foreign key
    exists to make unwritable.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")
    employee = models.ForeignKey(
        Employee, on_delete=models.PROTECT, db_column="employee_id", related_name="contracts"
    )

    #: The domain of the art. 22 invariant, as a key rather than a string
    #: (ADR-071). With a string somebody writes `orice_bază_CAS` and the defect is
    #: back; with a key, a type that does not exist never reaches the table.
    relationship_type = models.ForeignKey(
        "fiscal_registry.EmploymentRelationshipType",
        on_delete=models.PROTECT,
        db_column="relationship_type",
        related_name="contracts",
    )

    contract_number = models.TextField()
    signed_on = models.DateField()
    effective_from = models.DateField()

    #: The end agreed at signing, for a fixed-term contract. Distinct from
    #: `ended_on`, which is when it actually ended: a contract can end early, and
    #: a model that keeps one column cannot tell "was due to end" from "ended".
    effective_to = models.DateField(null=True, blank=True)
    ended_on = models.DateField(null=True, blank=True)

    #: The generating fact of the IRM19 record (instruction point 3). Required:
    #: a hire without an order is not a hire that can be reported.
    hire_order_number = models.TextField()
    hire_order_date = models.DateField()

    termination_order_number = models.TextField(null=True, blank=True)
    termination_order_date = models.DateField(null=True, blank=True)

    #: Free text until the classifier of positions (IRM19 col. 11) is obtained.
    #: The column is ready for a code; what is missing is the list, and a list
    #: invented here would produce declarations that validate and are wrong.
    position_title = models.TextField()

    base_salary = models.DecimalField(max_digits=18, decimal_places=4)

    #: Needed by art. 22 para (1), not by presentation: the minimum base is
    #: proportional to time worked, and at part time the contribution may not be
    #: under 25% of the one at the minimum wage. A handler that multiplies base by
    #: rate misses it, which is why the hours are stored rather than assumed.
    weekly_hours = models.DecimalField(max_digits=5, decimal_places=2)

    #: The CAS payer category, **of the relationship rather than of the company**
    #: (ADR-068 section 3). A resident of an IT park is simultaneously point 1.4
    #: for its employees and point 1.1 for its civil contracts, so a column on the
    #: company cannot answer the question the declaration asks.
    cas_payer_point = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "employment_contract"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "contract_number"], name="employment_contract_number_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(effective_to__isnull=True)
                | models.Q(effective_to__gte=models.F("effective_from")),
                name="employment_contract_term_ordered",
            ),
            models.CheckConstraint(
                condition=models.Q(ended_on__isnull=True)
                | models.Q(ended_on__gte=models.F("effective_from")),
                name="employment_contract_end_after_start",
            ),
            models.CheckConstraint(
                condition=models.Q(base_salary__gte=0), name="employment_contract_salary_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(weekly_hours__gt=0), name="employment_contract_hours_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(cas_payer_point__in=EMPLOYER_CAS_POINTS),
                name="employment_contract_cas_point_valid",
            ),
            # An ended contract says by which order it ended. Without this the
            # end date can arrive with nothing behind it, and the IRM19 line for
            # the termination has no date to run its deadline from.
            models.CheckConstraint(
                condition=models.Q(ended_on__isnull=True)
                | (
                    models.Q(termination_order_number__isnull=False)
                    & models.Q(termination_order_date__isnull=False)
                ),
                name="employment_contract_end_has_an_order",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "company", "effective_from"], name="employment_contract_idx"
            ),
            models.Index(fields=["employee"], name="employment_contract_emp_idx"),
        ]

    def __str__(self) -> str:
        return self.contract_number


class EmploymentContractAmendment(models.Model):
    """One signed amendment -- ADR-067.

    Art. 49 para (1) has nineteen clauses and any change to any of them requires
    one of these. Three of them are modelled as columns because the calculation
    consumes them; the rest are named by `changed_clause` and described in
    `note`, so an amendment to a clause this module does not model is still
    recordable rather than silently absent.

    A `NULL` column means *that clause was not touched by this amendment*, which
    is why none of them carries a default.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")
    contract = models.ForeignKey(
        EmploymentContract,
        on_delete=models.PROTECT,
        db_column="contract_id",
        related_name="amendments",
    )

    amendment_number = models.TextField()
    signed_on = models.DateField()
    effective_from = models.DateField()

    #: The order that carries the change. Required for the same reason the hire
    #: order is: the IRM19 deadline for a modification runs from it.
    order_number = models.TextField()
    order_date = models.DateField()

    #: Which clause of art. 49 para (1) changed -- the letter, as the article
    #: numbers them. Required, and it is what makes an unmodelled clause
    #: representable instead of invisible.
    changed_clause = models.TextField()
    note = models.TextField(blank=True, default="")

    position_title = models.TextField(null=True, blank=True)
    base_salary = models.DecimalField(max_digits=18, decimal_places=4, null=True, blank=True)
    weekly_hours = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "employment_contract_amendment"
        constraints = [
            models.UniqueConstraint(
                fields=["contract", "amendment_number"],
                name="employment_amendment_number_unique",
            ),
            models.CheckConstraint(
                condition=~models.Q(changed_clause=""), name="employment_amendment_has_clause"
            ),
            models.CheckConstraint(
                condition=models.Q(base_salary__isnull=True) | models.Q(base_salary__gte=0),
                name="employment_amendment_salary_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(weekly_hours__isnull=True) | models.Q(weekly_hours__gt=0),
                name="employment_amendment_hours_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["contract", "effective_from"], name="employment_amendment_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.contract_id}/{self.amendment_number}"


class TimesheetStatus(models.TextChoices):
    OPEN = "open"
    CLOSED = "closed"


class Timesheet(models.Model):
    """One month of one company's attendance.

    `norm_hours` is entered rather than derived: the working-time norm comes from
    the production calendar, which this repository does not hold. Entering it is
    what an accountant does anyway; deriving it from a calendar we do not have
    would be a number nobody can defend.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    year = models.IntegerField()
    month = models.IntegerField()
    norm_hours = models.DecimalField(max_digits=7, decimal_places=2)
    status = models.TextField(choices=TimesheetStatus.choices, default=TimesheetStatus.OPEN)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "timesheet"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "year", "month"], name="timesheet_month_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(month__gte=1) & models.Q(month__lte=12),
                name="timesheet_month_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(norm_hours__gt=0), name="timesheet_norm_positive"
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=TimesheetStatus.values), name="timesheet_status_valid"
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "company", "year", "month"], name="timesheet_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.year}-{self.month:02d}"


class TimesheetDay(models.Model):
    """Hours on one day of one contract.

    **Hours per day rather than days per month**, and the choice is not
    stylistic: art. 22 para (1) wants the minimum base proportional to time
    worked, and at part time a share of the contribution at the minimum wage.
    Days can be derived from hours; hours cannot be derived from days.

    Night and holiday hours are *part of* the hours worked, not additions to
    them -- they carry a different rate, not a different day. The CHECKs say so,
    because a model that let them exceed the day would produce a payroll that
    balances and is wrong.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")
    timesheet = models.ForeignKey(
        Timesheet, on_delete=models.CASCADE, db_column="timesheet_id", related_name="days"
    )
    contract = models.ForeignKey(
        EmploymentContract,
        on_delete=models.PROTECT,
        db_column="contract_id",
        related_name="timesheet_days",
    )

    work_date = models.DateField()
    hours_worked = models.DecimalField(max_digits=5, decimal_places=2)
    night_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    holiday_hours = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    class Meta:
        db_table = "timesheet_day"
        constraints = [
            models.UniqueConstraint(fields=["contract", "work_date"], name="timesheet_day_unique"),
            models.CheckConstraint(
                condition=models.Q(hours_worked__gte=0) & models.Q(hours_worked__lte=24),
                name="timesheet_day_hours_in_a_day",
            ),
            models.CheckConstraint(
                condition=models.Q(night_hours__gte=0)
                & models.Q(night_hours__lte=models.F("hours_worked")),
                name="timesheet_day_night_within_worked",
            ),
            models.CheckConstraint(
                condition=models.Q(holiday_hours__gte=0)
                & models.Q(holiday_hours__lte=models.F("hours_worked")),
                name="timesheet_day_holiday_within_worked",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "company", "work_date"], name="timesheet_day_idx"),
            models.Index(fields=["timesheet", "contract"], name="timesheet_day_contract_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.contract_id} {self.work_date}"


class ExemptionCode(models.TextChoices):
    """The codes an exemption application can carry -- ADR-065 section 5.

    **Five, and the absence of a sixth is the point.** There is no ordinary
    spouse exemption: art. 34 para (2) grants only the increased one, so `S` does
    not exist and a vocabulary that offered it would let somebody claim an
    exemption the Fiscal Code does not give. The parameter
    `income_tax.exemption_spouse_ordinary = 0` is already loaded for the same
    reason -- the exemption that is not granted has to be visibly zero rather
    than absent.

    HG 697/2014 point 11 still refers to *"art. 34 para (1) or (2)"*: the
    regulation lagged behind the Code. ADR-045 is the rule that stops anyone
    "correcting" the engine towards the regulation -- amounts come from the Code,
    the regulation gives the procedure.

    No amounts here. What an exemption is worth is a fiscal parameter (`R15`),
    resolved by the effective date of the period being calculated.
    """

    PERSONAL = "P"
    PERSONAL_MAJOR = "M"
    SPOUSE_MAJOR = "Sm"
    DEPENDENT = "N"
    DEPENDENT_DISABLED = "H"


#: The codes that name somebody other than the employee, and therefore require a
#: dependent to point at. Enumerated rather than inferred from the letter: `Sm`
#: is about a spouse and still is not one of these, because the increased spouse
#: exemption is granted on the spouse's status, not on a dependent's identity.
DEPENDENT_CODES = (ExemptionCode.DEPENDENT, ExemptionCode.DEPENDENT_DISABLED)


class Dependent(models.Model):
    """A person an employee's exemption is claimed for.

    **With an identifier of their own**, and ADR-065 section 5 says why: without
    one there is no legitimate uniqueness constraint either, so the same child
    entered twice on one employee is indistinguishable from two children.

    **And no uniqueness across employees.** The number of taxpayers who may claim
    the exemption for the same person is not limited by law -- both parents may
    claim for the same child -- so a `UNIQUE` there would be our invention,
    refusing a case the law allows, with no way for the person to find out why.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")
    employee = models.ForeignKey(
        Employee, on_delete=models.PROTECT, db_column="employee_id", related_name="dependents"
    )

    last_name = models.TextField()
    first_name = models.TextField()
    idnp = models.TextField(null=True, blank=True)
    identity_document_type = models.TextField(null=True, blank=True)
    identity_document_number = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "exemption_dependent"
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(idnp__isnull=False)
                    & models.Q(identity_document_type__isnull=True)
                    & models.Q(identity_document_number__isnull=True)
                )
                | (
                    models.Q(idnp__isnull=True)
                    & models.Q(identity_document_type__isnull=False)
                    & models.Q(identity_document_number__isnull=False)
                ),
                name="dependent_exactly_one_identity",
            ),
            models.UniqueConstraint(
                fields=["employee", "idnp"],
                condition=models.Q(idnp__isnull=False),
                name="dependent_idnp_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "company", "employee"], name="dependent_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.last_name} {self.first_name}"


class ExemptionApplication(models.Model):
    """The employee's application -- annex 6 to HG 697/2014.

    **`filed_on` is stored, not only used.** Point 18 grants and cancels
    exemptions *from the month following* the one the application was filed or
    withdrawn in. With only the effective date, that rule lives in the
    application: a bulk import or a correction written straight into the table
    walks past it, and recalculating a past month (`R18`) has no stored fact to
    show the date was derived correctly. With `filed_on`, it is a CHECK.

    **`declared_sole_workplace` is the employee's declaration, and it is stored
    as one.** Point 9 grants exemptions at one place of work only -- a fact about
    the person across employers, which no employer can verify and this system
    cannot see across tenants. What the employer relies on is the declaration on
    the form, so that is what the row carries: not a check we cannot perform,
    but the evidence the employer acted on.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        db_column="employee_id",
        related_name="exemption_applications",
    )

    filed_on = models.DateField()

    #: The first day of the month after `filed_on`. Derived by the service and
    #: **checked by the database**, which is the difference between a rule and a
    #: habit.
    effective_from = models.DateField()

    declared_sole_workplace = models.BooleanField()
    note = models.TextField(blank=True, default="")

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "exemption_application"
        indexes = [
            models.Index(
                fields=["tenant", "company", "employee", "effective_from"],
                name="exemption_application_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.employee_id} {self.filed_on}"


class ExemptionEntitlement(models.Model):
    """One exemption, for one period. The history point 18 makes necessary.

    Granted by an application and withdrawn by another, so the row can always say
    *which document* opened and closed it. "What exemptions did this person have
    in March" is a query by date, which is what `R18` asks of every recalculation
    of a past month -- and what a boolean on the employee could never answer.

    The overlap constraint is in SQL (an `EXCLUDE`), because the pair it has to
    refuse is *the same dependent, the same code, overlapping periods* -- the
    same child entered twice -- while leaving the case the law allows: two
    employees claiming for the same person.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")
    employee = models.ForeignKey(
        Employee,
        on_delete=models.PROTECT,
        db_column="employee_id",
        related_name="exemptions",
    )

    code = models.TextField(choices=ExemptionCode.choices)
    dependent = models.ForeignKey(
        Dependent,
        on_delete=models.PROTECT,
        db_column="dependent_id",
        null=True,
        blank=True,
        related_name="entitlements",
    )

    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    granted_by = models.ForeignKey(
        ExemptionApplication,
        on_delete=models.PROTECT,
        db_column="granted_by_id",
        related_name="granted",
    )
    withdrawn_by = models.ForeignKey(
        ExemptionApplication,
        on_delete=models.PROTECT,
        db_column="withdrawn_by_id",
        null=True,
        blank=True,
        related_name="withdrawn",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "exemption_entitlement"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(code__in=ExemptionCode.values),
                name="exemption_code_valid",
            ),
            # `N` and `H` name somebody; `P`, `M` and `Sm` do not. Both halves
            # are enforced: a dependent on a personal exemption is as wrong as a
            # missing one on `N`, and it would silently double a claim.
            models.CheckConstraint(
                condition=(models.Q(code__in=DEPENDENT_CODES) & models.Q(dependent__isnull=False))
                | (~models.Q(code__in=DEPENDENT_CODES) & models.Q(dependent__isnull=True)),
                name="exemption_dependent_matches_code",
            ),
            models.CheckConstraint(
                condition=models.Q(valid_to__isnull=True)
                | models.Q(valid_to__gt=models.F("valid_from")),
                name="exemption_period_valid",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "company", "employee", "valid_from"],
                name="exemption_entitlement_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.employee_id} {self.code} {self.valid_from}"
