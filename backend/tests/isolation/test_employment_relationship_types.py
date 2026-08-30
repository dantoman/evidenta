"""The vocabulary of work relationship types -- ADR-071, `C1(b)`.

Four claims, and only the first is about tenancy in the ordinary sense.

1. **Every tenant reads the same three rows.** Not an isolation hole -- the
   opposite. The distinction is drawn by point 1.1 of annex 1 to Law 489/1999,
   the same for everyone inside one jurisdiction; a per-tenant vocabulary would
   let two installations disagree about what a work relationship *is*.
2. **No tenant can write it.** The default privileges in `0001_roles.sql` grant
   INSERT on every owner-created table, so a global table left with only a SELECT
   policy would be read-only by omission. The migration revokes explicitly.
3. **The set is closed in the database, not in prose.** A fourth code is a CHECK
   violation. `general`, `altul`, `orice` are the road by which "invariant applied
   blindly" comes back under another name (ADR-071 section 2), and a vocabulary
   that only documents its own closure is not closed.
4. **The seeding actually happened, and it wrote what it said it would.** The
   migration ran through `backfill()` with `expected=0`; this asserts the state
   it left, which is the fact that matters (`OD-98`).

Under the application role throughout (`T1`).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

import pytest
from django.db import transaction
from django.db.utils import IntegrityError, ProgrammingError

from evidenta.fiscal.registry.models import EmploymentRelationshipType
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

#: The three the act distinguishes. Repeated here rather than imported from the
#: model: a test that reads the same constant as the code under test agrees with
#: itself by construction, which is the shape `P1` was measured to have.
EXPECTED = {"employment_contract", "service_relationship", "civil_contract"}


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(
        tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="relationship-types"
    )


def test_the_migration_seeded_exactly_the_three_forms(context: TenantContext) -> None:
    """The state the seeding left, asserted rather than assumed.

    Point 1.1's first indent names three forms in one clause. An earlier reading
    of the same sentence found two -- the service relationship under an
    administrative act was the one that fell out -- so the count is part of the
    assertion, not an incidental detail of it.
    """
    with tenant_context(context):
        codes = set(EmploymentRelationshipType.objects.values_list("code", flat=True))

    assert codes == EXPECTED


def test_every_row_carries_the_anchor_it_was_seeded_with(context: TenantContext) -> None:
    """A type whose citation lives one document away is a value somebody typed."""
    with tenant_context(context):
        rows = list(EmploymentRelationshipType.objects.all())

    assert rows, "the vocabulary is empty; every other assertion here would pass vacuously"
    for row in rows:
        assert "Legea nr. 489/1999" in row.statutory_reference, row.code
        assert "pct. 1.1" in row.statutory_reference, row.code


def test_every_tenant_reads_the_same_vocabulary(world: dict[str, uuid.UUID]) -> None:
    """One jurisdiction, one vocabulary. A second tenant sees the same rows."""
    seen = []
    for tenant, user in (
        (world["tenant_a"], world["user_a"]),
        (world["tenant_b"], world["user_b"]),
    ):
        ctx = TenantContext(tenant_id=tenant, user_id=user, request_id="relationship-types")
        with tenant_context(ctx):
            seen.append(set(EmploymentRelationshipType.objects.values_list("code", flat=True)))

    assert seen[0] == seen[1] == EXPECTED


def test_a_tenant_cannot_add_a_type(context: TenantContext) -> None:
    """The revoke, not the missing policy, is what stops this (`OD-47`)."""
    with (
        tenant_context(context),
        pytest.raises((ProgrammingError, IntegrityError)),
        transaction.atomic(),
    ):
        EmploymentRelationshipType.objects.create(
            code="employer_convenience",
            statutory_reference="inventat de un tenant",
        )


def test_a_tenant_cannot_rewrite_or_delete_a_type(context: TenantContext) -> None:
    """A repealed type stays; a renamed one would silently re-point every key.

    Both are refused by **privilege**, loudly -- not by a policy that would match
    no rows and report zero changed. The difference matters at the call site: a
    silent zero reads as "there was nothing to update".
    """
    with tenant_context(context):
        with pytest.raises(ProgrammingError), transaction.atomic():
            EmploymentRelationshipType.objects.filter(code="civil_contract").update(
                statutory_reference="rescris"
            )

        with pytest.raises(ProgrammingError), transaction.atomic():
            EmploymentRelationshipType.objects.filter(code="civil_contract").delete()

        assert EmploymentRelationshipType.objects.filter(code="civil_contract").exists()


def test_the_set_is_closed_by_the_database(
    seed: Callable[..., None], context: TenantContext
) -> None:
    """A fourth code is refused where it is written, not where it is read.

    Seeded through the owner, which is the only role that may write here -- so
    this measures the CHECK rather than the revoke. Without it, `general` would
    be an accepted value and the residue would go back from "chose the wrong one
    of three real types" to "chose nothing", which is the one that leaves no
    trace (ADR-070 section 4).
    """
    with pytest.raises(Exception) as refused:
        seed(
            "INSERT INTO employment_relationship_type (code, statutory_reference) "
            "VALUES ('general', 'nimic')"
        )

    assert "employment_relationship_type_vocabulary_closed" in str(refused.value)
