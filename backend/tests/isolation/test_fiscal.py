"""Fiscal parameters and the registry -- R15, R17, R18.

Two claims are under test, and neither is about tenancy in the usual sense.

The first: **selection follows the date of the period being calculated.** Every
test here resolves a past date and expects the past answer. A resolver that fell
back to "today" would pass no test in this file, which is the point of writing
them before any rate exists.

The second: **a tenant cannot write what applies to everyone.** The tables are
global and readable by all; writing goes through the privileged path. A tenant
able to insert a VAT rate would be able to change what the law says for every
other tenant in the installation.

**No test here contains a real rate, threshold or deadline.** The values are
obvious nonsense on purpose -- `test.rate.alpha`, 1 and 2 -- because a plausible
number in a test file is the first place someone copies a rate from, and `OD-22`
is not closed. What is under test is the mechanism, and the mechanism does not
care what the number is.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import date

import pytest
from django.db import transaction
from django.db.utils import IntegrityError, ProgrammingError

from evidenta.fiscal.parameters.models import (
    FiscalParameter,
    FiscalParameterSource,
    ParameterScope,
    ParameterStatus,
    SourceConfidence,
    ValueType,
)
from evidenta.fiscal.parameters.services.resolution import (
    FiscalResolutionError,
    provisional_in_force,
    resolve_parameter,
)
from evidenta.fiscal.registry.models import FiscalLogicVersion, LogicStatus
from evidenta.fiscal.registry.services.resolution import resolve_logic
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

SOURCE_ID = uuid.UUID("00000000-0000-0000-0000-0000000000a1")
APPROVER = uuid.UUID("00000000-0000-0000-0000-0000000000b1")


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="fiscal")


@pytest.fixture
def source(seed: Callable[..., None]) -> uuid.UUID:
    """One normative act, seeded through the privileged path.

    Fictitious on purpose: no act number in this repository should be mistakable
    for a real one -- which is why the date is fictitious too. An act is cited by
    number *and* date, so a test act carrying a real date would be half-citable.
    """
    seed(
        """
        INSERT INTO fiscal_parameter_source
            (id, act_type, act_number, act_date, official_gazette_number,
             official_gazette_article, published_at, effective_from, created_at)
        VALUES (%s, 'test', 'TEST-0/0000', DATE '2000-01-01', 'TEST 0',
                'art. 0', DATE '2000-01-01', DATE '2000-01-01', now())
        """,
        [SOURCE_ID],
    )
    return SOURCE_ID


def _param(
    seed: Callable[..., None],
    key: str,
    value: int,
    valid_from: str,
    valid_to: str | None = None,
    *,
    status: str = ParameterStatus.ACTIVE,
    scope: str = ParameterScope.GLOBAL,
    scope_ref: uuid.UUID | None = None,
    confidence: str = SourceConfidence.CONFIRMED,
    provisional_reason: str | None = None,
) -> None:
    # Confidence is spelled out rather than left to the column default, and the
    # default here is the opposite of the column's on purpose: a test about
    # something else should not have to think about it, while a row reaching the
    # table for real should have to.
    if confidence == SourceConfidence.PROVISIONAL and provisional_reason is None:
        provisional_reason = "test: inferred, reason supplied so the check passes"
    seed(
        """
        INSERT INTO fiscal_parameter
            (id, parameter_key, scope, scope_ref, value_type, value, valid_from,
             valid_to, source_id, status, approved_by_user_id, approved_at,
             source_confidence, provisional_reason, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, now(), %s, %s,
                now(), now())
        """,
        [
            uuid.uuid4(),
            key,
            scope,
            scope_ref,
            ValueType.INTEGER,
            str(value),
            valid_from,
            valid_to,
            SOURCE_ID,
            status,
            APPROVER if status == ParameterStatus.ACTIVE else None,
            confidence,
            provisional_reason,
        ],
    )


def _logic(
    seed: Callable[..., None],
    key: str,
    version: str,
    valid_from: str,
    valid_to: str | None = None,
) -> None:
    seed(
        """
        INSERT INTO fiscal_logic_version
            (id, logic_key, implementation_ref, version, valid_from, valid_to,
             source_id, regression_case_set, status, approved_by_user_id,
             approved_at, created_at, updated_at)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now(), now(), now())
        """,
        [
            uuid.uuid4(),
            key,
            f"tests.fixtures.{key}.{version}",
            version,
            valid_from,
            valid_to,
            SOURCE_ID,
            f"corpus/{key}/{version}",
            LogicStatus.ACTIVE,
            APPROVER,
        ],
    )


# --- Selection follows the period, not the clock -----------------------------


def test_resolves_the_value_in_force_on_the_given_date(
    seed: Callable[..., None], source: uuid.UUID, context: TenantContext
) -> None:
    """Two successive versions; each date gets its own.

    This is R18 in one assertion. The later value exists, is active, and is not
    returned -- because the question was about a date it does not cover.
    """
    _param(seed, "test.rate.alpha", 1, "2020-01-01", "2024-01-01")
    _param(seed, "test.rate.alpha", 2, "2024-01-01")

    with tenant_context(context):
        assert resolve_parameter("test.rate.alpha", date(2022, 6, 30)).value == 1
        assert resolve_parameter("test.rate.alpha", date(2024, 1, 1)).value == 2


def test_the_boundary_day_belongs_to_the_new_value(
    seed: Callable[..., None], source: uuid.UUID, context: TenantContext
) -> None:
    """`[from, to)` -- the last day of the old window is the day before the new one.

    An off-by-one here is wrong on exactly one day a year. That is a defect found
    by a client at year end, not by a developer, so it gets its own test rather
    than being left to the reader of the query.
    """
    _param(seed, "test.rate.beta", 1, "2020-01-01", "2024-01-01")
    _param(seed, "test.rate.beta", 2, "2024-01-01")

    with tenant_context(context):
        assert resolve_parameter("test.rate.beta", date(2023, 12, 31)).value == 1
        assert resolve_parameter("test.rate.beta", date(2024, 1, 1)).value == 2


def test_a_draft_for_next_year_does_not_apply(
    seed: Callable[..., None], source: uuid.UUID, context: TenantContext
) -> None:
    """Preparing a change is not making it.

    A rate voted in November for January has to be enterable in November. If a
    draft resolved, every recalculation between the two dates would quietly use a
    value that was not law yet.
    """
    _param(seed, "test.rate.gamma", 1, "2020-01-01")
    _param(seed, "test.rate.gamma", 2, "2026-01-01", status=ParameterStatus.DRAFT)

    with tenant_context(context):
        assert resolve_parameter("test.rate.gamma", date(2026, 6, 1)).value == 1


def test_a_scoped_value_wins_over_the_global_one(
    seed: Callable[..., None], source: uuid.UUID, context: TenantContext
) -> None:
    other = uuid.uuid4()
    _param(seed, "test.rate.delta", 1, "2020-01-01")
    _param(
        seed,
        "test.rate.delta",
        2,
        "2020-01-01",
        scope=ParameterScope.COMPANY,
        scope_ref=other,
    )

    with tenant_context(context):
        assert resolve_parameter("test.rate.delta", date(2022, 1, 1)).value == 1
        assert resolve_parameter("test.rate.delta", date(2022, 1, 1), scope_ref=other).value == 2


# --- Zero and two are errors, never a choice ---------------------------------


def test_a_missing_parameter_is_an_error_not_a_zero(
    seed: Callable[..., None], source: uuid.UUID, context: TenantContext
) -> None:
    """The single most valuable assertion in this file.

    A resolver returning 0, or None, for an unconfigured rate produces a posting
    with no tax on it. That posts, balances, and passes every other check in the
    system.
    """
    _param(seed, "test.rate.epsilon", 1, "2024-01-01")

    with tenant_context(context), pytest.raises(FiscalResolutionError) as excinfo:
        resolve_parameter("test.rate.epsilon", date(2020, 1, 1))
    assert excinfo.value.code == "fiscal.no_parameter"


def test_a_missing_implementation_is_an_error(
    seed: Callable[..., None], source: uuid.UUID, context: TenantContext
) -> None:
    _logic(seed, "test.logic.alpha", "v1", "2024-01-01")

    with tenant_context(context), pytest.raises(FiscalResolutionError) as excinfo:
        resolve_logic("test.logic.alpha", date(2020, 1, 1))
    assert excinfo.value.code == "fiscal.no_logic"


def test_the_registry_returns_the_implementation_of_the_period(
    seed: Callable[..., None], source: uuid.UUID, context: TenantContext
) -> None:
    """R17 whole: recalculating an old period reaches the old code.

    Both versions are active. Neither is 'current'. The date decides, which is
    exactly what makes `if year >= X` unnecessary in business code.
    """
    _logic(seed, "test.logic.beta", "v1", "2020-01-01", "2024-01-01")
    _logic(seed, "test.logic.beta", "v2", "2024-01-01")

    with tenant_context(context):
        assert resolve_logic("test.logic.beta", date(2021, 3, 1)).version == "v1"
        assert resolve_logic("test.logic.beta", date(2025, 3, 1)).version == "v2"


# --- The database refuses ambiguity before the resolver has to ---------------


def test_two_overlapping_active_values_are_refused_at_insert(
    seed: Callable[..., None], source: uuid.UUID
) -> None:
    """The resolver refuses two matches; the database refuses to hold them.

    Both belong. A refusal at calculation time means the misconfiguration reached
    a user closing a month, who cannot fix it. A refusal at insert reaches the
    person who typed it, while they still have the act in front of them.
    """
    _param(seed, "test.rate.zeta", 1, "2020-01-01", "2024-01-01")

    with pytest.raises(Exception) as excinfo:
        _param(seed, "test.rate.zeta", 2, "2023-01-01", "2025-01-01")
    assert "fiscal_parameter_no_overlap" in str(excinfo.value)


def test_overlap_is_detected_between_two_global_values(
    seed: Callable[..., None], source: uuid.UUID
) -> None:
    """The NULL trap, tested because it is invisible in the constraint's shape.

    Both rows are global, so both have `scope_ref` NULL, and `NULL = NULL` is
    unknown -- an EXCLUDE on the bare column would never fire in the most common
    case of all. `COALESCE` to a fixed uuid is what makes this fail.
    """
    _param(seed, "test.rate.eta", 1, "2020-01-01")

    with pytest.raises(Exception) as excinfo:
        _param(seed, "test.rate.eta", 2, "2022-01-01")
    assert "fiscal_parameter_no_overlap" in str(excinfo.value)


def test_a_draft_may_overlap_an_active_value(seed: Callable[..., None], source: uuid.UUID) -> None:
    """The constraint is partial for a reason, and the reason is operational.

    Entering next year's rate before it takes effect necessarily overlaps nothing
    -- but entering a *correction* to the current one, as a draft, does. Blocking
    that would push the preparation of every change outside the system.
    """
    _param(seed, "test.rate.theta", 1, "2020-01-01")
    _param(seed, "test.rate.theta", 2, "2020-01-01", status=ParameterStatus.DRAFT)


def test_active_without_an_approver_is_refused(
    seed: Callable[..., None], source: uuid.UUID
) -> None:
    """Amendment D.1 as a constraint rather than a step someone remembers."""
    with pytest.raises(Exception) as excinfo:
        seed(
            """
            INSERT INTO fiscal_parameter
                (id, parameter_key, scope, value_type, value, valid_from,
                 source_id, status, source_confidence, created_at, updated_at)
            VALUES (%s, 'test.rate.iota', 'global', 'integer', '1'::jsonb,
                    DATE '2020-01-01', %s, 'active', 'confirmed', now(), now())
            """,
            [uuid.uuid4(), SOURCE_ID],
        )
    assert "fiscal_parameter_active_requires_approval" in str(excinfo.value)


def test_a_parameter_cannot_exist_without_a_source(
    seed: Callable[..., None], source: uuid.UUID
) -> None:
    """R15's provenance requirement, enforced rather than reviewed.

    A rate without a source is a number somebody typed. Three years later, when
    the recalculation has to be defended, "it was 20%" is not an answer without
    "under which act, published when".
    """
    with pytest.raises(Exception) as excinfo:
        seed(
            """
            INSERT INTO fiscal_parameter
                (id, parameter_key, scope, value_type, value, valid_from,
                 status, created_at, updated_at)
            VALUES (%s, 'test.rate.kappa', 'global', 'integer', '1'::jsonb,
                    DATE '2020-01-01', 'draft', now(), now())
            """,
            [uuid.uuid4()],
        )
    assert "source_id" in str(excinfo.value)


def test_a_logic_version_cannot_go_active_without_a_regression_set(
    seed: Callable[..., None], source: uuid.UUID
) -> None:
    """Amendment D.2. An algorithm change with no regression case is how a rate
    change for 2027 silently breaks the recalculation of 2025 -- and that is
    discovered at a client, months later.
    """
    with pytest.raises(Exception) as excinfo:
        seed(
            """
            INSERT INTO fiscal_logic_version
                (id, logic_key, implementation_ref, version, valid_from,
                 regression_case_set, status, approved_by_user_id, approved_at,
                 created_at, updated_at)
            VALUES (%s, 'test.logic.gamma', 'x.y', 'v1', DATE '2020-01-01',
                    NULL, 'active', %s, now(), now(), now())
            """,
            [uuid.uuid4(), APPROVER],
        )
    assert "regression_case_set" in str(excinfo.value)


# --- Global, readable by all, writable by none through the ordinary path -----


def test_every_tenant_reads_the_same_parameters(
    seed: Callable[..., None],
    source: uuid.UUID,
    world: dict[str, uuid.UUID],
) -> None:
    """Not an isolation hole -- the opposite.

    If a parameter were tenant-scoped, two tenants could compute the same period
    differently and both be right by their own database. The law is one law, so
    the row is one row.
    """
    _param(seed, "test.rate.lambda", 1, "2020-01-01")

    for tenant, user in (
        (world["tenant_a"], world["user_a"]),
        (world["tenant_b"], world["user_b"]),
    ):
        ctx = TenantContext(tenant_id=tenant, user_id=user, request_id="fiscal")
        with tenant_context(ctx):
            assert resolve_parameter("test.rate.lambda", date(2022, 1, 1)).value == 1


def test_a_tenant_cannot_write_a_fiscal_parameter(
    seed: Callable[..., None], source: uuid.UUID, context: TenantContext
) -> None:
    """The privilege, not the policy, is what stops this.

    Default privileges in `0001_roles.sql` grant INSERT on every owner-created
    table, so a global table left with only a SELECT policy would be held
    read-only by an *omission*. The migration revokes explicitly; this asserts the
    revoke is there (OD-47).
    """
    with (
        tenant_context(context),
        pytest.raises((ProgrammingError, IntegrityError)),
        transaction.atomic(),
    ):
        FiscalParameter.objects.create(
            parameter_key="test.rate.mu",
            value_type=ValueType.INTEGER,
            value=1,
            valid_from=date(2020, 1, 1),
            source_id=SOURCE_ID,
        )


def test_a_tenant_cannot_write_a_source_or_a_logic_version(
    seed: Callable[..., None], source: uuid.UUID, context: TenantContext
) -> None:
    """Writing the source would be enough on its own.

    A tenant able to insert an act could give a fabricated rate a provenance that
    looks exactly like a real one -- which is worse than an unsourced rate,
    because it survives review.
    """
    with tenant_context(context):
        with pytest.raises((ProgrammingError, IntegrityError)), transaction.atomic():
            FiscalParameterSource.objects.create(
                act_type="test", act_number="X", effective_from=date(2020, 1, 1)
            )
        with pytest.raises((ProgrammingError, IntegrityError)), transaction.atomic():
            FiscalLogicVersion.objects.create(
                logic_key="test.logic.delta",
                implementation_ref="x.y",
                version="v1",
                valid_from=date(2020, 1, 1),
                regression_case_set="corpus/x",
            )


def test_resolution_requires_a_context(seed: Callable[..., None], source: uuid.UUID) -> None:
    """Global does not mean unguarded.

    The tables carry no `tenant_id`, so nothing about *them* needs a context. The
    query guard still refuses, and that is deliberate: a code path that can reach
    the database without a context is a code path that will be copied to a table
    that does need one.
    """
    _param(seed, "test.rate.nu", 1, "2020-01-01")

    with pytest.raises(RuntimeError):
        resolve_parameter("test.rate.nu", date(2022, 1, 1))


# --- Confirmed or inferred, and the difference has to survive ------------------


def test_a_provisional_value_resolves_and_says_so(
    seed: Callable[..., None], source: uuid.UUID, context: TenantContext
) -> None:
    """An inferred value is usable. That is the whole point of the column.

    Refusing to resolve it would be worse than the problem: the 2026 exemptions
    have to be calculated with long before the tax service publishes them. What
    must not happen is calculating with them while believing they were read in
    the act.
    """
    _param(
        seed,
        "test.rate.inferred",
        29_700,
        "2026-01-01",
        confidence=SourceConfidence.PROVISIONAL,
        provisional_reason="2025 value; both official change lists leave art. 33-35 untouched",
    )

    with tenant_context(context):
        row = resolve_parameter("test.rate.inferred", date(2026, 6, 1))

    assert row.source_confidence == SourceConfidence.PROVISIONAL
    assert "art. 33-35" in (row.provisional_reason or "")


def test_provisional_values_are_listed_for_the_date_asked_about(
    seed: Callable[..., None], source: uuid.UUID, context: TenantContext
) -> None:
    """The question a compliance screen asks before a declaration is filed.

    Asked about a date, not about today -- a period closed in March must report
    what was inferred *then*, which is what an inspection would ask about.
    """
    _param(seed, "test.rate.solid", 12, "2024-01-01")
    _param(
        seed,
        "test.rate.shaky",
        99,
        "2026-01-01",
        confidence=SourceConfidence.PROVISIONAL,
        provisional_reason="deduced",
    )

    with tenant_context(context):
        during_2026 = provisional_in_force(date(2026, 6, 1))
        during_2024 = provisional_in_force(date(2024, 6, 1))

    assert [r.parameter_key for r in during_2026] == ["test.rate.shaky"]
    # The inferred value does not exist yet on that date, and a confirmed one
    # never appears here however long it has been in force.
    assert during_2024 == []


def test_a_provisional_value_without_its_reasoning_is_refused(
    seed: Callable[..., None], source: uuid.UUID, context: TenantContext
) -> None:
    """Marked uncertain and silent about why is indistinguishable from mislabelled.

    Enforced in the database rather than in a service, because the row is what
    somebody reads in three years, and by then the service that wrote it may not
    exist.
    """
    with pytest.raises(Exception) as excinfo:
        _param(
            seed,
            "test.rate.unexplained",
            1,
            "2026-01-01",
            confidence=SourceConfidence.PROVISIONAL,
            provisional_reason="",
        )
    assert "fiscal_parameter_provisional_has_reason" in str(excinfo.value)


def test_a_raw_insert_that_omits_the_confidence_fails_loudly(
    seed: Callable[..., None], source: uuid.UUID
) -> None:
    """The guarantee the model docstring claims, pinned so it cannot quietly go.

    Parameters arrive through privileged SQL, not the ORM, and Django's
    `default=` is applied in Python -- so the model default does *not* protect
    that path. Measured while writing the migration: an INSERT omitting the
    column gets NULL and fails. That is the outcome we want, which is why no
    `db_default` is set; if someone adds one later, this test says what breaks.
    """
    with pytest.raises(Exception) as excinfo:
        seed(
            """
            INSERT INTO fiscal_parameter
                (id, parameter_key, scope, value_type, value, valid_from,
                 source_id, status, approved_by_user_id, approved_at,
                 created_at, updated_at)
            VALUES (%s, 'test.rate.kappa', 'global', 'integer', '1'::jsonb,
                    DATE '2020-01-01', %s, 'active', %s, now(), now(), now())
            """,
            [uuid.uuid4(), SOURCE_ID, APPROVER],
        )
    assert "source_confidence" in str(excinfo.value)
