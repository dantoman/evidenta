"""The unified monthly return -- IPC. One entity, three sections.

**Article 5 para (1) of Law 489/1999 decides the shape.** The declaration on the
nominal record of insured persons and the one on the calculation of social
contributions are *part of* the return, not returns of their own. So this is one
header with a totals section and a nominal section, not three objects that have
to be kept in step.

**It is versioned, and that is form rather than convenience** (art. 188 of the
Fiscal Code): a correction is a *corrected return*, a new version, never an
overwrite. Adding versioning after returns have been filed is a migration over
artefacts already transmitted -- which is why it is here on the first day.

**It stores its rows; it does not recompute them.** Regenerating a past period has
to produce what was filed then, not what today's rules would produce -- the rates,
the codes, the identities and the amounts are frozen at generation. That is the
same reason a posted journal line carries its own accrual date rather than
looking one up.

**What is deliberately absent.** The printed form: Annex 1 of Ordinul MF nr.
94/2020 is not in this repository (`f2-x2-formularele-sfs.md` reconstructs its
shape from ministry drafts and marks every inference as one), and Annex 4 -- the
validations the tax service's channel applies -- is not obtained at all. What is
built is the register the form reads from; the rendering waits for the text.
"""

from __future__ import annotations

import uuid

from django.db import models

from evidenta.platform.tenancy.models import Company, Tenant


class DeclarationStatus(models.TextChoices):
    DRAFT = "draft"
    SUBMITTED = "submitted"


class IpcDeclaration(models.Model):
    """One version of one month's return.

    The header carries what the form's header carries, **frozen**: the company's
    fiscal code, the classifier codes, the period, the deadline and the date of
    submission. Frozen because a return filed in March under one CAEM code does
    not become a return under another the day somebody corrects the company card.

    `version_number` is 1 for the primary return and grows with each correction;
    `corrects` points at the version this one replaces, so the chain reads in both
    directions. Nothing is ever deleted or overwritten.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    year = models.IntegerField()
    month = models.IntegerField()

    version_number = models.IntegerField()
    corrects = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        db_column="corrects_id",
        null=True,
        blank=True,
        related_name="corrected_by",
    )

    #: Frozen from the company at generation. The fiscal code is required -- a
    #: return without one identifies nobody -- while the two classifier codes are
    #: nullable, because neither classifier is in this repository. A generated
    #: return says which of them was missing instead of carrying an invented one.
    fiscal_code = models.TextField()
    cuatm_code = models.TextField(null=True, blank=True)
    caem_code = models.TextField(null=True, blank=True)

    #: The 25th of the month following the reporting month -- art. 5 para (1)
    #: letter a) of Law 489/1999, and art. 92 para (1)-(2) of the Fiscal Code for
    #: the withheld tax. Stored rather than derived at read time: a deadline rule
    #: that changes must not silently restate what a filed return was due by.
    due_on = models.DateField()

    status = models.TextField(choices=DeclarationStatus.choices, default=DeclarationStatus.DRAFT)
    submitted_on = models.DateField(null=True, blank=True)

    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "ipc_declaration"
        constraints = [
            models.UniqueConstraint(
                fields=["company", "year", "month", "version_number"],
                name="ipc_declaration_version_unique",
            ),
            models.CheckConstraint(
                condition=models.Q(month__gte=1) & models.Q(month__lte=12),
                name="ipc_declaration_month_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(version_number__gte=1),
                name="ipc_declaration_version_positive",
            ),
            # A first version corrects nothing; every later one corrects
            # something. Without this, a chain can start in the middle and the
            # question "which return did this replace" has no answer.
            models.CheckConstraint(
                condition=(models.Q(version_number=1) & models.Q(corrects__isnull=True))
                | (models.Q(version_number__gt=1) & models.Q(corrects__isnull=False)),
                name="ipc_declaration_correction_chain",
            ),
            models.CheckConstraint(
                condition=~models.Q(status=DeclarationStatus.SUBMITTED)
                | models.Q(submitted_on__isnull=False),
                name="ipc_declaration_submitted_has_a_date",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=DeclarationStatus.values),
                name="ipc_declaration_status_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "company", "year", "month"], name="ipc_declaration_idx"),
        ]

    def __str__(self) -> str:
        return f"IPC {self.year}-{self.month:02d} v{self.version_number}"


class IpcTotalLine(models.Model):
    """One row of the totals section: the three withholdings, by code.

    **Two code columns, not one, and the reason is that the adopted form splits
    the same numbers two ways.** Table 1 groups income and the two withheld
    amounts by *income source code*; the second part of table 2 groups the social
    contribution by *tariff row*. Carrying both dimensions on the row means either
    grouping is a read rather than a second stored truth -- and neither is
    invented, because the row is written from what the calculation actually
    produced.

    Amounts are frozen at generation and never recomputed.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")
    declaration = models.ForeignKey(
        IpcDeclaration,
        on_delete=models.CASCADE,
        db_column="declaration_id",
        related_name="totals",
    )

    #: From the classifier of income source codes (Ordinul MF nr. 126/2017),
    #: which is **not** in this repository. Today the only value written is `SAL`,
    #: named in the IPC instruction's own ECO mapping; nothing derives a second
    #: code from anything.
    income_source_code = models.TextField()

    #: The row of the tariff table: `1.1a` budget-funded, `1.1b` private.
    cas_tariff_code = models.TextField()

    income_paid = models.DecimalField(max_digits=18, decimal_places=2)
    income_tax_withheld = models.DecimalField(max_digits=18, decimal_places=2)
    health_insurance_withheld = models.DecimalField(max_digits=18, decimal_places=2)
    social_contribution = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        db_table = "ipc_total_line"
        constraints = [
            models.UniqueConstraint(
                fields=["declaration", "income_source_code", "cas_tariff_code"],
                name="ipc_total_line_unique",
            ),
            # Every amount is a magnitude, as in the cumulatives (ADR-061): the
            # meaning is in the code, never in the sign.
            models.CheckConstraint(
                condition=models.Q(income_paid__gte=0)
                & models.Q(income_tax_withheld__gte=0)
                & models.Q(health_insurance_withheld__gte=0)
                & models.Q(social_contribution__gte=0),
                name="ipc_total_line_amounts_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.income_source_code}/{self.cas_tariff_code}"


class IpcNominalLine(models.Model):
    """One insured person's row -- the nominal section.

    **The population is insured persons, not employees** (ADR-069). Today they
    coincide because civil contracts are a later step; the word here is the wide
    one so that nothing changes when they stop coinciding.

    **`person_id` is a plain identifier, not a foreign key**, and that is the same
    decision: a key into `employee` would say that every insured person is one,
    which art. 19 para (7) contradicts. The identity is **frozen** alongside it --
    a filed return names the person as they were named then, and a corrected
    surname does not rewrite what was transmitted.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")
    declaration = models.ForeignKey(
        IpcDeclaration,
        on_delete=models.CASCADE,
        db_column="declaration_id",
        related_name="nominal",
    )

    #: Column 1 of the nominal table. Stored rather than derived from the read
    #: order, so two readings of one filed return number the rows identically.
    line_number = models.IntegerField()

    person_id = models.UUIDField()
    last_name = models.TextField()
    first_name = models.TextField()

    #: Column 3, thirteen digits, and mandatory on the adopted form. Nullable
    #: here because a non-resident has none: the form's answer to that is `0`,
    #: which is a rendering decision and not a fact about the person.
    idnp = models.TextField(null=True, blank=True)

    #: Column 4 -- the personal social insurance code CNAS assigns. Nullable for
    #: the same reason: it comes from an institution, not from us.
    personal_insurance_code = models.TextField(null=True, blank=True)

    #: Columns 5 and 6.
    work_period_start = models.DateField()
    work_period_end = models.DateField()

    #: Column 7, from Annex 3's classifier of insured-person categories -- which
    #: is **not obtained**. Nullable, and the generator writes nothing rather than
    #: guessing a numeric code: a wrong category on a filed return is not an error
    #: the channel rejects, it is a right answer to a different question.
    insured_category_code = models.TextField(null=True, blank=True)

    #: Column 7¹, the tariff; column 9, the base; column 11, the contribution.
    tariff_rate = models.DecimalField(max_digits=9, decimal_places=4, null=True, blank=True)
    insured_income = models.DecimalField(max_digits=18, decimal_places=2)
    contribution = models.DecimalField(max_digits=18, decimal_places=2)

    class Meta:
        db_table = "ipc_nominal_line"
        constraints = [
            models.UniqueConstraint(
                fields=["declaration", "person_id"], name="ipc_nominal_line_unique"
            ),
            models.UniqueConstraint(
                fields=["declaration", "line_number"], name="ipc_nominal_line_number_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(insured_income__gte=0) & models.Q(contribution__gte=0),
                name="ipc_nominal_line_amounts_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(work_period_end__gte=models.F("work_period_start")),
                name="ipc_nominal_line_period_ordered",
            ),
        ]
        indexes = [
            models.Index(fields=["declaration", "person_id"], name="ipc_nominal_person_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.line_number}. {self.last_name} {self.first_name}"
