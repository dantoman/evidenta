"""Writing the registry of logic versions -- the public door for the loaders (D6).

`resolve_logic` answers "which implementation runs on this date"; this module
answers the loader's questions: is this version registered, register it as a
draft, activate it as the named approver. Rows leave here as a frozen dataclass,
never as the model, so `fiscal.parameters` (which hosts the loading commands)
does not import `fiscal.registry`'s models.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, date, datetime

from evidenta.fiscal.registry.models import FiscalLogicVersion, LogicStatus

DRAFT = LogicStatus.DRAFT
ACTIVE = LogicStatus.ACTIVE


@dataclass(frozen=True, slots=True)
class VersionRow:
    id: uuid.UUID
    logic_key: str
    version: str
    implementation_ref: str
    valid_from: date
    status: str


def _row(model: FiscalLogicVersion) -> VersionRow:
    return VersionRow(
        id=uuid.UUID(str(model.pk)),
        logic_key=model.logic_key,
        version=model.version,
        implementation_ref=model.implementation_ref,
        valid_from=model.valid_from,
        status=model.status,
    )


def find_version(logic_key: str, version: str, *, using: str) -> VersionRow | None:
    model = (
        FiscalLogicVersion.objects.using(using).filter(logic_key=logic_key, version=version).first()
    )
    return None if model is None else _row(model)


def register_version(
    *,
    logic_key: str,
    version: str,
    implementation_ref: str,
    valid_from: date,
    valid_to: date | None,
    source_id: uuid.UUID,
    regression_case_set: str,
    using: str,
) -> VersionRow:
    """A new version, as a draft. Activation is a separate act (`activate_version`)."""
    model = FiscalLogicVersion.objects.using(using).create(
        logic_key=logic_key,
        version=version,
        implementation_ref=implementation_ref,
        valid_from=valid_from,
        valid_to=valid_to,
        source_id=source_id,
        regression_case_set=regression_case_set,
        status=LogicStatus.DRAFT,
    )
    return _row(model)


def activate_version(version_id: uuid.UUID, *, approver: uuid.UUID, using: str) -> VersionRow:
    model = FiscalLogicVersion.objects.using(using).get(pk=version_id)
    model.status = LogicStatus.ACTIVE
    model.approved_by_user_id = approver
    model.approved_at = datetime.now(tz=UTC)
    model.save(
        using=using, update_fields=["status", "approved_by_user_id", "approved_at", "updated_at"]
    )
    return _row(model)
