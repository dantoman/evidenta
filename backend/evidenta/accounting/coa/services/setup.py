"""Setting a company up to keep books -- the chart **and** the role bindings.

Two operations that are one product step, composed here rather than in a view or
in a screen. `instantiate_chart` stays the primitive it was: it copies a template
and answers for nothing else. What this adds is the step that has to happen with
it and never did.

**The gap this closes was measured, not suspected** (ADR-073 §10):
`install_default_bindings` had **no caller outside the tests**. Every company
created through the product had a chart and not one role binding, so the first
posting that asked for a role -- a sales invoice, a payroll entry, a settlement
difference -- would have failed with a refusal nobody could act on. Nothing
noticed because the only thing posting so far was the manual note, which names
accounts by id and never asks for a role.

**Why here and not inside `instantiate_chart`.** Installing the bindings requires
the chart to contain every account the catalogue names, and `install_default_bindings`
refuses on a missing one rather than binding half. Folding that into the primitive
would make a partial template impossible to instantiate at all -- which is a
different rule than the one being fixed, and one nobody asked for. Composed here,
the primitive keeps answering the narrow question and the product step carries the
requirement it actually has.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from evidenta.accounting.coa.services.instantiation import instantiate_chart
from evidenta.accounting.slots.services.binding import install_default_bindings
from evidenta.platform.rls.context import MissingTenantContextError, current_context
from evidenta.platform.tenancy.services.companies import accounting_start_date


@dataclass(frozen=True, slots=True)
class ChartSetup:
    chart_id: uuid.UUID
    bindings: int


def set_up_chart(company_id: uuid.UUID, template_id: uuid.UUID) -> ChartSetup:
    """Instantiate the chart and bind every role the catalogue names.

    Dated from the company's **accounting start**, not from today: a chart set up
    in September for books that start in January must bind the roles from January,
    or the first entry of the year meets a binding that did not exist yet.
    """
    context = current_context()
    if context is None:
        raise MissingTenantContextError("set_up_chart needs a tenant context")

    chart = instantiate_chart(company_id, template_id)
    bindings = install_default_bindings(
        tenant_id=context.tenant_id,
        company_id=company_id,
        on_date=accounting_start_date(company_id),
    )
    return ChartSetup(chart_id=chart.id, bindings=len(bindings))
