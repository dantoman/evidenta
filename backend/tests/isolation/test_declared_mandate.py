"""A declared mandate is an ordinary active engagement -- ADR-081 section 3.3.

The claim this file exists to keep true is a **negative** one: the second access
path of ``rls.has_tenant_access`` was not touched, because an engagement the firm
declared produces the same ``status = 'active'`` row as one the client accepted.
Nothing about a negative claim shows up in a feature test, so it is measured from
two sides -- the access the two bases actually grant, compared to each other, and
the text of the predicate, read.

The rest of the file is the schema saying what it will not hold: an acceptance
without a basis, a basis outside the vocabulary, a declared mandate without the
contact that makes it claimable.

Everything runs under the application role (`T1`).
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime
from typing import Any, NamedTuple

import pytest
from django.db import connection, transaction
from django.db.utils import IntegrityError

from evidenta.platform.engagement.models import AcceptanceBasis, Engagement, EngagementStatus
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


def acting_for_firm(tenant_id: uuid.UUID, user_id: uuid.UUID, firm_id: uuid.UUID) -> TenantContext:
    return TenantContext(
        tenant_id=tenant_id, user_id=user_id, request_id="test", actor_firm_id=firm_id
    )


class Reach(NamedTuple):
    """How far a context sees: its own tenant row, and its tenant-scoped rows.

    Two numbers rather than one, because the tenant row alone would pass on a
    predicate that granted the root and nothing under it.
    """

    tenants: int
    tenant_scoped_rows: int


def reach() -> Reach:
    with connection.cursor() as cursor:
        cursor.execute("SELECT (SELECT count(*) FROM tenant), (SELECT count(*) FROM role)")
        row = cursor.fetchone()
    return Reach(tenants=row[0], tenant_scoped_rows=row[1])


def declare(
    firm_id: uuid.UUID,
    client_tenant_id: uuid.UUID,
    invited_by: uuid.UUID,
    **overrides: Any,
) -> Engagement:
    """Write an engagement through the ORM, under whatever context is open.

    The fixtures seed on the admin connection, which proves nothing about what
    the application role may write. These cases are about the checks, so the row
    goes in the way production puts it in.
    """
    fields: dict[str, Any] = {
        "firm_id": firm_id,
        "client_tenant_id": client_tenant_id,
        "status": EngagementStatus.ACTIVE,
        "covers_all_companies": True,
        "valid_from": date(2020, 1, 1),
        "initiated_by": "firm",
        "invited_by_id": invited_by,
        "invited_at": datetime.now(UTC),
        "accepted_at": datetime.now(UTC),
        "acceptance_basis": AcceptanceBasis.DECLARED_MANDATE,
        "claim_contact_email": "revendicare@example.md",
    }
    fields.update(overrides)
    return Engagement.objects.create(**fields)


def test_a_declared_mandate_reaches_exactly_what_a_client_acceptance_reaches(
    firm_world: dict[str, uuid.UUID], engage: Callable[..., uuid.UUID]
) -> None:
    """IZ-79. The property ADR-081 section 3.3 rests on, measured on both sides.

    One firm, two clients, one basis each -- and the ``world`` fixture is
    deliberately symmetric, so whatever the firm reaches in one it must reach in
    the other. Parametrising instead would compare each run against a constant
    this test wrote itself; comparing the two runs to each other cannot be
    satisfied by a predicate that is equally wrong in both.
    """
    engage(
        firm_world["firm"],
        firm_world["tenant_a"],
        firm_world["user_f"],
        acceptance_basis="client",
    )
    engage(
        firm_world["firm"],
        firm_world["tenant_b"],
        firm_world["user_f"],
        acceptance_basis="declared_mandate",
    )

    with tenant_context(
        acting_for_firm(firm_world["tenant_a"], firm_world["user_f"], firm_world["firm"])
    ):
        by_client_acceptance = reach()

    with tenant_context(
        acting_for_firm(firm_world["tenant_b"], firm_world["user_f"], firm_world["firm"])
    ):
        by_declared_mandate = reach()

    assert by_declared_mandate == by_client_acceptance
    # Equal, and equal to something: two empty answers are also equal, and a test
    # that passes when nothing is visible proves nothing (ADR-070 section 1).
    assert by_declared_mandate.tenants == 1
    assert by_declared_mandate.tenant_scoped_rows > 0


def test_the_access_predicate_never_reads_the_basis(
    firm_world: dict[str, uuid.UUID],
) -> None:
    """The other half of IZ-79, read rather than inferred.

    The test above would still pass if somebody taught the predicate about both
    bases symmetrically -- equal access, new branch, and the property ADR-081 was
    bought with quietly gone. This reads the function the database actually holds.

    Inside a context like any other query: the guard refuses a bare connection
    (`R3`), and reading the catalogue is not a reason to make an exception.

    If this fails, the change is not necessarily wrong; it means the reasoning in
    section 3.3 no longer describes the system, and the ADR is where that gets
    settled.
    """
    with (
        tenant_context(
            acting_for_firm(firm_world["firm_tenant"], firm_world["user_f"], firm_world["firm"])
        ),
        connection.cursor() as cursor,
    ):
        cursor.execute("SELECT pg_get_functiondef('rls.has_tenant_access(uuid)'::regprocedure)")
        definition = cursor.fetchone()[0]

    # Whitespace collapsed: the layout of the SQL file is frozen by `C31` anyway,
    # and pinning it here would turn a reformatted correction file into a failure
    # about nothing.
    normalised = " ".join(definition.split())

    assert "acceptance_basis" not in normalised
    # And it is the right function: a predicate that had stopped reading
    # `engagement` altogether would also contain no basis, and would satisfy a
    # test that only looked for an absence.
    assert "FROM engagement e" in normalised
    assert "e.status = 'active'" in normalised


def test_an_acceptance_without_a_basis_is_refused(firm_world: dict[str, uuid.UUID]) -> None:
    """Accepted on whose word? A row that cannot answer is not written."""
    with (
        tenant_context(
            acting_for_firm(firm_world["firm_tenant"], firm_world["user_f"], firm_world["firm"])
        ),
        pytest.raises(IntegrityError, match="engagement_acceptance_states_its_basis"),
        transaction.atomic(),
    ):
        declare(
            firm_world["firm"],
            firm_world["tenant_b"],
            firm_world["user_f"],
            acceptance_basis=None,
            claim_contact_email=None,
        )


def test_a_basis_outside_the_vocabulary_is_refused(firm_world: dict[str, uuid.UUID]) -> None:
    """Two bases, enumerated in one place. A third is a typo, not a new kind."""
    with (
        tenant_context(
            acting_for_firm(firm_world["firm_tenant"], firm_world["user_f"], firm_world["firm"])
        ),
        pytest.raises(IntegrityError, match="engagement_acceptance_basis_valid"),
        transaction.atomic(),
    ):
        declare(
            firm_world["firm"],
            firm_world["tenant_b"],
            firm_world["user_f"],
            acceptance_basis="verbal",
        )


def test_a_declared_mandate_without_a_claim_contact_is_refused(
    firm_world: dict[str, uuid.UUID],
) -> None:
    """ADR-081 section 3.5: unverified, and mandatory anyway.

    The contact is the only channel INV-7 has towards a client who never signs
    in. Optional here, it would be absent on exactly the rows where somebody
    later needs it.
    """
    with (
        tenant_context(
            acting_for_firm(firm_world["firm_tenant"], firm_world["user_f"], firm_world["firm"])
        ),
        pytest.raises(IntegrityError, match="engagement_declared_mandate_has_claim_contact"),
        transaction.atomic(),
    ):
        declare(
            firm_world["firm"],
            firm_world["tenant_b"],
            firm_world["user_f"],
            claim_contact_email=None,
        )


def test_a_client_acceptance_needs_no_claim_contact(firm_world: dict[str, uuid.UUID]) -> None:
    """The check binds to the declared mandate, not to acceptance in general.

    A client who accepted is already in the product; there is nobody to invite.
    """
    with tenant_context(
        acting_for_firm(firm_world["firm_tenant"], firm_world["user_f"], firm_world["firm"])
    ):
        engagement = declare(
            firm_world["firm"],
            firm_world["tenant_b"],
            firm_world["user_f"],
            acceptance_basis=AcceptanceBasis.CLIENT,
            claim_contact_email=None,
        )

    assert engagement.acceptance_basis == AcceptanceBasis.CLIENT


def test_the_application_role_writes_a_declared_mandate(
    firm_world: dict[str, uuid.UUID],
) -> None:
    """The positive case, under the role that will actually write it.

    Not obvious from the refusals above: each of those could equally have been a
    policy refusing the insert, and the whole file would still look green.
    """
    with tenant_context(
        acting_for_firm(firm_world["firm_tenant"], firm_world["user_f"], firm_world["firm"])
    ):
        engagement = declare(
            firm_world["firm"],
            firm_world["tenant_b"],
            firm_world["user_f"],
            mandate_ref="CD-2026-118",
        )

        stored = Engagement.objects.get(pk=engagement.pk)
        assert stored.acceptance_basis == AcceptanceBasis.DECLARED_MANDATE
        assert stored.mandate_ref == "CD-2026-118"
        assert stored.status == EngagementStatus.ACTIVE
