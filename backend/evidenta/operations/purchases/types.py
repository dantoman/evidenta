"""The purchase-side document vocabulary."""

from __future__ import annotations

from evidenta.platform.documents.registry import DocumentTypeSpec, register

#: What we received, with the supplier's own number and date beside it.
PURCHASE_DOCUMENT = "purchases.document"

#: What we asked a supplier for. Operational, no accounting effect.
SUPPLIER_ORDER = "purchases.order"


def register_purchase_types() -> None:
    register(
        DocumentTypeSpec(
            code=PURCHASE_DOCUMENT,
            owner="purchases",
            requires_partner=True,
            carries_lines=True,
            requires_lines=True,
        )
    )
    register(
        DocumentTypeSpec(
            code=SUPPLIER_ORDER,
            owner="purchases",
            requires_partner=True,
            carries_lines=True,
            requires_lines=False,
            converts_into=(PURCHASE_DOCUMENT,),
        )
    )
