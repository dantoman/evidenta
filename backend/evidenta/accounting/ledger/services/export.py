"""Exports of the reports -- CSV, on the server, from the same result the screen got.

`C20`: an export is generated server-side, from the same source as the display,
so the two cannot diverge. Every function here takes the dataclass the view has
already rendered on screen and writes it out; nothing is recomputed, nothing is
re-queried.

`C38`: a register is a legal document, so the pipeline opens the Romanian
context explicitly on entry and formats through `platform.documents.formatting`,
which reads no active language. `tests/architecture/test_document_language.py`
renders one of these with `ru` active and requires the same bytes.

**The shape is the one a Moldovan spreadsheet opens without a dialog:** UTF-8
with a byte-order mark (Excel otherwise guesses a code page and mangles every
diacritic), `;` as the field separator (the decimal comma makes `,` unusable),
`CRLF` line ends. Column labels are Romanian and live here: they are part of the
document, not interface strings (`C32` is about the client; ADR-033 puts
"registrele" in the layer that is exclusively Romanian).

What is deliberately absent: Excel and PDF. Both need a library or a rendering
pipeline nobody has chosen, and choosing one in passing is what `OD-74` exists
to prevent. CSV needs neither.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Sequence
from datetime import date
from decimal import Decimal

from django.utils import translation

from evidenta.accounting.ledger.services.account_ledger import AccountLedger
from evidenta.accounting.ledger.services.correspondence import Correspondence
from evidenta.accounting.ledger.services.general_ledger import GeneralLedger
from evidenta.accounting.ledger.services.trial_balance import TrialBalance
from evidenta.platform.documents.formatting import date_ro, decimal_ro

#: What the jurisdiction's spreadsheets read: BOM, semicolon, CRLF.
ENCODING = "utf-8-sig"
DELIMITER = ";"


def _document(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> bytes:
    """Write one table, in the Romanian context, whatever was active before.

    `translation.override("ro")` is the explicit entry ADR-033 asks for. The
    formatter below reads no language at all, so the override changes nothing
    today -- which is exactly the state the guard pins: the day something in this
    path consults the active language, the override is what keeps the register
    Romanian.
    """
    with translation.override("ro"):
        buffer = io.StringIO()
        writer = csv.writer(buffer, delimiter=DELIMITER, lineterminator="\r\n")
        writer.writerow(headers)
        for row in rows:
            writer.writerow([_cell(value) for value in row])
        return buffer.getvalue().encode(ENCODING)


def _cell(value: object) -> str:
    if isinstance(value, Decimal):
        return decimal_ro(value)
    if isinstance(value, date):
        return date_ro(value)
    if value is None:
        return ""
    return str(value)


def trial_balance_csv(balance: TrialBalance) -> bytes:
    return _document(
        ("Cont", "Denumire", "Sold inițial", "Rulaj debit", "Rulaj credit", "Sold final"),
        [
            *(
                (row.account_code, row.name_ro, row.opening, row.debit, row.credit, row.closing)
                for row in balance.rows
            ),
            ("Total", "", None, balance.total_debit, balance.total_credit, None),
        ],
    )


def account_ledger_csv(ledger: AccountLedger) -> bytes:
    return _document(
        (
            "Data",
            "Număr",
            "Data documentului",
            "Descriere",
            "Cont corespondent",
            "Debit",
            "Credit",
            "Sold",
        ),
        [
            (None, None, None, "Sold inițial", None, None, None, ledger.opening),
            *(
                (
                    row.accounting_date,
                    row.entry_number,
                    row.document_date,
                    row.description,
                    ", ".join(c.account_code for c in row.correspondents),
                    row.debit,
                    row.credit,
                    row.balance,
                )
                for row in ledger.rows
            ),
            (None, None, None, "Total", None, ledger.total_debit, ledger.total_credit, None),
            (None, None, None, "Sold final", None, None, None, ledger.closing),
        ],
    )


def general_ledger_csv(ledger: GeneralLedger) -> bytes:
    rows: list[Sequence[object]] = []
    for month in ledger.months:
        label = f"{date_ro(month.start_date)} - {date_ro(month.end_date)}"
        rows.append((label, "Sold inițial", "", None, None, month.opening))
        for turnover in month.debit_by:
            rows.append((label, "Debit", turnover.account_code, turnover.amount, None, None))
        if month.debit_unassigned:
            rows.append((label, "Debit", "fără corespondență", month.debit_unassigned, None, None))
        for turnover in month.credit_by:
            rows.append((label, "Credit", turnover.account_code, None, turnover.amount, None))
        if month.credit_unassigned:
            rows.append(
                (label, "Credit", "fără corespondență", None, month.credit_unassigned, None)
            )
        rows.append((label, "Rulaj", "", month.debit, month.credit, None))
        rows.append((label, "Sold final", "", None, None, month.closing))
    rows.append(("Total", "", "", ledger.total_debit, ledger.total_credit, ledger.closing))
    return _document(("Luna", "Rând", "Cont corespondent", "Debit", "Credit", "Sold"), rows)


def correspondence_csv(report: Correspondence) -> bytes:
    return _document(
        ("Cont debitor", "Cont creditor", "Sumă"),
        [
            *((cell.debit_code, cell.credit_code, cell.amount) for cell in report.cells),
            ("Total corespondențe", "", report.total),
            ("Fără corespondență", "", report.unassigned),
        ],
    )
