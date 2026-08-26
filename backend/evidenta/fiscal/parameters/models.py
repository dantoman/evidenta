"""Fiscal parameters as versioned data -- R15, amendment section B.1.

The invariant splits compliance in two. **Parameters are data**: rates,
thresholds, ceilings, exemptions, coefficients, deadlines, default account
mappings. Changing one is an INSERT. **Logic is versioned code**: calculation
algorithms, declaration schemas, validation rules -- changing one is a
deployment, and that is correct rather than a failure.

This module is the first half. It holds no values.

**No rate, threshold or deadline is in this repository**, and none will be added
by anyone reading a changelog. Every parameter carries provenance -- the act, the
Monitorul Oficial number, the publication and effective dates -- because a rate
without a source is a number somebody typed, and a system that cannot say where a
number came from cannot defend a recalculation three years later. Filling them in
is OD-22, and it needs a citable source and the practising accountant.
"""

from __future__ import annotations

import uuid

from django.db import models


class ParameterScope(models.TextChoices):
    """Who a parameter applies to.

    Almost all are global -- the same law for everyone. ``company`` exists for
    the cases where an entity's own status changes the parameter, and it holds a
    plain identifier rather than a foreign key: fiscal depends on no business
    module (D1), and a key to `company` would be exactly that dependency.
    """

    GLOBAL = "global"
    COMPANY_CLASS = "company_class"
    COMPANY = "company"


class ValueType(models.TextChoices):
    DECIMAL = "decimal"
    INTEGER = "integer"
    MONEY = "money"
    PERCENTAGE = "percentage"
    DATE = "date"
    BOOLEAN = "boolean"
    TABLE = "table"


class ParameterStatus(models.TextChoices):
    DRAFT = "draft"
    APPROVED = "approved"
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class FiscalParameterSource(models.Model):
    """Where a parameter came from. Required, not decorative.

    ``fiscal-reviewer`` checks that every parameter has one, and the reason is
    not bookkeeping: recalculating a 2026 period in 2030 has to be defensible,
    and "the rate was 20%" is not an answer without "under which act, published
    when".

    **One publication per source, which is not always true.** An order and the
    annex it approves can appear in different issues months apart -- the chart of
    accounts was published as MO nr. 177-181 art. 1225 of 16.08.2013 while its
    annex, the nomenclature itself, came in MO nr. 233-237 art. 1534 of
    22.10.2013. The columns here record one of the two. Whether the second
    belongs in more columns or in a publications table is OD-65, left open rather
    than guessed: it decides what a citation looks like everywhere downstream.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    act_type = models.TextField()
    act_number = models.TextField()

    # Part of the act's identity, not decoration. Moldovan acts are cited as
    # number *and* date -- "Ordinul MF nr. 119 din 06.08.2013" -- because the
    # number alone repeats across years: the chart of accounts is amended by
    # orders 188/2014, 100/2019 and 111/2021, and the ministry issues a fresh
    # number sequence annually. A source row keyed on the number alone cannot
    # say which act it means.
    act_date = models.DateField()

    official_gazette_number = models.TextField(null=True, blank=True)

    # The pinpoint within the issue. Moldovan citations carry it -- "MO nr.
    # 177-181 art. 1225 din 16.08.2013" -- and an issue number without the
    # article is a magazine, not a reference.
    official_gazette_article = models.TextField(null=True, blank=True)

    published_at = models.DateField(null=True, blank=True)
    effective_from = models.DateField()
    url = models.TextField(null=True, blank=True)
    notes = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "fiscal_parameter_source"
        indexes = [
            models.Index(fields=["act_number", "act_date"], name="fiscal_source_act_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.act_type} {self.act_number} din {self.act_date}"


class FiscalParameter(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    parameter_key = models.TextField()
    scope = models.TextField(choices=ParameterScope.choices, default=ParameterScope.GLOBAL)

    # Null when scope is global. A plain identifier, not a foreign key -- see
    # ParameterScope.
    scope_ref = models.UUIDField(null=True, blank=True)

    value_type = models.TextField(choices=ValueType.choices)

    # jsonb, because not every fiscal parameter is a scalar: progressive scales,
    # ceilings by bracket, coefficients by asset class. The exact shape for those
    # -- free jsonb, dedicated tables per form, or jsonb with a declared schema --
    # is DNB-06 and open, so nothing here validates the inside of a `table` value
    # yet.
    value = models.JSONField()
    unit = models.TextField(null=True, blank=True)

    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    source = models.ForeignKey(
        "fiscal_parameters.FiscalParameterSource",
        on_delete=models.PROTECT,
        db_column="source_id",
    )

    status = models.TextField(choices=ParameterStatus.choices, default=ParameterStatus.DRAFT)
    approved_by_user_id = models.UUIDField(null=True, blank=True)
    approved_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "fiscal_parameter"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(valid_to__isnull=True)
                | models.Q(valid_to__gt=models.F("valid_from")),
                name="fiscal_parameter_period_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(scope__in=ParameterScope.values),
                name="fiscal_parameter_scope_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(value_type__in=ValueType.values),
                name="fiscal_parameter_value_type_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(status__in=ParameterStatus.values),
                name="fiscal_parameter_status_valid",
            ),
            # A global parameter with a scope reference, or a scoped one without,
            # is a row the resolver cannot place.
            models.CheckConstraint(
                condition=models.Q(scope=ParameterScope.GLOBAL, scope_ref__isnull=True)
                | ~models.Q(scope=ParameterScope.GLOBAL),
                name="fiscal_parameter_global_has_no_ref",
            ),
            # Nothing goes live without a practising accountant's approval
            # (amendment D.1). The approval is part of the compliance process, so
            # it is a constraint rather than a step someone remembers.
            models.CheckConstraint(
                condition=~models.Q(status=ParameterStatus.ACTIVE)
                | models.Q(approved_by_user_id__isnull=False),
                name="fiscal_parameter_active_requires_approval",
            ),
        ]
        indexes = [
            models.Index(fields=["parameter_key", "valid_from"], name="fiscal_parameter_key_idx"),
            models.Index(fields=["status"], name="fiscal_parameter_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.parameter_key}@{self.valid_from}"
