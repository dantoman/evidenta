"""What a calculation stood on, kept where the calculation is -- `OD-68`, ADR-047.

ADR-046 gave the parameter its history: every state ``source_confidence`` has
been in, and from when. That answers *how firm was this parameter in March*. It
cannot answer *what did the March posting actually stand on*, and the difference
is the whole reason this table exists: **confirming a value does not change the
value.** The moment the tax service publishes, every query about the parameter
says confirmed -- while the March posting was, in fact, made on a deduction.

So the calculation stamps its own basis, at the instant it calculates, and the
confidence is **copied** rather than referenced. The first test below is the one
that matters: it confirms the parameter afterwards and shows the stamp unmoved.
If that test is ever deleted, this table has no reason to exist.

**Under the application role, like every test in this suite** (`T1`). A stamp that
was only visible because the seeding connection could see more would prove
nothing about what an accountant can retrieve at an inspection.

No parameter key here belongs to a real fiscal parameter: the content of the
register is `R15`'s business, and a plausible rate in a fixture is that content
arriving through the back door.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import pytest
from django.db import transaction
from django.db.utils import IntegrityError, ProgrammingError

from evidenta.accounting.events.services.emission import emit
from evidenta.accounting.ledger.models import EntryParameterStamp, JournalEntry
from evidenta.accounting.ledger.services.writing import LineToWrite, ParameterStamp, post_entry
from evidenta.accounting.posting.services.manual import (
    EVENT_TYPE,
    SOURCE_DOCUMENT_TYPE,
    SOURCE_MODULE,
)
from evidenta.fiscal.parameters.services.resolution import confidence_at
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.test_manual_entry import (
    POSTING,
    SNAPSHOT,
    seed_account,
    seed_period,
    seed_template,
)

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

#: The calculation happens inside the open month; the tax service publishes
#: months later. Both instants are fixed so the assertions are about ordering,
#: not about when the suite happened to run.
CALCULATED_AT = datetime(2026, 1, 15, 9, 30, tzinfo=UTC)
PUBLISHED_AT = datetime(2026, 6, 1, 12, 0, tzinfo=UTC)

#: Deliberately not a real parameter key.
KEY = "fixture.exemption.personal"


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="stamp")


@pytest.fixture
def parameter(seed: Callable[..., None]) -> uuid.UUID:
    """One provisional parameter, with the history that makes it provisional.

    Global, like every fiscal parameter: when the tax service publishes, the fact
    is the same for every tenant. Seeded through the privileged connection
    because the application has no business writing these (`P-4`).
    """
    source_id = uuid.uuid4()
    seed(
        "INSERT INTO fiscal_parameter_source (id, act_type, act_number, act_date,"
        " effective_from, created_at) VALUES (%s, 'lege', 'FIXTURE-1', '2025-12-01',"
        " '2026-01-01', now())",
        [source_id],
    )
    parameter_id = uuid.uuid4()
    seed(
        "INSERT INTO fiscal_parameter (id, parameter_key, scope, scope_ref, value_type,"
        " value, unit, valid_from, valid_to, source_id, status, approved_by_user_id,"
        " approved_at, source_confidence, provisional_reason, created_at, updated_at)"
        " VALUES (%s, %s, 'global', NULL, 'money', '1000'::jsonb, 'MDL', '2026-01-01',"
        " NULL, %s, 'active', %s, now(), 'provisional',"
        " 'dedus din lista de modificari', now(), now())",
        # Active means a practising accountant approved it (`R15`); the constraint
        # says so, and a fixture that worked around it would be testing a state
        # the register cannot hold.
        [parameter_id, KEY, source_id, uuid.uuid4()],
    )
    seed(
        "INSERT INTO fiscal_parameter_confidence_event (id, parameter_id, confidence,"
        " provisional_reason, note, effective_at, recorded_at)"
        " VALUES (%s, %s, 'provisional', 'dedus din lista de modificari',"
        " 'stare initiala', '2026-01-01T00:00:00Z', now())",
        [uuid.uuid4(), parameter_id],
    )
    return parameter_id


@pytest.fixture
def scene(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> dict[str, uuid.UUID]:
    """One company, one open month, two accounts, one numbering template."""
    tenant = world["tenant_a"]
    company = company_of(tenant, "1002600000777", "Alpha Stampila")
    grant_company(tenant, company, world["user_a"], world["user_a"])

    year_id = uuid.uuid4()
    seed(
        "INSERT INTO fiscal_year (id, tenant_id, company_id, code, start_date, end_date,"
        " status, created_at, updated_at) VALUES (%s, %s, %s, '2026', '2026-01-01',"
        " '2026-12-31', 'open', now(), now())",
        [year_id, tenant, company],
    )
    seed_template(seed, tenant, company)
    return {
        "tenant": tenant,
        "company": company,
        "user": world["user_a"],
        "period": seed_period(
            seed,
            tenant,
            company,
            year_id,
            period_no=1,
            start="2026-01-01",
            end="2026-01-31",
            status="open",
        ),
        "debit": seed_account(seed, tenant, company, "FIXTURE-D"),
        "credit": seed_account(seed, tenant, company, "FIXTURE-C"),
    }


def post(
    scene: dict[str, uuid.UUID],
    stamps: list[ParameterStamp],
    *,
    key: str = "stamp-1",
    number: str = "NC-0001",
) -> uuid.UUID:
    """One correct entry, stamped. Amounts are irrelevant here and stay round."""
    event, _ = emit(
        tenant_id=scene["tenant"],
        company_id=scene["company"],
        event_type=EVENT_TYPE,
        source_module=SOURCE_MODULE,
        source_document_type=SOURCE_DOCUMENT_TYPE,
        source_document_id=uuid.uuid5(uuid.NAMESPACE_URL, key),
        occurred_at=CALCULATED_AT,
        accounting_date=POSTING,
        idempotency_key=key,
        payload={
            "description": "Nota cu parametru fiscal",
            "lines": [
                {"account_id": str(scene["debit"]), "debit": "1000.00", "credit": "0"},
                {"account_id": str(scene["credit"]), "debit": "0", "credit": "1000.00"},
            ],
        },
        capability_snapshot=dict(SNAPSHOT),
        actor_user_id=scene["user"],
        request_id="stamp-test",
    )
    # Adnotat, altfel dict-ul se deduce ca `dict[str, object]` si fiecare
    # `**common` raporteaza cate sapte nepotriviri — paisprezece erori dintr-un
    # singur tip lipsa, si niciuna despre codul testat.
    common: dict[str, Any] = {
        "currency": "MDL",
        "exchange_rate": Decimal(1),
        "accounting_date": POSTING,
        "document_date": POSTING,
        "rate_date": POSTING,
    }
    return post_entry(
        tenant_id=scene["tenant"],
        company_id=scene["company"],
        entry_number=number,
        accounting_date=POSTING,
        period_id=scene["period"],
        accounting_event_id=event.id,
        description="Nota cu parametru fiscal",
        request_id="stamp-test",
        rule_ref="fixture.stamp.v1",
        fiscal_effective_date=POSTING,
        chart_template_id=None,
        lines=[
            LineToWrite(
                account_id=scene["debit"],
                debit=Decimal("1000.0000"),
                credit=Decimal(0),
                amount_currency=Decimal("1000.0000"),
                **common,
            ),
            LineToWrite(
                account_id=scene["credit"],
                debit=Decimal(0),
                credit=Decimal("1000.0000"),
                amount_currency=Decimal("1000.0000"),
                **common,
            ),
        ],
        parameter_stamps=stamps,
    )


def seed_posted_entry(
    seed: Callable[..., None], scene: dict[str, uuid.UUID], parameter_id: uuid.UUID
) -> tuple[uuid.UUID, uuid.UUID]:
    """A posted entry and one stamp, written through the privileged connection.

    Committed rather than held in the test transaction, because the trigger under
    test only fires on rows another connection can see.
    """
    event_id = uuid.uuid4()
    seed(
        "INSERT INTO accounting_event (id, tenant_id, company_id, event_type,"
        " event_version, source_module, source_document_type, source_document_id,"
        " occurred_at, accounting_date, idempotency_key, payload, capability_snapshot,"
        " status, posted_at, actor_user_id, request_id, created_at)"
        " VALUES (%s, %s, %s, %s, 1, %s, %s, %s, %s, %s, 'stamp-seed', '{}'::jsonb,"
        " %s::jsonb, 'posted', now(), %s, 'stamp-test', now())",
        [
            event_id,
            scene["tenant"],
            scene["company"],
            EVENT_TYPE,
            SOURCE_MODULE,
            SOURCE_DOCUMENT_TYPE,
            uuid.uuid4(),
            CALCULATED_AT,
            POSTING,
            json.dumps(SNAPSHOT),
            scene["user"],
        ],
    )
    entry_id = uuid.uuid4()
    seed(
        "INSERT INTO journal_entry (id, tenant_id, company_id, entry_number,"
        " accounting_date, period_id, entry_type, accounting_event_id, status,"
        " posted_at, posted_by_user_id, description, total_debit, total_credit,"
        " request_id, created_at, updated_at)"
        " VALUES (%s, %s, %s, 'NC-SEED', %s, %s, 'standard', %s, 'posted', now(), %s,"
        " 'Nota semanata', 1000, 1000, 'stamp-test', now(), now())",
        [
            entry_id,
            scene["tenant"],
            scene["company"],
            POSTING,
            scene["period"],
            event_id,
            scene["user"],
        ],
    )
    stamp_id = uuid.uuid4()
    seed(
        "INSERT INTO entry_parameter_stamp (id, tenant_id, company_id, journal_entry_id,"
        " parameter_id, parameter_key, effective_date, confidence, resolved_at, created_at)"
        " VALUES (%s, %s, %s, %s, %s, %s, %s, 'provisional', %s, now())",
        [
            stamp_id,
            scene["tenant"],
            scene["company"],
            entry_id,
            parameter_id,
            KEY,
            POSTING,
            CALCULATED_AT,
        ],
    )
    return entry_id, stamp_id


def provisional_stamp(parameter_id: uuid.UUID) -> ParameterStamp:
    return ParameterStamp(
        parameter_id=parameter_id,
        parameter_key=KEY,
        effective_date=POSTING,
        confidence="provisional",
        resolved_at=CALCULATED_AT,
    )


def confirm(seed: Callable[..., None], parameter_id: uuid.UUID) -> None:
    """What the tax service publishing looks like in the database.

    An UPDATE on the parameter plus a new history event -- which is exactly the
    shape ADR-046 describes, and exactly why the value alone forgets.
    """
    seed(
        "UPDATE fiscal_parameter SET source_confidence = 'confirmed',"
        " provisional_reason = NULL, updated_at = now() WHERE id = %s",
        [parameter_id],
    )
    seed(
        "INSERT INTO fiscal_parameter_confidence_event (id, parameter_id, confidence,"
        " provisional_reason, note, effective_at, recorded_at)"
        " VALUES (%s, %s, 'confirmed', NULL, 'nota anuala publicata', %s, now())",
        [uuid.uuid4(), parameter_id, PUBLISHED_AT],
    )


# --- the one that matters ----------------------------------------------------


def test_the_stamp_survives_the_parameter_being_confirmed(
    context: TenantContext,
    scene: dict[str, uuid.UUID],
    parameter: uuid.UUID,
    seed: Callable[..., None],
) -> None:
    """Confirmation moves the parameter and leaves the posting where it was.

    Without this table, the second half of this test would read ``confirmed`` --
    and an accountant asked at an inspection what January stood on would be told,
    by their own system, something that was not true in January.
    """
    with tenant_context(context):
        entry_id = post(scene, [provisional_stamp(parameter)])

    confirm(seed, parameter)

    with tenant_context(context):
        stamp = EntryParameterStamp.objects.get(journal_entry_id=entry_id)

    assert stamp.confidence == "provisional"
    assert stamp.parameter_id == parameter
    assert stamp.parameter_key == KEY
    assert stamp.resolved_at == CALCULATED_AT


def test_the_stamp_can_be_re_derived_from_the_history(
    context: TenantContext,
    scene: dict[str, uuid.UUID],
    parameter: uuid.UUID,
    seed: Callable[..., None],
) -> None:
    """Evidence rather than assertion, which is the difference `resolved_at` buys.

    A stamp nobody can check is a number the system wrote about itself. Because
    the instant is recorded, the confidence can be recomputed from ADR-046's
    history and shown to agree -- and the same call at *today's* instant gives
    the other answer, which is what makes the agreement mean something.
    """
    with tenant_context(context):
        entry_id = post(scene, [provisional_stamp(parameter)])

    confirm(seed, parameter)

    with tenant_context(context):
        stamp = EntryParameterStamp.objects.get(journal_entry_id=entry_id)
        assert confidence_at(stamp.parameter_id, stamp.resolved_at) == stamp.confidence
        assert confidence_at(stamp.parameter_id, PUBLISHED_AT) == "confirmed"


def test_the_provisional_postings_can_be_listed(
    context: TenantContext, scene: dict[str, uuid.UUID], parameter: uuid.UUID
) -> None:
    """The operational question the index exists for.

    The tax service published; what did we post on an inference and must now
    re-examine? A jsonb blob on the entry would hold the same facts and answer
    this with a sequential scan and a hand-written path expression.
    """
    with tenant_context(context):
        entry_id = post(scene, [provisional_stamp(parameter)])

        found = list(
            EntryParameterStamp.objects.filter(
                company_id=scene["company"], confidence="provisional"
            ).values_list("journal_entry_id", flat=True)
        )

    assert found == [entry_id]


# --- immutability ------------------------------------------------------------


def test_the_application_cannot_rewrite_a_stamp(
    context: TenantContext, scene: dict[str, uuid.UUID], parameter: uuid.UUID
) -> None:
    """No UPDATE and no DELETE privilege: the first refusal is a grant.

    Measured rather than assumed, and the measurement changed the migration: a
    narrow ``GRANT SELECT, INSERT`` does not *withdraw* anything, and the table
    arrived with all four privileges from the defaults every new table gets. The
    ``REVOKE`` in ``0043`` exists because the catalogue said so.
    """
    with tenant_context(context):
        post(scene, [provisional_stamp(parameter)])

        with pytest.raises(ProgrammingError, match="permission denied"), transaction.atomic():
            EntryParameterStamp.objects.update(confidence="confirmed")

        with pytest.raises(ProgrammingError, match="permission denied"), transaction.atomic():
            EntryParameterStamp.objects.all().delete()


def test_not_even_the_privileged_path_can_rewrite_a_stamp(
    seed: Callable[..., None], scene: dict[str, uuid.UUID], parameter: uuid.UUID
) -> None:
    """The trigger, which is what the revoked grant above cannot cover.

    The grant stops the application. It does not stop a migration, a data fix, or
    anything else running as owner -- and the migration that decides to "correct"
    a stamp is exactly the event this table exists to survive. Same discipline as
    the ledger, same reason (`R10`).

    Seeded rather than posted through the ORM, and that is not a shortcut: ORM
    rows live in the test transaction, so an UPDATE issued on another connection
    matches nothing and a FOR EACH ROW trigger never fires. A test written that
    way passes whether the trigger exists or not.
    """
    entry_id, stamp_id = seed_posted_entry(seed, scene, parameter)
    assert entry_id  # the chain is real; the FK below would have refused otherwise

    with pytest.raises(Exception) as excinfo:
        seed(
            "UPDATE entry_parameter_stamp SET confidence = 'confirmed' WHERE id = %s",
            [stamp_id],
        )
    assert "append-only" in str(excinfo.value)

    with pytest.raises(Exception) as excinfo:
        seed("DELETE FROM entry_parameter_stamp WHERE id = %s", [stamp_id])
    assert "append-only" in str(excinfo.value)


def test_the_same_parameter_cannot_be_stamped_twice_on_one_entry(
    context: TenantContext, scene: dict[str, uuid.UUID], parameter: uuid.UUID
) -> None:
    """Two answers for one parameter inside one calculation is a defect.

    Refused here rather than averaged, or silently kept as whichever row was
    written last.
    """
    stamp = provisional_stamp(parameter)
    confirmed = ParameterStamp(
        parameter_id=parameter,
        parameter_key=KEY,
        effective_date=POSTING,
        confidence="confirmed",
        resolved_at=CALCULATED_AT,
    )
    with tenant_context(context), pytest.raises(IntegrityError), transaction.atomic():
        post(scene, [stamp, confirmed])


def test_a_refused_stamp_takes_the_entry_with_it(
    context: TenantContext, scene: dict[str, uuid.UUID], parameter: uuid.UUID
) -> None:
    """Same transaction, demonstrated rather than declared.

    If the stamps could fail after the entry was written, the case this table
    exists for -- a posting whose basis nobody recorded -- would be reachable by
    accident, and reachable exactly on the entry that was hard to write.
    """
    stamp = provisional_stamp(parameter)
    with tenant_context(context):
        with pytest.raises(IntegrityError), transaction.atomic():
            post(scene, [stamp, stamp])

        assert not JournalEntry.objects.filter(entry_number="NC-0001").exists()


# --- isolation ---------------------------------------------------------------


def test_a_stamp_of_another_tenant_is_invisible(
    context: TenantContext,
    scene: dict[str, uuid.UUID],
    parameter: uuid.UUID,
    world: dict[str, uuid.UUID],
) -> None:
    """`R1` and `R4`, on a table that carries a company's fiscal reasoning."""
    with tenant_context(context):
        post(scene, [provisional_stamp(parameter)])

    other = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="stamp-b"
    )
    with tenant_context(other):
        assert EntryParameterStamp.objects.count() == 0
