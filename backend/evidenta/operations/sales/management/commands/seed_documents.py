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
from evidenta.operations.purchases.services.documents import (
    convert_to_purchase,
    open_purchase,
    open_supplier_order,
)
from evidenta.operations.purchases.services.lines import service_line as purchase_line
from evidenta.operations.purchases.services.recording import record_and_post as record_purchase
from evidenta.operations.sales.models import SalesDocument
from evidenta.operations.sales.services.documents import (
    convert_to_sale,
    open_customer_order,
    open_proforma,
    open_sale,
)
from evidenta.operations.sales.services.issuing import issue_and_post
from evidenta.operations.sales.services.lines import service_line as sale_line
from evidenta.operations.settlements.services.allocation import allocate
from evidenta.operations.treasury.services.documents import open_payment, open_receipt
from evidenta.operations.treasury.services.recording import record_and_post as record_movement
from evidenta.platform.capabilities.services.profile import active_profile
from evidenta.platform.documents.services.lifecycle import validate
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
        """Every situation the product can express today, each reported by name.

        Written as a list of attempts rather than a straight line, and each one is
        caught: a refusal is **information**, not a crash. What the run prints is
        therefore a map of what this build supports -- goods and finished products
        select revenue roles that nothing binds yet, non-residents select another,
        and each of those refuses with a sentence saying which. A seeder that
        stopped at the first refusal would have hidden the other eleven.
        """
        scale = _scale(company_id)
        snapshot = active_profile(company_id, base).as_snapshot()
        made = 0

        def day(number: int) -> date:
            return date(base.year, base.month, min(number, 28))

        def issue(document_id: uuid.UUID, description: str, amount: str, on: date) -> None:
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

        def record(document_id: uuid.UUID, description: str, amount: str, on: date) -> None:
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

        def movement(document_id: uuid.UUID) -> None:
            record_movement(
                document_id=document_id,
                actor_user_id=user_id,
                request_id="seed_documents",
                capability_snapshot=snapshot,
            )

        # Kept for the settlement below: an allocation needs an invoice with a
        # balance and a receipt with money on it, both of them real.
        invoiced: uuid.UUID | None = None
        received: uuid.UUID | None = None

        def sale_delivery_resident() -> str:
            nonlocal invoiced
            on = day(5)
            document_id = open_sale(
                company_id=company_id,
                partner_id=customer,
                document_date=on,
                revenue_kind="services",
                partner_resident=True,
            )
            issue(document_id, "Servicii de consultanță", "48000.00", on)
            invoiced = document_id
            return "vânzare · livrare · rezident"

        def sale_delivery_non_resident() -> str:
            on = day(6)
            document_id = open_sale(
                company_id=company_id,
                partner_id=customer,
                document_date=on,
                revenue_kind="services",
                partner_resident=False,
            )
            issue(document_id, "Servicii către nerezident", "22000.00", on)
            return "vânzare · livrare · nerezident"

        def sale_advance() -> str:
            on = day(7)
            document_id = open_sale(
                company_id=company_id,
                partner_id=customer,
                document_date=on,
                revenue_kind="services",
                partner_resident=True,
                nature="advance",
            )
            issue(document_id, "Avans încasat", "15000.00", on)
            return "vânzare · avans"

        def sale_return() -> str:
            on = day(9)
            document_id = open_sale(
                company_id=company_id,
                partner_id=customer,
                document_date=on,
                revenue_kind="services",
                partner_resident=True,
                nature="return",
            )
            issue(document_id, "Storno servicii facturate", "5000.00", on)
            return "vânzare · retur (notă de credit)"

        def sale_goods() -> str:
            on = day(10)
            document_id = open_sale(
                company_id=company_id,
                partner_id=customer,
                document_date=on,
                revenue_kind="goods",
                partner_resident=True,
            )
            issue(document_id, "Mărfuri vândute", "18000.00", on)
            return "vânzare · mărfuri"

        def proforma_converted() -> str:
            on = day(11)
            source = open_proforma(company_id=company_id, partner_id=customer, document_date=on)
            replace_lines(
                source,
                [
                    sale_line(
                        description="Ofertă servicii",
                        quantity=Decimal("1"),
                        unit_price=_amount("9000.00", scale),
                        on=on,
                    )
                ],
            )
            # Validated first: only a commitment converts, and a draft proforma
            # is still an offer somebody is editing. The refusal that taught me
            # this said exactly that.
            validate(source)
            document_id = convert_to_sale(
                source_id=source,
                document_date=on,
                revenue_kind="services",
                partner_resident=True,
            )
            issue_and_post(
                document_id=document_id,
                actor_user_id=user_id,
                request_id="seed_documents",
                capability_snapshot=snapshot,
            )
            return "proformă → vânzare"

        def order_converted() -> str:
            on = day(12)
            source = open_customer_order(
                company_id=company_id, partner_id=customer, document_date=on
            )
            replace_lines(
                source,
                [
                    sale_line(
                        description="Comandă servicii",
                        quantity=Decimal("1"),
                        unit_price=_amount("7500.00", scale),
                        on=on,
                    )
                ],
            )
            validate(source)
            document_id = convert_to_sale(
                source_id=source,
                document_date=on,
                revenue_kind="services",
                partner_resident=True,
            )
            issue_and_post(
                document_id=document_id,
                actor_user_id=user_id,
                request_id="seed_documents",
                capability_snapshot=snapshot,
            )
            return "comandă client → vânzare"

        def purchase(destination: str, label: str, amount: str, offset: int) -> str:
            on = day(14 + offset)
            document_id = open_purchase(
                company_id=company_id,
                partner_id=supplier,
                document_date=on,
                # The supplier's own number, and it carries the company: without
                # it two companies buying from one supplier would be handed the
                # same reference by this seeder -- a collision the seeder invented
                # rather than one the world has. A re-run still collides, and
                # rightly: that is `R20`'s subject.
                supplier_document_number=f"FF-{base:%Y%m}-{company_id.hex[:4]}{offset}",
                supplier_document_date=on,
                cost_destination=destination,
                partner_resident=True,
            )
            record(document_id, label, amount, on)
            return f"achiziție · {destination}"

        def supplier_order_converted() -> str:
            on = day(18)
            source = open_supplier_order(
                company_id=company_id, partner_id=supplier, document_date=on
            )
            replace_lines(
                source,
                [
                    purchase_line(
                        description="Comandă consumabile",
                        quantity=Decimal("1"),
                        unit_price=_amount("3400.00", scale),
                        on=on,
                    )
                ],
            )
            validate(source)
            document_id = convert_to_purchase(
                source_id=source,
                document_date=on,
                supplier_document_number=f"FF-{base:%Y%m}-{company_id.hex[:4]}C",
                supplier_document_date=on,
                cost_destination="administrative",
                partner_resident=True,
            )
            record_purchase(
                document_id=document_id,
                actor_user_id=user_id,
                request_id="seed_documents",
                capability_snapshot=snapshot,
            )
            return "comandă furnizor → achiziție"

        def receipt(account: str, amount: str, offset: int) -> str:
            nonlocal received
            document_id = open_receipt(
                company_id=company_id,
                partner_id=customer,
                document_date=day(20 + offset),
                amount=_amount(amount, scale),
                treasury_account=account,
                partner_resident=True,
            )
            movement(document_id)
            if account == "bank":
                received = document_id
            return f"încasare · {account}"

        def payment(account: str, amount: str, offset: int) -> str:
            document_id = open_payment(
                company_id=company_id,
                partner_id=supplier,
                document_date=day(22 + offset),
                amount=_amount(amount, scale),
                treasury_account=account,
                partner_resident=True,
            )
            movement(document_id)
            return f"plată · {account}"

        def settlement() -> str:
            if invoiced is None or received is None:
                raise RuntimeError("nu există factură și încasare de decontat")
            allocate(
                settled_document_id=invoiced,
                movement_document_id=received,
                amount=_amount("20000.00", scale),
            )
            return "decontare · încasare alocată pe factură"

        situations = (
            sale_delivery_resident,
            sale_delivery_non_resident,
            sale_advance,
            sale_return,
            sale_goods,
            proforma_converted,
            order_converted,
            lambda: purchase("administrative", "Chirie spațiu", "12000.00", 0),
            lambda: purchase("commercial", "Publicitate", "4800.00", 1),
            lambda: purchase("production_direct", "Subcontractare", "9200.00", 2),
            supplier_order_converted,
            lambda: receipt("bank", "48000.00", 0),
            lambda: receipt("cash", "3500.00", 1),
            lambda: payment("bank", "12000.00", 0),
            lambda: payment("cash", "1800.00", 1),
            settlement,
        )

        for attempt in situations:
            try:
                label = attempt()
            except Exception as refusal:  # un refuz e informație, nu o oprire
                self.stdout.write(f"    refuzat: {refusal}")
            else:
                made += 1
                self.stdout.write(f"    {label}")

        return made
