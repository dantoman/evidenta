"""The public reading of the work-relationship vocabulary -- ADR-071.

A module that needs the three forms asks here rather than importing the model
(`D6`). The reason is not ceremony: `operations` reaching into `fiscal`'s models
would make the shape of a fiscal table part of the contract every caller depends
on, and the caller that then adds a column to its query is the one nobody
reviews.

**One list, not a copy.** The interface form needs these codes; a second list
maintained in the frontend or in `payroll` would be a second list that drifts,
and the drift would show up as a foreign key violation at the worst moment.
"""

from __future__ import annotations

from dataclasses import dataclass

from evidenta.fiscal.registry.models import (
    CalculationInvariantDomain,
    EmploymentRelationshipType,
)


@dataclass(frozen=True, slots=True)
class RelationshipType:
    code: str
    statutory_reference: str


def relationship_types() -> list[RelationshipType]:
    """The vocabulary, in code order. Three rows, and never a fourth silently."""
    return [
        RelationshipType(code=row.code, statutory_reference=row.statutory_reference)
        for row in EmploymentRelationshipType.objects.order_by("code")
    ]


#: The key the minimum-base invariant of art. 22 para (1) is registered under.
#: Named here so a caller asks for a constant rather than retyping a string that
#: nothing would check.
MINIMUM_BASE_INVARIANT = "cas.minimum_base_per_employee"


def invariant_domain(invariant_key: str) -> frozenset[str]:
    """The relationship types an invariant applies to -- a **set** (`OD-106`).

    Returns a set even when it holds one element, and callers must treat it as
    one. The single-value shape is what would let art. 22 bind to
    `employment_contract` and leave `service_relationship` out -- a contribution
    below the minimum, perfectly balanced, invisible to every balance test.

    An empty set is not "applies everywhere". A caller that gets one has asked
    about an invariant whose domain was never declared, and applying it anyway is
    the omission this table exists to make impossible.
    """
    return frozenset(
        CalculationInvariantDomain.objects.filter(invariant_key=invariant_key).values_list(
            "relationship_type_id", flat=True
        )
    )
