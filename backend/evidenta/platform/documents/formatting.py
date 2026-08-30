"""Document formatting -- fixed `ro-MD` conventions that never consult the active language.

ADR-033 "Formatarea": numbers and dates *on documents* come from a document
formatting module with fixed `ro-MD` conventions, and that module does not read
the active language. `C18` asks for one formatting module in the client, for
display; this is its pair on the server, for what leaves the system as a
register, an export or a printed form. They are not the same module and do not
share a source of truth: one follows the user, this one follows the jurisdiction.

**Nothing here touches `django.utils.formats` or `translation`.** Measured before
the rule was written (ADR-033 §Context): `date_format` renders a date according
to whoever activated a language last on the thread, and the decimal separator
flips with it. A register exported under a Russian interface would come out with
`7 марта` and a dot -- an artefact no inspection accepts (Legea nr. 287/2017,
art. 7 alin. (1)). So the conventions are literal here, and the guard in
`tests/architecture/test_document_language.py` proves the output does not move
when the active language does.

**What rounds, and why that is allowed.** `decimal_ro` reduces a stored amount to
the places asked for, which on a register is two. This is the display layer of
ADR-037 §4 -- the stored value is authoritative and untouched -- and the same
reduction the client's `amount()` makes through `Intl`, so an export and the
screen it was taken from show the same figure. Ties round away from zero, which
is what `Intl.NumberFormat` does by default; the point is not that this is the
right rounding for anything fiscal (it is not -- `DNB-08` is settled elsewhere)
but that the two display layers agree with each other.
"""

from __future__ import annotations

from datetime import date
from decimal import ROUND_HALF_UP, Decimal

#: The separator the jurisdiction reads. `1234,56`, never `1234.56`, on anything
#: a person or an inspector reads off a document.
DECIMAL_SEPARATOR = ","


def decimal_ro(value: Decimal, places: int = 2) -> str:
    """A stored decimal, written the Romanian way, at ``places`` decimals.

    No thousands separator. Exports are read by programs as often as by people,
    and a grouping dot inside a number is what makes a spreadsheet read `1.234`
    as one and a bit.
    """
    if not isinstance(value, Decimal):
        raise TypeError(f"decimal_ro formats Decimal, got {type(value).__name__}")
    quantum = Decimal(1).scaleb(-places)
    text = f"{value.quantize(quantum, rounding=ROUND_HALF_UP):f}"
    return text.replace(".", DECIMAL_SEPARATOR)


def date_ro(value: date) -> str:
    """`zz.ll.aaaa` -- the order and the separator every Moldovan form prints."""
    return f"{value.day:02d}.{value.month:02d}.{value.year:04d}"
