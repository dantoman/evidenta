"""The ledger -- F1.2, and the three refusals that must live in the database.

Every claim here is about what the **database** does, not what a service does.
That is the whole point of Spec B sections 1.6 and 6.3: the bulk importer, the 1C
migration and any data migration go around the service, and those are exactly the
paths that produce an unbalanced ledger.

Two exception families appear below, and the difference is not cosmetic: a
`check_violation` from the balance trigger reaches Django as ``IntegrityError``,
while a plpgsql ``RAISE`` with the default code reaches it as
``ProgrammingError``. Each test names the one it expects rather than catching
``DatabaseError``, because a service will branch on the class and a test that
accepted either would not notice it changing.

The deferred balance check needs one unusual move. It fires at COMMIT, and a
pytest transaction never commits -- so a test that only inserted rows would prove
nothing and pass. ``SET CONSTRAINTS ALL IMMEDIATE`` forces the deferred trigger to
run at that point instead, which is the same trigger firing for the same reason.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from decimal import Decimal

import pytest
from django.db import connection, transaction
from django.db.utils import IntegrityError, ProgrammingError

from evidenta.accounting.coa.dimensions import DIMENSION_KEYS
from evidenta.accounting.ledger.errors import (
    AlreadyReversedError,
    NotPostedError,
)
from evidenta.accounting.ledger.models import (
    CompanyDimension,
    EntryStatus,
    EntryType,
    JournalEntry,
    JournalLine,
)
from evidenta.accounting.ledger.services.lineage import (
    event_id_of_entry,
    line_ids_of_entry,
    origin_of_line,
)
from evidenta.accounting.ledger.services.reversal import reverse_entry
from evidenta.platform.rls.context import TenantContext, tenant_context, unguarded

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="ledger")


@pytest.fixture
def company(
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> uuid.UUID:
    company_id = company_of(world["tenant_a"], "1002600000301", "Alpha Registru")
    grant_company(world["tenant_a"], company_id, world["user_a"], world["user_a"])
    return company_id


def seed_period(
    seed: Callable[..., None],
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    *,
    status: str = "open",
    start: str = "2026-01-01",
    end: str = "2026-01-31",
    period_no: int = 1,
    year_id: uuid.UUID | None = None,
) -> tuple[uuid.UUID, uuid.UUID]:
    """One month, in an exercise -- creating the exercise only if asked to.

    A company has one exercise per year (`fiscal_year_code_unique`), so a second
    period of the same year has to be added to the first exercise rather than to
    a second one. Found by the unique constraint, which is where it should be
    found.
    """
    period_id = uuid.uuid4()
    if year_id is None:
        year_id = uuid.uuid4()
        seed(
            "INSERT INTO fiscal_year (id, tenant_id, company_id, code, start_date, end_date,"
            " status, created_at, updated_at)"
            " VALUES (%s, %s, %s, '2026', '2026-01-01', '2026-12-31', 'open', now(), now())",
            [year_id, tenant_id, company_id],
        )
    # A closed period must say when it was closed (`period_closed_has_timestamp`).
    # Seeding one without that is a state production cannot reach.
    closed_at = "now()" if status in ("closed", "locked") else "NULL"
    seed(
        "INSERT INTO period (id, tenant_id, company_id, fiscal_year_id, period_no,"
        " start_date, end_date, status, reopened_count, closed_at, created_at, updated_at)"
        f" VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, {closed_at}, now(), now())",
        [period_id, tenant_id, company_id, year_id, period_no, start, end, status],
    )
    return year_id, period_id


def seed_event(
    seed: Callable[..., None], tenant_id: uuid.UUID, company_id: uuid.UUID, user_id: uuid.UUID
) -> uuid.UUID:
    event_id = uuid.uuid4()
    seed(
        "INSERT INTO accounting_event (id, tenant_id, company_id, event_type, event_version,"
        " source_module, source_document_type, source_document_id, occurred_at,"
        " accounting_date, idempotency_key, payload, capability_snapshot, status,"
        " actor_user_id, request_id, created_at)"
        " VALUES (%s, %s, %s, 'fixture.event', 1, 'manual', 'fixture', %s, %s,"
        " '2026-01-15', %s, '{}', '{}', 'pending', %s, 'ledger', now())",
        [
            event_id,
            tenant_id,
            company_id,
            uuid.uuid4(),
            datetime.now(UTC),
            f"key-{event_id}",
            user_id,
        ],
    )
    return event_id


@pytest.fixture
def scaffold(
    seed: Callable[..., None], world: dict[str, uuid.UUID], company: uuid.UUID
) -> dict[str, uuid.UUID]:
    year_id, period_id = seed_period(seed, world["tenant_a"], company)
    return {
        "company": company,
        "tenant": world["tenant_a"],
        "fiscal_year": year_id,
        "period": period_id,
        "event": seed_event(seed, world["tenant_a"], company, world["user_a"]),
    }


def defer_checks() -> None:
    """Ask for the deferral the production path gets for free.

    In production the balance trigger is ``INITIALLY DEFERRED`` and the request
    transaction simply commits. Inside the harness the mode is whatever the last
    ``SET CONSTRAINTS`` in this transaction left, so each entry builder states
    what it needs rather than inheriting it from whichever test ran first.
    """
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL DEFERRED")


def make_entry(scaffold: dict[str, uuid.UUID], number: str = "JE-1") -> JournalEntry:
    defer_checks()
    return JournalEntry.objects.create(
        tenant_id=scaffold["tenant"],
        company_id=scaffold["company"],
        entry_number=number,
        accounting_date=date(2026, 1, 15),
        period_id=scaffold["period"],
        accounting_event_id=scaffold["event"],
        description="Inregistrare de fixture",
        request_id="ledger",
    )


def add_line(
    entry: JournalEntry, number: int, *, debit: str = "0", credit: str = "0", **extra: object
) -> JournalLine:
    """A domestic line by default; `extra` overrides any column of it.

    The defaults are merged rather than passed alongside `extra`, so a caller
    describing a foreign-currency line does not collide with the MDL ones.
    """
    fields: dict[str, object] = {
        "tenant_id": entry.tenant_id,
        "company_id": entry.company_id,
        "accounting_date": entry.accounting_date,
        "document_date": entry.accounting_date,
        "rate_date": entry.accounting_date,
        "journal_entry": entry,
        "line_number": number,
        "account_id": uuid.uuid4(),
        "debit": Decimal(debit),
        "credit": Decimal(credit),
        "currency": "MDL",
        "amount_currency": Decimal(debit) + Decimal(credit),
        "exchange_rate": Decimal("1"),
    }
    fields.update(extra)
    return JournalLine.objects.create(**fields)


def force_deferred_checks() -> None:
    """Run the deferred constraint trigger now instead of at COMMIT."""
    with connection.cursor() as cursor:
        cursor.execute("SET CONSTRAINTS ALL IMMEDIATE")


# --- R11: the balance is the database's business ----------------------------


def test_a_balanced_entry_passes_the_deferred_check(
    context: TenantContext, scaffold: dict[str, uuid.UUID]
) -> None:
    """And the intermediate state is unbalanced, which is why it must be deferred.

    Lines are inserted one at a time. Between the first and the last the entry
    does not balance -- by construction, not by accident -- so an immediate check
    would make a correct entry impossible to write.
    """
    with tenant_context(context):
        entry = make_entry(scaffold)
        add_line(entry, 1, debit="100.0000")

        entry.refresh_from_db()
        assert entry.total_debit == Decimal("100.0000")
        assert entry.total_credit == Decimal("0.0000")

        add_line(entry, 2, credit="100.0000")
        force_deferred_checks()

        entry.refresh_from_db()
        assert entry.total_debit == entry.total_credit == Decimal("100.0000")


def test_an_unbalanced_entry_cannot_reach_commit(
    context: TenantContext, scaffold: dict[str, uuid.UUID]
) -> None:
    with (
        tenant_context(context),
        pytest.raises(IntegrityError, match="out of balance"),
        transaction.atomic(),
    ):
        entry = make_entry(scaffold)
        add_line(entry, 1, debit="100.0000")
        force_deferred_checks()


def test_an_entry_with_no_amount_is_refused(
    context: TenantContext, scaffold: dict[str, uuid.UUID]
) -> None:
    """Balanced at zero is still not an entry. Spec B section 1.6 asks for
    `total_debit > 0`, and without it a posted entry recording nothing would be
    indistinguishable from one whose lines were never written.
    """
    # Everything inside the savepoint: the refusal aborts the transaction, so a
    # test that let it escape would fail on the next statement with an unrelated
    # "current transaction is aborted" rather than on the assertion it makes.
    with (
        tenant_context(context),
        pytest.raises(IntegrityError, match="has no amount"),
        transaction.atomic(),
    ):
        entry = make_entry(scaffold)
        entry.status = EntryStatus.POSTED
        entry.posted_at = datetime.now(UTC)
        entry.save(update_fields=["status", "posted_at"])
        force_deferred_checks()


def test_a_line_with_both_sides_is_refused_immediately(
    context: TenantContext, scaffold: dict[str, uuid.UUID]
) -> None:
    """Both zero is noise; both non-zero is a modelling error in a valid row's
    clothes. This one does not wait for commit -- it is a CHECK on the line.
    """
    with tenant_context(context):
        entry = make_entry(scaffold)
        with (
            pytest.raises(IntegrityError, match="journal_line_one_side_only"),
            transaction.atomic(),
        ):
            add_line(entry, 1, debit="100.0000", credit="100.0000")


# --- R10: posted is immutable -----------------------------------------------


def posted_entry(scaffold: dict[str, uuid.UUID]) -> JournalEntry:
    entry = make_entry(scaffold)
    add_line(entry, 1, debit="50.0000")
    add_line(entry, 2, credit="50.0000")
    entry.status = EntryStatus.POSTED
    entry.posted_at = datetime.now(UTC)
    entry.save(update_fields=["status", "posted_at"])
    force_deferred_checks()
    return entry


def test_a_posted_entry_cannot_be_edited(
    context: TenantContext, scaffold: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        entry = posted_entry(scaffold)
        entry.description = "Altceva"
        with pytest.raises(ProgrammingError, match="immutable"), transaction.atomic():
            entry.save(update_fields=["description"])


def test_a_posted_entry_cannot_be_deleted_by_the_application_role(
    context: TenantContext, scaffold: dict[str, uuid.UUID]
) -> None:
    """The refusal is a missing privilege, not a trigger someone can disable.

    Correction is a reversal and a re-entry, never an erasure -- so the ledger
    does not need DELETE at all, and not having it is stronger than refusing it.
    """
    with tenant_context(context):
        entry = posted_entry(scaffold)
        with (
            pytest.raises(ProgrammingError, match="permission denied"),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute("DELETE FROM journal_entry WHERE id = %s", [str(entry.id)])


def test_a_line_of_a_posted_entry_cannot_be_changed(
    context: TenantContext, scaffold: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        entry = posted_entry(scaffold)
        line = JournalLine.objects.filter(journal_entry=entry).first()
        assert line is not None
        line.description = "corectura"
        with pytest.raises(ProgrammingError, match="immutable"), transaction.atomic():
            line.save(update_fields=["description"])


# --- R12: a closed period refuses, in the database --------------------------


def test_nothing_posts_into_a_closed_period(
    context: TenantContext,
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company: uuid.UUID,
    scaffold: dict[str, uuid.UUID],
) -> None:
    """The second barrier of Spec B section 6.3.

    The engine refuses first, with a stable code and a legible message. This is
    what refuses the importer, which never asks the engine.
    """
    _, closed = seed_period(
        seed,
        world["tenant_a"],
        company,
        status="closed",
        start="2026-02-01",
        end="2026-02-28",
        period_no=2,
        year_id=scaffold["fiscal_year"],
    )
    with (
        tenant_context(context),
        pytest.raises(ProgrammingError, match="nothing posts into it"),
        transaction.atomic(),
    ):
        JournalEntry.objects.create(
            tenant_id=world["tenant_a"],
            company_id=company,
            entry_number="JE-CLOSED",
            accounting_date=date(2026, 2, 15),
            period_id=closed,
            accounting_event_id=scaffold["event"],
            description="Nu trebuie sa intre",
            request_id="ledger",
        )


def test_a_date_outside_its_period_is_refused(
    context: TenantContext, scaffold: dict[str, uuid.UUID], world: dict[str, uuid.UUID]
) -> None:
    """`period.end_date` is inclusive, unlike every validity window in the system.

    The trigger uses BETWEEN for exactly that reason, and this test pins it: an
    entry dated the 31st belongs to January, one dated the 1st of February does
    not -- the off-by-one the two conventions would otherwise produce is one day a
    year, found at a client.
    """
    with (
        tenant_context(context),
        pytest.raises(ProgrammingError, match="outside period"),
        transaction.atomic(),
    ):
        JournalEntry.objects.create(
            tenant_id=world["tenant_a"],
            company_id=scaffold["company"],
            entry_number="JE-OUTSIDE",
            accounting_date=date(2026, 2, 1),
            period_id=scaffold["period"],
            accounting_event_id=scaffold["event"],
            description="Data in afara perioadei",
            request_id="ledger",
        )


# --- R21/R22 and ADR-029: the shape of the largest table --------------------


def test_the_dimension_columns_are_exactly_the_vocabulary() -> None:
    """The tie between `coa.dimensions` and the columns, which is otherwise only
    a comment. A name that can be required by an account must have a column, and
    a column must have a name -- neither direction is allowed to drift.
    """
    columns = {
        field.name
        for field in JournalLine._meta.get_fields()
        if field.name.endswith("_id") and field.name not in {"journal_entry_id", "uom_id"}
    }
    columns -= {"tenant_id", "company_id", "account_id"}
    assert columns == {f"{name}_id" for name in DIMENSION_KEYS}


def test_no_foreign_key_points_at_the_line_table() -> None:
    """R21, stated here as well as in the schema guard.

    The guard reads `infra/schema/append_only.toml` and would catch this too. It
    is repeated because the reason is local: a table with ten incoming keys is
    not repartitioned, it is redesigned -- and `journal_line` is the table the
    volume model named.
    """
    with unguarded("reading the catalogue, not tenant data"), connection.cursor() as cursor:
        cursor.execute(
            "SELECT count(*) FROM pg_constraint con JOIN pg_class tgt ON tgt.oid = con.confrelid "
            "WHERE con.contype = 'f' AND tgt.relname = 'journal_line'"
        )
        assert cursor.fetchone()[0] == 0


# --- isolation --------------------------------------------------------------


def test_lines_of_one_tenant_are_invisible_to_another(
    context: TenantContext, scaffold: dict[str, uuid.UUID], world: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        entry = make_entry(scaffold)
        add_line(entry, 1, debit="10.0000")
        add_line(entry, 2, credit="10.0000")
        force_deferred_checks()
        assert JournalLine.objects.count() == 2

    other = TenantContext(tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="ledger")
    with tenant_context(other):
        assert JournalLine.objects.count() == 0
        assert JournalEntry.objects.count() == 0


def test_the_company_narrowing_of_adr_004_actually_narrows(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company: uuid.UUID,
    scaffold: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> None:
    """`app.company_id` narrows, it does not grant (ADR-004).

    Both companies belong to the caller, so access is not the question. With the
    context narrowed to one of them, the other's lines are simply not there --
    which is what stops a report written for one company from quietly summing
    two. Most company-scoped tables in the product do not carry this clause yet
    (`OD-57`); the ledger does, from its first row.
    """
    second = company_of(world["tenant_a"], "1002600000302", "Alpha Registru doi")
    grant_company(world["tenant_a"], second, world["user_a"], world["user_a"])
    _, second_period = seed_period(seed, world["tenant_a"], second)
    second_event = seed_event(seed, world["tenant_a"], second, world["user_a"])

    wide = TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="ledger")
    with tenant_context(wide):
        first_entry = make_entry(scaffold, number="JE-A")
        add_line(first_entry, 1, debit="10.0000")
        add_line(first_entry, 2, credit="10.0000")

        second_entry = JournalEntry.objects.create(
            tenant_id=world["tenant_a"],
            company_id=second,
            entry_number="JE-B",
            accounting_date=date(2026, 1, 15),
            period_id=second_period,
            accounting_event_id=second_event,
            description="A doua companie",
            request_id="ledger",
        )
        add_line(second_entry, 1, debit="20.0000")
        add_line(second_entry, 2, credit="20.0000")
        force_deferred_checks()

        assert JournalEntry.objects.count() == 2

    narrowed = TenantContext(
        tenant_id=world["tenant_a"],
        user_id=world["user_a"],
        request_id="ledger",
        company_id=company,
    )
    with tenant_context(narrowed):
        assert [e.entry_number for e in JournalEntry.objects.all()] == ["JE-A"]
        assert JournalLine.objects.count() == 2


# --- ADR-029: what a slot means, per company --------------------------------


def test_a_slot_outside_the_five_is_refused(
    context: TenantContext, company: uuid.UUID, world: dict[str, uuid.UUID]
) -> None:
    with (
        tenant_context(context),
        pytest.raises(IntegrityError, match="company_dimension_slot_known"),
        transaction.atomic(),
    ):
        CompanyDimension.objects.create(
            tenant_id=world["tenant_a"],
            company_id=company,
            slot="dim_6",
            name="A sasea axa",
        )


def test_two_slots_cannot_share_a_name(
    context: TenantContext, company: uuid.UUID, world: dict[str, uuid.UUID]
) -> None:
    """Two slots with one label make every report ambiguous in the one place the
    reader cannot check.
    """
    with tenant_context(context):
        CompanyDimension.objects.create(
            tenant_id=world["tenant_a"], company_id=company, slot="dim_1", name="Proiect"
        )
        with (
            pytest.raises(IntegrityError, match="company_dimension_name_unique"),
            transaction.atomic(),
        ):
            CompanyDimension.objects.create(
                tenant_id=world["tenant_a"], company_id=company, slot="dim_2", name="Proiect"
            )


# --- R13: the hops this module owns -----------------------------------------


def test_a_line_leads_to_its_entry_and_to_the_event(
    context: TenantContext, scaffold: dict[str, uuid.UUID]
) -> None:
    """Two hops of the chain, in one read, as plain data.

    The caller never receives a model: a `JournalEntry` handed across a module
    boundary is the coupling `D6` exists to stop, arriving through a service
    instead of an import.
    """
    with tenant_context(context):
        entry = make_entry(scaffold)
        line = add_line(entry, 1, debit="42.0000")
        add_line(entry, 2, credit="42.0000")
        force_deferred_checks()

        origin = origin_of_line(line.id)
        assert origin is not None
        assert origin.journal_entry_id == entry.id
        assert origin.accounting_event_id == scaffold["event"]
        assert origin.company_id == scaffold["company"]
        assert origin.accounting_date == date(2026, 1, 15)


def test_the_reverse_hop_is_an_index_read_in_line_order(
    context: TenantContext, scaffold: dict[str, uuid.UUID]
) -> None:
    """Entry to lines. Nothing points *at* `journal_line` (R21), so this is an
    index read, which is exactly what Spec B section 9.1 calls it.
    """
    with tenant_context(context):
        entry = make_entry(scaffold)
        second = add_line(entry, 2, credit="7.0000")
        first = add_line(entry, 1, debit="7.0000")
        force_deferred_checks()

        assert line_ids_of_entry(entry.id) == [first.id, second.id]
        assert event_id_of_entry(entry.id) == scaffold["event"]


def test_a_line_of_another_tenant_leads_nowhere(
    context: TenantContext,
    scaffold: dict[str, uuid.UUID],
    world: dict[str, uuid.UUID],
) -> None:
    """Absent, not forbidden -- the same answer for "no such line" and "not
    yours", so that a caller cannot enumerate another tenant's identifiers.
    """
    with tenant_context(context):
        entry = make_entry(scaffold)
        line = add_line(entry, 1, debit="5.0000")
        add_line(entry, 2, credit="5.0000")
        force_deferred_checks()

    other = TenantContext(tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="ledger")
    with tenant_context(other):
        assert origin_of_line(line.id) is None
        assert line_ids_of_entry(entry.id) == []
        assert event_id_of_entry(entry.id) is None


# --- R14: storno ------------------------------------------------------------


def reverse(
    scaffold: dict[str, uuid.UUID],
    seed: Callable[..., None],
    entry: JournalEntry,
    number: str = "JE-R",
    corrects_period_id: uuid.UUID | None = None,
) -> JournalEntry:
    """A reversal needs its own event: it is a correction somebody asked for."""
    event = seed_event(seed, scaffold["tenant"], scaffold["company"], uuid.uuid4())
    defer_checks()
    return reverse_entry(
        entry.id,
        accounting_event_id=event,
        period_id=scaffold["period"],
        accounting_date=date(2026, 1, 20),
        entry_number=number,
        request_id="ledger",
        rule_ref="fixture.reversal.v1",
        corrects_period_id=corrects_period_id,
    )


def test_a_reversal_carries_both_links(
    context: TenantContext, scaffold: dict[str, uuid.UUID], seed: Callable[..., None]
) -> None:
    """R14. Without the second link a drill-down shows two entries with opposite
    amounts and nothing saying one cancels the other.
    """
    with tenant_context(context):
        original = posted_entry(scaffold)
        reversal = reverse(scaffold, seed, original)
        force_deferred_checks()

        assert reversal.entry_type == EntryType.REVERSAL
        assert reversal.reverses_entry_id == original.id
        assert reversal.accounting_event_id != original.accounting_event_id
        assert reversal.status == EntryStatus.POSTED


def test_the_lines_are_swapped_not_negated(
    context: TenantContext, scaffold: dict[str, uuid.UUID], seed: Callable[..., None]
) -> None:
    """A negative line breaks turnover: the month's debit turnover would go *down*
    by the correction instead of up, and the trial balance would stop showing the
    activity that happened. Spec B section 9.2.
    """
    with tenant_context(context):
        original = posted_entry(scaffold)
        reversal = reverse(scaffold, seed, original)
        force_deferred_checks()

        originals = {
            line.line_number: line for line in JournalLine.objects.filter(journal_entry=original)
        }
        for line in JournalLine.objects.filter(journal_entry=reversal):
            counterpart = originals[line.line_number]
            assert line.debit == counterpart.credit
            assert line.credit == counterpart.debit
            assert line.debit >= 0 and line.credit >= 0
            # Same account, same analytics -- only the sides move.
            assert line.account_id == counterpart.account_id

        reversal.refresh_from_db()
        original.refresh_from_db()
        assert reversal.total_debit == original.total_credit
        assert reversal.total_credit == original.total_debit


def test_the_reversal_keeps_the_original_exchange_rate(
    context: TenantContext, scaffold: dict[str, uuid.UUID], seed: Callable[..., None]
) -> None:
    """Taking a fresh rate would leave the difference behind as a silent drift.

    And that difference is an exchange-difference event -- a different economic
    fact with its own treatment -- not a rounding artefact of a correction.
    """
    with tenant_context(context):
        entry = make_entry(scaffold, number="JE-FX")
        add_line(
            entry,
            1,
            debit="1900.0000",
            currency="EUR",
            amount_currency=Decimal("100.0000"),
            exchange_rate=Decimal("19.00000000"),
            rate_date=date(2026, 1, 10),
        )
        add_line(entry, 2, credit="1900.0000")
        entry.status = EntryStatus.POSTED
        entry.posted_at = datetime.now(UTC)
        entry.save(update_fields=["status", "posted_at"])
        force_deferred_checks()

        reversal = reverse(scaffold, seed, entry, number="JE-FXR")
        force_deferred_checks()

        line = JournalLine.objects.get(journal_entry=reversal, line_number=1)
        assert line.exchange_rate == Decimal("19.00000000")
        assert line.rate_date == date(2026, 1, 10)
        assert line.currency == "EUR"
        assert line.amount_currency == Decimal("100.0000")


def test_a_draft_is_not_reversed(
    context: TenantContext, scaffold: dict[str, uuid.UUID], seed: Callable[..., None]
) -> None:
    """Nothing was recorded, so there is nothing to cancel -- and reversing one
    would put two entries in the ledger where the correct outcome is none.
    """
    with tenant_context(context):
        entry = make_entry(scaffold)
        add_line(entry, 1, debit="5.0000")
        add_line(entry, 2, credit="5.0000")

        with pytest.raises(NotPostedError) as excinfo:
            reverse(scaffold, seed, entry)
    assert excinfo.value.code == "ledger.entry_not_posted"


def test_a_second_reversal_of_the_same_entry_is_refused(
    context: TenantContext, scaffold: dict[str, uuid.UUID], seed: Callable[..., None]
) -> None:
    """Almost always the same correction requested twice -- and the result is a
    ledger that cancels the entry twice, which no report shows as odd.
    """
    with tenant_context(context):
        original = posted_entry(scaffold)
        reverse(scaffold, seed, original)
        force_deferred_checks()

        with pytest.raises(AlreadyReversedError) as excinfo:
            reverse(scaffold, seed, original, number="JE-R2")
    assert excinfo.value.code == "ledger.entry_already_reversed"


def test_a_reversal_may_itself_be_reversed(
    context: TenantContext, scaffold: dict[str, uuid.UUID], seed: Callable[..., None]
) -> None:
    """Re-entry after a wrong correction, and the chain stays navigable.

    Spec B section 9.4 allows it precisely because the alternative -- editing the
    reversal -- is the UPDATE the ledger does not have.
    """
    with tenant_context(context):
        original = posted_entry(scaffold)
        first = reverse(scaffold, seed, original)
        force_deferred_checks()

        second = reverse(scaffold, seed, first, number="JE-RR")
        force_deferred_checks()

        assert second.reverses_entry_id == first.id
        assert first.reverses_entry_id == original.id
        # Both sides walk: from the original forward, and from the last back.
        assert JournalEntry.objects.get(reverses_entry_id=original.id).id == first.id


def test_the_original_is_untouched_by_its_reversal(
    context: TenantContext, scaffold: dict[str, uuid.UUID], seed: Callable[..., None]
) -> None:
    """ "Stornoul nu șterge nimic și nu marchează originalul altfel decât prin
    existența legăturii" -- Spec B section 9.4. There is no flag to set, and the
    immutability trigger would refuse one anyway.
    """
    with tenant_context(context):
        original = posted_entry(scaffold)
        # From the database, not from the in-memory object: the totals are
        # written by a trigger, so the attribute here is still the default.
        original.refresh_from_db()
        before = (original.total_debit, original.total_credit, original.description)

        reverse(scaffold, seed, original)
        force_deferred_checks()

        original.refresh_from_db()
        assert (original.total_debit, original.total_credit, original.description) == before
        assert original.status == EntryStatus.POSTED


def test_only_a_correction_may_name_the_period_it_corrects(
    context: TenantContext, scaffold: dict[str, uuid.UUID]
) -> None:
    """ADR-006's second date belongs to a reversal or an adjustment.

    A standard entry that named a corrected period would make the rectifying
    declaration include entries that rectify nothing.
    """
    with (
        tenant_context(context),
        pytest.raises(IntegrityError, match="journal_entry_corrects_only_when_correcting"),
        transaction.atomic(),
    ):
        defer_checks()
        JournalEntry.objects.create(
            tenant_id=scaffold["tenant"],
            company_id=scaffold["company"],
            entry_number="JE-BAD",
            accounting_date=date(2026, 1, 15),
            period_id=scaffold["period"],
            accounting_event_id=scaffold["event"],
            corrects_period_id=scaffold["period"],
            description="Nu e corectie",
            request_id="ledger",
        )
