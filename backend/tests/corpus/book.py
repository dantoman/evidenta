"""The book the corpus writes in: one company on the Plan's own codes.

Everywhere else in the suite an account is `FIXTURE-D` or `2FIX`, because the
chart's content is `OD-23` and a plausible `221` in a fixture is that content
arriving sideways. The corpus is the one place the codes are the point: a case
cites *Plan 221* and asserts a posting on 221, so the account is 221 -- seeded
here, for this company, with the name the nomenclature gives it. Nothing here
loads or decides the product's chart template.

The conventions the handlers stand on -- the amount scale, the rounding
direction, the absorption rule -- come from the **shipped** parameter files
(`fiscal/parameters/data/*.toml`) through the **shipped** loader and activator,
so a change to a file, to the loader or to the activation gate changes what the
corpus runs against (`C14`).

`agree` is the exit criterion of F1 (ADR-054 §3): on the same lines, the trial
balance, the account ledger, the general ledger and the correspondence board
give one answer. Every case ends by calling it.
"""

from __future__ import annotations

import os
import subprocess
import sys
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any

from django.conf import settings

from evidenta.accounting.ledger.models import JournalFormula, JournalLine
from evidenta.accounting.ledger.services.account_ledger import account_ledger
from evidenta.accounting.ledger.services.correspondence import correspondence
from evidenta.accounting.ledger.services.general_ledger import general_ledger
from evidenta.accounting.ledger.services.trial_balance import trial_balance
from evidenta.accounting.opening.models import BatchSource
from evidenta.accounting.opening.services.batches import (
    GlRow,
    add_rows,
    create_batch,
    validate_batch,
)
from evidenta.accounting.opening.services.posting import post_batch
from evidenta.accounting.periods.models import FiscalYear, Period
from evidenta.accounting.posting.services import closing, production, settlement
from evidenta.accounting.posting.services.manual import post_manual_entry
from evidenta.accounting.posting.services.reversal import post_reversal
from evidenta.fiscal import parameters
from evidenta.platform.rls.context import TenantContext

MDL = "MDL"
YEAR_START, YEAR_END = date(2026, 1, 1), date(2026, 12, 31)
SNAPSHOT: dict[str, Any] = {"version": 1, "on": "2026-01-01", "activated": [], "usable": []}

#: The shipped files the handlers of F1 resolve against, and the tree `manage.py` lives in.
DATA = Path(parameters.__file__).resolve().parent / "data"
BACKEND = DATA.parents[3]
CONVENTIONS = ("platform_conventions.toml", "snc_stocuri.toml")

#: The technical counterpart of an opening batch -- the engine's construct
#: (Spec B §8), not an account of the Plan, so its code is not a Plan code.
OPENING_COUNTERPART = "SOLD-INIT"

#: Code -> name, from the nomenclature (`od-23-nomenclatorul-planului-de-conturi.md`).
ACCOUNTS: dict[str, str] = {
    "216": "Produse",
    "2211": "Creanţe comerciale din ţară",
    "2212": "Creanţe comerciale din străinătate",
    "242": "Conturi curente în monedă naţională",
    "311": "Capital social",
    "333": "Profit net (pierdere netă) al perioadei de gestiune",
    "351": "Rezultat financiar total",
    "5211": "Datorii comerciale în ţară",
    "5212": "Datorii comerciale în străinătate",
    "5341": "Datorii privind impozitul pe venit din activitatea de întreprinzător şi profesională",
    "5344": "Datorii privind taxa pe valoarea adăugată",
    "6111": "Venituri din vînzarea produselor",
    "6127": (
        "Venituri aferente diferenţelor favorabile dintre cursul oficial al BNM şi cursul "
        "de cumpărare-vînzare a valutei străine"
    ),
    "6226": "Venituri din diferenţe de curs valutar",
    "6227": "Venituri din diferenţe de sumă",
    "7111": "Valoarea contabilă a produselor vîndute",
    "714": "Alte cheltuieli din activitatea operaţională",
    "7147": (
        "Cheltuieli aferente diferenţelor nefavorabile dintre cursul oficial al BNM şi cursul "
        "de cumpărare-vînzare a valutei străine"
    ),
    "7224": "Cheltuieli din diferenţe de curs valutar",
    "7225": "Cheltuieli din diferenţe de sumă",
    "731": "Cheltuieli privind impozitul pe venit",
    "811": "Activităţi de bază",
    "821": "Costuri indirecte de producţie",
    OPENING_COUNTERPART: "Cont tehnic de solduri iniţiale",
}

#: Class and normal balance by the first digit of the code -- Plan, cap. I:
#: classes 1-5 balance sheet, 6-7 results, 8 management (active, "calculaţie").
CLASS_OF: dict[str, tuple[str, str]] = {
    "1": ("asset", "debit"),
    "2": ("asset", "debit"),
    "3": ("equity", "credit"),
    "4": ("liability", "credit"),
    "5": ("liability", "credit"),
    "6": ("income", "credit"),
    "7": ("expense", "debit"),
    "8": ("asset", "debit"),
}

#: Which account each role the three handlers name resolves to, in this book.
ROLE_BINDINGS: dict[str, str] = {
    settlement.ROLE_CURS_FAVORABILA: "6226",
    settlement.ROLE_CURS_NEFAVORABILA: "7224",
    settlement.ROLE_SUMA_FAVORABILA: "6227",
    settlement.ROLE_SUMA_NEFAVORABILA: "7225",
    settlement.ROLE_ECART_FAVORABIL: "6127",
    settlement.ROLE_ECART_NEFAVORABIL: "7147",
    settlement.ROLE_CREANTE_TARA: "2211",
    settlement.ROLE_CREANTE_STRAINATATE: "2212",
    settlement.ROLE_DATORII_TARA: "5211",
    settlement.ROLE_DATORII_STRAINATATE: "5212",
    settlement.ROLE_CONT_MDL: "242",
    production.ROLE_INDIRECT: "821",
    production.ROLE_BASIC: "811",
    production.ROLE_UNABSORBED: "714",
    closing.ROLE_TOTAL: "351",
    closing.ROLE_TAX: "731",
    closing.ROLE_NET: "333",
}

Seed = Callable[..., None]


def load_shipped_conventions(approver: uuid.UUID) -> None:
    """The shipped files, through the shipped path: loaded as drafts by
    `load_fiscal_parameters` and activated by `activate_fiscal_parameters` under
    the reference-data role (ADR-049, P-4), exactly as production does -- so the
    corpus stands on the files *and* on the two commands, and a row in
    `privileged_access_log` records each. The act registry (both publications of
    OMF 118/2013) is written the way the loader writes it, not approximated.

    In a **subprocess**, pointed at the test database: pytest-django wraps every
    alias a test declares in a transaction, so an in-process load on the
    reference-data alias would stay invisible to the application connection the
    handlers resolve on. The commands commit; the isolation harness deletes the
    reference tables before every test, so nothing carries over.
    """
    script = "\n".join(
        [
            "import io",
            "from django.core.management import call_command",
            *[
                f"call_command({command!r}, {name!r}, {extra}actor='corpus', stdout=io.StringIO())"
                for name in CONVENTIONS
                for command, extra in (
                    ("load_fiscal_parameters", ""),
                    ("activate_fiscal_parameters", f"approver={str(approver)!r}, "),
                )
            ],
        ]
    )
    env = {**os.environ, "POSTGRES_DB": str(settings.DATABASES["default"]["NAME"])}
    subprocess.run(
        [sys.executable, "manage.py", "shell", "-c", script],
        cwd=BACKEND,
        env=env,
        check=True,
        capture_output=True,
        text=True,
    )


def plan_account(
    seed: Seed,
    tenant: uuid.UUID,
    company: uuid.UUID,
    code: str,
    name: str,
    *,
    slots: Sequence[str] = (),
) -> uuid.UUID:
    """One account of the company, classed by the first digit of its code."""
    account_class, normal_balance = CLASS_OF.get(code[:1], ("asset", "debit"))
    account_id = uuid.uuid4()
    padded: list[str | None] = [*slots, None, None, None, None][:4]
    seed(
        "INSERT INTO company_account (id, tenant_id, company_id, account_code,"
        " parent_id, origin, template_account_id, name_ro, account_class,"
        " normal_balance, allows_subaccounts, currency_tracking, quantity_tracking,"
        " required_dimensions, slot_1_dimension, slot_2_dimension, slot_3_dimension,"
        " slot_4_dimension, is_blocked, valid_from, valid_to, created_at, updated_at)"
        " VALUES (%s, %s, %s, %s, NULL, 'company', NULL, %s, %s, %s, false, false, false,"
        " '{}'::text[], %s, %s, %s, %s, false, '2020-01-01', NULL, now(), now())",
        [account_id, tenant, company, code, name, account_class, normal_balance, *padded],
    )
    return account_id


@dataclass(frozen=True, slots=True)
class Book:
    tenant: uuid.UUID
    company: uuid.UUID
    user: uuid.UUID
    year: FiscalYear
    context: TenantContext
    #: Plan code -> account id.
    accounts: dict[str, uuid.UUID]

    @property
    def codes(self) -> dict[uuid.UUID, str]:
        return {account_id: code for code, account_id in self.accounts.items()}

    def account(self, code: str) -> uuid.UUID:
        return self.accounts[code]

    def period(self, month: int) -> Period:
        return Period.objects.get(fiscal_year=self.year, period_no=month)

    def balance(self, code: str, *, start: date = YEAR_START, end: date = YEAR_END) -> Decimal:
        """The closing balance of the trial balance over the window, **debit-positive**:
        a credit balance is negative here, and the case says so where it asserts one."""
        rows = trial_balance(self.company, start, end).rows
        account_id = self.accounts[code]
        return next((row.closing for row in rows if row.account_id == account_id), Decimal(0))

    def correspondences(self, entry_id: uuid.UUID) -> list[tuple[str, str, Decimal]]:
        """(debit code, credit code, amount) for each formula, in the order written."""
        codes = self.codes
        return [
            (codes[f.debit_account_id], codes[f.credit_account_id], f.amount)
            for f in JournalFormula.objects.filter(journal_entry_id=entry_id).order_by("id")
        ]

    def formulas(self, entry_id: uuid.UUID) -> list[JournalFormula]:
        return list(JournalFormula.objects.filter(journal_entry_id=entry_id).order_by("id"))

    def lines(self, entry_id: uuid.UUID) -> list[tuple[str, Decimal, Decimal]]:
        """(code, debit, credit) for each line -- what a manual note writes, having no formula."""
        codes = self.codes
        return [
            (codes[line.account_id], line.debit, line.credit)
            for line in JournalLine.objects.filter(journal_entry_id=entry_id).order_by(
                "line_number"
            )
        ]

    def note(
        self, lines: Sequence[tuple[str, str, str]], *, on: date, description: str
    ) -> uuid.UUID:
        """A manual note of (code, debit, credit) lines, amounts as the API takes them."""
        note_id = uuid.uuid4()
        result = post_manual_entry(
            tenant_id=self.tenant,
            company_id=self.company,
            accounting_date=on,
            functional_currency=MDL,
            note_id=note_id,
            payload={
                "description": description,
                "lines": [
                    {"account_id": str(self.accounts[code]), "debit": debit, "credit": credit}
                    for code, debit, credit in lines
                ],
            },
            idempotency_key=f"corpus-note-{note_id}",
            actor_user_id=self.user,
            request_id="corpus",
            capability_snapshot=dict(SNAPSHOT),
        )
        return result.journal_entry_id

    def storno(self, entry_id: uuid.UUID, *, on: date, reason: str) -> uuid.UUID:
        result = post_reversal(
            tenant_id=self.tenant,
            company_id=self.company,
            entry_id=entry_id,
            accounting_date=on,
            reason=reason,
            idempotency_key=f"corpus-storno-{entry_id}",
            actor_user_id=self.user,
            request_id="corpus",
            capability_snapshot=dict(SNAPSHOT),
        )
        return result.journal_entry_id

    def open_with(
        self, balances: Mapping[str, tuple[str, str]], *, on: date = YEAR_START
    ) -> uuid.UUID:
        """An opening batch of {code: (debit, credit)} GL rows, validated and posted."""
        batch = create_batch(
            company_id=self.company,
            as_of_date=on,
            source=BatchSource.MANUAL,
            counterpart_account_id=self.accounts[OPENING_COUNTERPART],
            created_by_user_id=self.user,
        )
        add_rows(
            batch.id,
            gl=[
                GlRow(account_id=self.accounts[code], debit=Decimal(debit), credit=Decimal(credit))
                for code, (debit, credit) in balances.items()
            ],
        )
        validate_batch(batch.id, MDL)
        result = post_batch(
            batch_id=batch.id,
            functional_currency=MDL,
            idempotency_key=f"corpus-opening-{batch.id}",
            actor_user_id=self.user,
            request_id="corpus",
            capability_snapshot=dict(SNAPSHOT),
        )
        return result.journal_entry_id


def agree(book: Book, *, start: date = YEAR_START, end: date = YEAR_END) -> None:
    """The three reports and the board give one answer on the same lines.

    Trial balance row by row against the account ledger and the general ledger
    (opening, turnover, closing), the general ledger's months against its own
    totals, and the board's line total against the trial balance's.
    """
    balance = trial_balance(book.company, start, end)
    assert balance.balanced, "Σ debit ≠ Σ credit în balanță"
    for row in balance.rows:
        expected = (row.opening, row.debit, row.credit, row.closing)
        sheet = account_ledger(book.company, row.account_id, start, end)
        ledger = general_ledger(book.company, row.account_id, start, end)
        assert not sheet.truncated
        assert (sheet.opening, sheet.total_debit, sheet.total_credit, sheet.closing) == expected, (
            f"fișa contului {row.account_code} nu dă răspunsul balanței"
        )
        found = (ledger.opening, ledger.total_debit, ledger.total_credit, ledger.closing)
        assert found == expected, (
            f"Cartea Mare a contului {row.account_code} nu dă răspunsul balanței"
        )
        assert sum((month.debit for month in ledger.months), Decimal(0)) == row.debit
        assert sum((month.credit for month in ledger.months), Decimal(0)) == row.credit
    board = correspondence(book.company, start, end)
    assert board.lines_total == balance.total_debit, "șahul nu însumează liniile balanței"
    assert board.total + board.unassigned == board.lines_total
