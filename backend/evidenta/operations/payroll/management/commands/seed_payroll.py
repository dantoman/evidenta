"""People, contracts, a timesheet and a payroll run -- through the payroll services.

The third seeder, on the pattern the other two settled: every situation is
attempted by name, every refusal is caught and printed, and what the run prints
is a map of what this build can do rather than a claim that it did it.

**The three relationship types are the point of the contracts.** ADR-071 made
them a table with the act quoted on each row -- individual employment contract,
service relationship, civil contract -- and the CAS minimum base applies to two
of the three. A demo with one type would exercise the easy half.

**The run will not resolve most of its components, and that is the true state.**
`cnas.*`, `cnam.*` and `income_tax.*` sit in `fiscal_parameter` with status
`draft`: loaded, not activated. The calculation says so per component rather than
substituting a zero -- the shape ADR-064 argues for, and what the payroll screen
shows as `unresolved_reason`. Activating them is the owner's act, not a seeder's.
"""

from __future__ import annotations

import uuid
from calendar import monthrange
from datetime import date
from decimal import Decimal
from typing import Any

from django.core.management.base import BaseCommand, CommandError
from django.db import connections

from evidenta.operations.payroll.services.contracts import create_contract
from evidenta.operations.payroll.services.people import create_employee
from evidenta.operations.payroll.services.runs import create_run, recompute
from evidenta.operations.payroll.services.timesheets import close_month, open_month, set_days
from evidenta.platform.rls.context import TenantContext, tenant_context
from evidenta.platform.tenancy.services.companies import accounting_start_date

#: The staff pool. Each company draws its own slice, for the reason the other two
#: seeders settled: four identical names on three companies make "switch company
#: and look" prove nothing, because identical rows are what a leak would look like.
#:
#: `(last, first, residency, idnp, relationship, position, salary)`.
POOL: tuple[tuple[str, str, str, str, str, str, str], ...] = (
    ("Popescu", "Ion", "resident", "2001600012346", "employment_contract", "Operator", "9500.00"),
    (
        "Ciobanu",
        "Vera",
        "resident",
        "2001600012347",
        "service_relationship",
        "Referent",
        "11200.00",
    ),
    ("Nistor", "Mihai", "non_resident", "2001600012348", "civil_contract", "Consultant", "7400.00"),
    (
        "Munteanu",
        "Elena",
        "resident",
        "2001600012349",
        "employment_contract",
        "Vânzător",
        "8600.00",
    ),
    ("Cebotari", "Andrei", "resident", "2001600012350", "employment_contract", "Șofer", "10400.00"),
    ("Grosu", "Diana", "resident", "2001600012351", "service_relationship", "Casier", "9100.00"),
    ("Balan", "Sergiu", "resident", "2001600012352", "employment_contract", "Depozitar", "8800.00"),
    ("Lungu", "Cristina", "resident", "2001600012353", "civil_contract", "Traducător", "6200.00"),
    ("Ursu", "Vlad", "non_resident", "2001600012354", "civil_contract", "Analist", "12800.00"),
)

#: One person on purpose in every company, with the same IDNP: the accountant who
#: keeps the books of all of an entrepreneur's firms. It is not a duplicate --
#: `employee_idnp_unique` is `(company_id, idnp)` exactly so a person may have
#: several employers -- and a demo that never showed the case would leave the
#: reader assuming the constraint is global.
SHARED = (
    "Rusu",
    "Ana",
    "resident",
    "2001600012345",
    "employment_contract",
    "Contabil-șef",
    "18000.00",
)


def _staff(company_id: uuid.UUID) -> tuple[tuple[str, str, str, str, str, str, str], ...]:
    """Three of the pool, chosen by a stable hash, plus the shared accountant."""
    start = int(company_id.hex[8:12], 16) % len(POOL)
    slice_ = tuple(POOL[(start + step) % len(POOL)] for step in range(3))
    return (SHARED, *slice_)


#: Twenty-one working days at eight hours -- a plain month. Weekends are skipped
#: by the calendar rather than by a rule about holidays: the holiday calendar is
#: fiscal data this repository does not carry, and inventing one would put days
#: into a register that no act supports.
WORKDAY_HOURS = Decimal("8")


def _tenant_and_user(subdomain: str) -> tuple[uuid.UUID, uuid.UUID]:
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


def _workdays(year: int, month: int) -> list[date]:
    """Monday to Friday of the month, by the calendar.

    Public holidays are **not** removed, and the omission is deliberate: the
    holiday calendar is fiscal data this repository does not carry, and a list
    written from memory would put working days into a register that no act
    supports. A demo month is a plain month.
    """
    last = monthrange(year, month)[1]
    return [
        date(year, month, number)
        for number in range(1, last + 1)
        if date(year, month, number).weekday() < 5
    ]


class Command(BaseCommand):
    help = "Seed employees, contracts, a timesheet and a payroll run. Development only."

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("--subdomain", required=True)
        parser.add_argument("--company", default=None, help="Implicit: toate companiile.")
        parser.add_argument("--month", default=None, help="AAAA-LL. Implicit: luna de start.")

    def handle(self, *args: Any, **options: Any) -> None:
        tenant_id, user_id = _tenant_and_user(options["subdomain"].strip().lower())
        context = TenantContext(tenant_id=tenant_id, user_id=user_id, request_id="seed_payroll")

        with tenant_context(context):
            for company_id, name in _companies(tenant_id, options["company"]):
                self.stdout.write(name)
                self._company(tenant_id, user_id, company_id, options["month"])

    def _company(
        self,
        tenant_id: uuid.UUID,
        user_id: uuid.UUID,
        company_id: uuid.UUID,
        month_option: str | None,
    ) -> None:
        starts_on = accounting_start_date(company_id)
        if month_option:
            year, month = (int(part) for part in month_option.split("-"))
        else:
            year, month = starts_on.year, max(starts_on.month, 1)

        contracts: list[uuid.UUID] = []
        for last, first, residency, idnp, relationship, position, salary in _staff(company_id):
            try:
                employee = create_employee(
                    tenant_id=tenant_id,
                    company_id=company_id,
                    last_name=last,
                    first_name=first,
                    tax_residency=residency,
                    idnp=idnp,
                )
                contract = create_contract(
                    tenant_id=tenant_id,
                    company_id=company_id,
                    employee_id=employee.id,
                    relationship_type=relationship,
                    # Numbered from the person, not from how many succeeded: a
                    # counter that only advances on success hands the same number
                    # to every attempt after the first refusal, and the collision
                    # that follows is one the seeder invented.
                    contract_number=f"CM-{year}-{idnp[-4:]}",
                    signed_on=date(year, month, 1),
                    effective_from=date(year, month, 1),
                    hire_order_number=f"OA-{year}-{idnp[-4:]}",
                    hire_order_date=date(year, month, 1),
                    position_title=position,
                    base_salary=Decimal(salary),
                    weekly_hours=Decimal("40"),
                    cas_payer_point="1.1",
                    budget_funded_employer=False,
                )
            except Exception as refusal:  # un refuz e informație, nu o oprire
                self.stdout.write(f"    refuzat ({last} {first}): {refusal}")
                continue
            contracts.append(contract.id)
            self.stdout.write(f"    angajat · {last} {first} · {relationship}")

        if not contracts:
            return

        try:
            sheet = open_month(
                tenant_id=tenant_id,
                company_id=company_id,
                year=year,
                month=month,
                norm_hours=Decimal("168"),
            )
        except Exception as refusal:
            self.stdout.write(f"    refuzat (pontaj): {refusal}")
            return

        days = [
            {"work_date": day.isoformat(), "hours_worked": str(WORKDAY_HOURS)}
            for day in _workdays(year, month)
        ]
        for contract_id in contracts:
            try:
                set_days(timesheet_id=sheet.id, contract_id=contract_id, days=days)
            except Exception as refusal:
                self.stdout.write(f"    refuzat (zile): {refusal}")
        self.stdout.write(f"    pontaj · {year}-{month:02d} · {len(days)} zile lucrătoare")

        try:
            close_month(timesheet_id=sheet.id)
            self.stdout.write("    pontaj închis")
        except Exception as refusal:
            self.stdout.write(f"    refuzat (închidere pontaj): {refusal}")

        try:
            run = create_run(
                tenant_id=tenant_id,
                company_id=company_id,
                year=year,
                month=month,
                accrual_date=date(year, month, 28),
            )
            result = recompute(run_id=run.id)
        except Exception as refusal:
            self.stdout.write(f"    refuzat (calcul): {refusal}")
            return

        unresolved = sum(
            1
            for line in result.get("lines", [])
            for component in line.get("components", [])
            if component.get("unresolved_reason")
        )
        self.stdout.write(
            f"    calcul salarial · {len(result.get('lines', []))} persoane, "
            f"{unresolved} componente nerezolvate (parametri în `draft`)"
        )
