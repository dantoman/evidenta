"""The printed-document pipeline -- `C22`, `C38`, ADR-095.

**Opens the Romanian context explicitly, on entry.** ADR-033: a legal document
does not inherit the language of the request or of the task that asked for it.
`translation.override("ro")` wraps the whole rendering; the formatter it calls
reads no language at all, so today the override changes nothing -- which is the
state the guard in `tests/architecture/test_document_language.py` pins. The day
something in this path consults the active language, the override is what keeps
the document Romanian.

**The same document renders to the same bytes.** ReportLab is built with
``invariant=1``: the creation and modification dates are a fixed epoch, the file
identifier is derived from the content, and nothing on the page depends on the
clock. A PDF that can be regenerated and compared byte for byte is one that can be
archived once and checked later, which is what `F2.P1` asks for.

**One embedded font, shipped here.** DejaVu Sans covers the comma-below
diacritics (`ș`, `ț`, U+0218..U+021B) that the fonts a PDF reader has built in do
not, and it is embedded as a subset so the file reads the same on a machine with
no fonts at all. The face and its licence sit in `fonts/` next to this module; a
font resolved from the operating system would make the output depend on the
container image, which is the opposite of invariant.

**No knowledge of any business document.** This module renders the value in
`document.py`; what a fiscal invoice or a payslip contains is the caller's
(`operations/sales/services/printing.py`, `operations/payroll/services/payslip_pdf.py`).
"""

from __future__ import annotations

import io
from collections.abc import Sequence
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Any, Literal
from xml.sax.saxutils import escape

from django.utils import translation
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import Flowable, Paragraph, SimpleDocTemplate, Spacer, TableStyle
from reportlab.platypus import Table as GridTable

from evidenta.platform.documents.formatting import date_ro, decimal_ro
from evidenta.platform.documents.printing.document import (
    Align,
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
)

FONT = "DejaVuSans"
FONT_BOLD = "DejaVuSans-Bold"
FONTS = Path(__file__).resolve().parent / "fonts"

#: The producer string every document carries. Fixed: a version number here
#: would make the bytes change on every upgrade for no change in content.
PRODUCER = "Evidenta"

MARGIN = 15 * mm

BODY_SIZE = 9
SMALL_SIZE = 7.5
RULE = colors.HexColor("#444444")

#: ReportLab dispatches on the integer constants when it draws a line; the
#: string spellings its stubs also admit are not honoured on every path
#: (measured on 5.0.1: a right-aligned paragraph raises inside `drawPara`).
_ALIGNMENTS: dict[Align, Literal[0, 1, 2]] = {
    "left": TA_LEFT,
    "center": TA_CENTER,
    "right": TA_RIGHT,
}
SHADE = colors.HexColor("#EEEEEE")
MUTED = colors.HexColor("#555555")


def render(document: PrintableDocument) -> bytes:
    """The document as PDF bytes, in Romanian, whatever language was active."""
    with translation.override("ro"):
        return _render(document)


def text_of(value: Cell, places: int | None = 2, min_places: int = 0) -> str:
    """One cell as the text the page shows -- the only place a value is formatted."""
    if value is None:
        return ""
    if isinstance(value, Decimal):
        if places is None:
            places = max(min_places, _places_of(value))
        return decimal_ro(value, places)
    if isinstance(value, date):
        return date_ro(value)
    return str(value)


def _places_of(value: Decimal) -> int:
    """As many decimals as the value carries and no trailing zeros: `1.000000`
    prints as `1`, `1.500000` as `1,5`, `100` as `100`."""
    exponent = value.normalize().as_tuple().exponent
    return max(0, -exponent) if isinstance(exponent, int) else 0


def _register_fonts() -> None:
    """Idempotent: ReportLab keeps a process-wide registry, and registering a
    face twice under the same name is refused."""
    if FONT in pdfmetrics.getRegisteredFontNames():
        return
    pdfmetrics.registerFont(TTFont(FONT, str(FONTS / "DejaVuSans.ttf")))
    pdfmetrics.registerFont(TTFont(FONT_BOLD, str(FONTS / "DejaVuSans-Bold.ttf")))
    pdfmetrics.registerFontFamily(
        FONT, normal=FONT, bold=FONT_BOLD, italic=FONT, boldItalic=FONT_BOLD
    )


def _style(
    name: str,
    *,
    size: float = BODY_SIZE,
    bold: bool = False,
    align: Align = "left",
    colour: colors.Color = colors.black,
    leading: float | None = None,
) -> ParagraphStyle:
    return ParagraphStyle(
        name,
        fontName=FONT_BOLD if bold else FONT,
        fontSize=size,
        leading=leading if leading is not None else size * 1.25,
        alignment=_ALIGNMENTS[align],
        textColor=colour,
    )


STYLES = {
    "title": _style("title", size=15, bold=True),
    "subtitle": _style("subtitle", size=10, colour=MUTED),
    "heading": _style("heading", size=BODY_SIZE, bold=True),
    "body": _style("body"),
    "note": _style("note", size=SMALL_SIZE, colour=MUTED),
    "label": _style("label", size=SMALL_SIZE, colour=MUTED),
    "value": _style("value"),
    "value_bold": _style("value_bold", bold=True),
    "cell": _style("cell", size=SMALL_SIZE + 0.5),
    "cell_bold": _style("cell_bold", size=SMALL_SIZE + 0.5, bold=True),
    "header": _style("header", size=SMALL_SIZE - 1, bold=True, leading=SMALL_SIZE + 0.5),
    "signature": _style("signature", size=SMALL_SIZE, colour=MUTED),
}


def _paragraph(text: str, style: str, align: Align = "left") -> Paragraph:
    base = STYLES[style]
    if align != "left":
        base = ParagraphStyle(f"{style}-{align}", parent=base, alignment=_ALIGNMENTS[align])
    return Paragraph(escape(text).replace("\n", "<br/>"), base)


def _render(document: PrintableDocument) -> bytes:
    _register_fonts()
    buffer = io.BytesIO()
    pagesize = landscape(A4) if document.landscape else A4
    frame = pagesize[0] - 2 * MARGIN
    template = SimpleDocTemplate(
        buffer,
        pagesize=pagesize,
        leftMargin=MARGIN,
        rightMargin=MARGIN,
        topMargin=MARGIN,
        bottomMargin=MARGIN + 6 * mm,
        title=document.title,
        subject=document.subtitle or "",
        author=PRODUCER,
        creator=PRODUCER,
        producer=PRODUCER,
        # The whole reason this is a pipeline: identical bytes for an identical
        # document. Fixed dates, content-derived identifier, no clock anywhere.
        invariant=1,
    )
    story: list[Flowable] = [_paragraph(document.title, "title")]
    if document.subtitle:
        story.append(_paragraph(document.subtitle, "subtitle"))
    story.append(Spacer(1, 4 * mm))
    for section in document.sections:
        story.extend(_section(section, frame))
        story.append(Spacer(1, 3 * mm))
    template.build(story, onFirstPage=_page_footer, onLaterPages=_page_footer)
    return buffer.getvalue()


def _page_footer(canvas: Canvas, template: Any) -> None:
    """The page number, and nothing that could vary between two renderings."""
    canvas.saveState()
    canvas.setFont(FONT, SMALL_SIZE)
    canvas.setFillColor(MUTED)
    canvas.drawRightString(
        template.pagesize[0] - MARGIN, MARGIN / 2, f"Pagina {canvas.getPageNumber()}"
    )
    canvas.restoreState()


def _section(section: Section, frame: float) -> list[Flowable]:
    if isinstance(section, Text):
        return [_paragraph(section.text, section.style)]
    if isinstance(section, Fields):
        return [_fields(section, frame)]
    if isinstance(section, Columns):
        return [_columns(section, frame)]
    if isinstance(section, Table):
        return [_table(section, frame)]
    if isinstance(section, Totals):
        return [_totals(section)]
    return [_signatures(section, frame)]


def _fields(block: Fields, width: float) -> Flowable:
    rows: list[list[Flowable]] = []
    if block.title:
        rows.append([_paragraph(block.title, "heading"), _paragraph("", "value")])
    for field in block.fields:
        rows.append(
            [
                _paragraph(field.label, "label"),
                _paragraph(text_of(field.value, field.places), "value"),
            ]
        )
    label_width = min(width * 0.38, 55 * mm)
    grid = GridTable(rows, colWidths=[label_width, width - label_width], hAlign="LEFT")
    style: list[Any] = [
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 0),
        ("RIGHTPADDING", (0, 0), (-1, -1), 4),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
    ]
    if block.title:
        style.append(("SPAN", (0, 0), (1, 0)))
    grid.setStyle(TableStyle(style))
    return grid


def _columns(section: Columns, frame: float) -> Flowable:
    gutter = 6 * mm
    half = (frame - gutter) / 2
    grid = GridTable(
        [[_fields(section.left, half), _fields(section.right, half)]],
        colWidths=[half + gutter / 2, half + gutter / 2],
        hAlign="LEFT",
    )
    grid.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (0, 0), gutter),
                ("RIGHTPADDING", (1, 0), (1, 0), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    return grid


def _table(table: Table, frame: float) -> Flowable:
    total_weight = sum(column.weight for column in table.columns)
    widths = [frame * column.weight / total_weight for column in table.columns]
    header = [_paragraph(column.header, "header", column.align) for column in table.columns]
    body = [_row(table.columns, row, "cell") for row in table.rows]
    footer = [_row(table.columns, row, "cell_bold") for row in table.footer]
    grid = GridTable([header, *body, *footer], colWidths=widths, repeatRows=1, hAlign="LEFT")
    style: list[Any] = [
        ("GRID", (0, 0), (-1, -1), 0.4, RULE),
        ("BACKGROUND", (0, 0), (-1, 0), SHADE),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (-1, -1), 3),
        ("RIGHTPADDING", (0, 0), (-1, -1), 3),
        ("TOPPADDING", (0, 0), (-1, -1), 2),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
    ]
    if footer:
        first_footer = 1 + len(body)
        style.append(("BACKGROUND", (0, first_footer), (-1, -1), SHADE))
    grid.setStyle(TableStyle(style))
    return grid


def _row(columns: Sequence[Column], row: Sequence[Cell], style: str) -> list[Flowable]:
    return [
        _paragraph(text_of(value, column.places, column.min_places), style, column.align)
        for column, value in zip(columns, row, strict=True)
    ]


def _totals(section: Totals) -> Flowable:
    rows: list[list[Flowable]] = []
    last = len(section.fields) - 1
    for position, field in enumerate(section.fields):
        style = "value_bold" if position == last else "value"
        rows.append(
            [
                _paragraph(field.label, style, "right"),
                _paragraph(text_of(field.value, field.places), style, "right"),
            ]
        )
    grid = GridTable(rows, colWidths=[70 * mm, 40 * mm], hAlign="RIGHT")
    grid.setStyle(
        TableStyle(
            [
                ("LINEABOVE", (0, last), (-1, last), 0.6, RULE),
                ("TOPPADDING", (0, 0), (-1, -1), 2),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
            ]
        )
    )
    return grid


def _signatures(section: Signatures, frame: float) -> Flowable:
    count = max(1, len(section.labels))
    width = frame / count
    cells = [
        _paragraph(f"{label}\n\n______________________", "signature") for label in section.labels
    ]
    grid = GridTable([cells], colWidths=[width] * count, hAlign="LEFT")
    grid.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "BOTTOM"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 8 * mm),
            ]
        )
    )
    return grid


__all__ = ["Field", "render", "text_of"]
