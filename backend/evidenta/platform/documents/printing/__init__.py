"""Printed documents -- the server-side pipeline `C22` names, decided in ADR-095.

Two things live here: the value a printed document is (`document.py`) and the
renderer that turns it into PDF bytes (`render.py`). A business module builds the
first and calls the second; it never imports the PDF library.
"""

from evidenta.platform.documents.printing.document import (
    Cell,
    Column,
    Columns,
    Field,
    Fields,
    PrintableDocument,
    Section,
    Signatures,
    Table,
    Text,
    Totals,
    file_name_of,
)
from evidenta.platform.documents.printing.render import render
from evidenta.platform.documents.printing.response import pdf_response

__all__ = [
    "Cell",
    "Column",
    "Columns",
    "Field",
    "Fields",
    "PrintableDocument",
    "Section",
    "Signatures",
    "Table",
    "Text",
    "Totals",
    "file_name_of",
    "pdf_response",
    "render",
]
