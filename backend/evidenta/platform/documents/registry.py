"""The `document_type` vocabulary -- a registry, not a column of free text.

The core owns the mechanism; the modules that own the types **register** them.
That inversion is what keeps the graph intact: `operations.sales` calls
`documents.register(...)`, so `platform` never imports `operations`, and a type
nobody registered cannot be created at all.

The alternative -- a `TextChoices` here listing every document a Moldovan entity
can issue -- was rejected for the reason the list itself gives: it is not
consolidated, it changes by government decision (the delivery note and the
waybill left the strict-accountability nomenclature through HG 229/2024), and
half of it belongs to phases that do not exist yet. A closed enum in `platform`
would have to be edited by every module above it.

**What a spec may say and what it may not.** It declares documentary facts: does
this type need a counterparty, does it carry positions, what may it be converted
into. It declares nothing about accounts, correspondence or postings -- those are
not properties of a document type, and a field for them here would be the place a
default account eventually got written.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

#: Two segments, `snake_case` in both -- the same shape the accounting event
#: vocabulary uses (ADR-038). One naming convention across two closed
#: vocabularies, because two conventions means half the codes are written wrong
#: before anybody notices.
NAME = re.compile(r"^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$")


class RegistryError(RuntimeError):
    """A stable code, not only a message (C10)."""

    code = "documents.registry_error"

    def __init__(self, message: str) -> None:
        super().__init__(f"{self.code}: {message}")


class MalformedDocumentTypeError(RegistryError):
    code = "documents.type_malformed"


class DuplicateDocumentTypeError(RegistryError):
    code = "documents.type_duplicate"


class UnknownDocumentTypeError(RegistryError):
    code = "documents.type_unknown"


@dataclass(frozen=True, slots=True)
class DocumentTypeSpec:
    """What the core needs to know about one kind of document.

    ``owner`` is the app label that registered it, kept so a boot check can say
    which module a type came from rather than reporting an orphan.
    """

    code: str
    owner: str

    #: Whether a counterparty is required at validation. A sale without a buyer
    #: is not a sale; an internal document may legitimately have none. Checked at
    #: validation rather than at creation, because a draft is allowed to be
    #: incomplete -- that is what a draft is.
    requires_partner: bool = True

    #: Whether the type carries positions. Everything in the current scope does;
    #: the flag exists because the first type that does not (a payment order, a
    #: certificate) must not have to widen the validation rule to arrive.
    carries_lines: bool = True

    #: Whether validation demands at least one position. Distinct from
    #: `carries_lines`: an order may legitimately be validated empty and filled
    #: later, an invoice may not.
    requires_lines: bool = True

    #: Types this one may be turned into -- proforma into sale, order into
    #: purchase. Empty means the document is an end in itself.
    converts_into: tuple[str, ...] = field(default_factory=tuple)

    #: Whether this type is a reversal, which is the only type whose creation
    #: goes through `services.reversal` and whose row in `reversal_document`
    #: makes the link to the original mandatory.
    is_reversal: bool = False


#: Registered types, by code. Populated from `AppConfig.ready()`, the same place
#: `slots` fills the account-role catalogue.
REGISTRY: dict[str, DocumentTypeSpec] = {}


def register(spec: DocumentTypeSpec) -> DocumentTypeSpec:
    """Add one type to the vocabulary.

    Refuses a duplicate rather than overwriting. Two registrations of one code
    means two answers about whether a partner is required, one of them silently
    in force -- the failure shape the RLS contract and the dependency contract
    both guard against by name.
    """
    if not NAME.match(spec.code):
        raise MalformedDocumentTypeError(
            f"{spec.code!r} is not a document type name: two dot-separated "
            f"snake_case segments, as in 'sales.document'"
        )
    existing = REGISTRY.get(spec.code)
    if existing is not None and existing != spec:
        raise DuplicateDocumentTypeError(
            f"{spec.code!r} is already registered by {existing.owner!r} with a "
            f"different declaration; a vocabulary with two answers for one code "
            f"has no answer"
        )
    REGISTRY[spec.code] = spec
    return spec


def spec_for(code: str) -> DocumentTypeSpec:
    """The declaration for a type, or a refusal.

    Never a default. A document created under a type nobody declared would carry
    validation rules nobody chose, and it would be discovered by whatever failed
    downstream rather than here.
    """
    spec = REGISTRY.get(code)
    if spec is None:
        raise UnknownDocumentTypeError(
            f"{code!r} is not a registered document type. Registered: "
            f"{sorted(REGISTRY) or 'nothing yet'}"
        )
    return spec


def registered() -> tuple[DocumentTypeSpec, ...]:
    """Every declared type, ordered by code so the listing is stable."""
    return tuple(REGISTRY[code] for code in sorted(REGISTRY))


def types_owned_by(owner: str) -> tuple[str, ...]:
    """Every registered type one module owns, in a stable order.

    Exists so a report can name a **family** without naming its codes. The journal
    of sales documents is a report of *what `sales` issues*, and spelling
    `("sales.document",)` into `accounting` would put another module's vocabulary
    in this one -- the same coupling `D6` refuses at the level of tables, one
    layer up.

    Sorted, because a report's columns and a CSV's rows must not reorder
    themselves when a module registers a second type.
    """
    return tuple(sorted(spec.code for spec in REGISTRY.values() if spec.owner == owner))


def conversion_targets(code: str) -> tuple[str, ...]:
    """What this type may become. Empty is an answer, not a missing one."""
    return spec_for(code).converts_into
