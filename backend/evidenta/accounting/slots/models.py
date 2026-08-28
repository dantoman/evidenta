"""What a role means for one company, over time.

Versioned because a plan can change and a posting made last year has to keep
resolving the way it resolved then (`R18`). Per company rather than per tenant,
for the plain reason that accounts are per company: a role has to end at a row of
``company_account``, and a tenant-level binding would still have to be resolved
company by company -- one indirection that could only ever disagree with itself.

Bound to the account by foreign key rather than by code. Both `coa` and this are
`accounting`, so the reference is inside one module family, and the alternative --
storing a code and looking it up at posting -- would let a binding survive the
account it names being closed.
"""

from __future__ import annotations

import uuid

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateRangeField, RangeBoundary, RangeOperators
from django.db import models
from django.db.models import F, Func, Q

from evidenta.platform.tenancy.models import Company, Tenant


class DateRange(Func):
    """``daterange(valid_from, valid_to, '[)')`` as an expression.

    Half-open on purpose: a binding that ends on the day the next one starts is
    not an overlap, and a closed upper bound would make every clean succession
    look like a conflict.
    """

    function = "daterange"
    output_field = DateRangeField()

    def __init__(self) -> None:
        # `RangeBoundary()` *is* the third argument -- it renders the bound spec,
        # and it already defaults to '[)'. Passing a literal alongside it produces
        # a four-argument call to a function that takes three, which fails at
        # migrate rather than at import.
        super().__init__(F("valid_from"), F("valid_to"), RangeBoundary())


class AccountRoleBinding(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    #: A member of `slots.catalogue.ROLES`. Byte-ordered (`C34`): it is a key.
    role = models.TextField()
    #: By lazy reference, not by importing `coa.models`. `D6` is about modules
    #: reaching into each other's models; a foreign key declared by label is the
    #: shape the rule asks for, and it is what `ledger` already does for the
    #: period and the accounting event.
    account = models.ForeignKey(
        "coa.CompanyAccount", on_delete=models.PROTECT, db_column="account_id", related_name="+"
    )

    valid_from = models.DateField()
    valid_to = models.DateField(null=True, blank=True)

    #: Where the mapping came from -- the act, or the decision that departed from
    #: it. A binding with no provenance cannot be defended at an inspection.
    source = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "account_role_binding"
        constraints = [
            models.CheckConstraint(
                condition=Q(valid_to__isnull=True) | Q(valid_to__gt=F("valid_from")),
                name="account_role_binding_dates_ordered",
            ),
            # Two bindings for one role at one instant is not a preference to
            # resolve -- it is two answers, and the engine would pick one by
            # accident. Refused by the database, where the race cannot get past it.
            ExclusionConstraint(
                name="account_role_binding_no_overlap",
                expressions=[
                    ("company", RangeOperators.EQUAL),
                    ("role", RangeOperators.EQUAL),
                    (DateRange(), RangeOperators.OVERLAPS),
                ],
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "company", "role"], name="account_role_binding_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.role} -> {self.account_id}"
