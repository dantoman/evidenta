"""Load fiscal parameters from a file, under the reference-data role -- `P-4`.

This is the write path `OD-67` said did not exist. The rules it enforces are the
ones `R15` states and the model constrains, restated at the door so a mistake
reads as what it is:

* **Every parameter names its act, and every act carries its identity in full**
  -- type, number, date -- plus the date it entered into force. A parameter whose
  act has no `effective_from` is refused: "the rate was 20%" is not an answer
  without "under which act, from when".
* **Nothing goes live from a file.** Rows are written `draft` (or keep the status
  they have). Activation is the practising accountant's act (amendment D.1,
  `fiscal_parameter_active_requires_approval`), and a file cannot carry an
  approval.
* **An active value is never edited.** A different value from the same date is a
  new row with a new `valid_from` (`R15`, `R18`) -- and that is a decision, not a
  load. The command refuses and names the row.
* **Provisional means provisional with a reason** -- the constraint says so, and
  the file has to say it too.
* **Idempotent.** A parameter is matched on `(key, scope, scope_ref,
  valid_from)`; the second run writes nothing and says so. Every run leaves one
  row in `privileged_access_log`.

The file format is TOML, chosen for one property: the source citation sits next
to the value it justifies, in a form a reviewer reads without a schema. See
`data/platform_conventions.toml` for the shape.
"""

from __future__ import annotations

import tomllib
import uuid
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from evidenta.fiscal.parameters.models import (
    FiscalParameter,
    FiscalParameterSource,
    ParameterScope,
    ParameterStatus,
    SourceConfidence,
    ValueType,
)
from evidenta.platform.audit.services.privileged import (
    REFDATA_ALIAS,
    PrivilegedPath,
    privileged_run,
)
from evidenta.platform.legislation.services.registry import Act, Publication, register_act

DATA_DIR = Path(__file__).resolve().parents[2] / "data"

SCHEMA_VERSION = 1


@dataclass(frozen=True, slots=True)
class Outcome:
    acts: int = 0
    created: int = 0
    updated: int = 0
    unchanged: int = 0


def _date(value: Any, where: str) -> date:
    if isinstance(value, date):
        return value
    raise CommandError(f"{where}: expected a date (YYYY-MM-DD), got {value!r}")


def _act(entry: dict[str, Any]) -> Act:
    ref = entry.get("ref")
    if not ref:
        raise CommandError("an [[act]] entry has no `ref`; parameters name their act by it")
    for field in ("act_type", "act_number", "act_date", "title"):
        if not entry.get(field):
            raise CommandError(f"act {ref!r}: `{field}` is required -- an act is cited in full")
    publications = []
    for pub in entry.get("publications", []):
        for field in ("gazette_year", "gazette_number", "article"):
            if pub.get(field) in (None, ""):
                raise CommandError(
                    f"act {ref!r}: a publication needs `gazette_year`, `gazette_number` and "
                    f"`article` -- an issue number without the article is a magazine"
                )
        publications.append(
            Publication(
                gazette_year=int(pub["gazette_year"]),
                gazette_number=str(pub["gazette_number"]),
                article=str(pub["article"]),
                published_at=(
                    _date(pub["published_at"], f"act {ref!r}") if pub.get("published_at") else None
                ),
                role=pub.get("role"),
                url=pub.get("url"),
            )
        )
    return Act(
        act_type=str(entry["act_type"]),
        act_number=str(entry["act_number"]),
        act_date=_date(entry["act_date"], f"act {ref!r}"),
        title=str(entry["title"]),
        effective_from=(
            _date(entry["effective_from"], f"act {ref!r}") if entry.get("effective_from") else None
        ),
        url=entry.get("url"),
        notes=entry.get("notes"),
        publications=tuple(publications),
    )


class Command(BaseCommand):
    help = "Load fiscal parameters and their acts from a TOML file (P-4, ADR-049)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("file", help="TOML file; relative names resolve in the data directory")
        parser.add_argument("--database", default=REFDATA_ALIAS)
        parser.add_argument("--actor", default=None, help="who runs the load, for the log")

    def handle(self, *args: Any, **options: Any) -> None:
        path = Path(options["file"])
        if not path.is_absolute() and not path.exists():
            path = DATA_DIR / path
        if not path.exists():
            raise CommandError(f"data file not found: {path}")
        with path.open("rb") as handle:
            document = tomllib.load(handle)
        if document.get("schema_version") != SCHEMA_VERSION:
            raise CommandError(
                f"{path.name}: schema_version {document.get('schema_version')!r}, "
                f"this loader reads {SCHEMA_VERSION}"
            )

        acts = {entry.get("ref"): _act(entry) for entry in document.get("act", [])}
        parameters = document.get("parameter", [])

        db = options["database"]
        with privileged_run(
            PrivilegedPath.P4_FISCAL_RULES,
            actor=options["actor"],
            payload={"file": path.name},
            using=db,
        ) as run:
            outcome = self._load(acts, parameters, db)
            run.payload.update(
                {
                    "acts": outcome.acts,
                    "created": outcome.created,
                    "updated": outcome.updated,
                    "unchanged": outcome.unchanged,
                }
            )

        self.stdout.write(
            f"{path.name}: {outcome.acts} acte, {outcome.created} parametri noi, "
            f"{outcome.updated} actualizați, {outcome.unchanged} neschimbați"
        )

    def _load(self, acts: dict[str, Act], parameters: list[dict[str, Any]], db: str) -> Outcome:
        sources: dict[str, FiscalParameterSource] = {}
        for ref, act in acts.items():
            row = register_act(act, using=db)
            # The fiscal source row is the act as the resolver knows it; the
            # registry row is the act as a citation. One points at the other.
            if act.effective_from is None:
                # Recorded in the registry regardless -- a parameter that names
                # this act is what gets refused, below.
                continue
            source, _ = FiscalParameterSource.objects.using(db).update_or_create(
                act_type=act.act_type,
                act_number=act.act_number,
                act_date=act.act_date,
                defaults={
                    "effective_from": act.effective_from,
                    "url": act.url,
                    "notes": act.notes,
                    "act": row,
                },
            )
            sources[ref] = source

        created = updated = unchanged = 0
        for entry in parameters:
            key = entry.get("key")
            if not key:
                raise CommandError("a [[parameter]] entry has no `key`")
            act_ref = entry.get("act")
            if act_ref not in acts:
                raise CommandError(
                    f"parameter {key!r}: act {act_ref!r} is not declared in the file"
                )
            if act_ref not in sources:
                raise CommandError(
                    f"parameter {key!r}: act {act_ref!r} has no `effective_from`. R15 wants the "
                    f"date the act entered into force; a value without it cannot be defended"
                )
            value_type = entry.get("value_type")
            if value_type not in ValueType.values:
                raise CommandError(
                    f"parameter {key!r}: value_type {value_type!r} is not one of {ValueType.values}"
                )
            scope = entry.get("scope", ParameterScope.GLOBAL)
            if scope not in ParameterScope.values:
                raise CommandError(
                    f"parameter {key!r}: scope {scope!r} is not one of {ParameterScope.values}"
                )
            scope_ref = uuid.UUID(str(entry["scope_ref"])) if entry.get("scope_ref") else None
            confidence = entry.get("confidence", SourceConfidence.PROVISIONAL)
            if confidence not in SourceConfidence.values:
                raise CommandError(
                    f"parameter {key!r}: confidence {confidence!r} is not one of "
                    f"{SourceConfidence.values}"
                )
            reason = entry.get("provisional_reason")
            if confidence == SourceConfidence.PROVISIONAL and not (reason or "").strip():
                raise CommandError(
                    f"parameter {key!r}: a provisional value states what the inference rests on"
                )
            if "value" not in entry:
                raise CommandError(f"parameter {key!r}: no `value`")
            valid_from = _date(entry.get("valid_from"), f"parameter {key!r}")
            valid_to = (
                _date(entry["valid_to"], f"parameter {key!r}") if entry.get("valid_to") else None
            )

            fields = {
                "value_type": value_type,
                "value": entry["value"],
                "unit": entry.get("unit"),
                "valid_to": valid_to,
                "source": sources[act_ref],
                "source_confidence": confidence,
                "provisional_reason": reason
                if confidence == SourceConfidence.PROVISIONAL
                else None,
            }
            existing = (
                FiscalParameter.objects.using(db)
                .filter(parameter_key=key, scope=scope, scope_ref=scope_ref, valid_from=valid_from)
                .first()
            )
            if existing is None:
                FiscalParameter.objects.using(db).create(
                    parameter_key=key,
                    scope=scope,
                    scope_ref=scope_ref,
                    valid_from=valid_from,
                    status=ParameterStatus.DRAFT,
                    **fields,
                )
                created += 1
                continue

            changed = {
                name: value
                for name, value in fields.items()
                if (
                    getattr(existing, name + "_id") if name == "source" else getattr(existing, name)
                )
                != (value.pk if name == "source" else value)
            }
            if not changed:
                unchanged += 1
                continue
            if existing.status == ParameterStatus.ACTIVE and (
                "value" in changed or "value_type" in changed or "unit" in changed
            ):
                raise CommandError(
                    f"parameter {key!r} valid from {valid_from} is active with value "
                    f"{existing.value!r}; the file says {entry['value']!r}. An active value is "
                    f"not edited (R15): a new value is a new row with its own valid_from"
                )
            for name, value in changed.items():
                setattr(existing, name, value)
            existing.save(using=db, update_fields=[*changed, "updated_at"])
            updated += 1

        return Outcome(acts=len(acts), created=created, updated=updated, unchanged=unchanged)
