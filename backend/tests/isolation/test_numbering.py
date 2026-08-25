"""Document numbering -- ADR-022.

The four properties the ADR calls non-negotiable, each with the failure it
prevents.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime

import pytest
from django.db import transaction
from django.db.utils import IntegrityError

from evidenta.platform.documents.models import Document, DocumentState
from evidenta.platform.numbering.models import (
    NumberingCounter,
    NumberingTemplate,
    ResetPolicy,
    YearFormat,
)
from evidenta.platform.numbering.services.allocation import (
    NumberingError,
    allocate,
    format_number,
    resolve_template,
)
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])


@pytest.fixture
def company(
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> uuid.UUID:
    company_id = company_of(world["tenant_a"], "1002600000001", "Alpha Trading")
    grant_company(world["tenant_a"], company_id, world["user_a"], world["user_a"])
    return company_id


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="num")


def make_template(
    world: dict[str, uuid.UUID], company_id: uuid.UUID, **kwargs: object
) -> NumberingTemplate:
    defaults: dict[str, object] = {
        "tenant_id": world["tenant_a"],
        "company_id": company_id,
        "document_type": None,
        "series": "",
        "prefix": "FA",
        "suffix": "",
        "separator": "-",
        "digits": 6,
        "include_year": True,
        "year_format": YearFormat.FOUR_DIGIT,
        "reset_policy": ResetPolicy.YEARLY,
    }
    defaults.update(kwargs)
    return NumberingTemplate.objects.create(**defaults)


def test_a_type_without_a_template_is_an_error_not_a_default(
    context: TenantContext, company: uuid.UUID
) -> None:
    """Inventing a default here produces numbers nobody chose, on documents that
    leave the company."""
    with tenant_context(context), pytest.raises(NumberingError) as caught:
        resolve_template(company, "sales_invoice")
    assert caught.value.code == "numbering.no_template"


def test_a_type_specific_template_wins_over_the_general_one(
    context: TenantContext, world: dict[str, uuid.UUID], company: uuid.UUID
) -> None:
    with tenant_context(context):
        make_template(world, company, prefix="GEN")
        make_template(world, company, document_type="sales_invoice", prefix="FA")
        assert resolve_template(company, "sales_invoice").prefix == "FA"
        assert resolve_template(company, "receipt").prefix == "GEN"


def test_the_template_shapes_the_number(
    context: TenantContext, world: dict[str, uuid.UUID], company: uuid.UUID
) -> None:
    with tenant_context(context):
        template = make_template(world, company, prefix="FA", series="CHI", digits=4, separator="-")
        assert format_number(template, 7, date(2026, 3, 1)) == "FA-CHI-2026-0007"

        short_year = make_template(
            world,
            company,
            document_type="receipt",
            prefix="BON",
            digits=3,
            separator="/",
            year_format=YearFormat.TWO_DIGIT,
        )
        assert format_number(short_year, 42, date(2026, 3, 1)) == "BON/26/042"


def test_allocation_advances_and_never_repeats(
    context: TenantContext, world: dict[str, uuid.UUID], company: uuid.UUID
) -> None:
    with tenant_context(context):
        make_template(world, company)
        taken = [
            allocate(world["tenant_a"], company, "sales_invoice", date(2026, 3, 1)).number
            for _ in range(5)
        ]
    assert taken == [1, 2, 3, 4, 5]


def test_allocation_does_not_use_max_plus_one(
    context: TenantContext, world: dict[str, uuid.UUID], company: uuid.UUID
) -> None:
    """The counter is the source, not the documents.

    With MAX+1, deleting or cancelling the highest-numbered document would hand
    its number to the next one -- two documents, one number, discovered when the
    tax authority compares them.
    """
    with tenant_context(context):
        make_template(world, company)
        first = allocate(world["tenant_a"], company, "sales_invoice", date(2026, 3, 1))
        counter = NumberingCounter.objects.get()
        assert counter.next_number == first.number + 1

        # No documents exist at all, and the next number still moves on.
        second = allocate(world["tenant_a"], company, "sales_invoice", date(2026, 3, 1))
        assert second.number == first.number + 1


def test_the_yearly_policy_restarts_the_counter(
    context: TenantContext, world: dict[str, uuid.UUID], company: uuid.UUID
) -> None:
    with tenant_context(context):
        make_template(world, company, reset_policy=ResetPolicy.YEARLY)
        allocate(world["tenant_a"], company, "sales_invoice", date(2026, 12, 31))
        next_year = allocate(world["tenant_a"], company, "sales_invoice", date(2027, 1, 1))
    assert next_year.number == 1


def test_the_never_policy_does_not_restart(
    context: TenantContext, world: dict[str, uuid.UUID], company: uuid.UUID
) -> None:
    with tenant_context(context):
        make_template(world, company, reset_policy=ResetPolicy.NEVER)
        allocate(world["tenant_a"], company, "sales_invoice", date(2026, 12, 31))
        next_year = allocate(world["tenant_a"], company, "sales_invoice", date(2027, 1, 1))
    assert next_year.number == 2


def test_a_duplicate_number_is_refused_by_the_database(
    context: TenantContext, world: dict[str, uuid.UUID], company: uuid.UUID
) -> None:
    """ADR-022: uniqueness in the database.

    A service that checks and then inserts produces duplicates on the first
    concurrent write, and a duplicate invoice number is a compliance defect
    rather than a display glitch.
    """
    with tenant_context(context):
        for _ in range(2):
            with (
                pytest.raises(IntegrityError, match="document_number_unique")
                if _
                else (transaction.atomic())
            ):
                Document.objects.create(
                    tenant_id=world["tenant_a"],
                    company_id=company,
                    document_type="sales_invoice",
                    series="",
                    number=1,
                    formatted_number="FA-2026-000001",
                    fiscal_year=2026,
                    document_date=date(2026, 3, 1),
                    state=DocumentState.CONFIRMED,
                    created_by_id=world["user_a"],
                    confirmed_at=datetime.now(UTC),
                )


def test_a_draft_holds_no_number(
    context: TenantContext, world: dict[str, uuid.UUID], company: uuid.UUID
) -> None:
    """A draft that is abandoned must not consume a number."""
    with (
        tenant_context(context),
        pytest.raises(IntegrityError, match="document_draft_has_no_number"),
        transaction.atomic(),
    ):
        Document.objects.create(
            tenant_id=world["tenant_a"],
            company_id=company,
            document_type="sales_invoice",
            number=1,
            fiscal_year=2026,
            document_date=date(2026, 3, 1),
            state=DocumentState.DRAFT,
            created_by_id=world["user_a"],
        )


def test_half_a_number_is_refused(
    context: TenantContext, world: dict[str, uuid.UUID], company: uuid.UUID
) -> None:
    """A number without its year would slip past the unique constraint."""
    with (
        tenant_context(context),
        pytest.raises(IntegrityError, match="document_number_complete"),
        transaction.atomic(),
    ):
        Document.objects.create(
            tenant_id=world["tenant_a"],
            company_id=company,
            document_type="sales_invoice",
            number=1,
            fiscal_year=None,
            document_date=date(2026, 3, 1),
            state=DocumentState.CONFIRMED,
            created_by_id=world["user_a"],
            confirmed_at=datetime.now(UTC),
        )


def test_a_company_holds_one_general_template(
    context: TenantContext, world: dict[str, uuid.UUID], company: uuid.UUID
) -> None:
    """Postgres treats NULLs as distinct in a unique index, so without the partial
    constraint a company could hold several general templates and resolution
    would pick one arbitrarily."""
    with tenant_context(context):
        make_template(world, company)
        with (
            pytest.raises(IntegrityError, match="numbering_template_general_unique"),
            transaction.atomic(),
        ):
            make_template(world, company, prefix="ALT")
