"""The treasury document vocabulary -- money in, money out.

**Neither carries positions**, and the registry anticipated this case by name: a
receipt is an amount, not a list of things. What it settles is not on it either
(ADR-073 §5) -- the posting does not need to know which invoice, and the link is
settlement, which is `F2.A3`.
"""

from __future__ import annotations

from evidenta.platform.documents.registry import DocumentTypeSpec, register

#: Money received. Ours to number, unlike a supplier's invoice.
RECEIPT = "treasury.receipt"

#: Money paid out.
PAYMENT = "treasury.payment"


def register_treasury_types() -> None:
    for code in (RECEIPT, PAYMENT):
        register(
            DocumentTypeSpec(
                code=code,
                owner="treasury",
                requires_partner=True,
                # The first types in the product that carry no positions. The flag
                # existed before they did, so nothing had to be widened for them.
                carries_lines=False,
                requires_lines=False,
            )
        )
