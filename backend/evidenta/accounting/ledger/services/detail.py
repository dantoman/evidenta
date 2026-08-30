"""One entry, whole, for a drill-down -- F1.8, R13 in the reading direction.

    Journal Line -> Journal Entry -> Accounting Event -> Source Document -> Sursă

A report row is an entry; this is what opens when the reader clicks it: the
header with what it stood on (ADR-048 §3.3 -- rule, chart version, fiscal date),
the formulas as correspondences, the lines as the balance reads them, and the
origin -- which event, from which module, about which document. The last hop
stops at the document's identifier, deliberately: the ledger does not know the
source module's tables (`D2`), so it names the document and the module that owns
it answers what it is.

Plain data out, never a model instance (`ledger.services.lineage` gives the
reason). Names for accounts are asked of `coa` through its service (`D6`): a
journal line carries no foreign key to the account (R21), so there is nothing to
join and the reader has to ask.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal

from evidenta.accounting.coa.services.accounts import names_for
from evidenta.accounting.coa.services.chart import template_version
from evidenta.accounting.events.services.lineage import origin_of_event
from evidenta.accounting.ledger.models import JournalEntry, JournalFormula, JournalLine


@dataclass(frozen=True, slots=True)
class LineDetail:
    line_number: int
    account_id: uuid.UUID
    account_code: str
    name_ro: str
    debit: Decimal
    credit: Decimal
    currency: str
    amount_currency: Decimal
    exchange_rate: Decimal
    document_date: date
    rate_date: date
    description: str | None
    #: ADR-029 names carrying a value on this line.
    dimensions: tuple[tuple[str, uuid.UUID], ...]


@dataclass(frozen=True, slots=True)
class FormulaDetail:
    formula_number: int
    debit_account_id: uuid.UUID
    debit_code: str
    credit_account_id: uuid.UUID
    credit_code: str
    amount: Decimal
    currency: str
    amount_currency: Decimal
    exchange_rate: Decimal
    vat_rate: Decimal | None
    vat_rate_key: str | None
    description: str | None
    slots: tuple[tuple[str, uuid.UUID], ...]


@dataclass(frozen=True, slots=True)
class OriginDetail:
    accounting_event_id: uuid.UUID
    event_type: str
    source_module: str
    source_document_type: str
    source_document_id: uuid.UUID
    occurred_at: datetime


@dataclass(frozen=True, slots=True)
class EntryDetail:
    id: uuid.UUID
    company_id: uuid.UUID
    entry_number: str
    accounting_date: date
    entry_type: str
    status: str
    description: str
    total_debit: Decimal
    total_credit: Decimal
    posted_at: datetime | None
    reverses_entry_id: uuid.UUID | None
    reversed_by_entry_id: uuid.UUID | None
    #: What it stood on (ADR-048). `chart` is code/version of the stamped
    #: template, not the company's current one.
    rule_ref: str | None
    chart: str | None
    fiscal_effective_date: date | None
    lines: tuple[LineDetail, ...]
    formulas: tuple[FormulaDetail, ...]
    origin: OriginDetail | None


#: The fifteen dimension columns, read by name so a line reports what it carries.
_DIMENSION_COLUMNS = (
    "partner",
    "item",
    "employee",
    "contract",
    "warehouse",
    "project",
    "department",
    "cost_center",
    "asset",
    "production_order",
    "dim_1",
    "dim_2",
    "dim_3",
    "dim_4",
    "dim_5",
)


def entry_detail(entry_id: uuid.UUID) -> EntryDetail | None:
    """The entry, or None when this context cannot see it (IZ-04)."""
    entry = JournalEntry.objects.filter(id=entry_id).first()
    if entry is None:
        return None

    lines = list(JournalLine.objects.filter(journal_entry_id=entry.id).order_by("line_number"))
    formulas = list(
        JournalFormula.objects.filter(journal_entry_id=entry.id).order_by("formula_number")
    )
    ids = {line.account_id for line in lines}
    ids |= {formula.debit_account_id for formula in formulas}
    ids |= {formula.credit_account_id for formula in formulas}
    named = names_for(entry.company_id, ids)

    def naming(account_id: uuid.UUID) -> tuple[str, str]:
        return named.get(account_id, (str(account_id), ""))

    reversed_by = (
        JournalEntry.objects.filter(reverses_entry_id=entry.id).values_list("id", flat=True).first()
    )
    origin = origin_of_event(entry.accounting_event_id)
    chart = template_version(entry.chart_template_id) if entry.chart_template_id else None

    return EntryDetail(
        id=entry.id,
        company_id=entry.company_id,
        entry_number=entry.entry_number,
        accounting_date=entry.accounting_date,
        entry_type=entry.entry_type,
        status=entry.status,
        description=entry.description,
        total_debit=entry.total_debit,
        total_credit=entry.total_credit,
        posted_at=entry.posted_at,
        reverses_entry_id=entry.reverses_entry_id,
        reversed_by_entry_id=reversed_by,
        rule_ref=entry.rule_ref,
        chart=f"{chart.code}/{chart.version}" if chart else None,
        fiscal_effective_date=entry.fiscal_effective_date,
        lines=tuple(
            LineDetail(
                line_number=line.line_number,
                account_id=line.account_id,
                account_code=naming(line.account_id)[0],
                name_ro=naming(line.account_id)[1],
                debit=line.debit,
                credit=line.credit,
                currency=line.currency,
                amount_currency=line.amount_currency,
                exchange_rate=line.exchange_rate,
                document_date=line.document_date,
                rate_date=line.rate_date,
                description=line.description,
                dimensions=tuple(
                    (name, value)
                    for name in _DIMENSION_COLUMNS
                    if (value := getattr(line, f"{name}_id")) is not None
                ),
            )
            for line in lines
        ),
        formulas=tuple(
            FormulaDetail(
                formula_number=formula.formula_number,
                debit_account_id=formula.debit_account_id,
                debit_code=naming(formula.debit_account_id)[0],
                credit_account_id=formula.credit_account_id,
                credit_code=naming(formula.credit_account_id)[0],
                amount=formula.amount,
                currency=formula.currency,
                amount_currency=formula.amount_currency,
                exchange_rate=formula.exchange_rate,
                vat_rate=formula.vat_rate,
                vat_rate_key=formula.vat_rate_key,
                description=formula.description,
                slots=tuple(
                    (dimension, value)
                    for n in range(1, 5)
                    if (dimension := getattr(formula, f"slot_{n}_dimension")) is not None
                    and (value := getattr(formula, f"slot_{n}_value_id")) is not None
                ),
            )
            for formula in formulas
        ),
        origin=(
            OriginDetail(
                accounting_event_id=origin.accounting_event_id,
                event_type=origin.event_type,
                source_module=origin.source_module,
                source_document_type=origin.source_document_type,
                source_document_id=origin.source_document_id,
                occurred_at=origin.occurred_at,
            )
            if origin
            else None
        ),
    )
