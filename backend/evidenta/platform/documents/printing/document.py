"""What a printed document *is*, before it is a PDF -- `C22`, ADR-095.

A module that prints an invoice or a payslip does not touch the PDF library. It
builds one of these values -- title, blocks of labelled fields, a table, totals,
signature lines -- and hands it to :func:`evidenta.platform.documents.printing.render`.
The value is the seam: the document core knows nothing of sales or payroll
(`platform` imports nothing above it), and the caller knows nothing of fonts,
page sizes or content streams.

**Cells are typed, not pre-formatted.** A `Decimal` stays a `Decimal` and a
`date` stays a `date` all the way to the renderer, which is the only place that
turns them into text -- through `platform.documents.formatting`, whose `ro-MD`
conventions never consult the active language (ADR-033, `C38`). A caller that
formatted its own amounts would be a second formatter, and two formatters agree
until one is edited.

**Every value here is frozen.** A printed document is a record of a moment; the
value that produced it should not be able to change under the renderer's feet.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

#: What a cell may hold. Text passes through untouched (already Romanian: the
#: caller writes the document's own words); a decimal and a date are formatted
#: by the renderer; ``None`` prints as nothing.
Cell = str | Decimal | date | int | None

Align = Literal["left", "right", "center"]


@dataclass(frozen=True, slots=True)
class Column:
    header: str
    align: Align = "left"
    #: Relative width: each column takes ``weight / sum(weights)`` of the frame.
    weight: int = 1
    #: Decimal places for a `Decimal` cell. Money is two. ``None`` prints as
    #: many as the value carries and no trailing zeros -- for a quantity, whose
    #: precision is the unit's (ADR-055), or a rate, which is ``20`` and not
    #: ``20,00``.
    places: int | None = 2
    #: With ``places=None``, never fewer than this many: a unit price priced at
    #: four decimals prints all four, one priced at a round figure still prints
    #: ``1234,50`` and not ``1234,5``.
    min_places: int = 0


@dataclass(frozen=True, slots=True)
class Table:
    """The positions of a document. The header repeats on every page."""

    columns: tuple[Column, ...]
    rows: tuple[tuple[Cell, ...], ...]
    #: Rows set apart under the body, in bold: the totals the form asks for.
    footer: tuple[tuple[Cell, ...], ...] = ()

    def __post_init__(self) -> None:
        width = len(self.columns)
        for row in (*self.rows, *self.footer):
            if len(row) != width:
                raise ValueError(f"a row of {len(row)} cells in a table of {width} columns")


@dataclass(frozen=True, slots=True)
class Field:
    label: str
    value: Cell
    places: int | None = 2


@dataclass(frozen=True, slots=True)
class Fields:
    """A labelled block: a party to the document, or its own identifiers."""

    title: str | None
    fields: tuple[Field, ...]


@dataclass(frozen=True, slots=True)
class Columns:
    """Two blocks side by side -- the seller and the buyer."""

    left: Fields
    right: Fields


@dataclass(frozen=True, slots=True)
class Totals:
    """Label and amount lines set against the right margin; the last in bold."""

    fields: tuple[Field, ...]


@dataclass(frozen=True, slots=True)
class Signatures:
    """One line per signatory, with the room to sign."""

    labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Text:
    text: str
    style: Literal["body", "note", "heading"] = "body"


Section = Fields | Columns | Table | Totals | Signatures | Text


@dataclass(frozen=True, slots=True)
class PrintableDocument:
    #: The document's name as the form gives it -- *Factura fiscală*, *Fluturaș
    #: de salariu*. In Romanian, always: this is the document's own text, not an
    #: interface string (`C33`, ADR-033).
    title: str
    #: The identifying line under the title: series and number, or the period.
    subtitle: str | None
    sections: tuple[Section, ...]
    #: The name the browser offers when saving, without the extension. ASCII
    #: letters, digits, dots, dashes and underscores; the renderer does not
    #: sanitise it, because a name is part of what the caller decides.
    file_name: str
    #: A4 upright by default; the fiscal invoice's eight columns need the sheet
    #: turned, as the printed form is.
    landscape: bool = False


def file_name_of(*parts: str) -> str:
    """A file name from the document's own identifiers, ASCII by construction.

    `Fluturaș` becomes `Fluturas`, spaces and anything else become a dash: the
    name travels in a header, and a header with a diacritic in it is one some
    client drops. Empty parts are skipped; an empty result is `document`.
    """
    joined = "-".join(part for part in parts if part)
    ascii_only = unicodedata.normalize("NFKD", joined).encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9._-]+", "-", ascii_only).strip("-.") or "document"
