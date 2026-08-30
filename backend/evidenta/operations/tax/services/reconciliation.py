"""The population reconciliation, both directions -- `T1`.

> Every person with a social-contribution charge in period `P` appears as a
> nominal row in the return for `P` -- **and every nominal row has a charge**.

**The converse matters as much**, and that half is the one nobody writes: a
nominal row without a charge is a person declared as insured who was not, which
CNAS reads as a period of insurance that did not happen.

**The two sides are read from different places, deliberately.** The return's rows
are frozen artefacts; the charges are read straight from the payroll lines by
`charged_person_ids`, which is not the function the generator used. A comparison
whose two sides come from one source is an echo -- exactly the shape measured at
`P1`, where a manual list agreed with the generator that had corrected it.

**Not a guard over the build.** It is a reading a person asks for: the screen
shows it before a return is filed, and the test drives it. What makes it worth
anything is that it has been seen failing on a fixture -- on an empty database it
passes vacuously, which is the failure mode it would otherwise have.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from evidenta.operations.payroll.services.insured import charged_person_ids
from evidenta.operations.tax.models import IpcDeclaration, IpcNominalLine
from evidenta.operations.tax.services.ipc import IpcNotFoundError


@dataclass(frozen=True, slots=True)
class Reconciliation:
    """What the two sides disagree about, named from both directions."""

    #: Charged in the period, absent from the return.
    missing: tuple[uuid.UUID, ...]

    #: Declared in the return, with no charge in the period.
    extra: tuple[uuid.UUID, ...]

    #: How many people each side holds -- so a reconciliation over an empty
    #: period is visibly empty rather than quietly green.
    charged_count: int
    declared_count: int

    @property
    def agrees(self) -> bool:
        return not self.missing and not self.extra


def reconcile(*, declaration_id: uuid.UUID) -> Reconciliation:
    declaration = IpcDeclaration.objects.filter(id=declaration_id).first()
    if declaration is None:
        raise IpcNotFoundError("no such return in this context")

    charged = charged_person_ids(
        company_id=declaration.company_id,
        year=declaration.year,
        month=declaration.month,
    )
    declared = set(
        IpcNominalLine.objects.filter(declaration=declaration).values_list("person_id", flat=True)
    )

    return Reconciliation(
        missing=tuple(sorted(charged - declared)),
        extra=tuple(sorted(declared - charged)),
        charged_count=len(charged),
        declared_count=len(declared),
    )


def reconciliation_report(*, declaration_id: uuid.UUID) -> dict[str, Any]:
    result = reconcile(declaration_id=declaration_id)
    return {
        "agrees": result.agrees,
        "charged_count": result.charged_count,
        "declared_count": result.declared_count,
        "missing": [str(person) for person in result.missing],
        "extra": [str(person) for person in result.extra],
    }
