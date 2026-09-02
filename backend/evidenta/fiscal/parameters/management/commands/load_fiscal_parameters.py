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
* **Logic versions ride the same file.** A `[[logic]]` entry names which
  registered implementation runs from when (`R17`) -- the tie-direction of
  rounding, for one -- and is matched on `(logic_key, version)`. Same rules:
  draft in, no edit of an active row, the act's `effective_from` required.

The file format is TOML, chosen for one property: the source citation sits next
to the value it justifies, in a form a reviewer reads without a schema. See
`data/platform_conventions.toml` for the shape.

The rules themselves live in `services/authoring.py` since ADR-076 gave the
table a second writer -- the console. This command keeps only what is the file's
own: resolving `[[act]]` references and reading TOML.
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
    FiscalParameterSource,
    ParameterScope,
    SourceConfidence,
)
from evidenta.fiscal.parameters.services.authoring import (
    AuthoringError,
    ParameterDraft,
    register_source,
    write_parameter,
)
from evidenta.fiscal.registry.services import versions as logic_versions
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
    logic_created: int = 0
    logic_unchanged: int = 0


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
        logic = document.get("logic", [])

        db = options["database"]
        with privileged_run(
            PrivilegedPath.P4_FISCAL_RULES,
            actor=options["actor"],
            payload={"file": path.name},
            using=db,
        ) as run:
            outcome = self._load(acts, parameters, logic, db)
            run.payload.update(
                {
                    "acts": outcome.acts,
                    "created": outcome.created,
                    "updated": outcome.updated,
                    "unchanged": outcome.unchanged,
                    "logic_created": outcome.logic_created,
                    "logic_unchanged": outcome.logic_unchanged,
                }
            )

        self.stdout.write(
            f"{path.name}: {outcome.acts} acte, {outcome.created} parametri noi, "
            f"{outcome.updated} actualizați, {outcome.unchanged} neschimbați; "
            f"{outcome.logic_created} versiuni de logică noi, {outcome.logic_unchanged} neschimbate"
        )

    def _load(
        self,
        acts: dict[str, Act],
        parameters: list[dict[str, Any]],
        logic: list[dict[str, Any]],
        db: str,
    ) -> Outcome:
        # The source rows, through the same door the console uses (ADR-076):
        # `register_source` refuses an act with no `effective_from`, and the file
        # loader records that act in the registry regardless -- a citation is a
        # citation -- while every parameter naming it is refused below.
        sources: dict[str, FiscalParameterSource] = {}
        for ref, act in acts.items():
            if act.effective_from is None:
                register_act(act, using=db)
                continue
            sources[ref] = register_source(act, using=db)

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
            if "value" not in entry:
                raise CommandError(f"parameter {key!r}: no `value`")
            # `OD-92`: the file names the act whose final article sets the margin,
            # which need not be the act the value was read in. Resolving that
            # reference is the file's business; the rule about what a margin
            # needs is the service's.
            margin_act: Act | None = None
            if entry.get("valid_from") and entry.get("margin_basis") == "act":
                margin_ref = entry.get("margin_act", act_ref)
                if margin_ref not in sources:
                    raise CommandError(
                        f"parameter {key!r}: `margin_act` {margin_ref!r} is not an "
                        f"[[act]] in this file -- OD-92 wants the act whose final "
                        f"article sets the margin, which need not be the act the "
                        f"value was read in"
                    )
                margin_act = acts[margin_ref]
            draft = ParameterDraft(
                key=str(key),
                value_type=str(entry.get("value_type")),
                value=entry["value"],
                act=acts[act_ref],
                unit=entry.get("unit"),
                scope=entry.get("scope", ParameterScope.GLOBAL),
                scope_ref=uuid.UUID(str(entry["scope_ref"])) if entry.get("scope_ref") else None,
                valid_from=(
                    _date(entry["valid_from"], f"parameter {key!r}")
                    if entry.get("valid_from")
                    else None
                ),
                valid_to=(
                    _date(entry["valid_to"], f"parameter {key!r}")
                    if entry.get("valid_to")
                    else None
                ),
                margin_basis=entry.get("margin_basis"),
                margin_reference=entry.get("margin_reference"),
                margin_act=margin_act,
                observed_in=entry.get("observed_in"),
                confidence=entry.get("confidence", SourceConfidence.PROVISIONAL),
                provisional_reason=entry.get("provisional_reason"),
            )
            try:
                written = write_parameter(draft, using=db)
            except AuthoringError as error:
                raise CommandError(str(error)) from error
            if written.outcome == "created":
                created += 1
            elif written.outcome == "updated":
                updated += 1
            else:
                unchanged += 1

        logic_created = logic_unchanged = 0
        for entry in logic:
            key = entry.get("logic_key")
            if not key:
                raise CommandError("a [[logic]] entry has no `logic_key`")
            act_ref = entry.get("act")
            if act_ref not in sources:
                raise CommandError(
                    f"logic {key!r}: act {act_ref!r} is not declared with an `effective_from`"
                )
            for field in ("implementation_ref", "version", "valid_from", "regression_case_set"):
                if entry.get(field) in (None, ""):
                    raise CommandError(f"logic {key!r}: `{field}` is required")
            valid_from = _date(entry["valid_from"], f"logic {key!r}")
            known = logic_versions.find_version(key, str(entry["version"]), using=db)
            if known is None:
                logic_versions.register_version(
                    logic_key=key,
                    version=str(entry["version"]),
                    implementation_ref=str(entry["implementation_ref"]),
                    valid_from=valid_from,
                    valid_to=(
                        _date(entry["valid_to"], f"logic {key!r}")
                        if entry.get("valid_to")
                        else None
                    ),
                    source_id=uuid.UUID(str(sources[act_ref].pk)),
                    regression_case_set=str(entry["regression_case_set"]),
                    using=db,
                )
                logic_created += 1
                continue
            if (
                known.implementation_ref != str(entry["implementation_ref"])
                or known.valid_from != valid_from
            ) and known.status == logic_versions.ACTIVE:
                raise CommandError(
                    f"logic {key!r} version {entry['version']!r} is active with "
                    f"{known.implementation_ref!r} from {known.valid_from}; an active "
                    f"version is not edited -- a change is a new version"
                )
            logic_unchanged += 1

        return Outcome(
            acts=len(acts),
            created=created,
            updated=updated,
            unchanged=unchanged,
            logic_created=logic_created,
            logic_unchanged=logic_unchanged,
        )
