"""Fill companies with commercial documents, through the same services the API calls.

The companion of `seed_demo`, which posts manual notes. This one exercises the
document chain the commercial modules added: a sale is opened as a draft, given
positions, then issued and posted; a purchase records somebody else's invoice;
a receipt and a payment move the money. Every one goes through its module's
public service, so what lands in the ledger got there the way the product puts it
there -- numbering, validation, posting rules and all.

**Why it lives in `operations` and `seed_demo` does not.** It reaches across
sales, purchases and treasury, and `operations` is the only layer allowed to see
all three. `accounting`, where the notes seeder sits, may not import upward.

**What it refuses.** A company that already has sales documents, unless `--force`.
A posted document is immutable, and a second run would not correct the first --
it would double it.

**Amounts are net.** `vat.standard` is `draft` in `fiscal_parameter`, so nothing
may resolve a rate yet; a demo that wrote one would put a number in the ledger the
fiscal registry would refuse to confirm (`R15`).
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from evidenta.accounting.slots.services.binding import install_default_bindings
from evidenta.masterdata.partners.services.directory import create_partner, partners_of
from evidenta.operations.purchases.services.documents import open_purchase
from evidenta.operations.purchases.services.lines import service_line as purchase_line
from evidenta.operations.purchases.services.recording import record_and_post as record_purchase
from evidenta.operations.sales.models import SalesDocument
from evidenta.operations.sales.services.documents import open_sale
from evidenta.operations.sales.services.issuing import issue_and_post
from evidenta.operations.sales.services.lines import service_line as sale_line
from evidenta.operations.treasury.services.documents import open_payment, open_receipt
from evidenta.operations.treasury.services.recording import record_and_post as record_movement
from evidenta.platform.capabilities.services.profile import active_profile
from evidenta.platform.documents.services.lines import replace_lines
from evidenta.platform.numbering.services.allocation import resolve_template
from evidenta.platform.rls.context import TenantContext, tenant_context
from evidenta.platform.tenancy.services.companies import accounting_start_date

#: Two of each, so every list screen has more than one row and every total is a
#: sum rather than a single number wearing one.
SALES = (("Servicii de consultanță", "48000.00"), ("Servicii de mentenanță", "31500.00"))
PURCHASES = (("Chirie spațiu", "12000.00"), ("Servicii de contabilitate", "6500.00"))

#: Each company gets its own scale, for the reason `seed_demo` gives at length:
#: three companies carrying identical figures make the check a person actually
#: performs -- switch company, read the total -- prove nothing, because identical
#: numbers are also what a leak would look like. Keyed by a stable hash of the
#: company id, so a re-run keeps a company on its own scale.
SCALES = (Decimal("1.0"), Decimal("0.35"), Decimal("1.7"), Decimal("0.6"))


def _scale(company_id: uuid.UUID) -> Decimal:
    return SCALES[int(company_id.hex[:8], 16) % len(SCALES)]


def _amount(raw: str, scale: Decimal) -> Decimal:
    return (Decimal(raw) * scale).quantize(Decimal("0.01"))


def _tenant_and_user(subdomain: str) -> tuple[uuid.UUID, uuid.UUID]:
    """Read on the installation connection -- `membership` answers nothing without a context."""
    if "admin" not in connections.databases:
        raise CommandError("conexiunea de instalare nu este configurată (DB_ADMIN_USER)")
    with connections["admin"].cursor() as cursor:
        cursor.execute(
            """
            SELECT t.id, m.user_id
              FROM tenant t
              JOIN membership m ON m.tenant_id = t.id AND m.status = 'active'
             WHERE t.subdomain = %s
             ORDER BY m.created_at
             LIMIT 1
            """,
            [subdomain],
        )
        row = cursor.fetchone()
    if row is None:
        raise CommandError(f"nu există tenantul {subdomain!r} cu un membru activ")
    return uuid.UUID(str(row[0])), uuid.UUID(str(row[1]))


def _companies(tenant_id: uuid.UUID, only: str | None) -> list[tuple[uuid.UUID, str]]:
    with connections["admin"].cursor() as cursor:
        cursor.execute(
            "SELECT id, legal_name FROM company WHERE tenant_id = %s"
            + (" AND legal_name = %s" if only else "")
            + " ORDER BY legal_name",
            [tenant_id, only] if only else [tenant_id],
        )
        rows = cursor.fetchall()
    if not rows:
        raise CommandError("nicio companie de însămânțat în acest spațiu de lucru")
    return [(uuid.UUID(str(r[0])), str(r[1])) for r in rows]


def _first_postable(company_id: uuid.UUID, starts_on: date) -> date:
    """The first month this company can number a document.

    A series has a start, and a company created in August cannot have issued
    anything in January. Asking `numbering` rather than assuming is what keeps the
    demo from being refused halfway through its first document.
    """
    probe = date(starts_on.year, 1, 1)
    for _ in range(24):
        try:
            resolve_template(company_id, "sales_invoice", probe)
        except Exception:  # orice refuz înseamnă „nicio serie în vigoare"
            month = probe.month % 12 + 1
            probe = date(probe.year + (1 if month == 1 else 0), month, 1)
        else:
            return probe
    raise CommandError(f"compania {company_id} n-are nicio serie de numerotare în doi ani")


class Command(BaseCommand):
    help = "Seed commercial documents: sales, purchases, receipts, payments. Development only."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--subdomain", required=True)
        parser.add_argument("--company", default=None, help="Implicit: toate companiile.")
        parser.add_argument("--force", action="store_true")

    def handle(self, *args: Any, **options: Any) -> None:
        tenant_id, user_id = _tenant_and_user(options["subdomain"].strip().lower())
        context = TenantContext(tenant_id=tenant_id, user_id=user_id, request_id="seed_documents")

        with tenant_context(context):
            customer, supplier = self._counterparties(tenant_id)

            for company_id, name in _companies(tenant_id, options["company"]):
                seeded = SalesDocument.objects.filter(document__company_id=company_id).exists()
                if seeded and not options["force"]:
                    self.stdout.write(f"{name}: are deja documente comerciale, sărită")
                    continue

                starts_on = accounting_start_date(company_id)
                base = _first_postable(company_id, starts_on)

                # A company whose chart was instantiated before the role bindings
                # existed has none, and the posting engine refuses at the first
                # document -- rightly: it will not pick an account, because a
                # wrong one balances exactly as well as a right one. Installing
                # them is idempotent and dated from the day the books start, which
                # is the same thing chart setup does now.
                install_default_bindings(
                    tenant_id=tenant_id, company_id=company_id, on_date=starts_on
                )

                made = self._documents(company_id, user_id, customer, supplier, base)
                self.stdout.write(
                    f"{name}: {made} documente din {base:%m.%Y}, scara {_scale(company_id)}"
                )

    def _counterparties(self, tenant_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
        """A customer and a supplier, reused if the directory already has them."""
        existing = partners_of(tenant_id)
        customer = next((p for p in existing if p["is_customer"]), None)
        supplier = next((p for p in existing if p["is_supplier"]), None)
        if customer is None:
            customer = {
                "id": str(
                    create_partner(
                        tenant_id=tenant_id,
                        legal_name="SA Franzeluta",
                        idno="1002600055668",
                        is_customer=True,
                    ).id
                )
            }
        if supplier is None:
            supplier = {
                "id": str(
                    create_partner(
                        tenant_id=tenant_id,
                        legal_name="ICS Termocom SRL",
                        idno="1002600011224",
                        is_supplier=True,
                    ).id
                )
            }
        return uuid.UUID(customer["id"]), uuid.UUID(supplier["id"])

    def _documents(
        self,
        company_id: uuid.UUID,
        user_id: uuid.UUID,
        customer: uuid.UUID,
        supplier: uuid.UUID,
        base: date,
    ) -> int:
        made = 0
        scale = _scale(company_id)
        snapshot = active_profile(company_id, base).as_snapshot()

        for index, (description, amount) in enumerate(SALES):
            on = date(base.year, base.month, 5 + index * 10)
            document_id = open_sale(
                company_id=company_id,
                partner_id=customer,
                document_date=on,
                revenue_kind="services",
                partner_resident=True,
            )
            replace_lines(
                document_id,
                [
                    sale_line(
                        description=description,
                        quantity=Decimal("1"),
                        unit_price=_amount(amount, scale),
                        on=on,
                    )
                ],
            )
            issue_and_post(
                document_id=document_id,
                actor_user_id=user_id,
                request_id="seed_documents",
                capability_snapshot=snapshot,
            )
            made += 1

        for index, (description, amount) in enumerate(PURCHASES):
            on = date(base.year, base.month, 8 + index * 10)
            try:
                document_id = open_purchase(
                    company_id=company_id,
                    partner_id=supplier,
                    document_date=on,
                    # The supplier's own number, and it carries the company:
                    # without it two companies buying from the same supplier
                    # would be issued the same reference by this seeder, which is
                    # a collision the seeder invented rather than one the world
                    # has. A re-run still collides, and rightly -- the same
                    # document recorded twice is `R20`'s whole subject.
                    supplier_document_number=f"FF-{base:%Y}-{company_id.hex[:4]}{index}",
                    supplier_document_date=on,
                    cost_destination="administrative",
                    partner_resident=True,
                )
            except Exception as recorded:  # documentul furnizorului e deja înregistrat
                self.stdout.write(f"  achiziție sărită: {recorded}")
                continue
            replace_lines(
                document_id,
                [
                    purchase_line(
                        description=description,
                        quantity=Decimal("1"),
                        unit_price=_amount(amount, scale),
                        on=on,
                    )
                ],
            )
            record_purchase(
                document_id=document_id,
                actor_user_id=user_id,
                request_id="seed_documents",
                capability_snapshot=snapshot,
            )
            made += 1

        receipt = open_receipt(
            company_id=company_id,
            partner_id=customer,
            document_date=date(base.year, base.month, 20),
            amount=_amount("48000.00", scale),
            treasury_account="bank",
            partner_resident=True,
        )
        payment = open_payment(
            company_id=company_id,
            partner_id=supplier,
            document_date=date(base.year, base.month, 22),
            amount=_amount("12000.00", scale),
            treasury_account="bank",
            partner_resident=True,
        )
        for movement in (receipt, payment):
            record_movement(
                document_id=movement,
                actor_user_id=user_id,
                request_id="seed_documents",
                capability_snapshot=snapshot,
            )
            made += 1

        return made
