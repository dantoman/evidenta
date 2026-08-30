"""Templates for typical operations -- F1.7.3, ADR-036 section 8.

The criterion is a border, not a feature: **a template may not produce a posting a
hand-typed note cannot produce.** If it can, the product has a second engine, and
the second implementation is always the one that breaks (Spec B section 1.5 says
so about the manual note itself, for the same reason).

So the file is organised around that border rather than around the tables. The
first group proves the template is a shortcut -- the payload it expands to is the
payload a person types, the entry it posts is the entry a person posts, the event
is `manual.journal_entry` and no new type was registered. The second group proves
the engine still judges: every refusal a hand-typed note can earn is provoked
through a template and comes back with the same stable code, with the ledger left
empty. The third proves this module judges nothing else -- what it checks is the
shape of a form.

**Under the application role, like every test in this suite** (T1). The reads the
expansion makes go through the same policies a request does.

**No account code from the published chart appears** (R15, `OD-23`). The fixture
uses codes no chart uses.
"""

from __future__ import annotations

import ast
import inspect
import uuid
from collections.abc import Callable
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

import pytest
from django.db import connection, transaction
from django.db.utils import IntegrityError, ProgrammingError

from evidenta.accounting.events.models import AccountingEvent
from evidenta.accounting.events.registry import REGISTRY
from evidenta.accounting.ledger.models import JournalEntry, JournalLine
from evidenta.accounting.periods.errors import PeriodLockedError, PeriodNotOpenError
from evidenta.accounting.posting.dimensions import MissingRequiredDimensionError
from evidenta.accounting.posting.invariants import AccountNotPostableError, OutOfBalanceError
from evidenta.accounting.posting.models import (
    OperationTemplate,
    OperationTemplateDimension,
    OperationTemplateLine,
)
from evidenta.accounting.posting.services import templates as templates_module
from evidenta.accounting.posting.services.manual import (
    EVENT_TYPE,
    SOURCE_DOCUMENT_TYPE,
    SOURCE_MODULE,
    ManualPayloadError,
    post_manual_entry,
)
from evidenta.accounting.posting.services.templates import (
    FromInput,
    TemplateAmountNotStorableError,
    TemplateInputInvalidError,
    TemplateInputMissingError,
    TemplateInputUnexpectedError,
    TemplateLine,
    TemplateMalformedError,
    TemplateNameTakenError,
    TemplateNotFoundError,
    TemplateUnknownDimensionError,
    define_template,
    inputs_of,
    payload_for,
    post_from_template,
    redefine_template,
    set_template_active,
)
from evidenta.platform.rls.context import TenantContext, tenant_context

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

#: The same open day the manual-note suite posts on.
POSTING = date(2026, 1, 15)

SNAPSHOT: dict[str, Any] = {
    "version": 1,
    "on": POSTING.isoformat(),
    "activated": [],
    "usable": [],
}


# --- the world ---------------------------------------------------------------


@pytest.fixture
def context(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(
        tenant_id=world["tenant_a"], user_id=world["user_a"], request_id="templates"
    )


def seed_account(
    seed: Callable[..., None],
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    code: str,
    *,
    blocked: bool = False,
    requires: str = "{}",
) -> uuid.UUID:
    # What it requires it also carries (ADR-048): the CHECK
    # `company_account_required_within_slots` holds for a fixture too.
    account_id = uuid.uuid4()
    slots = [name for name in requires.strip("{}").split(",") if name]
    padded: list[str | None] = [*slots, None, None, None, None][:4]
    seed(
        "INSERT INTO company_account (id, tenant_id, company_id, account_code,"
        " parent_id, origin, template_account_id, name_ro, account_class,"
        " normal_balance, allows_subaccounts, currency_tracking, quantity_tracking,"
        " required_dimensions, slot_1_dimension, slot_2_dimension, slot_3_dimension,"
        " slot_4_dimension, is_blocked, valid_from, valid_to, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, NULL, 'company', NULL, %s, 'asset', 'debit',"
        " false, false, false, %s::text[], %s, %s, %s, %s, %s, '2020-01-01', NULL, now(), now())",
        [
            account_id,
            tenant_id,
            company_id,
            code,
            f"Cont de fixture {code}",
            requires,
            *padded,
            blocked,
        ],
    )
    return account_id


def seed_period(
    seed: Callable[..., None],
    tenant_id: uuid.UUID,
    company_id: uuid.UUID,
    year_id: uuid.UUID,
    *,
    period_no: int,
    start: str,
    end: str,
    status: str,
) -> uuid.UUID:
    period_id = uuid.uuid4()
    closed_at = "now()" if status in ("closed", "locked") else "NULL"
    seed(
        "INSERT INTO period (id, tenant_id, company_id, fiscal_year_id, period_no,"
        " start_date, end_date, status, reopened_count, closed_at, created_at, updated_at)"
        f" VALUES (%s, %s, %s, %s, %s, %s, %s, %s, 0, {closed_at}, now(), now())",
        [period_id, tenant_id, company_id, year_id, period_no, start, end, status],
    )
    return period_id


@pytest.fixture
def scene(
    seed: Callable[..., None],
    world: dict[str, uuid.UUID],
    company_of: Callable[..., uuid.UUID],
    grant_company: Callable[..., uuid.UUID],
) -> dict[str, uuid.UUID]:
    """Two companies of one tenant, three months in three states, five accounts.

    The second company is not decoration: it is how "a template naming an account
    that is not this company's" becomes a case that can be built at all, and that
    case is the visible consequence of there being no foreign key to the chart.
    """
    tenant = world["tenant_a"]
    company = company_of(tenant, "1002600000601", "Alpha Sabloane")
    other = company_of(tenant, "1002600000602", "Alpha A Doua")
    grant_company(tenant, company, world["user_a"], world["user_a"])
    grant_company(tenant, other, world["user_a"], world["user_a"])

    year_id = uuid.uuid4()
    seed(
        "INSERT INTO fiscal_year (id, tenant_id, company_id, code, start_date, end_date,"
        " status, created_at, updated_at)"
        " VALUES (%s, %s, %s, '2026', '2026-01-01', '2026-12-31', 'open', now(), now())",
        [year_id, tenant, company],
    )
    template_id = uuid.uuid4()
    seed(
        # `regime` and `valid_from` are not optional: a series belongs to one of
        # the two numbering regimes and applies over a window. Spelled out here
        # rather than left to a database default, because a row that arrived
        # without anybody choosing a regime would number documents freely under a
        # series that may not be ours to number.
        "INSERT INTO numbering_template (id, tenant_id, company_id, document_type,"
        " series, prefix, suffix, separator, digits, include_year, year_format,"
        " reset_policy, regime, valid_from, created_at, updated_at)"
        " VALUES (%s, %s, %s, 'journal_entry', '', 'NC', '', '-', 4, true, 'yyyy',"
        " 'yearly', 'own', DATE '2000-01-01', now(), now())",
        [template_id, tenant, company],
    )

    return {
        "tenant": tenant,
        "company": company,
        "other_company": other,
        "user": world["user_a"],
        "open_period": seed_period(
            seed,
            tenant,
            company,
            year_id,
            period_no=1,
            start="2026-01-01",
            end="2026-01-31",
            status="open",
        ),
        "closed_period": seed_period(
            seed,
            tenant,
            company,
            year_id,
            period_no=2,
            start="2026-02-01",
            end="2026-02-28",
            status="closed",
        ),
        "locked_period": seed_period(
            seed,
            tenant,
            company,
            year_id,
            period_no=3,
            start="2026-03-01",
            end="2026-03-31",
            status="locked",
        ),
        "debit_account": seed_account(seed, tenant, company, "FIXTURE-D"),
        "credit_account": seed_account(seed, tenant, company, "FIXTURE-C"),
        "blocked_account": seed_account(seed, tenant, company, "FIXTURE-B", blocked=True),
        "partner_account": seed_account(seed, tenant, company, "FIXTURE-P", requires="{partner}"),
        "foreign_account": seed_account(seed, tenant, other, "FIXTURE-X"),
    }


# --- building templates ------------------------------------------------------


def two_liner(
    scene: dict[str, uuid.UUID],
    *,
    amount: Decimal | FromInput | None = None,
    name: str = "Incasare de fixture",
) -> uuid.UUID:
    """The smallest useful template: one debit, one credit, one amount typed once.

    The shape that carries most of the value of the whole feature -- the person
    picks the operation and types a number, and the two accounts and the sentence
    are already right.
    """
    value: Decimal | FromInput = FromInput("suma") if amount is None else amount
    return define_template(
        tenant_id=scene["tenant"],
        company_id=scene["company"],
        name=name,
        entry_description="Nota din sablon de fixture",
        lines=[
            TemplateLine(account_id=scene["debit_account"], side="debit", amount=value),
            TemplateLine(account_id=scene["credit_account"], side="credit", amount=value),
        ],
    ).id


def post(
    scene: dict[str, uuid.UUID],
    template_id: uuid.UUID,
    inputs: dict[str, Any] | None = None,
    *,
    on: date = POSTING,
    key: str = "tmpl-1",
    description: str | None = None,
) -> Any:
    return post_from_template(
        tenant_id=scene["tenant"],
        company_id=scene["company"],
        template_id=template_id,
        accounting_date=on,
        functional_currency="MDL",
        note_id=uuid.uuid5(uuid.NAMESPACE_URL, key),
        inputs={"suma": "1000.0000"} if inputs is None else inputs,
        idempotency_key=key,
        actor_user_id=scene["user"],
        request_id="templates-test",
        capability_snapshot=dict(SNAPSHOT),
        description=description,
    )


def lines_of(entry_id: uuid.UUID) -> list[tuple[Any, ...]]:
    """An entry reduced to what a person would compare between two of them."""
    return [
        (
            line.line_number,
            line.account_id,
            line.debit,
            line.credit,
            line.currency,
            line.exchange_rate,
            line.amount_currency,
            line.accounting_date,
            line.document_date,
            line.description,
            line.partner_id,
            line.dim_1_id,
        )
        for line in JournalLine.objects.filter(journal_entry_id=entry_id).order_by("line_number")
    ]


# --- the border: a template is a shortcut, not a second path -----------------


def test_a_template_expands_to_the_payload_a_person_would_type(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The centre of the task, and it is an equality, not a description.

    The expected value below is written out by hand, in the form
    `test_manual_entry` writes it, precisely so that the assertion is between two
    independent things. If a template ever gains a key the manual payload does not
    have -- a provenance marker, a flag, a hint to the engine -- this fails, and it
    should: the engine would then be reading something only templates can send.
    """
    with tenant_context(context):
        template_id = two_liner(scene)

        assert payload_for(
            template_id, company_id=scene["company"], inputs={"suma": "1000.0000"}
        ) == {
            "description": "Nota din sablon de fixture",
            "lines": [
                {
                    "account_id": str(scene["debit_account"]),
                    "debit": "1000.0000",
                    "credit": "0",
                },
                {
                    "account_id": str(scene["credit_account"]),
                    "debit": "0",
                    "credit": "1000.0000",
                },
            ],
        }


def test_the_template_posts_the_entry_the_typed_note_posts(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Two notes, one written by hand and one expanded, compared line by line.

    Not "both produced an entry" -- both produced the *same* entry, down to the
    currency triple and the three dates. The entry number differs, and that is the
    only thing that may: it is drawn from the company's counter, and two notes are
    two notes.
    """
    with tenant_context(context):
        typed = post_manual_entry(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            accounting_date=POSTING,
            functional_currency="MDL",
            note_id=uuid.uuid5(uuid.NAMESPACE_URL, "by-hand"),
            payload={
                "description": "Nota din sablon de fixture",
                "lines": [
                    {
                        "account_id": str(scene["debit_account"]),
                        "debit": "1000.0000",
                        "credit": "0",
                    },
                    {
                        "account_id": str(scene["credit_account"]),
                        "debit": "0",
                        "credit": "1000.0000",
                    },
                ],
            },
            idempotency_key="by-hand",
            actor_user_id=scene["user"],
            request_id="templates-test",
            capability_snapshot=dict(SNAPSHOT),
        )
        from_template = post(scene, two_liner(scene))

        assert lines_of(typed.journal_entry_id) == lines_of(from_template.journal_entry_id)

        one = JournalEntry.objects.get(id=typed.journal_entry_id)
        two = JournalEntry.objects.get(id=from_template.journal_entry_id)
        assert one.description == two.description
        assert one.entry_type == two.entry_type
        assert one.period_id == two.period_id
        assert one.total_debit == two.total_debit == Decimal("1000.0000")
        assert one.entry_number != two.entry_number


def test_the_event_is_the_manual_one_and_names_no_document(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """`produc manual.journal_entry, nu tipuri proprii` -- the backlog's own words.

    And the second half of the same sentence: the event's origin is the manual
    note, so a template cannot be pointed at an invoice. Nothing checks this at
    runtime because nothing can: `post_manual_entry` writes those two strings
    itself and takes no argument that could change them.
    """
    with tenant_context(context):
        result = post(scene, two_liner(scene))

        event = AccountingEvent.objects.get(id=result.accounting_event_id)
        assert event.event_type == EVENT_TYPE
        assert event.source_module == SOURCE_MODULE
        assert event.source_document_type == SOURCE_DOCUMENT_TYPE
        assert JournalEntry.objects.get(id=result.journal_entry_id).accounting_event_id == event.id


def test_no_event_type_is_registered_for_templates() -> None:
    """The vocabulary is unchanged by this module existing (ADR-038).

    A template with its own `event_type` would be layer 1 -- the form of the
    posting -- arriving in a tenant, which is the one thing ADR-036 puts in the
    product for everybody.
    """
    assert EVENT_TYPE in REGISTRY
    assert [name for name in REGISTRY if "template" in name] == []


def test_the_module_can_reach_the_ledger_only_through_the_manual_service() -> None:
    """Read from the source, not from a convention nobody re-reads.

    The service imports `posting.services.manual` and nothing else from the
    accounting side. It cannot write an entry, cannot emit an event and cannot mark
    one posted, so "a template does not post by itself" is a property of the import
    graph rather than a promise in a docstring.
    """
    source = ast.parse(Path(inspect.getsourcefile(templates_module) or "").read_text())
    imported = {
        node.module for node in ast.walk(source) if isinstance(node, ast.ImportFrom) and node.module
    }

    assert "evidenta.accounting.posting.services.manual" in imported
    assert not [name for name in imported if name.startswith("evidenta.accounting.ledger")]
    assert not [name for name in imported if name.startswith("evidenta.accounting.events")]


def test_posting_from_a_template_takes_no_document() -> None:
    """The signature is the border, so the test reads the signature.

    ADR-036 section 8: "Nu pot fi folosite pentru postarea automata a
    documentelor." A parameter naming a source document is all it would take, so
    its absence is asserted rather than assumed.
    """
    parameters = set(inspect.signature(post_from_template).parameters)
    assert not [name for name in parameters if "document" in name or "source" in name]
    assert "note_id" in parameters


# --- expansion ---------------------------------------------------------------


def test_a_fixed_amount_expands_as_the_column_holds_it(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """A rent that is the same every month is typed once, when the template is written."""
    with tenant_context(context):
        template_id = two_liner(scene, amount=Decimal("500"))

        payload = payload_for(template_id, company_id=scene["company"], inputs={})
        assert payload["lines"][0]["debit"] == "500.0000"
        assert payload["lines"][1]["credit"] == "500.0000"

        result = post(scene, template_id, {})
        assert JournalEntry.objects.get(id=result.journal_entry_id).total_debit == Decimal("500")


def test_a_typed_amount_reaches_the_engine_unchanged(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The string the person typed, not a number this module parsed and re-printed.

    Parsing it here would be the second implementation: two places deciding what
    counts as an amount, and the one that drifts is the one the engine does not
    use.
    """
    with tenant_context(context):
        template_id = two_liner(scene)
        # Two decimals: what a posted amount carries (ADR-037 §3.2, ADR-059). The
        # string is still the person's -- the point of the test is that nothing
        # in between re-printed it.
        payload = payload_for(template_id, company_id=scene["company"], inputs={"suma": "1234.56"})
        assert payload["lines"][0]["debit"] == "1234.56"

        result = post(scene, template_id, {"suma": "1234.56"})
        stored = JournalLine.objects.filter(journal_entry_id=result.journal_entry_id).first()
        assert stored is not None
        assert stored.debit == Decimal("1234.56")


def test_a_dimension_can_be_fixed_or_asked_for(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Both kinds on one line: the cost centre never changes, the partner does."""
    cost_centre = uuid.uuid4()
    partner = uuid.uuid4()
    with tenant_context(context):
        template = define_template(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            name="Incasare de la partener",
            entry_description="Nota din sablon cu analitica",
            lines=[
                TemplateLine(
                    account_id=scene["partner_account"],
                    side="debit",
                    amount=FromInput("suma"),
                    dimensions={"partner": FromInput("partener"), "dim_1": cost_centre},
                ),
                TemplateLine(
                    account_id=scene["credit_account"], side="credit", amount=FromInput("suma")
                ),
            ],
        )

        payload = payload_for(
            template.id,
            company_id=scene["company"],
            inputs={"suma": "700.0000", "partener": str(partner)},
        )
        assert payload["lines"][0]["dimensions"] == {
            "partner": str(partner),
            "dim_1": str(cost_centre),
        }
        assert "dimensions" not in payload["lines"][1]

        result = post(scene, template.id, {"suma": "700.0000", "partener": str(partner)})
        stored = list(
            JournalLine.objects.filter(journal_entry_id=result.journal_entry_id).order_by(
                "line_number"
            )
        )
        assert stored[0].partner_id == partner
        assert stored[0].dim_1_id == cost_centre
        assert stored[1].partner_id is None


def test_a_line_description_is_carried_and_an_absent_one_is_not_invented(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        template = define_template(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            name="Cu explicatie pe linie",
            entry_description="Nota din sablon cu explicatii",
            lines=[
                TemplateLine(
                    account_id=scene["debit_account"],
                    side="debit",
                    amount=FromInput("suma"),
                    description="Incasare in casierie",
                ),
                TemplateLine(
                    account_id=scene["credit_account"], side="credit", amount=FromInput("suma")
                ),
            ],
        )
        payload = payload_for(template.id, company_id=scene["company"], inputs={"suma": "10.0000"})
        assert payload["lines"][0]["description"] == "Incasare in casierie"
        assert "description" not in payload["lines"][1]


def test_the_form_asks_for_each_name_once_in_the_order_the_lines_mention_them(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """`inputs_of` is what an interface builds a form from.

    Derived from the lines rather than declared separately: two lists of inputs
    would drift, and the one that drifts is the one nothing reads at expansion.
    """
    with tenant_context(context):
        template = define_template(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            name="Doua sume si un partener",
            entry_description="Nota din sablon cu trei intrari",
            lines=[
                TemplateLine(
                    account_id=scene["partner_account"],
                    side="debit",
                    amount=FromInput("net"),
                    dimensions={"partner": FromInput("partener")},
                ),
                TemplateLine(
                    account_id=scene["debit_account"], side="debit", amount=FromInput("taxa")
                ),
                TemplateLine(
                    account_id=scene["credit_account"], side="credit", amount=FromInput("total")
                ),
            ],
        )
        assert inputs_of(template.id, company_id=scene["company"]) == (
            "net",
            "partener",
            "taxa",
            "total",
        )


def test_the_caller_may_replace_the_sentence(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The template's description is a default, not a lock.

    A manual note is the only entry with no document behind it, so the sentence is
    the whole of what says later what it was -- and a person who knows more than
    the template does must be able to say it.
    """
    with tenant_context(context):
        result = post(scene, two_liner(scene), description="Incasare avans contract 12 din 2026")
        entry = JournalEntry.objects.get(id=result.journal_entry_id)
        assert entry.description == "Incasare avans contract 12 din 2026"


# --- the engine still judges -------------------------------------------------


def unbalanced(scene: dict[str, uuid.UUID]) -> uuid.UUID:
    """A template whose two lines take different inputs.

    Legitimate as a definition -- a purchase with VAT has three amounts and no
    symbolic balance -- so it is not refused when written. It is refused when the
    numbers arrive, by the engine, like any other note.
    """
    return define_template(
        tenant_id=scene["tenant"],
        company_id=scene["company"],
        name="Doua sume independente",
        entry_description="Nota din sablon dezechilibrat",
        lines=[
            TemplateLine(
                account_id=scene["debit_account"], side="debit", amount=FromInput("stanga")
            ),
            TemplateLine(
                account_id=scene["credit_account"], side="credit", amount=FromInput("dreapta")
            ),
        ],
    ).id


def test_a_template_that_does_not_balance_is_refused_by_the_engine(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        with pytest.raises(OutOfBalanceError) as refusal:
            post(scene, unbalanced(scene), {"stanga": "100.0000", "dreapta": "90.0000"})

        assert refusal.value.code == "posting.out_of_balance"
        assert not JournalEntry.objects.exists()
        assert not JournalLine.objects.exists()


def test_a_template_cannot_post_into_a_closed_period(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """R12, reached through the shortcut. The refusal is the engine's, not a copy."""
    with tenant_context(context):
        with pytest.raises(PeriodNotOpenError) as refusal:
            post(scene, two_liner(scene), on=date(2026, 2, 10))

        assert refusal.value.code == "periods.period_not_open"
        assert not JournalEntry.objects.exists()


def test_a_template_cannot_post_into_a_locked_period(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        with pytest.raises(PeriodLockedError) as refusal:
            post(scene, two_liner(scene), on=date(2026, 3, 10))

        assert refusal.value.code == "periods.period_locked"
        assert not JournalEntry.objects.exists()


def test_a_template_naming_a_blocked_account_is_refused_at_posting(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Blocked after the template was written -- which is the ordinary case.

    The account was fine on the day somebody wrote the shortcut. Whether it is fine
    today is a question with a date in it, and it is answered by the engine on the
    day of the posting.
    """
    with tenant_context(context):
        template = define_template(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            name="Pe un cont blocat",
            entry_description="Nota din sablon pe cont blocat",
            lines=[
                TemplateLine(
                    account_id=scene["blocked_account"], side="debit", amount=FromInput("suma")
                ),
                TemplateLine(
                    account_id=scene["credit_account"], side="credit", amount=FromInput("suma")
                ),
            ],
        )

        with pytest.raises(AccountNotPostableError) as refusal:
            post(scene, template.id)

        assert refusal.value.code == "posting.account_not_postable"
        assert not JournalEntry.objects.exists()


def test_a_template_naming_another_companys_account_is_refused_at_posting(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The visible consequence of there being no foreign key to the chart.

    The row can be written -- the template says an id and nothing checks whose it
    is -- and the note cannot be posted, because the engine asks *this* company's
    chart. The alternative, a foreign key, would answer the question at definition
    time, on a different date, and would additionally confirm the existence of a
    row this context cannot see.
    """
    with tenant_context(context):
        template = define_template(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            name="Pe contul altei companii",
            entry_description="Nota din sablon cu cont strain",
            lines=[
                TemplateLine(
                    account_id=scene["foreign_account"], side="debit", amount=FromInput("suma")
                ),
                TemplateLine(
                    account_id=scene["credit_account"], side="credit", amount=FromInput("suma")
                ),
            ],
        )

        with pytest.raises(AccountNotPostableError):
            post(scene, template.id)
        assert not JournalEntry.objects.exists()


def test_a_template_that_omits_a_required_dimension_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """F1.1.3 holds through the shortcut too.

    The template names an account that requires `partner` and carries no partner.
    Nothing here notices; the engine does, and the code is the same one a typed
    note earns.
    """
    with tenant_context(context):
        template = define_template(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            name="Fara partener",
            entry_description="Nota din sablon fara analitica ceruta",
            lines=[
                TemplateLine(
                    account_id=scene["partner_account"], side="debit", amount=FromInput("suma")
                ),
                TemplateLine(
                    account_id=scene["credit_account"], side="credit", amount=FromInput("suma")
                ),
            ],
        )

        with pytest.raises(MissingRequiredDimensionError) as refusal:
            post(scene, template.id)

        assert refusal.value.code == "posting.missing_required_dimension"
        assert not JournalEntry.objects.exists()


def test_a_fifth_decimal_typed_into_a_template_is_refused_by_the_engine(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The value passes through untouched, and the engine refuses it.

    Refusing it here would be the second parser. Rounding it here would be
    answering `DNB-08` in a shortcut.
    """
    with tenant_context(context):
        with pytest.raises(ManualPayloadError) as refusal:
            post(scene, two_liner(scene), {"suma": "1.00001"})

        assert refusal.value.code == "posting.manual_payload_malformed"
        assert not JournalEntry.objects.exists()


def test_a_dimension_value_that_is_not_an_identifier_is_refused_by_the_engine(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        template = define_template(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            name="Cu partener tastat",
            entry_description="Nota din sablon cu partener",
            lines=[
                TemplateLine(
                    account_id=scene["debit_account"],
                    side="debit",
                    amount=FromInput("suma"),
                    dimensions={"partner": FromInput("partener")},
                ),
                TemplateLine(
                    account_id=scene["credit_account"], side="credit", amount=FromInput("suma")
                ),
            ],
        )

        with pytest.raises(ManualPayloadError) as refusal:
            post(scene, template.id, {"suma": "5.0000", "partener": "Ionescu SRL"})

        assert refusal.value.code == "posting.manual_payload_malformed"
        assert not JournalEntry.objects.exists()


# --- what this module does check: the shape of a form ------------------------


def test_a_missing_input_is_named_rather_than_defaulted(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """A zero would be refused too -- for the wrong reason, on the wrong line."""
    with tenant_context(context):
        with pytest.raises(TemplateInputMissingError) as refusal:
            post(scene, two_liner(scene), {})

        assert refusal.value.code == "posting.template_input_missing"
        assert "suma" in str(refusal.value)
        assert not AccountingEvent.objects.exists()


def test_a_value_nothing_reads_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The typo case, and the reason it matters.

    With `suma` also supplied, the note would balance and post, and the number the
    person believed they had entered would be nowhere in it.
    """
    with tenant_context(context):
        with pytest.raises(TemplateInputUnexpectedError) as refusal:
            post(scene, two_liner(scene), {"suma": "10.0000", "sumaa": "90.0000"})

        assert refusal.value.code == "posting.template_input_unexpected"
        assert not AccountingEvent.objects.exists()


def test_an_input_that_is_not_text_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """A float never reaches the payload, and the reason is serialisation.

    The payload is stored as `jsonb` and fingerprinted for idempotency, so a value
    JSON cannot carry has no stable form. That 0.1 is not a tenth is the engine's
    argument, and it makes the same refusal one step later.
    """
    with tenant_context(context):
        with pytest.raises(TemplateInputInvalidError) as refusal:
            post(scene, two_liner(scene), {"suma": 1000.0})

        assert refusal.value.code == "posting.template_input_invalid"


@pytest.mark.parametrize(
    "lines",
    [
        pytest.param([], id="no lines at all"),
    ],
)
def test_a_template_with_no_lines_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID], lines: list[TemplateLine]
) -> None:
    with tenant_context(context), pytest.raises(TemplateMalformedError) as refusal:
        define_template(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            name="Gol",
            entry_description="Nota din sablon gol",
            lines=lines,
        )
    assert refusal.value.code == "posting.template_malformed"


def test_a_template_without_a_sentence_is_refused_when_it_is_written(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """It would be refused at every single use; refusing it once is better."""
    with tenant_context(context), pytest.raises(TemplateMalformedError):
        define_template(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            name="Fara explicatie",
            entry_description="   ",
            lines=[
                TemplateLine(account_id=scene["debit_account"], side="debit", amount=Decimal("1")),
                TemplateLine(
                    account_id=scene["credit_account"], side="credit", amount=Decimal("1")
                ),
            ],
        )


def test_a_dimension_outside_the_vocabulary_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """ADR-029's list is closed, and a name outside it would be dropped silently."""
    with tenant_context(context), pytest.raises(TemplateUnknownDimensionError) as refusal:
        define_template(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            name="Cu dimensiune inventata",
            entry_description="Nota din sablon cu dimensiune inventata",
            lines=[
                TemplateLine(
                    account_id=scene["debit_account"],
                    side="debit",
                    amount=Decimal("1"),
                    dimensions={"filiala": uuid.uuid4()},
                ),
            ],
        )
    assert refusal.value.code == "posting.template_unknown_dimension"


@pytest.mark.parametrize(
    "amount",
    [
        pytest.param(Decimal("1.00001"), id="a fifth decimal"),
        pytest.param(Decimal("0"), id="zero"),
        pytest.param(Decimal("-5"), id="negative"),
    ],
)
def test_a_fixed_amount_the_ledger_cannot_hold_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID], amount: Decimal
) -> None:
    """Refused when written, because a fixed amount fails identically every time.

    The opposite of a typed one: that is refused at posting, because the value is
    not known until then.
    """
    with tenant_context(context), pytest.raises(TemplateAmountNotStorableError) as refusal:
        define_template(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            name=f"Suma imposibila {amount}",
            entry_description="Nota din sablon cu suma imposibila",
            lines=[
                TemplateLine(account_id=scene["debit_account"], side="debit", amount=amount),
            ],
        )
    assert refusal.value.code == "posting.template_amount_not_storable"


def test_one_name_cannot_be_both_a_sum_and_a_reference(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The form would ask for it once and two lines would read it as two things."""
    with tenant_context(context), pytest.raises(TemplateMalformedError) as refusal:
        define_template(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            name="Nume ambiguu",
            entry_description="Nota din sablon ambiguu",
            lines=[
                TemplateLine(
                    account_id=scene["debit_account"],
                    side="debit",
                    amount=FromInput("valoare"),
                    dimensions={"partner": FromInput("valoare")},
                ),
            ],
        )
    assert refusal.value.code == "posting.template_malformed"


@pytest.mark.parametrize(
    "key", [pytest.param("Suma", id="capitalised"), pytest.param("suma totala", id="with a space")]
)
def test_an_input_name_that_is_not_a_key_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID], key: str
) -> None:
    """Keys are keys. The label a person reads is interface, and lives in a resource file (C32)."""
    with tenant_context(context), pytest.raises(TemplateMalformedError):
        define_template(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            name=f"Cheie gresita {key}",
            entry_description="Nota din sablon cu cheie gresita",
            lines=[
                TemplateLine(
                    account_id=scene["debit_account"], side="debit", amount=FromInput(key)
                ),
            ],
        )


def test_a_side_that_is_neither_debit_nor_credit_is_refused(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context), pytest.raises(TemplateMalformedError):
        define_template(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            name="Latura inventata",
            entry_description="Nota din sablon cu latura inventata",
            lines=[
                TemplateLine(account_id=scene["debit_account"], side="ambele", amount=Decimal("1")),
            ],
        )


def test_two_templates_in_use_cannot_share_a_name(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Picked from a list by a person; two identical rows are picked by guessing."""
    with tenant_context(context):
        two_liner(scene, name="Incasare")
        with pytest.raises(TemplateNameTakenError) as refusal:
            two_liner(scene, name="Incasare")
        assert refusal.value.code == "posting.template_name_taken"


# --- editing -----------------------------------------------------------------


def test_redefining_a_template_leaves_the_entries_it_already_posted_alone(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The guarantee ADR-036 section 6.4 gives for bindings, here by construction.

    The payload is expanded at the moment of use and the register is append-only,
    so there is no recalculation to suppress: the old entry keeps the accounts it
    was posted with, and the next note uses the new ones.
    """
    with tenant_context(context):
        template_id = two_liner(scene)
        first = post(scene, template_id, key="before")
        before = lines_of(first.journal_entry_id)

        redefine_template(
            template_id,
            company_id=scene["company"],
            name="Incasare de fixture",
            entry_description="Nota din sablon rescris",
            lines=[
                TemplateLine(
                    account_id=scene["credit_account"], side="debit", amount=FromInput("suma")
                ),
                TemplateLine(
                    account_id=scene["debit_account"], side="credit", amount=FromInput("suma")
                ),
            ],
        )

        assert lines_of(first.journal_entry_id) == before
        assert OperationTemplateLine.objects.filter(template_id=template_id).count() == 2

        second = post(scene, template_id, key="after")
        assert (
            JournalEntry.objects.get(id=second.journal_entry_id).description
            == "Nota din sablon rescris"
        )
        assert lines_of(second.journal_entry_id)[0][1] == scene["credit_account"]


def test_redefining_replaces_the_dimensions_too(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The child rows go with the lines. A dimension left behind would be an orphan."""
    with tenant_context(context):
        template = define_template(
            tenant_id=scene["tenant"],
            company_id=scene["company"],
            name="Cu apoi fara analitica",
            entry_description="Nota din sablon cu analitica",
            lines=[
                TemplateLine(
                    account_id=scene["debit_account"],
                    side="debit",
                    amount=FromInput("suma"),
                    dimensions={"partner": uuid.uuid4()},
                ),
                TemplateLine(
                    account_id=scene["credit_account"], side="credit", amount=FromInput("suma")
                ),
            ],
        )
        assert OperationTemplateDimension.objects.count() == 1

        redefine_template(
            template.id,
            company_id=scene["company"],
            name="Cu apoi fara analitica",
            entry_description="Nota din sablon fara analitica",
            lines=[
                TemplateLine(
                    account_id=scene["debit_account"], side="debit", amount=FromInput("suma")
                ),
                TemplateLine(
                    account_id=scene["credit_account"], side="credit", amount=FromInput("suma")
                ),
            ],
        )
        assert OperationTemplateDimension.objects.count() == 0


def test_a_retired_template_cannot_be_used_and_releases_its_name(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """Retirement, not deletion -- and the name comes back with it.

    A company that stops using "Incasare din casa" must be able to write a new one
    under the same name without inventing "Incasare din casa 2", and must still be
    able to see what the old one said.
    """
    with tenant_context(context):
        template_id = two_liner(scene, name="Incasare din casa")
        set_template_active(template_id, company_id=scene["company"], active=False)

        with pytest.raises(TemplateNotFoundError) as refusal:
            post(scene, template_id)
        assert refusal.value.code == "posting.template_not_found"

        replacement = two_liner(scene, name="Incasare din casa")
        assert replacement != template_id
        assert OperationTemplate.objects.filter(id=template_id).exists()


def test_a_template_of_another_company_is_not_found(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """One answer for "no such id" and for "not yours", like `coa` gives."""
    with tenant_context(context):
        template_id = two_liner(scene)
        with pytest.raises(TemplateNotFoundError):
            payload_for(template_id, company_id=scene["other_company"], inputs={"suma": "1.0000"})


# --- idempotency, isolation, and the database's own refusals -----------------


def test_the_same_key_twice_posts_one_entry(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """R19 through the shortcut. The template adds no second key and no second event."""
    with tenant_context(context):
        template_id = two_liner(scene)
        first = post(scene, template_id, key="tmpl-once")
        second = post(scene, template_id, key="tmpl-once")

        assert first.journal_entry_id == second.journal_entry_id
        assert first.posted_now is True
        assert second.posted_now is False
        assert JournalEntry.objects.count() == 1
        assert AccountingEvent.objects.count() == 1


def test_another_tenant_sees_no_templates(
    context: TenantContext, scene: dict[str, uuid.UUID], world: dict[str, uuid.UUID]
) -> None:
    with tenant_context(context):
        two_liner(scene)
        assert OperationTemplate.objects.count() == 1

    other = TenantContext(
        tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="templates-b"
    )
    with tenant_context(other):
        assert not OperationTemplate.objects.exists()
        assert not OperationTemplateLine.objects.exists()
        assert not OperationTemplateDimension.objects.exists()


def test_the_application_role_cannot_delete_a_template(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The refusal is a grant, not a service check.

    A service-level refusal is bypassed by a data migration and by any importer,
    which is exactly where a shortcut would vanish along with the answer to what it
    used to say.
    """
    with tenant_context(context):
        template_id = two_liner(scene)
        with (
            pytest.raises(ProgrammingError),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute("DELETE FROM operation_template WHERE id = %s", [template_id])


def test_a_line_cannot_be_written_under_another_companys_context(
    context: TenantContext, scene: dict[str, uuid.UUID]
) -> None:
    """The state the model cannot express and the table could.

    A line carrying a different `company_id` than its template would be visible
    under a context in which the template is not -- the hole the policy exists to
    close. The composite key makes it unwritable, and the check is here rather than
    in the service because a data migration does not call the service.
    """
    with tenant_context(context):
        template_id = two_liner(scene)
        with (
            pytest.raises(IntegrityError),
            transaction.atomic(),
            connection.cursor() as cursor,
        ):
            cursor.execute(
                "INSERT INTO operation_template_line (id, tenant_id, company_id,"
                " template_id, line_number, account_id, side, fixed_amount,"
                " input_key, description)"
                " VALUES (%s, %s, %s, %s, 9, %s, 'debit', 1, NULL, NULL)",
                [
                    uuid.uuid4(),
                    scene["tenant"],
                    scene["other_company"],
                    template_id,
                    scene["debit_account"],
                ],
            )
