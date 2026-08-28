"""Load a published chart-of-accounts version from its data file.

Run as the owner, because ``coa_template`` and ``coa_template_account`` are
global tables whose writes are revoked from the application role
(``infra/rls/exceptions.toml``, ``policy_shape = "global_read_only"``). The
``migration`` connection is that role, and the guard leaves it alone -- it never
serves a request.

**Idempotent and re-runnable.** Accounts are matched on ``(template,
account_code)``, which is the table's own unique key: a second run updates what
changed and creates what is missing. That match is a **read**, and it passes
through the owner policy from ``0044`` -- written for the write side, with the
read half arriving as a side effect. Narrowing that policy to
``FOR INSERT``/``FOR UPDATE`` would leave this command inserting everything on
every run. The dependency is asserted, not merely noted, in
``tests/schema_guard/test_reference_load_policy.py``. Nothing is deleted, ever. A code that
disappears from the file is reported and left in place: charts built on this
version reference these rows, and deleting one would silently unlink a company's
account from the version it was copied from.

The content is not typed in here. It is transcribed in
``data/snc_2020.csv`` from the repository's own extraction of the act
(``docs/_input/cercetare/od-23-nomenclatorul-planului-de-conturi.md``), which was
read out of the Ministry of Finance PDF and checked round-trip. Names carry the
act's own spelling, including the "î" forms, and nothing is normalised.
"""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from evidenta.accounting.coa.models import CoaTemplate, CoaTemplateAccount, TemplateStatus

DATA = Path(__file__).resolve().parents[2] / "data" / "snc_2020.csv"

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

COPIED = (
    "name_ro",
    "account_class",
    "normal_balance",
    "allows_subaccounts",
    "parent_code",
    "valid_from",
)


class Command(BaseCommand):
    help = "Load the SNC chart of accounts into coa_template / coa_template_account."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--file", default=str(DATA))
        parser.add_argument("--code", default="SNC")
        parser.add_argument("--template-version", default="2020")
        # The owner connection by default. Passing `default` here would run as
        # the application role, which has no write on these tables at all -- so
        # the failure would be a permission error, not silent.
        parser.add_argument("--database", default="migration")

    def handle(self, *args: Any, **options: Any) -> None:
        path = Path(options["file"])
        if not path.exists():
            raise CommandError(f"data file not found: {path}")

        with path.open(encoding="utf-8", newline="") as handle:
            rows = list(csv.DictReader(handle))
        if not rows:
            raise CommandError(f"data file is empty: {path}")

        db = options["database"]
        with transaction.atomic(using=db):
            template, created = CoaTemplate.objects.using(db).update_or_create(
                code=options["code"], version=options["template_version"], defaults=DEFAULTS
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
