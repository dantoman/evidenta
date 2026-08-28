"""The register of state-issued form ranges -- `art. 118²`, F1 module 2.

The property that matters is not that a number comes out. It is that **the same
number never comes out twice**, and that when the range is finished nothing
invents a continuation. Two fiscal invoices carrying one number is not a defect
an accountant repairs afterwards; it is a document that should not have been
issued.

**Under the application role, like every test in this suite** (`T1`).

No real series appears. Which forms are under the regime and what their series
look like is a nomenclature question -- data, and unverified data at that, since
HG 294/1998 has been amended twice since the sources at hand. The fixture uses a
form code no nomenclature contains.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest
from django.db import transaction
from django.db.utils import IntegrityError, ProgrammingError

from evidenta.platform.rls.context import TenantContext, tenant_context
from evidenta.platform.strictforms.models import (
    FormNumberState,
    StrictFormAllocation,
    StrictFormNumber,
)
from evidenta.platform.strictforms.services.register import (
    AllocationExhaustedError,
    AllocationMalformedError,
    NoAllocationError,
    consume_number,
    record_allocation,
    remaining,
    state_of,
    void_number,
)

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

#: Deliberately not a real form code. See the module docstring.
FORM = "FIXTURE-FACTURA"
SERIES = "FX"
ISSUED = date(2026, 1, 5)


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="forms")


@pytest.fixture
def scene(
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> dict[str, uuid.UUID]:
    tenant = world["tenant_a"]
    company = company_of(tenant, "1002600000901", "Alpha Formulare")
    grant_company(tenant, company, world["user_a"], world["user_a"])
    return {"tenant": tenant, "company": company, "user": world["user_a"]}


def allocate(
    scene: dict[str, uuid.UUID], *, first: int = 100, last: int = 104, series: str = SERIES
) -> StrictFormAllocation:
    return record_allocation(
        tenant_id=scene["tenant"],
        company_id=scene["company"],
        form_type_code=FORM,
        series=series,
        first_number=first,
        last_number=last,
        issued_on=ISSUED,
        source_reference="Recipisa SIA nr. FIXTURE-1",
        responsible_user_id=scene["user"],
    )


def take(scene: dict[str, uuid.UUID]) -> int:
    return consume_number(
        company_id=scene["company"],
        form_type_code=FORM,
        document_id=uuid.uuid4(),
        actor_user_id=scene["user"],
    ).number


# --- the range is consumed, not generated ------------------------------------


def test_numbers_come_out_in_order_and_only_once(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        allocate(scene, first=100, last=104)
        taken = [take(scene) for _ in range(5)]

    assert taken == [100, 101, 102, 103, 104]
    assert len(set(taken)) == 5


def test_a_finished_range_refuses_rather_than_continuing(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The refusal is the point.

    A counter would have carried on into 105, which the tax service never issued.
    The document that would have carried it is not a document.
    """
    with tenant_context(context):
        allocate(scene, first=100, last=101)
        take(scene)
        take(scene)

        with pytest.raises(AllocationExhaustedError) as excinfo:
            take(scene)

    assert excinfo.value.code == "strictforms.allocation_exhausted"


def test_a_company_with_no_range_cannot_post(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Nothing here invents a series. The order is an errand, not a computation."""
    with tenant_context(context), pytest.raises(NoAllocationError) as excinfo:
        take(scene)

    assert excinfo.value.code == "strictforms.no_allocation"


def test_the_older_range_is_finished_first(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Two ranges open at once is normal after a re-order.

    Consuming from the newer one would leave the older with a tail nobody ever
    uses -- and the register would have to account for numbers that were issued,
    never used and never voided.
    """
    with tenant_context(context):
        allocate(scene, first=100, last=101, series="FX-A")
        allocate(scene, first=500, last=501, series="FX-B")
        taken = [take(scene) for _ in range(3)]

    assert taken == [100, 101, 500]


# --- the register has to add up ----------------------------------------------


def test_issued_equals_consumed_plus_voided_plus_remaining(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The identity an inspection reconstructs, asserted as arithmetic.

    A spoiled blank that is not recorded breaks it silently: the numbers are gone
    and nothing says where.
    """
    with tenant_context(context):
        allocation = allocate(scene, first=100, last=109)
        take(scene)
        take(scene)
        void_number(
            company_id=scene["company"],
            form_type_code=FORM,
            state=FormNumberState.DAMAGED,
            actor_user_id=scene["user"],
            note="Deteriorat la imprimare",
        )
        left = remaining(scene["company"], FORM)
        gone = StrictFormNumber.objects.filter(allocation_id=allocation.id).count()

    issued = allocation.last_number - allocation.first_number + 1
    assert gone == 3
    assert left == 7
    assert gone + left == issued


def test_a_cancelled_number_is_a_state_not_an_absence(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """What the regulation asks the register to be able to answer.

    `allocated` is derived -- in range, not yet handed out. Everything else was
    written down at the moment the number left.
    """
    with tenant_context(context):
        allocation = allocate(scene, first=100, last=102)
        take(scene)
        void_number(
            company_id=scene["company"],
            form_type_code=FORM,
            state=FormNumberState.CANCELLED,
            actor_user_id=scene["user"],
            note="Anulat inainte de emitere",
        )

        assert state_of(allocation.id, 100) == "consumed"
        assert state_of(allocation.id, 101) == "cancelled"
        assert state_of(allocation.id, 102) == "allocated"


def test_voiding_without_a_reason_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The only part of the register a reader cannot reconstruct from the numbers."""
    with tenant_context(context):
        allocate(scene)
        with pytest.raises(AllocationMalformedError):
            void_number(
                company_id=scene["company"],
                form_type_code=FORM,
                state=FormNumberState.CANCELLED,
                actor_user_id=scene["user"],
                note="   ",
            )


# --- what cannot be rewritten -------------------------------------------------


def test_a_recorded_number_cannot_be_rewritten_by_the_application(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """No UPDATE and no DELETE: a number leaves the range once."""
    with tenant_context(context):
        allocate(scene)
        take(scene)

        with pytest.raises(ProgrammingError, match="permission denied"), transaction.atomic():
            StrictFormNumber.objects.update(state=FormNumberState.CANCELLED)

        with pytest.raises(ProgrammingError, match="permission denied"), transaction.atomic():
            StrictFormNumber.objects.all().delete()


def test_the_same_number_cannot_be_recorded_twice(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Belt and braces on the cursor: the constraint is the authority.

    The cursor is what keeps numbers unique in practice. This asserts the
    database would refuse a duplicate anyway -- because the cursor is a value in
    a row, and a value can be wrong.
    """
    with tenant_context(context):
        allocation = allocate(scene)
        take(scene)

        with pytest.raises(IntegrityError), transaction.atomic():
            StrictFormNumber.objects.create(
                tenant_id=scene["tenant"],
                company_id=scene["company"],
                allocation=allocation,
                number=allocation.first_number,
                state=FormNumberState.CANCELLED,
                occurred_at=datetime.now(UTC),
                recorded_by_user_id=scene["user"],
                note="duplicat",
            )


def test_a_consumed_number_must_name_its_document(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """A number reported as used with nothing to show for it is the gap.

    Enforced in the database rather than by the service, because the importer and
    any data migration will write these rows too.
    """
    with tenant_context(context):
        allocation = allocate(scene)

        with pytest.raises(IntegrityError), transaction.atomic():
            StrictFormNumber.objects.create(
                tenant_id=scene["tenant"],
                company_id=scene["company"],
                allocation=allocation,
                number=allocation.first_number,
                state=FormNumberState.CONSUMED,
                document_id=None,
                occurred_at=datetime.now(UTC),
                recorded_by_user_id=scene["user"],
            )


def test_a_range_that_ends_before_it_starts_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context), pytest.raises(AllocationMalformedError):
        allocate(scene, first=200, last=100)


def test_a_range_without_provenance_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """A range with no order behind it cannot be told from one somebody typed."""
    with tenant_context(context), pytest.raises(AllocationMalformedError):
        record_allocation(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            form_type_code=FORM,
            series=SERIES,
            first_number=1,
            last_number=10,
            issued_on=ISSUED,
            source_reference="  ",
            responsible_user_id=scene["user"],
        )


# --- isolation ----------------------------------------------------------------


def test_another_tenant_sees_no_ranges(
    context: TenantContext, scene: dict[str, uuid.UUID], world: dict[str, uuid.UUID]
) -> None:
    """`R1` and `R4` on a register that carries a company's fiscal blanks."""
    with tenant_context(context):
        allocate(scene)
        take(scene)

    other = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="forms-b"
    )
    with tenant_context(other):
        assert StrictFormAllocation.objects.count() == 0
        assert StrictFormNumber.objects.count() == 0


def test_the_privileged_path_cannot_rewrite_a_recorded_number(
    seed: Callable[..., None], scene: dict[str, uuid.UUID]
) -> None:
    """The trigger, which the revoked grant cannot cover.

    A migration or a data fix runs as owner, and the migration that decides to
    tidy away a cancelled blank is the one this stops. Seeded rather than written
    through the ORM: ORM rows live in the test transaction, so an UPDATE from
    another connection matches nothing and a FOR EACH ROW trigger never fires --
    a test written that way passes with the trigger and without it.
    """
    allocation_id, number_id = uuid.uuid4(), uuid.uuid4()
    seed(
        "INSERT INTO strict_form_allocation (id, tenant_id, company_id, form_type_code,"
        " series, first_number, last_number, next_number, issued_on, source_reference,"
        " responsible_user_id, is_active, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, %s, 100, 104, 101, %s, 'Recipisa fixture', %s, true,"
        " now(), now())",
        [allocation_id, scene["tenant"], scene["company"], FORM, SERIES, ISSUED, scene["user"]],
    )
    seed(
        "INSERT INTO strict_form_number (id, tenant_id, company_id, allocation_id, number,"
        " state, document_id, occurred_at, recorded_by_user_id, created_at)"
        " VALUES (%s, %s, %s, %s, 100, 'consumed', %s, now(), %s, now())",
        [number_id, scene["tenant"], scene["company"], allocation_id, uuid.uuid4(), scene["user"]],
    )

    with pytest.raises(Exception) as excinfo:
        seed("UPDATE strict_form_number SET state = 'cancelled' WHERE id = %s", [number_id])
    assert "append-only" in str(excinfo.value)

    with pytest.raises(Exception) as excinfo:
        seed("DELETE FROM strict_form_number WHERE id = %s", [number_id])
    assert "append-only" in str(excinfo.value)
