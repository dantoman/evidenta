"""Document numbering -- ADR-022: a template, not a formula.

The company defines the shape of the number; the platform applies it and
guarantees uniqueness. A template can be general, for every document type of the
company, or specific to one type -- resolution takes the specific one when it
exists, and a type with neither is a configuration error rather than an invented
default.

``prefix`` is where a branch, a point of sale or a fiscal series goes. The branch
is deliberately not modelled: it would add a level to the tenancy layer, which is
layer zero. The accepted consequence, stated in the ADR rather than discovered
later: **the platform does not know what the series means.** It cannot report by
branch, cannot check that a branch is real, and cannot stop a user issuing on
someone else's series.
"""

from __future__ import annotations

import uuid

from django.db import models

from evidenta.platform.tenancy.models import Company, Tenant


class ResetPolicy(models.TextChoices):
    NEVER = "never"
    YEARLY = "yearly"
    MONTHLY = "monthly"


class YearFormat(models.TextChoices):
    FOUR_DIGIT = "yyyy"
    TWO_DIGIT = "yy"


class NumberingTemplate(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    # Null means the general template: it applies to every document type that has
    # no template of its own.
    document_type = models.TextField(null=True, blank=True)

    series = models.TextField(default="")
    prefix = models.TextField(default="")
    suffix = models.TextField(default="")
    separator = models.TextField(default="")
    digits = models.SmallIntegerField(default=6)

    include_year = models.BooleanField(default=True)
    year_format = models.TextField(choices=YearFormat.choices, default=YearFormat.FOUR_DIGIT)

    reset_policy = models.TextField(choices=ResetPolicy.choices, default=ResetPolicy.YEARLY)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "numbering_template"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(digits__gte=1) & models.Q(digits__lte=12),
                name="numbering_template_digits_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(reset_policy__in=ResetPolicy.values),
                name="numbering_template_reset_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(year_format__in=YearFormat.values),
                name="numbering_template_year_format_valid",
            ),
            # One general template per company, and one per document type.
            # Postgres treats NULLs as distinct in a unique index, so the general
            # template needs its own partial constraint or a company could hold
            # several of them and resolution would pick arbitrarily.
            models.UniqueConstraint(
                fields=["company", "document_type"],
                condition=models.Q(document_type__isnull=False),
                name="numbering_template_per_type_unique",
            ),
            models.UniqueConstraint(
                fields=["company"],
                condition=models.Q(document_type__isnull=True),
                name="numbering_template_general_unique",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.company_id}:{self.document_type or '*'}"


class NumberingCounter(models.Model):
    """The next number, as a row that can be locked.

    Not ``MAX(number) + 1``. Under concurrency two transactions read the same
    maximum and both write it, and a duplicate invoice number is a compliance
    defect rather than a display glitch. A counter row taken with ``SELECT FOR
    UPDATE`` serialises exactly the allocation and nothing else.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    template = models.ForeignKey(
        NumberingTemplate, on_delete=models.PROTECT, db_column="template_id"
    )

    # Identifies the reset window: "2026", "2026-03", or "" when the policy is
    # never. Keeping it as text means changing the policy does not need a
    # different table.
    period_key = models.TextField()

    next_number = models.BigIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "numbering_counter"
        constraints = [
            models.UniqueConstraint(
                fields=["template", "period_key"], name="numbering_counter_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(next_number__gte=1),
                name="numbering_counter_positive",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.template_id}:{self.period_key}={self.next_number}"
