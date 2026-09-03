"""Exports of the reports -- CSV, on the server, from the same result the screen got.

`C20`: an export is generated server-side, from the same source as the display,
so the two cannot diverge. Every function here takes the dataclass the view has
already rendered on screen and writes it out; nothing is recomputed, nothing is
re-queried.

`C38`: a register is a legal document, so the pipeline opens the Romanian
context explicitly on entry and formats through `platform.documents.formatting`,
which reads no active language. `tests/architecture/test_document_language.py`
renders one of these with `ru` active and requires the same bytes.

**The writer lives in the document core since ADR-090**
(`platform.documents.services.csv`): the VAT register in `operations/tax` may
not import this module (`D3`), and two writers that agree until one is edited is
the defect `C20` names. What stays here is the shape of each report. Column
labels are Romanian and live here: they are part of the document, not interface
strings (`C32` is about the client; ADR-033 puts "registrele" in the layer that
is exclusively Romanian).

What is deliberately absent: Excel and PDF. PDF has its pipeline since ADR-095
(`platform/documents/printing`), and the reports may join it -- each report is a
`PrintableDocument` to build, which nobody has asked for yet. Excel still needs a
library nobody has chosen; `OD-74` closed on the PDF half and left that to the
first client who asks.
"""

from __future__ import annotations

from collections.abc import Sequence

from evidenta.accounting.ledger.services.account_ledger import AccountLedger
from evidenta.accounting.ledger.services.correspondence import Correspondence
from evidenta.accounting.ledger.services.document_journal import DocumentJournal
from evidenta.accounting.ledger.services.general_ledger import GeneralLedger
from evidenta.accounting.ledger.services.trial_balance import TrialBalance
from evidenta.platform.documents.formatting import date_ro
from evidenta.platform.documents.services.csv import DELIMITER, ENCODING, csv_document

__all__ = [
    "DELIMITER",
    "ENCODING",
    "account_ledger_csv",
    "correspondence_csv",
    "document_journal_csv",
    "general_ledger_csv",
    "trial_balance_csv",
]

_document = csv_document


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


def document_journal_csv(journal: DocumentJournal) -> bytes:
    """The document journal, in the shape a Moldovan spreadsheet opens.

    The counterparty column carries the **legal** name (`C39`), and the VAT column
    is present although every document in it carries zero: a register whose
    columns changed with its content could not be compared with the next month's.
    """
    return _document(
        (
            "Data contabilă",
            "Data documentului",
            "Număr",
            "Contraparte",
            "Valută",
            "Fără TVA",
            "TVA",
            "Total",
        ),
        [
            *(
                (
                    row.accounting_date,
                    row.document_date,
                    row.formatted_number,
                    row.partner_name,
                    row.currency,
                    row.net,
                    row.vat,
                    row.total,
                )
                for row in journal.rows
            ),
            (
                None,
                None,
                None,
                "Total",
                None,
                journal.total_net,
                journal.total_vat,
                journal.total_amount,
            ),
        ],
    )
