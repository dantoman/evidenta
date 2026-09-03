"""Document core -- the concepts every business document shares.

One header table with a type discriminator rather than a base class per module.
The reason is not tidiness: numbering, state, history and the cancellation trail
have to work identically for a sales invoice and for a supplier order, and four
implementations of "what state is this in" become four answers to the same
question within a year.

Typed modules add their own tables, each linked one-to-one to a row here, and
carry only what is theirs -- the nature of a sale, the supplier's own number and
date on a purchase. This module knows nothing about them: accounting does not
know the source (`D2`), and neither does the document core.

**What this module deliberately does not do.**

* It does not post. The transition to ``posted`` is declared in the state machine
  and has no implementation here; adding one must not require reshaping anything
  below.
* It does not resolve accounts, rules of correspondence or analytical dimensions.
  There is no account column on a document line and there will not be one placed
  by this layer.
* It does not compute VAT. A rate arrives resolved from the fiscal nomenclature
  by date (`R15`, `R17`); the amounts arrive computed, because the single
  rounding step that produces them is versioned fiscal logic and is still open
  (`DNB-08`, ADR-037). A column here that quietly rounded would be that decision
  taken by the least entitled layer.
"""

from __future__ import annotations

import uuid

from django.db import models

from evidenta.platform.amounts import (
    AMOUNT_DIGITS,
    CURRENCY_SCALE,
    PERCENT_DIGITS,
    PERCENT_SCALE,
    QUANTITY_SCALE,
    RATE_DIGITS,
    RATE_SCALE,
    UNIT_PRICE_SCALE,
)
from evidenta.platform.identity.models import User
from evidenta.platform.numbering.regimes import NumberingRegime
from evidenta.platform.tenancy.models import Company, Tenant


class RateTerm(models.TextChoices):
    """Which day's rate settles a document in foreign currency -- SNC "Diferenţe
    de curs valutar şi de sumă", pct. 19: the rate at the payment date, the rate
    at the delivery date, or a rate the parties fixed. At the last two no
    difference ever arises (pct. 21): both sides recognise at the same rate.

    **The default is the act's own suppletive rule, not a platform choice.**
    Points 6 and 8 recalculate at the rate of the settlement day when the
    contract says nothing, so a document without a stipulation really does fall
    under `payment_date`. This is the difference from `decimal_places = 0` on the
    unit of measure (ADR-055): that default stood in for a choice nobody had
    made; this one states what the norm applies. Delivery-date and fixed rates
    are contractual stipulations and are written here explicitly (ADR-057).
    """

    PAYMENT_DATE = "payment_date"
    DELIVERY_DATE = "delivery_date"
    FIXED = "fixed"


class ContractDenomination(models.TextChoices):
    """What a contract not in lei is denominated in -- the discriminator of
    ADR-057 section 2.2, carried on the document since ADR-097 (`OD-127`).

    Two values and no third: SNC "Diferenţe de curs valutar şi de sumă" names
    operations *in foreign currency* (pct. 4) and contracts between residents in
    foreign currency or *conventional units* (pct. 17). Neither means "in lei",
    which is why the column is null on a document in the functional currency
    and required on every other -- a denomination is a property of a contract
    that is not in lei, and a default would be the silent choice ADR-057 refuses.
    """

    FOREIGN_CURRENCY = "foreign_currency"
    CONVENTIONAL_UNITS = "conventional_units"


class DocumentState(models.TextChoices):
    """The generic lifecycle. Domain variants extend it, never replace it.

    ``Draft`` is editable and means nothing has happened. ``Confirmed`` is the
    business commitment -- in Romanian, *validat*: the number is allocated and the
    document freezes. ``Posted`` means the accounting effect exists -- and from
    that point the document is immutable for a second reason, because the ledger
    is (`R10`). ``Cancelled`` is terminal and does **not** free the number.

    ``Posted`` is declared and unreachable from this module: nothing here makes
    the transition, and the machine accepts it as an extension rather than as a
    reshaping.
    """

    DRAFT = "draft"
    CONFIRMED = "confirmed"
    POSTED = "posted"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


#: Which moves are allowed. Absent pairs are refused, as in the engagement
#: matrix, and for the same reason: adding one should be an edit to a table
#: rather than a condition slipped into a branch.
#:
#: **``confirmed -> draft`` is not here, and its absence is the decision.** A
#: validated document is immutable and its number is allocated; un-validating it
#: either releases a number -- which a register may never do -- or burns one
#: silently. Correcting a validated document is a reversal and a new document,
#: which is the same answer `R10` gives for the ledger, one layer up.
DOCUMENT_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        (DocumentState.DRAFT, DocumentState.CONFIRMED),
        (DocumentState.DRAFT, DocumentState.CANCELLED),
        (DocumentState.CONFIRMED, DocumentState.POSTED),
        (DocumentState.CONFIRMED, DocumentState.CANCELLED),
        (DocumentState.POSTED, DocumentState.COMPLETED),
        # No way out of POSTED except forward, and no way back into DRAFT from
        # anywhere. Cancelling after posting is not a transition: it is a
        # reversal, which produces a document of its own.
    }
)

#: The states in which a document is still being written. Everything outside this
#: set is frozen -- enforced by a trigger, not by the services that happen to be
#: written today.
EDITABLE_STATES: frozenset[str] = frozenset({DocumentState.DRAFT})


class Document(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    #: A code registered in `documents.registry`. Free text in the column and a
    #: closed vocabulary in the application, exactly like `accounting_event`
    #: (ADR-038): an unregistered type cannot be created, and the database does
    #: not carry a list that a government decision can change.
    document_type = models.TextField()

    # Allocated at validation, never at creation: a draft that is abandoned must
    # not consume a number. Once allocated it is never reused -- cancelling
    # leaves a gap, and a register with reassigned numbers is not a register.
    series = models.TextField(default="")
    number = models.BigIntegerField(null=True, blank=True)
    formatted_number = models.TextField(null=True, blank=True)
    fiscal_year = models.SmallIntegerField(null=True, blank=True)

    #: Which of the two numbering regimes this document belongs to, copied from
    #: the series in force when the draft was opened. Copied rather than looked
    #: up: the series can be superseded, and what the document *was* numbered
    #: under has to stay legible afterwards.
    numbering_regime = models.TextField(
        choices=NumberingRegime.choices, default=NumberingRegime.OWN
    )

    #: The identifier assigned elsewhere -- an e-Factura series and number, a
    #: strict-accountability form taken from an SFS range, a supplier's own
    #: reference on an incoming document under an external regime. Nullable even
    #: at validation, and that is a requirement rather than laxity: the number is
    #: not ours to have yet, and refusing to validate without it would block a
    #: document the exchange has not answered about.
    external_number = models.TextField(null=True, blank=True)

    #: Two dates, always. The document's own date is what is printed on it and
    #: what the counterparty sees; the accounting date decides which period the
    #: effect will fall in and which parameters and logic apply to it (`R17`,
    #: `R18`). A delivery on the 28th recorded on the 5th has two different
    #: answers to "when", and collapsing them loses the one an inspection asks
    #: about. Nothing in this module posts, so nothing here reads the second --
    #: it is carried, not used, and that is the point of carrying it now.
    document_date = models.DateField()
    accounting_date = models.DateField()

    state = models.TextField(choices=DocumentState.choices, default=DocumentState.DRAFT)

    currency = models.CharField(max_length=3, default="MDL")

    #: MDL per one unit of `currency` (ADR-039, `DN-04`). Exactly 1 when the
    #: document is already in the company's functional currency -- stored rather
    #: than left NULL so the derivation has no special case, the same choice Spec
    #: B section 1.3 made for the journal line.
    #:
    #: **Which day's rate applies is not decided here.** Art. 97 alin. (6) names a
    #: date that is neither the document's nor the posting's, and that question is
    #: open (ADR-039 `DN-04`). The service takes the rate as an input; it does not
    #: look one up by a date it chose.
    exchange_rate = models.DecimalField(
        max_digits=RATE_DIGITS, decimal_places=RATE_SCALE, default=1
    )

    #: The contractual term on the rate (pct. 19), the precondition of the
    #: realised-difference handler (C4, ADR-057). See `RateTerm` for why the
    #: default is safe. Frozen with the rest of the header once the document is
    #: confirmed: the trigger compares the whole row.
    rate_term = models.TextField(choices=RateTerm.choices, default=RateTerm.PAYMENT_DATE)

    #: Foreign currency or conventional units -- null exactly when the document
    #: is in the functional currency (see `ContractDenomination`). Required, not
    #: defaulted, on a document in another currency: it chooses between two pairs
    #: of accounts at settlement and decides whether the balance is revalued at
    #: the reporting date (pct. 11 against pct. 22). Frozen with the header.
    contract_denomination = models.TextField(
        choices=ContractDenomination.choices, null=True, blank=True
    )

    # The counterparty, without a foreign key: partners live in masterdata, and a
    # key from every document to them is a cost paid on every write for an
    # integrity the service already asserts.
    partner_id = models.UUIDField(null=True, blank=True)

    #: The document this one was produced from -- a proforma turned into a sale,
    #: an order turned into a purchase. A self-reference, so the chain is
    #: navigable in both directions without a second table.
    #:
    #: Distinct from a reversal, which lives in `ReversalDocument`. Two different
    #: relationships ("produced by converting that") and ("undoes that") in one
    #: column would be two facts that can disagree.
    source_document = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        db_column="source_document_id",
        null=True,
        blank=True,
        related_name="derived_documents",
    )

    created_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        db_column="created_by_user_id",
        related_name="documents_created",
    )
    confirmed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        db_column="confirmed_by_user_id",
        null=True,
        blank=True,
        related_name="documents_confirmed",
    )
    cancelled_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        db_column="cancelled_by_user_id",
        null=True,
        blank=True,
        related_name="documents_cancelled",
    )
    confirmed_at = models.DateTimeField(null=True, blank=True)
    posted_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancellation_reason = models.TextField(null=True, blank=True)

    notes = models.TextField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "document"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(state__in=DocumentState.values),
                name="document_state_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(numbering_regime__in=NumberingRegime.values),
                name="document_regime_valid",
            ),
            # A number belongs to a year and a series or to nothing. Half a
            # number is how a duplicate slips past the unique constraint.
            models.CheckConstraint(
                condition=models.Q(number__isnull=True, fiscal_year__isnull=True)
                | models.Q(number__isnull=False, fiscal_year__isnull=False),
                name="document_number_complete",
            ),
            models.CheckConstraint(
                condition=~models.Q(state=DocumentState.DRAFT) | models.Q(number__isnull=True),
                name="document_draft_has_no_number",
            ),
            # A document under an external regime never carries a number this
            # system produced. Without this, a series switched to external after
            # the fact would leave documents holding two identifiers, one of them
            # ours and wrong.
            models.CheckConstraint(
                condition=~models.Q(numbering_regime=NumberingRegime.EXTERNAL)
                | models.Q(number__isnull=True),
                name="document_external_has_no_own_number",
            ),
            # ... and one under our own regime cannot be validated without one.
            # Cancelled is exempt because a draft can be cancelled before it ever
            # reached a number, and that gap is legitimate.
            models.CheckConstraint(
                condition=models.Q(state__in=[DocumentState.DRAFT, DocumentState.CANCELLED])
                | models.Q(numbering_regime=NumberingRegime.EXTERNAL)
                | models.Q(number__isnull=False),
                name="document_own_regime_is_numbered_when_validated",
            ),
            # A cancellation nobody can explain is a cancellation nobody can
            # audit. The law asks the register to account for what was voided,
            # not to fall silent about it.
            models.CheckConstraint(
                condition=~models.Q(state=DocumentState.CANCELLED)
                | models.Q(cancellation_reason__isnull=False),
                name="document_cancelled_has_reason",
            ),
            # A zero or negative rate does not convert an amount, it erases or
            # inverts it.
            models.CheckConstraint(
                condition=models.Q(exchange_rate__gt=0),
                name="document_exchange_rate_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(rate_term__in=RateTerm.values),
                name="document_rate_term_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(contract_denomination__isnull=True)
                | models.Q(contract_denomination__in=ContractDenomination.values),
                name="document_contract_denomination_valid",
            ),
            # ADR-022: uniqueness in the database. A service that checks and then
            # inserts produces duplicates on the first concurrent write.
            models.UniqueConstraint(
                fields=["company", "document_type", "series", "fiscal_year", "number"],
                condition=models.Q(number__isnull=False),
                name="document_number_unique",
            ),
            # The same guarantee for the regime where the identifier arrives:
            # two documents carrying one e-Factura number is the same compliance
            # defect, reached by the other road.
            models.UniqueConstraint(
                fields=["company", "document_type", "external_number"],
                condition=models.Q(external_number__isnull=False),
                name="document_external_number_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "company", "document_date"], name="document_scope_idx"),
            models.Index(fields=["company", "document_type", "state"], name="document_state_idx"),
            models.Index(fields=["company", "partner_id"], name="document_partner_idx"),
            # Document -> what it produced, the direction a conversion is read in.
            models.Index(fields=["source_document"], name="document_source_idx"),
            models.Index(
                fields=["tenant", "company", "accounting_date"], name="document_accounting_idx"
            ),
        ]

    def __str__(self) -> str:
        return self.formatted_number or self.external_number or f"{self.document_type}:draft"


class DocumentLine(models.Model):
    """One position on a document.

    Shared by every type, for the same reason the header is: a line of a sale and
    a line of a purchase differ in direction, not in shape, and two tables would
    mean two answers to "what was this position worth".

    **The amounts are stored, not derived.** `net_amount`, `vat_amount` and
    `total_amount` arrive computed and the database checks only the identity that
    needs no rounding -- ``total = net + vat``. It does not check
    ``net = quantity x price - discount`` or ``vat = net x rate``, and the reason
    is not laziness: reducing either product to a stored scale is a rounding step,
    the rule for it is versioned fiscal logic selected by date (`R16`, `R17`), and
    which rule applies is open on three axes at once -- where VAT is rounded
    (line or document), in which direction at a tie, and to how many decimals
    (ADR-037 sections 3.1 to 3.3, `DNB-08`). A CHECK written before that is
    settled would encode one of the answers as if it were the law.

    **No account, no dimension, no correspondence.** Not omitted for later: the
    document layer does not decide them, and a nullable column here would be read
    as a place to put a default.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    #: Denormalised from the header so the company-scoped policy decides without a
    #: JOIN. A JOIN inside a policy on the second-largest table in the system is
    #: paid on every read of every line.
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    document = models.ForeignKey(
        Document, on_delete=models.CASCADE, db_column="document_id", related_name="lines"
    )

    #: Position on the printed document, 1-based. Ordering is data, not the
    #: order rows happen to come back in.
    line_no = models.IntegerField()

    #: The catalogue entry, or nothing -- a line may be free text. No foreign key:
    #: items live in `masterdata` and the document core is `platform`, which
    #: imports nothing. Existence is asserted by the service that writes the line,
    #: exactly as it is for `partner_id` on the header.
    item_id = models.UUIDField(null=True, blank=True)

    #: What the document says, which is not always what the catalogue says. Copied
    #: at entry so a later rename of the item cannot rewrite a document already
    #: issued. It is the **legal** name that belongs here (`C39`): the internal
    #: name exists for lists and search and never reaches a document.
    description = models.TextField()

    quantity = models.DecimalField(max_digits=AMOUNT_DIGITS, decimal_places=QUANTITY_SCALE)

    #: The unit the quantity is expressed in, and its symbol as printed. The
    #: identifier carries no foreign key, for the reason `item_id` does not; the
    #: code is copied because it is what the document shows.
    unit_id = models.UUIDField(null=True, blank=True)
    unit_code = models.TextField(default="")

    unit_price = models.DecimalField(max_digits=AMOUNT_DIGITS, decimal_places=UNIT_PRICE_SCALE)

    #: How the discount was expressed, and what it came to. Both, because a
    #: document shows the percentage and a control recomputes the amount, and
    #: keeping only one makes the other unreconstructable.
    discount_percent = models.DecimalField(
        max_digits=PERCENT_DIGITS, decimal_places=PERCENT_SCALE, null=True, blank=True
    )
    discount_amount = models.DecimalField(
        max_digits=AMOUNT_DIGITS, decimal_places=CURRENCY_SCALE, default=0
    )

    net_amount = models.DecimalField(max_digits=AMOUNT_DIGITS, decimal_places=CURRENCY_SCALE)

    #: The VAT treatment of this position, as a **code**, and the numeric rate
    #: separately. They are different facts: an exempt supply and a zero-rated
    #: export both carry 0, and a declaration that cannot tell them apart is
    #: filed wrong.
    #:
    #: The vocabulary of regimes is **not** enumerated in this repository. Which
    #: treatments exist, and what each is called, comes from the Cod fiscal and
    #: changes by act -- so it is data, resolved through `fiscal.parameters` like
    #: every other fiscal fact (`R15`), and this column stores the code it was
    #: given. The same discipline `strictforms.form_type_code` follows for the
    #: list of strict-accountability forms.
    vat_regime_code = models.TextField()

    #: The key the rate was resolved under, kept so the resolution is reproducible
    #: -- `R18`: recalculating this document has to reach the same parameter row.
    vat_rate_key = models.TextField(null=True, blank=True)

    #: The rate as a percentage, resolved from the nomenclature by the document's
    #: date and **copied**. Copied because the parameter is versioned and the
    #: document is not: reading it live would silently restate an issued invoice
    #: the day a rate changes.
    vat_rate = models.DecimalField(max_digits=PERCENT_DIGITS, decimal_places=PERCENT_SCALE)
    vat_amount = models.DecimalField(max_digits=AMOUNT_DIGITS, decimal_places=CURRENCY_SCALE)

    total_amount = models.DecimalField(max_digits=AMOUNT_DIGITS, decimal_places=CURRENCY_SCALE)

    #: The line this one was copied from -- a proforma position carried into the
    #: invoice, a position reversed by a storno. Self-referencing for the same
    #: reason the header's source is.
    source_line = models.ForeignKey(
        "self",
        on_delete=models.PROTECT,
        db_column="source_line_id",
        null=True,
        blank=True,
        related_name="derived_lines",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "document_line"
        constraints = [
            models.UniqueConstraint(
                fields=["document", "line_no"], name="document_line_position_unique"
            ),
            models.CheckConstraint(
                condition=models.Q(line_no__gte=1), name="document_line_position_positive"
            ),
            # A position of nothing is not a position. It is also how a document
            # ends up with lines that print and total to zero.
            models.CheckConstraint(
                condition=~models.Q(quantity=0), name="document_line_quantity_nonzero"
            ),
            # Exact addition, no rounding involved -- so the database can hold it
            # and a line whose three amounts disagree cannot be written at all.
            models.CheckConstraint(
                condition=models.Q(total_amount=models.F("net_amount") + models.F("vat_amount")),
                name="document_line_total_is_net_plus_vat",
            ),
            models.CheckConstraint(
                condition=models.Q(discount_percent__isnull=True)
                | (models.Q(discount_percent__gte=0) & models.Q(discount_percent__lte=100)),
                name="document_line_discount_percent_valid",
            ),
            # A negative rate is not a treatment, and no act has ever named one.
            # Signs live on the amounts, where a storno puts them.
            models.CheckConstraint(
                condition=models.Q(vat_rate__gte=0), name="document_line_vat_rate_valid"
            ),
            models.CheckConstraint(
                condition=~models.Q(vat_regime_code=""),
                name="document_line_has_a_vat_regime",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "company", "document"], name="document_line_scope_idx"),
            models.Index(fields=["company", "item_id"], name="document_line_item_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.document_id}#{self.line_no}"


class ReversalDocument(models.Model):
    """A storno: the document that undoes another one.

    Its own type, with a link that is mandatory at the database level -- which is
    the whole reason this table exists rather than a nullable column on the
    header. A storno with nothing to point at is not a storno, and a CHECK naming
    the type on the shared header would have put the type vocabulary in the schema.

    **No accounting effect here.** `R14` asks a reversing *entry* for two links --
    to the source document and to the entry it cancels -- and this is the
    documentary half of that shape, built so the accounting half can be added
    without moving it. Nothing in this module produces a journal entry.
    """

    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        db_column="document_id",
        primary_key=True,
        related_name="reversal",
    )
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    reversed_document = models.ForeignKey(
        Document,
        on_delete=models.PROTECT,
        db_column="reversed_document_id",
        related_name="reversals",
    )

    #: Why. Required, for the same reason a cancellation reason is: a correction
    #: nobody can explain is a correction nobody can defend.
    reason = models.TextField()

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "reversal_document"
        constraints = [
            # One storno per document. A second one would double the reversal,
            # and the ledger would carry it twice once posting exists.
            models.UniqueConstraint(fields=["reversed_document"], name="reversal_document_once"),
            models.CheckConstraint(
                condition=~models.Q(document=models.F("reversed_document")),
                name="reversal_document_not_itself",
            ),
            models.CheckConstraint(
                condition=~models.Q(reason=""), name="reversal_document_has_a_reason"
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "company", "reversed_document"], name="reversal_document_idx"
            ),
        ]

    def __str__(self) -> str:
        return f"storno of {self.reversed_document_id}"


class DocumentEvent(models.Model):
    """The state history of documents -- append-only, high volume (R21, R22).

    Named in the amendment's list alongside journal lines and audit events, so it
    carries the same discipline from the first migration: no incoming foreign
    keys, ``occurred_at`` NOT NULL, bigint key, indexes leading with the tenant.

    Distinct from ``audit_event``: that records who did what across the system,
    this records what happened to one document. Merging them would make the
    largest table in the system the answer to both questions, and the drill-down
    from a document would scan it.
    """

    id = models.BigAutoField(primary_key=True)

    tenant_id = models.UUIDField()
    company_id = models.UUIDField()
    document_id = models.UUIDField()

    occurred_at = models.DateTimeField()
    event_type = models.TextField()
    from_state = models.TextField(null=True, blank=True)
    to_state = models.TextField(null=True, blank=True)

    actor_user_id = models.UUIDField()
    request_id = models.TextField()
    detail = models.JSONField(null=True, blank=True)

    class Meta:
        db_table = "document_event"
        indexes = [
            models.Index(
                fields=["tenant_id", "company_id", "occurred_at"],
                name="document_event_scope_idx",
            ),
            models.Index(fields=["document_id", "occurred_at"], name="document_event_doc_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.event_type}@{self.occurred_at:%Y-%m-%d}"
