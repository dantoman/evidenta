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

from evidenta.fiscal.registry.models import EmploymentRelationshipType


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
