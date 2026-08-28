"""Instantiating a template version into one company's chart -- Spec B section 2.3.

Runs under an ordinary tenant context: the company already exists and the caller
can see it, so RLS answers "may this context touch this company" before the
service does anything. There is no privileged path here and there should not be.

**Where this gets called from is not built yet.** Creating a company is `P-9`
(ADR-040), decided and unwritten, and the onboarding wizard that chooses the
starting period (ADR-039 section 11) is the same missing screen. Until then the
service is called directly -- which is what the tests do, and what a data
migration would do.
"""

from __future__ import annotations

import uuid

from django.db import transaction

from evidenta.accounting.coa.errors import (
    ChartAlreadyInstantiatedError,
    CompanyNotVisibleError,
    TemplateNotPublishedError,
)
from evidenta.accounting.coa.models import (
    AccountOrigin,
    CoaTemplate,
    CoaTemplateAccount,
    CompanyAccount,
    CompanyChart,
    TemplateStatus,
)
from evidenta.platform.audit.services.recording import record
from evidenta.platform.rls.context import MissingTenantContextError, current_context
from evidenta.platform.tenancy.services.access import company_visible_in_context


@transaction.atomic
def instantiate_chart(company_id: uuid.UUID, template_id: uuid.UUID) -> CompanyChart:
    """Copy a published template version into ``company_id`` as its chart.

    Every account of the version is copied, including ones whose validity window
    has not opened yet or has already closed. Filtering to "valid today" would
    make the chart depend on the day it was created, and R18 asks the opposite:
    recalculating an earlier period has to find the account as it was then.

    Parents are resolved in a second pass. Inside a template the hierarchy is a
    code, and the published act does not promise that a parent is listed before
    its children.

    ``origin`` comes from the template's ``is_system``. That is where the column
    is read, and reading it anywhere else would be inventing a second meaning for
    it: section 2.2 puts the flag on the template account and section 2.4
    contrasts the same two kinds on the company side, so they are one fact
    written in two places. A template row marked ``is_system = false`` yields a
    renameable account that still keeps its ``template_account`` link, so
    propagation can find it either way.
    """
    context = current_context()
    if context is None:
        raise MissingTenantContextError("instantiate_chart needs a tenant context")

    # Asked of `tenancy`, not read off `Company`. The company's tenant is the one
    # in context by construction -- the policy on every table here requires
    # `tenant_id = app.current_tenant_id()` -- so there is nothing to look up on
    # the row, and looking it up anyway would be `D6` arriving as a convenience.
    if not company_visible_in_context(company_id):
        raise CompanyNotVisibleError(f"company {company_id} is not visible in this context")

    if CompanyChart.objects.filter(company_id=company_id).exists():
        raise ChartAlreadyInstantiatedError(f"company {company_id} already has a chart")

    template = CoaTemplate.objects.filter(id=template_id).first()
    if template is None or template.status != TemplateStatus.PUBLISHED:
        raise TemplateNotPublishedError(
            f"template {template_id} is not published; a company is not built on a draft"
        )

    chart = CompanyChart.objects.create(
        tenant_id=context.tenant_id, company_id=company_id, template=template
    )

    source = list(CoaTemplateAccount.objects.filter(template_id=template_id))
    CompanyAccount.objects.bulk_create(
        [
            CompanyAccount(
                tenant_id=context.tenant_id,
                company_id=company_id,
                account_code=account.account_code,
                origin=(AccountOrigin.SYSTEM if account.is_system else AccountOrigin.COMPANY),
                template_account=account,
                name_ro=account.name_ro,
                account_class=account.account_class,
                normal_balance=account.normal_balance,
                allows_subaccounts=account.allows_subaccounts,
                currency_tracking=account.currency_tracking,
                quantity_tracking=account.quantity_tracking,
                required_dimensions=list(account.required_dimensions),
                # The plan's declaration of what the account carries, copied
                # like the rest (ADR-048). The company may extend it later;
                # what it starts with is what the act's transcription said.
                slot_1_dimension=account.slot_1_dimension,
                slot_2_dimension=account.slot_2_dimension,
                slot_3_dimension=account.slot_3_dimension,
                slot_4_dimension=account.slot_4_dimension,
                valid_from=account.valid_from,
                valid_to=account.valid_to,
            )
            for account in source
        ]
    )

    _link_parents(company_id, source)

    # Explicit, from the service (C4, F0.4.2). Instantiating a chart happens once
    # per company and decides which published version every later posting is read
    # against -- so "which version, chosen when, by whom" has to be answerable
    # without inferring it from row timestamps.
    record(
        action="coa.chart_instantiated",
        entity_type="company_chart",
        entity_id=chart.id,
        company_id=company_id,
        new_value={
            "template_id": str(template.id),
            "template": f"{template.code}/{template.version}",
            "accounts": len(source),
        },
    )
    return chart


def _link_parents(company_id: uuid.UUID, source: list[CoaTemplateAccount]) -> None:
    """Second pass: turn ``parent_code`` into ``parent_id`` within this company.

    A parent code the template does not define is left unlinked rather than
    refused. That is not leniency about bad data -- it is where the refusal
    belongs: the loader that publishes a template version is the place that knows
    the act, and it does not exist yet (`OD-23`). Refusing here would move the
    failure to the first company created, months later, with nothing to fix it
    against.
    """
    by_code = {
        account.account_code: account.id
        for account in CompanyAccount.objects.filter(company_id=company_id).only(
            "id", "account_code"
        )
    }

    updates = []
    for account in source:
        if not account.parent_code:
            continue
        parent_id = by_code.get(account.parent_code)
        child_id = by_code.get(account.account_code)
        if parent_id is None or child_id is None:
            continue
        updates.append(CompanyAccount(id=child_id, parent_id=parent_id))

    if updates:
        CompanyAccount.objects.bulk_update(updates, ["parent_id"])
