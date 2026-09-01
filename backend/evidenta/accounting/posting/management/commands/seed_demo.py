"""Fill one company with a year of ordinary activity, through the product's own paths.

**Why a command and not SQL.** Rows written straight into `journal_entry` would
be rows no rule ever saw: `R9` says no module writes to the ledger, `R11` is
checked by the database, and a period has to be open for a posting to land. A
seeder that inserted directly would produce a database that looks like the
product's and is not -- and the first screen to disagree with it would be blamed.
So every note here goes through `post_manual_entry`, the same service the API
calls, and every partner through `create_partner`.

**It lives in `accounting.posting` and not in `platform`, and the dependency
guard is what decided that.** The command posts notes and creates partners, so it
reaches *upward* -- and `platform` may import nothing. From here the direction is
the one the graph allows: accounting may ask `masterdata`, and the posting service
is its own.

**It runs under the application role, in a real tenant context.** The only thing
it borrows the installation connection for is a *read*: the tenant and the user to
act as, which live behind policies that answer nothing without a context
(`membership` is self-row). Everything written afterwards is written the way a
signed-in person writes it, policies included.

**What it refuses.** A company that already has posted entries. Demo data mixed
into real books is not removable -- a posted entry is immutable by `R10`, and the
only correction is a storno that would itself be a lie. `--force` exists for a
development database that is already demo data, and says so out loud.

**No VAT split, and that is a statement about the system rather than a
simplification.** `vat.standard` is in `fiscal_parameter` with status `draft`: the
rate exists as data but is not activated, so nothing may resolve it yet. Writing
20% into these notes would put a number in the ledger that the fiscal registry
would refuse to confirm -- exactly the shape `R15` exists to prevent. The notes
are therefore net: sales, collections, purchases, payments, wages. When the
parameter is activated, VAT enters through the posting rules, not through here.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from evidenta.accounting.coa.services.accounts import postable_accounts
from evidenta.accounting.ledger.services.trial_balance import trial_balance
from evidenta.accounting.posting.services.manual import post_manual_entry
from evidenta.masterdata.partners.services.directory import create_partner
from evidenta.platform.capabilities.services.profile import active_profile
from evidenta.platform.numbering.services.allocation import resolve_template
from evidenta.platform.numbering.services.templates import create_general_template
from evidenta.platform.rls.context import TenantContext, tenant_context
from evidenta.platform.tenancy.services.companies import accounting_start_date, functional_currency

#: Counterparties, with IDNOs: a demo without them would trip the very refusal
#: this repository added for nameless duplicates, and a directory of anonymous
#: partners teaches the wrong habit.
PARTNERS = (
    ("ICS Termocom SRL", "1002600011223", False, True),
    ("SA Franzeluta", "1002600055667", True, False),
    ("SRL Agroteh", "1013600044556", True, True),
    ("BC Moldindconbank SA", "1002600028096", False, True),
)

#: Three months of ordinary movement, as (month offset, day, description, debit,
#: credit, amount). Offsets rather than calendar months: the first month a
#: company can number a document is not always January (see `_first_postable`),
#: and a demo that insisted on January would refuse to seed a company created in
#: August.
NOTES: tuple[tuple[int, int, str, str, str, str], ...] = (
    (0, 15, "Vânzare produse", "221", "611", "128300.00"),
    (0, 20, "Încasare de la client", "242", "221", "96000.00"),
    (0, 25, "Achiziție materiale", "211", "521", "48900.00"),
    (0, 28, "Salarii calculate", "713", "531", "62000.00"),
    (1, 5, "Plată furnizor", "521", "242", "48900.00"),
    (1, 12, "Vânzare produse", "221", "611", "214800.00"),
    (1, 18, "Ridicare numerar", "241", "242", "12000.00"),
    (1, 28, "Salarii calculate", "713", "531", "62000.00"),
    (2, 6, "Încasare de la client", "242", "221", "180000.00"),
    (2, 14, "Cheltuieli administrative", "713", "521", "17400.00"),
    (2, 20, "Consum de materiale", "711", "211", "31200.00"),
    (2, 28, "Salarii calculate", "713", "531", "62000.00"),
)


def _shift(base: date, months: int, day: int) -> date:
    month = base.month - 1 + months
    return date(base.year + month // 12, month % 12 + 1, day)


def _identifiers(subdomain: str, legal_name: str) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    """The tenant, a user to act as, and the company -- on the installation connection.

    Reads, and only reads. `membership` answers nothing without a context, so the
    alternative would be passing three UUIDs on the command line, which is how a
    demo ends up seeded into the wrong workspace. The company is resolved here for
    a second reason: `platform.tenancy` exposes facts about a company by id, and
    finding one by name is not among them -- adding a public service so a seeder
    can search would widen the module's surface for a development convenience.
    """
    admin = connections["admin"] if "admin" in connections.databases else None
    if admin is None:
        raise CommandError(
            "conexiunea de instalare nu este configurată: setați DB_ADMIN_USER și DB_ADMIN_PASSWORD"
        )
    with admin.cursor() as cursor:
        cursor.execute(
            """
            SELECT t.id, m.user_id, c.id
              FROM tenant t
              JOIN membership m ON m.tenant_id = t.id AND m.status = 'active'
              JOIN company c    ON c.tenant_id = t.id AND c.legal_name = %s
             WHERE t.subdomain = %s
             ORDER BY m.created_at
             LIMIT 1
            """,
            [legal_name, subdomain],
        )
        row = cursor.fetchone()
    if row is None:
        raise CommandError(
            f"nu există tenantul {subdomain!r} cu un membru activ și compania {legal_name!r}"
        )
    return uuid.UUID(str(row[0])), uuid.UUID(str(row[1])), uuid.UUID(str(row[2]))


class Command(BaseCommand):
    help = "Seed one company with demo partners and a year of notes. Development only."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--subdomain", required=True)
        parser.add_argument("--company", required=True, help="Denumirea legală a companiei.")
        parser.add_argument("--year", type=int, default=None, help="Implicit: anul exercițiului.")
        parser.add_argument(
            "--force",
            action="store_true",
            help="Postează chiar dacă există deja înregistrări. Într-o bază reală, nu.",
        )

    def handle(self, *args: Any, **options: Any) -> None:
        tenant_id, user_id, company_id = _identifiers(
            options["subdomain"].strip().lower(), options["company"]
        )
        context = TenantContext(tenant_id=tenant_id, user_id=user_id, request_id="seed_demo")

        with tenant_context(context):
            # Every read below goes through the policies: an identifier resolved
            # on the installation connection buys nothing if the company is not
            # this caller's to see -- `functional_currency` answers from the row
            # the policy allows, and refuses otherwise.
            currency = functional_currency(company_id)
            starts_on = accounting_start_date(company_id)

            # Asked through the public report rather than by counting rows in
            # another module's table (`D6`): what matters is whether this company
            # has movement, and the trial balance is the service that answers it.
            year = options["year"] or starts_on.year
            moved = trial_balance(company_id, date(year, 1, 1), date(year, 12, 31))
            existing = len(moved.rows)
            if existing and not options["force"]:
                raise CommandError(
                    f"compania are deja mișcare pe {existing} conturi. Datele de demonstrație "
                    f"amestecate în registre reale nu se mai scot: o înregistrare postată "
                    f"e imutabilă (`R10`), iar corecția ar fi un storno care ar minți. "
                    f"Dacă baza e deja de demonstrație, --force."
                )

            # **Where the demo can actually be posted.** A company numbers its
            # documents from a series, and a series has a start: `II Tomsa Dan`
            # carries one valid from the day it was created, in August, so notes
            # dated January are refused by `platform.numbering` in the middle of
            # the first posting -- which reads as a seeder bug rather than as the
            # true answer, that the company could not have issued a document then.
            #
            # So the base month is searched forward from the day the books start,
            # and only when no month of the year has a series is one created.
            base = None
            probe = date(year, 1, 1)
            for _ in range(12):
                try:
                    resolve_template(company_id, "journal_entry", probe)
                except Exception:  # orice refuz înseamnă „nicio serie în vigoare"
                    probe = _shift(probe, 1, 1)
                else:
                    base = probe
                    break
            if base is None:
                create_general_template(tenant_id, company_id, valid_from=starts_on)
                base = starts_on
                self.stdout.write("  serie de numerotare creată (nu exista niciuna)")

            # Postabile în luna de la care începe demonstrația, adică exact
            # întrebarea pe care o pune o notă: un cont închis înainte de atunci
            # nu e unul în care se postează.
            accounts = {row.account_code: row.id for row in postable_accounts(company_id, base)}
            made = 0
            for name, idno, customer, supplier in PARTNERS:
                try:
                    create_partner(
                        tenant_id=tenant_id,
                        legal_name=name,
                        idno=idno,
                        is_customer=customer,
                        is_supplier=supplier,
                    )
                    made += 1
                except Exception as clash:
                    self.stdout.write(f"  partener sărit ({name}): {clash}")

            posted = 0
            for months, day, description, debit, credit, amount in NOTES:
                if debit not in accounts or credit not in accounts:
                    self.stdout.write(f"  notă sărită: contul {debit} sau {credit} lipsește")
                    continue
                on = _shift(base, months, day)
                note_id = uuid.uuid4()
                post_manual_entry(
                    tenant_id=tenant_id,
                    company_id=company_id,
                    accounting_date=on,
                    functional_currency=currency,
                    note_id=note_id,
                    payload={
                        "description": description,
                        "lines": [
                            {
                                "account_id": str(accounts[debit]),
                                "debit": amount,
                                "credit": "0",
                                "description": None,
                            },
                            {
                                "account_id": str(accounts[credit]),
                                "debit": "0",
                                "credit": amount,
                                "description": None,
                            },
                        ],
                    },
                    # Derived from the note, so a re-run finds the same key and
                    # the same entry rather than doubling the books (`R19`).
                    idempotency_key=f"seed:{company_id}:{on}:{description}:{amount}",
                    actor_user_id=user_id,
                    request_id="seed_demo",
                    capability_snapshot=active_profile(company_id, on).as_snapshot(),
                )
                posted += 1

        self.stdout.write(
            f"{options['company']}: {made} parteneri, {posted} note din {base:%m.%Y}."
        )
