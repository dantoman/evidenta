"""Posting a set of formulas through the engine -- ADR-048, the formula path.

The manual note (`services.manual`) posts lines a person typed and derives
nothing. This is the other door: a handler has produced **formulas** for an
event, and the engine turns them into a posted entry. Same seven steps, same
refusals, same ledger writer -- the difference is what arrives, not where it
goes. There is no third door.

What this service does, in order, and why the order:

1. the chart is read once at the posting's date (`declarations_for`), and each
   formula's dimensions are **placed** -- each side keeps what its account
   declares, the row keeps the union
2. formulas that agree on the merge key are **folded**; the amount is the only
   thing that adds
3. the six invariants judge the expansion into lines (`invariants.verify`) --
   one implementation, not a second one for formulas -- and return the period
4. the mandatory dimensions are checked per side (`assert_dimensions_present`)
5. the chart version is read, so the header can say which chart the accounts
   came from (`coa.services.chart`)
6. a number is taken, last before the write, because a number consumed by a
   posting that is then refused is a permanent gap (ADR-022)
7. the ledger writes the entry, its lines, its formulas and its stamps in one
   transaction

**What it does not do.** It does not emit the accounting event and does not mark
it -- the caller owns the event, because the caller is the handler-specific
service that knows the source document and the idempotency key
(`services.manual` shows the shape). It does not resolve roles: `bind_roles`
exists for that and the caller runs it, because a caller may also arrive with
accounts already chosen (an import). And it computes no amount: a formula's
amount is the handler's, and from Stage 3 on a valuation strategy's.
"""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date

from django.db import transaction

from evidenta.accounting.coa.services.chart import chart_version_of
from evidenta.accounting.ledger.services.writing import ParameterStamp, post_entry
from evidenta.accounting.posting.dimensions import assert_dimensions_present
from evidenta.accounting.posting.formula import (
    Formula,
    NoFormulasError,
    declarations_for,
    formulas_to_write,
    line_dimensions,
    lines_to_write,
    merge,
    place,
    proposed_lines,
)
from evidenta.accounting.posting.invariants import Origin, ProposedPosting, verify
from evidenta.platform.numbering.services.allocation import allocate

#: The one series every journal entry is numbered in (ADR-022) -- the manual
#: note's, so an entry produced from formulas and one typed by hand sit in the
#: same register, indistinguishable by number.
NUMBERING_DOCUMENT_TYPE = "journal_entry"


@dataclass(frozen=True, slots=True)
class FormulaPostingResult:
    """What one posting through formulas produced."""

    journal_entry_id: uuid.UUID
    #: After merging -- the number of rows in ``journal_formula``.
    formulas: int
    #: Twice the formulas, always; stated so a caller can assert it.
    lines: int


@transaction.atomic
def post_formulas(
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    accounting_date: date,
    functional_currency: str,
    accounting_event_id: uuid.UUID,
    origin: Origin,
    rule_ref: str,
    description: str,
    request_id: str,
    actor_user_id: uuid.UUID | None,
    formulas: Sequence[Formula],
    fiscal_effective_date: date | None = None,
    entry_type: str = "standard",
    parameter_stamps: Sequence[ParameterStamp] = (),
) -> FormulaPostingResult:
    """Judge the formulas and write them as one posted entry, or refuse.

    ``rule_ref`` is the treatment that produced the formulas -- the
    ``implementation_ref`` `resolution.selected_treatment` hands back -- and it
    is stamped on the header. ``fiscal_effective_date`` defaults to the
    accounting date and is the date the fiscal set was resolved for; a caller
    whose economic date differs from its technical one (ADR-039 section 9.1)
    says so here.

    Every refusal is an ``ApiError`` with a stable code (C10). The formula shape
    refusals are this module's; the six invariants and the period keep their
    own; a role that does not bind refused before this was called.
    """
    if not formulas:
        raise NoFormulasError(
            f"a posting for company {company_id} on {accounting_date} has no "
            f"formulas; nothing to expand and nothing to balance"
        )

    declarations = declarations_for(company_id, accounting_date)
    placed = merge(place(formulas, declarations, functional_currency=functional_currency))

    period_id = verify(
        ProposedPosting(
            tenant_id=tenant_id,
            company_id=company_id,
            accounting_date=accounting_date,
            accounting_event_id=accounting_event_id,
            origin=origin,
            lines=proposed_lines(
                placed,
                tenant_id=tenant_id,
                company_id=company_id,
                accounting_date=accounting_date,
            ),
        )
    )
    assert_dimensions_present(company_id, accounting_date, line_dimensions(placed))

    chart = chart_version_of(company_id)
    number = allocate(tenant_id, company_id, NUMBERING_DOCUMENT_TYPE, accounting_date)

    lines = lines_to_write(placed, accounting_date=accounting_date)
    entry_id = post_entry(
        tenant_id=tenant_id,
        company_id=company_id,
        entry_number=number.formatted,
        accounting_date=accounting_date,
        period_id=period_id,
        accounting_event_id=accounting_event_id,
        entry_type=entry_type,
        description=description,
        request_id=request_id,
        posted_by_user_id=actor_user_id,
        lines=lines,
        formulas=formulas_to_write(placed),
        rule_ref=rule_ref,
        fiscal_effective_date=fiscal_effective_date or accounting_date,
        chart_template_id=chart.template_id if chart is not None else None,
        parameter_stamps=parameter_stamps,
    )
    return FormulaPostingResult(journal_entry_id=entry_id, formulas=len(placed), lines=len(lines))
