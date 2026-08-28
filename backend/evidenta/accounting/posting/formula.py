"""The formula -- what the engine emits, and how it becomes lines. ADR-048.

A handler produces **formulas**, *n* per document line, never a fixed number:

    reverse-charge VAT   two, with opposite signs, on one line
    standard cost        the movement plus a deviation
    a plain delivery     one

Each formula is one correspondence -- a debit account, a credit account, one
amount -- and expands into exactly two journal lines. That is what makes the
formula the right unit: it balances by construction, so `R11` holds per formula
before the six invariants ever look at the entry. Fixing the number would close
a shape, and reopening it later is a migration on an append-only register.

**Nothing here decides an account, a treatment or an amount.** Accounts arrive
from `slots.resolve_role` (a handler asks for `CREANTE_COMERCIALE_TARA`, never
`2211`); the amount arrives from the handler, and from Stage 3 on from a
valuation strategy; the VAT rate arrives resolved. What this module decides is
**shape**: which dimension lands on which side, what folds into what, and what
the two lines of a formula look like.

The three steps, in the order the engine runs them:

1. ``place`` -- the chart decides what each side keeps. An account carries the
   dimensions it declares (`company_account.slot_n_dimension`) and nothing
   else, so a value the handler attached for an axis neither side declares is
   *not carried*. That is layer 2 of ADR-036 doing its job -- the same fact
   posts with item analytics at one company and without at another, because
   the two charts say so -- and it is why the drop is silent: the handler
   describes the fact completely, the chart says what the entity keeps.
2. ``merge`` -- formulas of one entry that agree on everything but the amount
   are one formula. The key is exactly what the row stores; the database
   enforces the same key as ``journal_formula_merge_key``.
3. ``expand`` -- two lines per formula, each side with its own dimensions.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from decimal import Decimal

from evidenta.accounting.coa.dimensions import DIMENSION_KEYS, SLOT_COUNT
from evidenta.accounting.coa.services.accounts import postable_accounts
from evidenta.accounting.ledger.services.writing import FormulaToWrite, LineToWrite
from evidenta.accounting.posting.dimensions import LineDimensions
from evidenta.accounting.posting.invariants import PostingRefusedError, ProposedLine
from evidenta.accounting.slots.services.binding import resolve_role

ONE = Decimal(1)
ZERO = Decimal(0)


class NoFormulasError(PostingRefusedError):
    """A posting with no formulas. Nothing to expand, nothing to balance."""

    code = "posting.no_formulas"


class FormulaMalformedError(PostingRefusedError):
    """A formula that is not a correspondence.

    Zero or negative amount, one account on both sides, an unknown or repeated
    dimension, a functional-currency formula at a rate other than one, a
    quantity without a unit. Each is a handler bug, refused before any read.
    """

    code = "posting.formula_malformed"


class FormulaSlotsExceededError(PostingRefusedError):
    """The two sides together carry more than the row's four slots.

    The stored formula holds the union of what its two accounts declared. Two
    accounts declaring four different dimensions each is a formula that would
    need eight -- a limit as visible and countable as ADR-029's five, and raised
    the same way: by an ADR, not by a fifth column added in passing.
    """

    code = "posting.formula_slots_exceeded"


@dataclass(frozen=True, slots=True)
class DimensionValue:
    """One typed analytical value -- an ADR-029 name and the id it points at."""

    dimension: str
    value_id: uuid.UUID


@dataclass(frozen=True, slots=True)
class Formula:
    """One correspondence, accounts resolved, as the engine judges it.

    ``amount`` is in the functional currency; ``amount_currency`` in the
    transaction's own. Nothing here derives one from the other -- the rounding
    that would take is `DNB-08`, and the value that would take is Stage 3.

    ``dimensions`` are the facts the handler attached, any number of them, each
    dimension once. Which of them the ledger keeps is decided by ``place``.

    ``vat_rate`` is an attribute of the formula, not a dimension (ADR-048): it
    parameterises the calculation the formula records, it is not an axis of
    analysis, and it has no ledger of its own to be indexed for.
    """

    debit_account_id: uuid.UUID
    credit_account_id: uuid.UUID
    amount: Decimal
    currency: str
    amount_currency: Decimal
    exchange_rate: Decimal
    rate_date: date
    document_date: date
    dimensions: tuple[DimensionValue, ...] = ()
    vat_rate: Decimal | None = None
    vat_rate_key: str | None = None
    quantity: Decimal | None = None
    uom_id: uuid.UUID | None = None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class RoleFormula:
    """A formula as a handler writes it: roles where the accounts will be.

    ADR-036 section 5.1 -- a handler asks for semantic slots, never for account
    codes. ``bind_roles`` turns this into a ``Formula`` through the company's
    bindings at the posting's date, or refuses with the binding's own code.
    """

    debit_role: str
    credit_role: str
    amount: Decimal
    currency: str
    amount_currency: Decimal
    exchange_rate: Decimal
    rate_date: date
    document_date: date
    dimensions: tuple[DimensionValue, ...] = ()
    vat_rate: Decimal | None = None
    vat_rate_key: str | None = None
    quantity: Decimal | None = None
    uom_id: uuid.UUID | None = None
    description: str | None = None


@dataclass(frozen=True, slots=True)
class PlacedFormula:
    """A formula after the chart decided what each side keeps.

    ``formula.dimensions`` now holds exactly the stored slots, in stored order:
    the debit account's declaration first, then whatever the credit account adds.
    The two mappings are each side's share, and a value can be in both.
    """

    formula: Formula
    debit_dimensions: Mapping[str, uuid.UUID]
    credit_dimensions: Mapping[str, uuid.UUID]

    @property
    def slots(self) -> tuple[tuple[str, uuid.UUID], ...]:
        return tuple((d.dimension, d.value_id) for d in self.formula.dimensions)


#: Account id -> the dimensions it declares, in slot order.
Declarations = Mapping[uuid.UUID, tuple[str, ...]]


# --- roles -------------------------------------------------------------------


def bind_roles(
    company_id: uuid.UUID, on_date: date, formulas: Sequence[RoleFormula]
) -> tuple[Formula, ...]:
    """Resolve every role to the account it means for this company on this date.

    Refuses on the first unbound role rather than posting to a fallback -- ADR-036
    section 5.1, and `slots.services.binding` says why in its own words. Roles
    are resolved once each: a formula set naming the same role forty times asks
    the database once.
    """
    resolved: dict[str, uuid.UUID] = {}

    def account(role: str) -> uuid.UUID:
        if role not in resolved:
            resolved[role] = resolve_role(company_id, role, on_date)
        return resolved[role]

    return tuple(
        Formula(
            debit_account_id=account(f.debit_role),
            credit_account_id=account(f.credit_role),
            amount=f.amount,
            currency=f.currency,
            amount_currency=f.amount_currency,
            exchange_rate=f.exchange_rate,
            rate_date=f.rate_date,
            document_date=f.document_date,
            dimensions=f.dimensions,
            vat_rate=f.vat_rate,
            vat_rate_key=f.vat_rate_key,
            quantity=f.quantity,
            uom_id=f.uom_id,
            description=f.description,
        )
        for f in formulas
    )


# --- placement ---------------------------------------------------------------


def declarations_for(company_id: uuid.UUID, on_date: date) -> Declarations:
    """What every postable account of the company carries, on the posting's date.

    Through `coa`'s public service, not its models (`D6`), and at the posting's
    date, so a recalculation of March meets March's chart (`R18`). An account
    absent from the answer is absent from the chart on that date, and invariant
    4 will say so with its own code -- here it simply declares nothing.
    """
    return {
        account.id: account.declared_slots() for account in postable_accounts(company_id, on_date)
    }


def place(
    formulas: Sequence[Formula], declarations: Declarations, *, functional_currency: str
) -> tuple[PlacedFormula, ...]:
    """Give each side the dimensions its account declares; store their union.

    Order is the debit account's slot order, then the credit account's slots not
    already placed. Deterministic given the declarations, which is what lets the
    merge key be a column tuple rather than a sorted-and-hashed string.

    ``functional_currency`` is a parameter for the reason it is on the manual
    note: the engine states which currency it believes the books are kept in,
    and a functional-currency formula at a rate other than one is refused rather
    than trusted.
    """
    placed: list[PlacedFormula] = []
    for number, formula in enumerate(formulas, start=1):
        _check_shape(formula, number, functional_currency)
        by_name = {d.dimension: d.value_id for d in formula.dimensions}
        debit_slots = declarations.get(formula.debit_account_id, ())
        credit_slots = declarations.get(formula.credit_account_id, ())

        debit_dimensions = {name: by_name[name] for name in debit_slots if name in by_name}
        credit_dimensions = {name: by_name[name] for name in credit_slots if name in by_name}

        order = list(debit_dimensions) + [
            name for name in credit_dimensions if name not in debit_dimensions
        ]
        if len(order) > SLOT_COUNT:
            raise FormulaSlotsExceededError(
                f"formula {number} ({formula.debit_account_id} / "
                f"{formula.credit_account_id}) carries {len(order)} dimensions "
                f"between its two sides ({', '.join(order)}); the row holds "
                f"{SLOT_COUNT}. Two accounts declaring that many distinct axes need "
                f"an ADR, not a wider row"
            )
        stored = tuple(DimensionValue(name, by_name[name]) for name in order)
        placed.append(
            PlacedFormula(
                formula=replace(formula, dimensions=stored),
                debit_dimensions=debit_dimensions,
                credit_dimensions=credit_dimensions,
            )
        )
    return tuple(placed)


def _check_shape(formula: Formula, number: int, functional_currency: str) -> None:
    for name, value in (
        ("amount", formula.amount),
        ("amount_currency", formula.amount_currency),
        ("exchange_rate", formula.exchange_rate),
    ):
        if not isinstance(value, Decimal):
            raise FormulaMalformedError(
                f"formula {number}: {name} is {type(value).__name__}, not Decimal; "
                f"a float reaching a ledger is how a balance ends up a ban off"
            )
    if formula.amount <= ZERO or formula.amount_currency <= ZERO:
        raise FormulaMalformedError(
            f"formula {number} carries amount {formula.amount} / "
            f"{formula.amount_currency}; a formula is strictly positive, and its "
            f"direction is the pair of accounts, never a sign"
        )
    if formula.debit_account_id == formula.credit_account_id:
        raise FormulaMalformedError(
            f"formula {number} debits and credits {formula.debit_account_id}; with "
            f"one set of slots on both sides that moves nothing"
        )
    if formula.exchange_rate <= ZERO:
        raise FormulaMalformedError(f"formula {number} has rate {formula.exchange_rate}")
    if formula.currency == functional_currency and (
        formula.exchange_rate != ONE or formula.amount_currency != formula.amount
    ):
        raise FormulaMalformedError(
            f"formula {number} is in {functional_currency}, the functional currency, "
            f"at rate {formula.exchange_rate} with own amount {formula.amount_currency} "
            f"against {formula.amount}; a domestic formula is the same number at rate 1 "
            f"(ADR-039 section 3)"
        )
    if (formula.quantity is None) != (formula.uom_id is None):
        raise FormulaMalformedError(
            f"formula {number} names a quantity and a unit as a pair or not at all"
        )
    if formula.vat_rate is not None and formula.vat_rate < ZERO:
        raise FormulaMalformedError(f"formula {number} has VAT rate {formula.vat_rate}")
    if formula.vat_rate_key is not None and formula.vat_rate is None:
        raise FormulaMalformedError(
            f"formula {number} names VAT rate key {formula.vat_rate_key!r} without a rate"
        )
    names = [d.dimension for d in formula.dimensions]
    unknown = sorted(set(names) - set(DIMENSION_KEYS))
    if unknown:
        raise FormulaMalformedError(
            f"formula {number} names {', '.join(unknown)}, which is not an "
            f"analytical dimension (ADR-029)"
        )
    if len(set(names)) != len(names):
        raise FormulaMalformedError(f"formula {number} names a dimension twice: {names}")


# --- merging -----------------------------------------------------------------


def merge(placed: Sequence[PlacedFormula]) -> tuple[PlacedFormula, ...]:
    """Fold formulas that agree on everything but the amount into one.

    The key is what ``journal_formula`` stores minus the amounts: accounts,
    currency, rate and its date, document date, VAT rate and key, unit, and the
    four typed slots. First occurrence keeps its position; a description kept
    only when every folded formula said the same thing -- a merged row that
    quoted one of two different descriptions would be quoting something nobody
    wrote about the whole.
    """
    folded: dict[tuple[object, ...], PlacedFormula] = {}
    for item in placed:
        f = item.formula
        key = (
            f.debit_account_id,
            f.credit_account_id,
            f.currency,
            f.exchange_rate,
            f.rate_date,
            f.document_date,
            f.vat_rate,
            f.vat_rate_key,
            f.uom_id,
            item.slots,
        )
        existing = folded.get(key)
        if existing is None:
            folded[key] = item
            continue
        e = existing.formula
        folded[key] = replace(
            existing,
            formula=replace(
                e,
                amount=e.amount + f.amount,
                amount_currency=e.amount_currency + f.amount_currency,
                quantity=(
                    None if e.quantity is None or f.quantity is None else e.quantity + f.quantity
                ),
                description=e.description if e.description == f.description else None,
            ),
        )
    return tuple(folded.values())


# --- expansion ---------------------------------------------------------------


def proposed_lines(
    placed: Sequence[PlacedFormula],
    *,
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    accounting_date: date,
) -> tuple[ProposedLine, ...]:
    """The two sides of every formula, in the shape the six invariants judge."""
    lines: list[ProposedLine] = []
    for item in placed:
        f = item.formula
        for account_id, debit, credit in (
            (f.debit_account_id, f.amount, ZERO),
            (f.credit_account_id, ZERO, f.amount),
        ):
            lines.append(
                ProposedLine(tenant_id, company_id, accounting_date, account_id, debit, credit)
            )
    return tuple(lines)


def line_dimensions(placed: Sequence[PlacedFormula]) -> list[LineDimensions]:
    """Each side with its own share, for the mandatory-dimension check."""
    out: list[LineDimensions] = []
    for item in placed:
        out.append(LineDimensions(item.formula.debit_account_id, dict(item.debit_dimensions)))
        out.append(LineDimensions(item.formula.credit_account_id, dict(item.credit_dimensions)))
    return out


def lines_to_write(placed: Sequence[PlacedFormula], *, accounting_date: date) -> list[LineToWrite]:
    """Two ``journal_line`` rows per formula: the debit side, then the credit side.

    Line order follows formula order, so line ``2n-1`` and ``2n`` are formula
    ``n`` -- readable without a join, and the reason ``formula_number`` and
    ``line_number`` are both dense from 1.
    """
    lines: list[LineToWrite] = []
    for item in placed:
        f = item.formula
        for account_id, debit, credit, dimensions in (
            (f.debit_account_id, f.amount, ZERO, item.debit_dimensions),
            (f.credit_account_id, ZERO, f.amount, item.credit_dimensions),
        ):
            lines.append(
                LineToWrite(
                    account_id=account_id,
                    debit=debit,
                    credit=credit,
                    currency=f.currency,
                    amount_currency=f.amount_currency,
                    exchange_rate=f.exchange_rate,
                    accounting_date=accounting_date,
                    document_date=f.document_date,
                    rate_date=f.rate_date,
                    description=f.description,
                    quantity=f.quantity,
                    uom_id=f.uom_id,
                    dimensions=dict(dimensions),
                )
            )
    return lines


def formulas_to_write(placed: Sequence[PlacedFormula]) -> list[FormulaToWrite]:
    return [
        FormulaToWrite(
            debit_account_id=item.formula.debit_account_id,
            credit_account_id=item.formula.credit_account_id,
            amount=item.formula.amount,
            currency=item.formula.currency,
            amount_currency=item.formula.amount_currency,
            exchange_rate=item.formula.exchange_rate,
            rate_date=item.formula.rate_date,
            document_date=item.formula.document_date,
            slots=item.slots,
            vat_rate=item.formula.vat_rate,
            vat_rate_key=item.formula.vat_rate_key,
            quantity=item.formula.quantity,
            uom_id=item.formula.uom_id,
            description=item.formula.description,
        )
        for item in placed
    ]
