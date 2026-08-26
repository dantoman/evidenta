"""Building an opening balance batch and checking it -- Spec B section 8.1, 8.2.

The batch is filled while it is ``draft``, checked once, and then frozen. Three
stages, and the freeze is the interesting one: from ``validated`` onwards the six
line tables refuse every write, in the database, so what the engine later posts
is exactly what was checked. Without it, "validated" would mean "was correct at
some point", which is not a property anybody can rely on.

**The four checks of Spec B section 8.2, and where each one actually lives.**

    debit total = credit total on the GL set            here
    analytical balance = its synthetic GL balance       here
    account exists, is open and valid on the date       the chart, via the engine
    a mandatory dimension is missing                    the engine

Only the first two are this module's own. The other two already exist as
``posting.dimensions.assert_dimensions_present``, which resolves the chart at the
posting date and refuses an unknown account and a missing dimension with the
codes the engine uses everywhere else. Reimplementing them here would produce a
second answer to "may this account receive a posting", and the second answer is
always the one that drifts.

**A batch is refused whole.** Spec B section 8.2 closes with V2 section 14 --
"refuz de import partial" -- so every check below raises on the first defect it
finds and nothing is written. Loading nine tenths of a trial balance produces a
company whose books are wrong in a way no report can point at.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from django.db import transaction

from evidenta.accounting.opening.errors import (
    AccountMissingFromGlError,
    AnalyticalMismatchError,
    BatchNotDraftError,
    BatchNotFoundError,
    CounterpartInGlError,
    EmptyGlSetError,
    ForeignCurrencyBalanceError,
    GlOutOfBalanceError,
    IllegalBatchTransitionError,
    OpeningBalanceError,
    StartPeriodFixedError,
)
from evidenta.accounting.opening.models import (
    BatchStatus,
    OpeningBalanceAsset,
    OpeningBalanceBatch,
    OpeningBalanceGl,
    OpeningBalanceInventory,
    OpeningBalancePayable,
    OpeningBalancePayrollCumulative,
    OpeningBalanceReceivable,
)
from evidenta.accounting.periods.services.resolution import assert_postable
from evidenta.accounting.posting.dimensions import (
    LineDimensions,
    assert_dimensions_present,
)
from evidenta.platform.audit.services.recording import record
from evidenta.platform.rls.context import MissingTenantContextError, current_context
from evidenta.platform.tenancy.services.access import company_visible_in_context

ZERO = Decimal(0)

#: ``numeric(20,4)`` on every amount column, here and on ``journal_line``.
#: PostgreSQL rounds a fifth decimal silently on INSERT, and which way it should
#: round is `DNB-08` -- so a value that would be altered is refused instead.
SCALE = 4

#: ``draft`` may be filled; everything after it is frozen. ``validated -> draft``
#: exists because a batch that failed review has to be fixable without losing the
#: record that it was built -- and because the alternative, rejecting and
#: retyping five thousand rows, is how people end up loading balances by hand
#: into the ledger.
TRANSITIONS: dict[str, frozenset[str]] = {
    BatchStatus.DRAFT: frozenset({BatchStatus.VALIDATED, BatchStatus.REJECTED}),
    BatchStatus.VALIDATED: frozenset({BatchStatus.DRAFT, BatchStatus.POSTED, BatchStatus.REJECTED}),
    #: Terminal. A posted batch is corrected with a reversal and a new batch
    #: (Spec B section 8.3), never by walking its status back: the entry it
    #: produced is in an append-only ledger.
    BatchStatus.POSTED: frozenset(),
    BatchStatus.REJECTED: frozenset(),
}


# --- what the caller hands over ----------------------------------------------
#
# Plain dataclasses rather than model instances, so that no caller outside this
# module ever holds one of its rows. Amounts are `Decimal` and only `Decimal`:
# a caller reading JSON converts at its own boundary, where the string it
# received is still visible, rather than here where a `float` would already have
# lost the value it came from.


@dataclass(frozen=True, slots=True)
class GlRow:
    """One line of the trial balance."""

    account_id: uuid.UUID
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    currency: str | None = None
    amount_currency: Decimal | None = None


@dataclass(frozen=True, slots=True)
class PartnerRow:
    """One partner balance, with the document behind it."""

    account_id: uuid.UUID
    partner_id: uuid.UUID
    debit: Decimal = ZERO
    credit: Decimal = ZERO
    document_type: str | None = None
    document_number: str | None = None
    document_date: date | None = None
    due_date: date | None = None
    currency: str | None = None
    amount_currency: Decimal | None = None


@dataclass(frozen=True, slots=True)
class InventoryRow:
    """One stock balance.

    ``total_cost`` is the debit; there is no credit side and no parameter for
    one. A stock balance is an asset, and a negative one is a data defect rather
    than a case to model -- refusing it here is the only place it can still be
    fixed at the source.
    """

    account_id: uuid.UUID
    item_id: uuid.UUID
    uom_id: uuid.UUID
    quantity: Decimal
    total_cost: Decimal
    warehouse_id: uuid.UUID | None = None
    lot: str | None = None
    unit_cost: Decimal | None = None
    currency: str | None = None
    amount_currency: Decimal | None = None


@dataclass(frozen=True, slots=True)
class AssetRow:
    """One fixed asset: what it cost, and what has been written off it."""

    asset_id: uuid.UUID
    cost_account_id: uuid.UUID
    depreciation_account_id: uuid.UUID
    entry_cost: Decimal
    in_service_date: date
    accumulated_depreciation: Decimal = ZERO
    remaining_months: int | None = None


@dataclass(frozen=True, slots=True)
class PayrollRow:
    """One year-to-date payroll amount -- `OD-04`.

    ``code`` is uninterpreted. This module stores it and never reads it: naming
    the income types and contributions is the open decision itself.
    """

    employee_id: uuid.UUID
    code: str
    amount: Decimal
    from_date: date


@dataclass(frozen=True, slots=True)
class BatchContents:
    """Every row of one batch, loaded once.

    Loaded together because every check of Spec B section 8.2 is a comparison
    *between* sets: reading them one at a time would let a batch change between
    two reads, and the whole point of validation is that what is checked is what
    posts.
    """

    batch: OpeningBalanceBatch
    gl: tuple[OpeningBalanceGl, ...] = ()
    receivables: tuple[OpeningBalanceReceivable, ...] = ()
    payables: tuple[OpeningBalancePayable, ...] = ()
    inventory: tuple[OpeningBalanceInventory, ...] = ()
    assets: tuple[OpeningBalanceAsset, ...] = ()
    payroll: tuple[OpeningBalancePayrollCumulative, ...] = ()

    @property
    def analytical(
        self,
    ) -> tuple[OpeningBalanceReceivable | OpeningBalancePayable | OpeningBalanceInventory, ...]:
        """The three sets that decompose a GL account into dimensioned rows.

        Assets are the fourth decomposition and are deliberately not here: an
        asset row carries two accounts and two amounts, so it cannot be summed by
        the same expression. It is handled explicitly wherever this appears.
        """
        return (*self.receivables, *self.payables, *self.inventory)


# --- creating and filling ----------------------------------------------------


def _amount(value: Decimal, label: str) -> Decimal:
    """An amount this schema can store exactly, or a refusal.

    A `float` is refused rather than converted: `0.1` is not a tenth in binary,
    and a trial balance that accepted one would balance by luck. A fifth decimal
    is refused for the neighbouring reason -- ``numeric(20,4)`` would round it on
    INSERT, and which way it rounds is `DNB-08`.
    """
    if not isinstance(value, Decimal):
        raise OpeningBalanceError(
            f"{label} is {type(value).__name__}, not a Decimal. Converting here "
            f"would hide where the value stopped being exact"
        )
    if not value.is_finite():
        raise OpeningBalanceError(f"{label} is {value}, not a finite amount")
    exponent = value.as_tuple().exponent
    if isinstance(exponent, int) and -exponent > SCALE:
        raise OpeningBalanceError(
            f"{label} has more than {SCALE} decimals ({value}); the column would "
            f"round it silently and which way is an open decision (DNB-08)"
        )
    return value


def _context_tenant() -> uuid.UUID:
    context = current_context()
    if context is None:
        raise MissingTenantContextError("opening balances need a tenant context")
    return context.tenant_id


@transaction.atomic
def create_batch(
    *,
    company_id: uuid.UUID,
    as_of_date: date,
    source: str,
    counterpart_account_id: uuid.UUID,
    created_by_user_id: uuid.UUID,
) -> OpeningBalanceBatch:
    """Open an empty batch for one company, as of one date.

    ``as_of_date`` is the choice ADR-039 section 11 calls irreversible. It is not
    checked against the company's ``accounting_start_date`` here, and that is a
    gap rather than a decision: the column lives on ``platform.tenancy`` and that
    module publishes no accessor for it, so reading it would be the `D6` import
    the rule exists to stop. What *is* enforced -- by a trigger, in the database
    -- is that once a batch of this company has posted, every later batch carries
    the same date.

    The period is resolved and required to be open at creation as well as at
    posting. Refusing early is worth a duplicate check: an accountant who typed
    five thousand rows into a batch dated into a month that was never opened
    should find out before the last one.
    """
    tenant_id = _context_tenant()
    if not company_visible_in_context(company_id):
        raise BatchNotFoundError(f"company {company_id} is not visible in this context")

    # Refuses `periods.period_not_found` when the exercise containing the date was
    # never opened, and `periods.period_not_open` / `periods.period_locked`
    # otherwise -- the period module's own codes, not flattened into one of ours,
    # because the remedies differ per code.
    assert_postable(company_id, as_of_date)

    fixed = (
        OpeningBalanceBatch.objects.filter(company_id=company_id, status=BatchStatus.POSTED)
        .values_list("as_of_date", flat=True)
        .first()
    )
    if fixed is not None and fixed != as_of_date:
        raise StartPeriodFixedError(
            f"company {company_id} posted its opening balances as of {fixed}; the "
            f"start period of a company is chosen once (ADR-039 section 11). A "
            f"correction is a reversal and a new batch at {fixed}"
        )

    batch = OpeningBalanceBatch.objects.create(
        tenant_id=tenant_id,
        company_id=company_id,
        as_of_date=as_of_date,
        source=source,
        counterpart_account_id=counterpart_account_id,
        created_by_user_id=created_by_user_id,
    )
    record(
        action="opening_balance.batch_created",
        entity_type="opening_balance_batch",
        entity_id=batch.id,
        company_id=company_id,
        new_value={"as_of_date": as_of_date.isoformat(), "source": source},
    )
    return batch


def batch_in_context(batch_id: uuid.UUID) -> OpeningBalanceBatch:
    """The batch, or a refusal that does not say whose it is.

    RLS has already narrowed the table, so "not visible" covers both "no such
    batch" and "not yours" -- the only answer that does not leak another tenant's
    row (IZ-04).
    """
    batch = OpeningBalanceBatch.objects.filter(id=batch_id).first()
    if batch is None:
        raise BatchNotFoundError(f"opening balance batch {batch_id} is not visible")
    return batch


@transaction.atomic
def add_rows(
    batch_id: uuid.UUID,
    *,
    gl: Sequence[GlRow] = (),
    receivables: Sequence[PartnerRow] = (),
    payables: Sequence[PartnerRow] = (),
    inventory: Sequence[InventoryRow] = (),
    assets: Sequence[AssetRow] = (),
    payroll: Sequence[PayrollRow] = (),
) -> None:
    """Add rows to a draft batch, in bulk.

    Bulk because the 1C import is the volume case and writes tens of thousands of
    rows in one call; every set is inserted with one statement.

    A batch that has left ``draft`` is refused here **and** by a trigger on each
    of the six tables. The trigger is the barrier that holds -- the importer and
    any data migration bypass this function -- and this check is what turns it
    into a stable code instead of a raised exception with no code (C10).
    """
    batch = batch_in_context(batch_id)
    if batch.status != BatchStatus.DRAFT:
        raise BatchNotDraftError(
            f"batch {batch.id} is {batch.status}; rows are added while it is "
            f"draft, and frozen afterwards so that what posts is what was checked"
        )

    scope = {"tenant_id": batch.tenant_id, "company_id": batch.company_id, "batch": batch}

    OpeningBalanceGl.objects.bulk_create(
        [
            OpeningBalanceGl(
                **scope,
                account_id=row.account_id,
                debit=_amount(row.debit, "gl.debit"),
                credit=_amount(row.credit, "gl.credit"),
                currency=row.currency,
                amount_currency=(
                    None
                    if row.amount_currency is None
                    else _amount(row.amount_currency, "gl.amount_currency")
                ),
            )
            for row in gl
        ]
    )

    OpeningBalanceReceivable.objects.bulk_create(
        _partner_instances(OpeningBalanceReceivable, scope, receivables)
    )
    OpeningBalancePayable.objects.bulk_create(
        _partner_instances(OpeningBalancePayable, scope, payables)
    )

    OpeningBalanceInventory.objects.bulk_create(
        [
            OpeningBalanceInventory(
                **scope,
                account_id=row.account_id,
                item_id=row.item_id,
                warehouse_id=row.warehouse_id,
                lot=row.lot,
                quantity=row.quantity,
                uom_id=row.uom_id,
                unit_cost=row.unit_cost,
                debit=_amount(row.total_cost, "inventory.total_cost"),
                credit=ZERO,
                currency=row.currency,
                amount_currency=(
                    None
                    if row.amount_currency is None
                    else _amount(row.amount_currency, "inventory.amount_currency")
                ),
            )
            for row in inventory
        ]
    )

    OpeningBalanceAsset.objects.bulk_create(
        [
            OpeningBalanceAsset(
                **scope,
                asset_id=row.asset_id,
                cost_account_id=row.cost_account_id,
                depreciation_account_id=row.depreciation_account_id,
                entry_cost=_amount(row.entry_cost, "asset.entry_cost"),
                accumulated_depreciation=_amount(
                    row.accumulated_depreciation, "asset.accumulated_depreciation"
                ),
                in_service_date=row.in_service_date,
                remaining_months=row.remaining_months,
            )
            for row in assets
        ]
    )

    OpeningBalancePayrollCumulative.objects.bulk_create(
        [
            OpeningBalancePayrollCumulative(
                **scope,
                employee_id=row.employee_id,
                code=row.code,
                amount=_amount(row.amount, "payroll.amount"),
                from_date=row.from_date,
            )
            for row in payroll
        ]
    )


def _partner_instances[PartnerModel: (OpeningBalanceReceivable, OpeningBalancePayable)](
    model: type[PartnerModel],
    scope: Mapping[str, Any],
    rows: Sequence[PartnerRow],
) -> list[PartnerModel]:
    """Build the rows of one partner set.

    Two sets with one shape, so one function rather than two copies -- and
    parameterised by the model rather than looped over a pair, because a loop
    over ``(Receivable, Payable)`` erases which of the two is being built and
    would let a receivable be created in the payable table without anything
    noticing.
    """
    return [
        model(
            **scope,
            account_id=row.account_id,
            partner_id=row.partner_id,
            debit=_amount(row.debit, "partner.debit"),
            credit=_amount(row.credit, "partner.credit"),
            document_type=row.document_type,
            document_number=row.document_number,
            document_date=row.document_date,
            due_date=row.due_date,
            currency=row.currency,
            amount_currency=(
                None
                if row.amount_currency is None
                else _amount(row.amount_currency, "partner.amount_currency")
            ),
        )
        for row in rows
    ]


def load_contents(batch: OpeningBalanceBatch) -> BatchContents:
    """Every row of the batch, in one shot."""
    return BatchContents(
        batch=batch,
        gl=tuple(OpeningBalanceGl.objects.filter(batch=batch).order_by("account_id", "id")),
        receivables=tuple(
            OpeningBalanceReceivable.objects.filter(batch=batch).order_by("partner_id", "id")
        ),
        payables=tuple(
            OpeningBalancePayable.objects.filter(batch=batch).order_by("partner_id", "id")
        ),
        inventory=tuple(
            OpeningBalanceInventory.objects.filter(batch=batch).order_by("item_id", "id")
        ),
        assets=tuple(OpeningBalanceAsset.objects.filter(batch=batch).order_by("asset_id", "id")),
        payroll=tuple(
            OpeningBalancePayrollCumulative.objects.filter(batch=batch).order_by(
                "employee_id", "code"
            )
        ),
    )


# --- the checks of Spec B section 8.2 ----------------------------------------


def decomposition(contents: BatchContents) -> dict[uuid.UUID, Decimal]:
    """The signed balance each analytical set contributes, per account.

    Debit positive, credit negative, so the comparison with a GL row is one
    subtraction rather than two cases. An asset contributes to **two** accounts
    from one row: its cost as a debit, its accumulated depreciation as a credit.

    A zero accumulated depreciation contributes nothing and does not register the
    depreciation account: an asset bought last month has none, and inventing a
    zero control total for it would demand a GL row that cannot exist -- the GL
    set holds no zero rows, by constraint.
    """
    totals: dict[uuid.UUID, Decimal] = {}
    for row in contents.analytical:
        totals[row.account_id] = totals.get(row.account_id, ZERO) + row.net
    for asset in contents.assets:
        totals[asset.cost_account_id] = totals.get(asset.cost_account_id, ZERO) + asset.entry_cost
        if asset.accumulated_depreciation != ZERO:
            totals[asset.depreciation_account_id] = (
                totals.get(asset.depreciation_account_id, ZERO) - asset.accumulated_depreciation
            )
    return totals


def check_contents(contents: BatchContents, functional_currency: str) -> None:
    """Spec B section 8.2, the two checks that are this module's own.

    Order is chosen so the first message is the useful one. An unbalanced trial
    balance is reported before a mismatched decomposition, because a batch whose
    GL set does not balance almost always has one wrong figure and every
    downstream comparison would then be noise.
    """
    batch = contents.batch

    if not contents.gl:
        raise EmptyGlSetError(
            f"batch {batch.id} has no GL rows. The trial balance is the set the "
            f"other five decompose; without it there is nothing to post and "
            f"nothing to check the rest against"
        )

    _check_currency(contents, functional_currency)

    debit = sum((row.debit for row in contents.gl), ZERO)
    credit = sum((row.credit for row in contents.gl), ZERO)
    if debit != credit:
        raise GlOutOfBalanceError(
            f"the GL set totals debit {debit} against credit {credit} (difference "
            f"{debit - credit}) over {len(contents.gl)} row(s). Reconciling to zero "
            f"is the condition of the import, not its goal"
        )

    if any(row.account_id == batch.counterpart_account_id for row in contents.gl):
        raise CounterpartInGlError(
            f"account {batch.counterpart_account_id} is the technical opening "
            f"account of this batch and also carries a GL balance. It is the other "
            f"side of every opening line, never one of them -- otherwise its "
            f"balance after posting is not zero and stops being the completeness "
            f"test Spec B section 8.3 names it for"
        )

    control = {row.account_id: row.net for row in contents.gl}
    for account_id, detail in sorted(
        decomposition(contents).items(), key=lambda pair: str(pair[0])
    ):
        expected = control.get(account_id)
        if expected is None:
            raise AccountMissingFromGlError(
                f"account {account_id} is detailed by {detail} in an analytical set "
                f"and carries no GL balance. That is an incomplete trial balance, "
                f"not a rounding difference: the detail would post with no synthetic "
                f"figure behind it"
            )
        if expected != detail:
            raise AnalyticalMismatchError(
                f"account {account_id} carries {expected} in the GL set and {detail} "
                f"across its analytical rows (difference {expected - detail}). One of "
                f"the two numbers is wrong, and posting either would make the partner "
                f"ledger disagree with the account it rolls up into"
            )


def _check_currency(contents: BatchContents, functional_currency: str) -> None:
    """Every balance is in the company's own currency, or the batch is refused.

    Not converted, and not stored unchecked. Converting needs a rounding rule
    (`DNB-08`, open); storing a foreign amount whose relation to the functional
    one nothing verified would put lines in an append-only ledger that cannot be
    reconciled afterwards. The manual note refuses the same thing for the same
    reason, and the two refusals are removed by the same decision.
    """
    for row in (*contents.gl, *contents.analytical):
        if row.currency is not None and row.currency != functional_currency:
            raise ForeignCurrencyBalanceError(
                f"a balance on account {row.account_id} is in {row.currency} and this "
                f"company keeps its books in {functional_currency}. An opening "
                f"balance in another currency needs the conversion and rounding "
                f"convention, which is open (DNB-08)"
            )


def posting_dimensions(contents: BatchContents) -> list[LineDimensions]:
    """What the engine's dimension check is given -- one entry per proposed line.

    Built here rather than in the posting service so that ``validate_batch`` asks
    exactly the question ``post_batch`` will ask. A validation that checked a
    different set of lines than the one that posts would be worth nothing.

    The technical counterpart is included once. If a company chose an account that
    requires a dimension for it, every opening line would be refused at posting --
    better said now, while the choice can still be changed.
    """
    decomposed = set(decomposition(contents))
    lines = [
        LineDimensions(row.account_id, {})
        for row in contents.gl
        if row.account_id not in decomposed
    ]
    lines += [
        LineDimensions(row.account_id, {"partner": row.partner_id}) for row in contents.receivables
    ]
    lines += [
        LineDimensions(row.account_id, {"partner": row.partner_id}) for row in contents.payables
    ]
    lines += [
        LineDimensions(row.account_id, {"item": row.item_id, "warehouse": row.warehouse_id})
        for row in contents.inventory
    ]
    for asset in contents.assets:
        lines.append(LineDimensions(asset.cost_account_id, {"asset": asset.asset_id}))
        if asset.accumulated_depreciation != ZERO:
            lines.append(LineDimensions(asset.depreciation_account_id, {"asset": asset.asset_id}))
    lines.append(LineDimensions(contents.batch.counterpart_account_id, {}))
    return lines


# --- the lifecycle -----------------------------------------------------------


def assert_transition(batch: OpeningBalanceBatch, target: str) -> None:
    """Refuse a status change the matrix does not carry.

    Public because ``services.posting`` makes the ``validated -> posted`` move and
    must meet the same matrix. A second copy of the rule there is exactly how a
    posted batch would one day become editable again.
    """
    if target not in TRANSITIONS[batch.status]:
        raise IllegalBatchTransitionError(
            f"batch {batch.id}: {batch.status} -> {target} is not permitted"
        )


@transaction.atomic
def validate_batch(batch_id: uuid.UUID, functional_currency: str) -> OpeningBalanceBatch:
    """Run Spec B section 8.2 and freeze the batch, or refuse with a code.

    After this the six line tables refuse every write. That is what makes
    ``validated`` mean something: the rows the engine posts are the rows these
    checks ran against, rather than whatever the table held at some earlier
    moment.
    """
    batch = batch_in_context(batch_id)
    assert_transition(batch, BatchStatus.VALIDATED)

    contents = load_contents(batch)
    check_contents(contents, functional_currency)

    # The period, the chart and the mandatory dimensions -- asked of the modules
    # that own them, with their own codes. `assert_dimensions_present` refuses an
    # account that is absent, closed on the date or blocked
    # (`posting.account_not_postable`) before it looks at dimensions at all, so
    # the third and fourth bullets of section 8.2 are both covered by this call.
    assert_postable(batch.company_id, batch.as_of_date)
    assert_dimensions_present(batch.company_id, batch.as_of_date, posting_dimensions(contents))

    batch.status = BatchStatus.VALIDATED
    batch.validated_at = datetime.now(UTC)
    batch.save(update_fields=["status", "validated_at", "updated_at"])

    record(
        action="opening_balance.batch_validated",
        entity_type="opening_balance_batch",
        entity_id=batch.id,
        company_id=batch.company_id,
        new_value=summary(contents),
    )
    return batch


@transaction.atomic
def reopen_batch(batch_id: uuid.UUID) -> OpeningBalanceBatch:
    """Send a validated batch back to ``draft`` so its rows can be corrected."""
    batch = batch_in_context(batch_id)
    assert_transition(batch, BatchStatus.DRAFT)
    batch.status = BatchStatus.DRAFT
    batch.validated_at = None
    batch.save(update_fields=["status", "validated_at", "updated_at"])
    record(
        action="opening_balance.batch_reopened",
        entity_type="opening_balance_batch",
        entity_id=batch.id,
        company_id=batch.company_id,
    )
    return batch


@transaction.atomic
def reject_batch(batch_id: uuid.UUID, reason: str) -> OpeningBalanceBatch:
    """Abandon a batch, keeping it.

    ``rejected`` exists so that a batch is never deleted. What somebody tried to
    load, and why it was stopped, is the question asked when the balances turn
    out wrong a year later, and a deleted row answers it with nothing.
    """
    if not reason.strip():
        raise OpeningBalanceError(
            "rejecting a batch needs a reason; a rejected batch with no reason "
            "records that somebody stopped and not what they saw"
        )
    batch = batch_in_context(batch_id)
    assert_transition(batch, BatchStatus.REJECTED)
    batch.status = BatchStatus.REJECTED
    batch.rejected_at = datetime.now(UTC)
    batch.rejected_reason = reason
    batch.save(update_fields=["status", "rejected_at", "rejected_reason", "updated_at"])
    record(
        action="opening_balance.batch_rejected",
        entity_type="opening_balance_batch",
        entity_id=batch.id,
        company_id=batch.company_id,
        new_value={"reason": reason},
    )
    return batch


def summary(contents: BatchContents) -> dict[str, object]:
    """A fingerprintable description of the batch, in numbers rather than rows.

    Two callers: the audit entry, which must not carry ten thousand rows, and the
    accounting event payload, whose fingerprint has to detect a batch that
    changed between two arrivals of one idempotency key. The batch is frozen from
    ``validated`` onwards, so a change big enough to matter cannot leave these
    numbers untouched.
    """
    return {
        "gl": len(contents.gl),
        "receivables": len(contents.receivables),
        "payables": len(contents.payables),
        "inventory": len(contents.inventory),
        "assets": len(contents.assets),
        "payroll": len(contents.payroll),
        "total_debit": str(sum((row.debit for row in contents.gl), ZERO)),
    }
