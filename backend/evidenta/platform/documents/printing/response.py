"""A printed document as an HTTP answer.

Inline rather than attachment: the link on a screen is opened by the browser in
its own tab, which is how a person reads an invoice before deciding to save it.
The file name is the document's own (`PrintableDocument.file_name`), ASCII by
construction -- a `Content-Disposition` header carrying a diacritic is a header
some clients drop -- and the body is exactly what :func:`render` produced, so two
downloads of one document are the same bytes.
"""

from __future__ import annotations

from django.http import HttpResponse

from evidenta.platform.documents.printing.document import PrintableDocument
from evidenta.platform.documents.printing.render import render

CONTENT_TYPE = "application/pdf"


def pdf_response(document: PrintableDocument) -> HttpResponse:
    response = HttpResponse(render(document), content_type=CONTENT_TYPE)
    response["Content-Disposition"] = f'inline; filename="{document.file_name}.pdf"'
    return response
