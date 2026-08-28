"""The sales-side document vocabulary.

Separate from `apps.py` so the declarations can be read and tested without
starting an application registry, and separate from `services` so importing a
service does not have the side effect of registering a type.
"""

from __future__ import annotations

from evidenta.platform.documents.registry import DocumentTypeSpec, register

#: One type, with a nature on the header -- delivery or advance. Not two types:
#: the header, the positions, the numbering and the lifecycle are identical, and
#: splitting them would have meant two of everything to keep one attribute apart.
SALES_DOCUMENT = "sales.document"

#: An offer. Operational, no accounting effect, becomes a sale.
PROFORMA = "sales.proforma"

#: What the customer asked for. Operational, no accounting effect, becomes a sale.
CUSTOMER_ORDER = "sales.order"


def register_sales_types() -> None:
    register(
        DocumentTypeSpec(
            code=SALES_DOCUMENT,
            owner="sales",
            requires_partner=True,
            carries_lines=True,
            requires_lines=True,
        )
    )
    register(
        DocumentTypeSpec(
            code=PROFORMA,
            owner="sales",
            requires_partner=True,
            carries_lines=True,
            requires_lines=True,
            converts_into=(SALES_DOCUMENT,),
        )
    )
    register(
        DocumentTypeSpec(
            code=CUSTOMER_ORDER,
            owner="sales",
            requires_partner=True,
            carries_lines=True,
            # An order may legitimately be validated before every position is
            # priced -- that is what an order is. An invoice may not.
            requires_lines=False,
            converts_into=(SALES_DOCUMENT,),
        )
    )
