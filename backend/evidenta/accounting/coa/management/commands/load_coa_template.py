"""Load a published chart-of-accounts version from its data file.

Runs under the reference-data role (ADR-049, `P-10`): ``coa_template`` and
``coa_template_account`` are global tables whose writes are revoked from the
application role (``infra/rls/exceptions.toml``, ``policy_shape =
"global_read_only"``, ``writer_role = "evidenta_refdata"``). The connection is
obtained through ``privileged_run``, which is also what writes the
``privileged_access_log`` row the path owes -- one row per run, in the same
transaction as the rows it loads. Until ADR-049 this ran as the owner, through a
policy ``0044`` had to add for it; ``0060`` retracted that policy, so the owner
connection is refused here now, on purpose.

**Idempotent and re-runnable.** Accounts are matched on ``(template,
account_code)``, which is the table's own unique key: a second run updates what
changed and creates what is missing. That match is a **read**, and it passes
through the writer's ``FOR ALL`` policy. Narrowing that policy to ``FOR
INSERT``/``FOR UPDATE`` would leave this command inserting everything on every
run. The dependency is asserted, not merely noted, in
``tests/schema_guard/test_reference_load_policy.py``. Nothing is deleted, ever. A
code that disappears from the file is reported and left in place: charts built on
this version reference these rows, and deleting one would silently unlink a
company's account from the version it was copied from.

The content is not typed in here. It is transcribed in
``data/snc_2020.csv`` from the repository's own extraction of the act
(``docs/_input/cercetare/od-23-nomenclatorul-planului-de-conturi.md``), which was
read out of the Ministry of Finance PDF and checked round-trip. Names carry the
act's own spelling, including the "î" forms, and nothing is normalised.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError

from evidenta.accounting.coa.dimensions import DIMENSION_KEYS, SLOT_COUNT, SLOT_FIELDS
from evidenta.accounting.coa.models import CoaTemplate, CoaTemplateAccount, TemplateStatus
from evidenta.platform.audit.services.privileged import (
    REFDATA_ALIAS,
    PrivilegedPath,
    privileged_run,
)
from evidenta.platform.legislation.services.registry import Act, Publication, register_act

DATA = Path(__file__).resolve().parents[2] / "data" / "snc_2020.csv"

#: Two optional columns, pipe-separated -- `partner|contract` -- ADR-048. Absent
#: from the file today, on purpose: which accounts carry which dimensions is the
#: owner's accounting decision, and the loader is the way it arrives as **data**,
#: in the same file as the accounts, rather than as an edit to a service.
SLOTS_COLUMN = "dimension_slots"
REQUIRED_COLUMN = "required_dimensions"

#: Provenance, from the act itself. `R15` wants the Monitorul Oficial number as
#: part of it, and this act has two.
#:
#: **The second one is not this act's annex, and the first version of this line
#: said it was.** The consolidated texts the Ministry publishes each print two
#: citations, and the second is *the same on both orders*: OMF 118/2013 (the
#: standards) carries `177-181 art.1224` and `233-237 art.1534`; OMF 119/2013
#: (this one, the chart of accounts) carries `177-181 art.1225` and the same
#: `233-237 art.1534`. One position in Monitorul Oficial covering two acts is a
#: different fact from one act having two publications, and it is the fact that
#: kills the obvious fix: a second pair of columns cannot be shared between two
#: rows. `OD-65` is recorded with the evidence.
DEFAULTS: dict[str, Any] = {
    "valid_from": "2020-01-01",
    "source_act": (
        "Ordinul Ministerului Finanțelor nr. 119 din 06.08.2013, "
        "nomenclator în redacția Ordinului nr. 100 din 28.06.2019, în vigoare 01.01.2020"
    ),
    "source_reference": (
        "Monitorul Oficial nr. 177-181 art. 1225 din 16.08.2013; "
        "a doua publicare, comună cu Ordinul nr. 118/2013: "
        "Monitorul Oficial nr. 233-237 art. 1534 din 22.10.2013"
    ),
    "published_at": "2013-08-16",
    "status": TemplateStatus.PUBLISHED,
}

#: The same act, as rows (ADR-049, OD-65): one act, two publications, the second
#: shared with OMF 118/2013 -- which is why it is a row and not a column.
ACT = Act(
    act_type="ordin_mf",
    act_number="119",
    act_date=date(2013, 8, 6),
    title=(
        "Ordinul Ministerului Finanțelor nr. 119 din 06.08.2013 privind aprobarea "
        "Planului general de conturi contabile"
    ),
    effective_from=date(2014, 1, 1),
    notes="Nomenclatorul în redacția Ordinului MF nr. 100 din 28.06.2019, în vigoare 01.01.2020.",
    publications=(
        Publication(2013, "177-181", "1225", published_at=date(2013, 8, 16), role="initial"),
        Publication(
            2013,
            "233-237",
            "1534",
            published_at=date(2013, 10, 22),
            role="a doua publicare, comună cu Ordinul MF nr. 118 din 06.08.2013",
        ),
    ),
)

COPIED = (
    "name_ro",
    "account_class",
    "normal_balance",
    "allows_subaccounts",
    "parent_code",
    "valid_from",
    "required_dimensions",
    *SLOT_FIELDS,
)


def _names(value: str | None, column: str, code: str) -> list[str]:
    """A pipe-separated list of dimension names, checked against the vocabulary."""
    names = [item.strip() for item in (value or "").split("|") if item.strip()]
    unknown = sorted(set(names) - set(DIMENSION_KEYS))
    if unknown:
        raise CommandError(
            f"account {code}: {column} names {', '.join(unknown)}, which is not in "
            f"the closed vocabulary of ADR-029"
        )
    if len(names) != len(set(names)):
        raise CommandError(f"account {code}: {column} repeats a dimension")
    return names


def _declaration(row: dict[str, Any]) -> dict[str, Any]:
    """The slot columns and the requirement of one account, from the file."""
    code = row["account_code"]
    slots = _names(row.get(SLOTS_COLUMN), SLOTS_COLUMN, code)
    required = _names(row.get(REQUIRED_COLUMN), REQUIRED_COLUMN, code)
    if len(slots) > SLOT_COUNT:
        raise CommandError(f"account {code}: {len(slots)} slots, at most {SLOT_COUNT} carried")
    if not set(required) <= set(slots):
        raise CommandError(
            f"account {code}: requires {required} but carries only {slots}; the "
            f"database refuses the same thing, this says it with the account code"
        )
    padded: list[str | None] = [*slots, *([None] * SLOT_COUNT)]
    return {
        "required_dimensions": required,
        **dict(zip(SLOT_FIELDS, padded[:SLOT_COUNT], strict=True)),
    }


class Command(BaseCommand):
    help = "Load the SNC chart of accounts into coa_template / coa_template_account."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--file", default=str(DATA))
        parser.add_argument("--code", default="SNC")
        parser.add_argument("--template-version", default="2020")
        # The reference-data connection by default (ADR-049). Passing `default`
        # runs as the application role and `migration` as the owner; neither has
        # a write policy on these tables any more, so either fails with a
        # permission error, not silently.
        parser.add_argument("--database", default=REFDATA_ALIAS)
        parser.add_argument(
            "--actor",
            default=None,
            help="who is running the load, for privileged_access_log (default: the OS login)",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"data file not found: {path}")

        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            raise CommandError(f"data file is empty: {path}")

        db = options["database"]
        with privileged_run(
            PrivilegedPath.P10_CHART_OF_ACCOUNTS,
            actor=options["actor"],
            payload={"file": path.name, "code": options["code"]},
            using=db,
        ) as run:
            act = register_act(ACT, using=db)
            template, created = CoaTemplate.objects.using(db).update_or_create(
                code=options["code"],
                version=options["template_version"],
                defaults={**DEFAULTS, "act": act},
            )

            existing = {
                account.account_code: account
                for account in CoaTemplateAccount.objects.using(db).filter(template=template)
            }

            to_create: list[CoaTemplateAccount] = []
            to_update: list[CoaTemplateAccount] = []
            for row in rows:
                fields = {
                    "name_ro": row["name_ro"],
                    "account_class": row["account_class"],
                    "normal_balance": row["normal_balance"],
                    "allows_subaccounts": row["allows_subaccounts"] == "true",
                    "parent_code": row["parent_code"] or None,
                    "valid_from": row["valid_from"],
                    **_declaration(row),
                }
                account = existing.get(row["account_code"])
                if account is None:
                    to_create.append(
                        CoaTemplateAccount(
                            template=template,
                            account_code=row["account_code"],
                            is_system=True,
                            **fields,
                        )
                    )
                    continue
                if any(str(getattr(account, name)) != str(value) for name, value in fields.items()):
                    for name, value in fields.items():
                        setattr(account, name, value)
                    to_update.append(account)

            CoaTemplateAccount.objects.using(db).bulk_create(to_create)
            if to_update:
                CoaTemplateAccount.objects.using(db).bulk_update(to_update, list(COPIED))

            run.payload.update(
                {
                    "version": template.version,
                    "created": created,
                    "accounts_created": len(to_create),
                    "accounts_updated": len(to_update),
                }
            )

        orphaned = sorted(set(existing) - {row["account_code"] for row in rows})

        self.stdout.write(
            f"{template.code}/{template.version} "
            f"({'creat' if created else 'actualizat'}): "
            f"{len(to_create)} conturi noi, {len(to_update)} actualizate, "
            f"{len(rows) - len(to_create) - len(to_update)} neschimbate"
        )
        if orphaned:
            # Reported, never deleted: a company chart points at these rows.
            self.stdout.write(f"în bază dar nu în fișier, păstrate: {', '.join(orphaned)}")
