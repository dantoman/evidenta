"""Turn the draft parameters of a file active -- the practising accountant's act.

`load_fiscal_parameters` writes `draft` and cannot do otherwise: a file carries
no approval (amendment D.1, `fiscal_parameter_active_requires_approval`). This
command is the approval. It takes the same file, so what is activated is exactly
what was reviewed, and it takes the approver's user id, which lands on every row
and on the `privileged_access_log` entry -- one row per run, `P-4`, with the
actor's identity, not just the OS login.

It activates only rows that are `draft` and match the file; a row already active
is left alone and counted, a row whose value differs from the file is refused --
approving the file must not approve something else.
"""

from __future__ import annotations

import tomllib
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from evidenta.fiscal.parameters.management.commands.load_fiscal_parameters import (
    DATA_DIR,
    SCHEMA_VERSION,
)
from evidenta.fiscal.parameters.models import FiscalParameter, ParameterScope, ParameterStatus
from evidenta.fiscal.registry.services import versions as logic_versions
from evidenta.platform.audit.services.privileged import (
    REFDATA_ALIAS,
    PrivilegedPath,
    privileged_run,
)


class Command(BaseCommand):
    help = "Activate the draft parameters of a TOML file, as the named approver (P-4, ADR-049)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("file")
        parser.add_argument("--approver", required=True, help="user id of the approving accountant")
        parser.add_argument("--database", default=REFDATA_ALIAS)
        parser.add_argument("--actor", default=None)

    def handle(self, *args: Any, **options: Any) -> None:
        path = Path(options["file"])
        if not path.is_absolute() and not path.exists():
            path = DATA_DIR / path
        if not path.exists():
            raise CommandError(f"data file not found: {path}")
        try:
            approver = uuid.UUID(str(options["approver"]))
        except ValueError as error:
            raise CommandError("--approver must be a user id (uuid)") from error
        with path.open("rb") as handle:
            document = tomllib.load(handle)
        if document.get("schema_version") != SCHEMA_VERSION:
            raise CommandError(f"{path.name}: schema_version is not {SCHEMA_VERSION}")

        db = options["database"]
        activated = already = 0
        with privileged_run(
            PrivilegedPath.P4_FISCAL_RULES,
            actor=options["actor"],
            actor_user_id=approver,
            payload={"file": path.name, "operation": "activate"},
            using=db,
        ) as run:
            for entry in document.get("parameter", []):
                row = (
                    FiscalParameter.objects.using(db)
                    .filter(
                        parameter_key=entry["key"],
                        scope=entry.get("scope", ParameterScope.GLOBAL),
                        scope_ref=(
                            uuid.UUID(str(entry["scope_ref"])) if entry.get("scope_ref") else None
                        ),
                        valid_from=entry["valid_from"],
                    )
                    .first()
                )
                if row is None:
                    raise CommandError(
                        f"parameter {entry['key']!r} valid from {entry['valid_from']} is not "
                        f"loaded; run load_fiscal_parameters first"
                    )
                if row.value != entry["value"]:
                    raise CommandError(
                        f"parameter {entry['key']!r}: the database holds {row.value!r}, the file "
                        f"says {entry['value']!r}; approving the file would approve something else"
                    )
                if row.status == ParameterStatus.ACTIVE:
                    already += 1
                    continue
                if row.status != ParameterStatus.DRAFT:
                    raise CommandError(
                        f"parameter {entry['key']!r} is {row.status}; only a draft is "
                        f"activated here"
                    )
                row.status = ParameterStatus.ACTIVE
                row.approved_by_user_id = approver
                row.approved_at = datetime.now(tz=UTC)
                row.save(
                    using=db,
                    update_fields=["status", "approved_by_user_id", "approved_at", "updated_at"],
                )
                activated += 1
            for entry in document.get("logic", []):
                version = logic_versions.find_version(
                    entry["logic_key"], str(entry["version"]), using=db
                )
                if version is None:
                    raise CommandError(
                        f"logic {entry['logic_key']!r} version {entry['version']!r} is not loaded"
                    )
                if version.implementation_ref != str(entry["implementation_ref"]):
                    raise CommandError(
                        f"logic {entry['logic_key']!r}: the database holds "
                        f"{version.implementation_ref!r}, the file says "
                        f"{entry['implementation_ref']!r}; approving the file would approve "
                        f"something else"
                    )
                if version.status == logic_versions.ACTIVE:
                    already += 1
                    continue
                if version.status != logic_versions.DRAFT:
                    raise CommandError(f"logic {entry['logic_key']!r} is {version.status}")
                logic_versions.activate_version(version.id, approver=approver, using=db)
                activated += 1
            run.payload.update({"activated": activated, "already_active": already})

        self.stdout.write(f"{path.name}: {activated} activați, {already} erau deja activi")
