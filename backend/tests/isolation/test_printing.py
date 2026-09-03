"""The printed fiscal invoice -- `C22`, `C38`, `C39`, ADR-095 -- under the application role.

The payslip has its own module (`test_printing_payslip.py`): its fixtures seed the
payroll ledger, whose conventions collide with the sales world's. Four claims:

1. **Romanian whatever language is active.** Rendered with `ru` active the bytes
   are the same as with `ro` -- the pipeline opens the Romanian context itself and
   formats through the document module, which reads no language (ADR-033).
2. **Deterministic.** The same document rendered twice is the same bytes, so a
   PDF can be archived once and compared later (`F2.P1`).
3. **Legal names only** (`C39`): the partner's `legal_name` is on the page, the
   `internal_name` is not. Read back through `pypdf`, because a subset-embedded
   font writes glyph ids, not text, into the content stream.
4. **The routes answer as documents, or refuse with a code**: `application/pdf`
   inline for a numbered invoice, `sales.not_printable` for a draft (`C10`), and
   for another tenant the same 404 every reader of this project gives (IZ-04).

`translation.override`, never `activate`: the architecture guard forbids
server-side activation, and these tests must leave no language behind them.
"""

from __future__ import annotations

import io
import uuid
from collections.abc import Callable
from typing import Any

import pytest
from django.test import Client
from django.utils import translation
from pypdf import PdfReader

from evidenta.operations.sales.services.issuing import issue_and_post
from evidenta.operations.sales.services.printing import (
    SaleNotPrintableError,
    invoice_pdf,
    invoice_printable,
)
from evidenta.platform.documents.errors import DocumentNotFoundError
from evidenta.platform.rls.context import TenantContext, tenant_context
from tests.isolation.test_coa_api import HOST_A, mfa_key, signed_in  # noqa: F401
from tests.isolation.test_line_rounding import scale, source  # noqa: F401
from tests.isolation.test_sales_posting import SNAPSHOT, a_sale, sales_world  # noqa: F401

pytestmark = pytest.mark.django_db(databases=["default", "migration"])

INTERNAL_NAME = "CLIENT-INTERN-DE-CAUTARE"


def text_of(pdf: bytes) -> str:
    assert pdf.startswith(b"%PDF-")
    return "\n".join(page.extract_text() for page in PdfReader(io.BytesIO(pdf)).pages)


def other_tenant(world: dict[str, uuid.UUID]) -> TenantContext:
    return TenantContext(tenant_id=world["tenant_b"], user_id=world["user_b"], request_id="print-b")


# --- the fiscal invoice -------------------------------------------------------


def issued(world: dict[str, Any]) -> uuid.UUID:
    document_id = a_sale(world, amount="1234.50")
    issue_and_post(
        document_id=document_id,
        actor_user_id=world["user"],
        request_id="print",
        capability_snapshot=SNAPSHOT,
    )
    return document_id


def test_the_invoice_is_romanian_deterministic_and_names_the_legal_name(
    sales_world: dict[str, Any],  # noqa: F811 -- fixtures, imported to be found
    seed: Callable[..., None],
) -> None:
    # The internal name exists for lists and search (ADR-034); the document must
    # not carry it. Seeded, so the row is what production would hold.
    seed(
        "UPDATE partner SET internal_name = %s WHERE id = %s",
        [INTERNAL_NAME, sales_world["partner"]],
    )

    with tenant_context(sales_world["context"]):
        document_id = issued(sales_world)
        number = invoice_printable(document_id).subtitle
        with translation.override("ru"):
            under_russian = invoice_pdf(document_id)
        with translation.override("ro"):
            romanian = invoice_pdf(document_id)
        again = invoice_pdf(document_id)

    assert romanian == under_russian == again

    text = text_of(romanian)
    assert "Factura fiscală" in text
    assert number is not None and number.startswith("Nr. ")
    # The seller and the buyer by their legal names and identifiers.
    assert "Alpha Vânzări" in text and "1002600000911" in text
    assert "Client SRL" in text
    assert INTERNAL_NAME not in text
    # The act's columns (read back across their wrapped lines), and the amounts
    # at the jurisdiction's separator.
    flat = " ".join(text.split())
    assert "10.5 Valoarea totală fără TVA, lei" in flat
    assert "10.8 Valoarea mărfurilor/activelor, serviciilor, lei" in flat
    assert "12. TOTAL (pe factura fiscală)" in flat
    assert "1234,50" in text and "1234.50" not in text
    # The date the Moldovan way, the quantity without the storage scale.
    assert "20.01.2026" in text
    assert "Pagina 1" in text


def test_a_draft_is_refused_and_a_numbered_invoice_is_served_inline(
    sales_world: dict[str, Any],  # noqa: F811
    signed_in: Client,  # noqa: F811
) -> None:
    with tenant_context(sales_world["context"]):
        draft = a_sale(sales_world)
        numbered = issued(sales_world)
        with pytest.raises(SaleNotPrintableError):
            invoice_printable(draft)

    refused = signed_in.get(f"/api/v1/sales/invoices/{draft}/pdf", headers={"host": HOST_A})
    assert refused.status_code == 409, refused.content
    assert refused.json()["code"] == "sales.not_printable"

    served = signed_in.get(f"/api/v1/sales/invoices/{numbered}/pdf", headers={"host": HOST_A})
    assert served.status_code == 200, served.content
    assert served["Content-Type"] == "application/pdf"
    assert served["Content-Disposition"].startswith('inline; filename="factura-')
    assert served["Content-Disposition"].endswith('.pdf"')
    assert served.content.startswith(b"%PDF-")

    # The same bytes over HTTP as from the service: nothing on the way adds a
    # date or a request id.
    with tenant_context(sales_world["context"]):
        assert served.content == invoice_pdf(numbered)


def test_another_tenant_cannot_print_the_invoice(
    sales_world: dict[str, Any],  # noqa: F811
    world: dict[str, uuid.UUID],
) -> None:
    with tenant_context(sales_world["context"]):
        numbered = issued(sales_world)

    with tenant_context(other_tenant(world)), pytest.raises(DocumentNotFoundError) as refused:
        invoice_printable(numbered)
    assert refused.value.status == 404
