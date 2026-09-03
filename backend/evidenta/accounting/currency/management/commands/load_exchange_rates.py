"""Load exchange rates from a CSV file, under the reference-data role -- `P-3`.

The door `Spec B section 7.2` names and nothing had built: the rate of a day
reaches `exchange_rate` through here, on the connection of `evidenta_refdata`,
with one row in `privileged_access_log` per run (ADR-049). The BNM connector
(`OD-76`) will feed the same service from a fetch instead of a file; until then
the operator downloads the bulletin and loads it.

The rules are the service's (`services/loading.py`); this command keeps only what
is the file's own: finding it and reading it. See `data/README.md` for the shape,
and for why no rates ship with the repository.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from evidenta.accounting.currency.services.loading import (
    RateConflictError,
    RateFileMalformedError,
    load_rates,
    parse_rates,
)
from evidenta.platform.audit.services.privileged import (
    REFDATA_ALIAS,
    PrivilegedPath,
    privileged_run,
)

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class Command(BaseCommand):
    help = "Load exchange rates from a CSV file (P-3, ADR-049)."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("file", help="CSV file; relative names resolve in the data directory")
        parser.add_argument("--database", default=REFDATA_ALIAS)
        parser.add_argument("--actor", default=None, help="who runs the load, for the log")

    def handle(self, *args: Any, **options: Any) -> None:
        path = Path(options["file"])
        if not path.is_absolute() and not path.exists():
            path = DATA_DIR / path
        if not path.exists():
            raise CommandError(f"rates file not found: {path}")
        try:
            with path.open(encoding="utf-8", newline="") as handle:
                rows = parse_rates(handle)
        except RateFileMalformedError as error:
            raise CommandError(f"{path.name}: {error}") from error

        db = options["database"]
        try:
            with privileged_run(
                PrivilegedPath.P3_BNM_RATES,
                actor=options["actor"],
                payload={"file": path.name, "rows": len(rows)},
                using=db,
            ) as run:
                outcome = load_rates(rows, using=db)
                run.payload.update({"created": outcome.created, "unchanged": outcome.unchanged})
        except RateConflictError as error:
            raise CommandError(f"{path.name}: {error}") from error

        self.stdout.write(
            f"{path.name}: {outcome.created} cursuri noi, {outcome.unchanged} neschimbate"
        )
