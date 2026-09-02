"""One CSV writer for every register and export -- `C20`, `C38`.

**The shape is the one a Moldovan spreadsheet opens without a dialog:** UTF-8
with a byte-order mark (Excel otherwise guesses a code page and mangles every
diacritic), `;` as the field separator (the decimal comma makes `,` unusable),
`CRLF` line ends. Numbers and dates go through `platform.documents.formatting`,
which reads no active language, and the whole table is written inside an
explicit Romanian context (ADR-033): a register is a legal document and does not
inherit the language of the request that asked for it.

Here, in the document core, since ADR-090: the ledger's exports wrote it first
(`accounting/ledger/services/export.py`), and the VAT register in
`operations/tax` may not import that module (`D3`). Two writers that agree until
one is edited is the class of defect `C20` names, so the writer moved down to the
layer both may use. What is deliberately absent is unchanged: Excel and PDF need
a library or a rendering pipeline nobody has chosen (`OD-74`).
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Sequence
from datetime import date
from decimal import Decimal

from django.utils import translation

from evidenta.platform.documents.formatting import date_ro, decimal_ro

#: What the jurisdiction's spreadsheets read: BOM, semicolon, CRLF.
ENCODING = "utf-8-sig"
DELIMITER = ";"


def csv_document(headers: Sequence[str], rows: Iterable[Sequence[object]]) -> bytes:
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
            writer.writerow([csv_cell(value) for value in row])
        return buffer.getvalue().encode(ENCODING)


def csv_cell(value: object) -> str:
    if isinstance(value, Decimal):
        return decimal_ro(value)
    if isinstance(value, date):
        return date_ro(value)
    if value is None:
        return ""
    return str(value)
