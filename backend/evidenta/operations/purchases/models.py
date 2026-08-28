"""What a purchase-side document carries beyond the shared header.

The same structure as a sale, in the other direction, and one difference that is
not cosmetic: **the supplier's number and date are the supplier's**. They are not
allocated by our numbering, they do not have to be unique in our register, and
they do not follow our series. Storing them in the shared `series`/`number`
columns would have been convenient and would have made our register claim
authorship of numbers we did not issue.
"""

from __future__ import annotations

from django.db import models

from evidenta.platform.documents.models import Document
from evidenta.platform.tenancy.models import Company, Tenant


class PurchaseDocument(models.Model):
    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        db_column="document_id",
        primary_key=True,
        related_name="purchase",
    )
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    #: The supplier, copied from the header. Denormalised for one reason: it is
    #: **part of the deduplication key** (`R20`), and a key that lived half on
    #: this table and half on `document` could not be a constraint at all. Two
    #: suppliers issuing invoice `001` on the same day is ordinary, and a key
    #: without the supplier would refuse the second one -- silently correct-looking
    #: and wrong.
    partner_id = models.UUIDField()

    #: As written on the document we received. A code, so byte ordering (`C34`).
    supplier_document_number = models.TextField()
    supplier_document_date = models.DateField()

    class Meta:
        db_table = "purchase_document"
        constraints = [
            models.CheckConstraint(
                condition=~models.Q(supplier_document_number=""),
                name="purchase_document_has_supplier_number",
            ),
            # The same document arriving twice -- once through an import, once
            # typed -- is deduplicated on the natural business key (`R20`): the
            # supplier, their own number, and their own date, inside one company.
            # Separate from idempotency, which lives on the accounting event and
            # answers a different question -- a technical retry rather than a
            # document that reached us by two roads.
            models.UniqueConstraint(
                fields=[
                    "company",
                    "partner_id",
                    "supplier_document_number",
                    "supplier_document_date",
                ],
                name="purchase_document_supplier_reference_unique",
            ),
        ]
        indexes = [
            models.Index(
                fields=["tenant", "company", "supplier_document_date"],
                name="purchase_document_idx",
            ),
            models.Index(fields=["company", "partner_id"], name="purchase_document_partner_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.supplier_document_number} din {self.supplier_document_date}"


class SupplierOrder(models.Model):
    """What we asked a supplier for. Operational; no accounting effect."""

    document = models.OneToOneField(
        Document,
        on_delete=models.CASCADE,
        db_column="document_id",
        primary_key=True,
        related_name="supplier_order",
    )
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey(Company, on_delete=models.PROTECT, db_column="company_id")

    expected_delivery_date = models.DateField(null=True, blank=True)

    class Meta:
        db_table = "supplier_order"
        indexes = [
            models.Index(
                fields=["tenant", "company", "expected_delivery_date"],
                name="supplier_order_idx",
            ),
        ]

    def __str__(self) -> str:
        return str(self.document_id)
