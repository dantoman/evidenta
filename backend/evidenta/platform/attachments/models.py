"""Attachment metadata -- Spec A section 5.3, ADR-030.

**Company level, not tenant level.** The deciding argument is access, not
consistency: documents are company-scoped and access is granted per company
(`company_access`), so an attachment held at tenant level would have a wider
access boundary than the document it accompanies. An accountant given access to
one company of a holding would see the others' attachments.

Attachments are the worst place for that to happen. An invoice PDF contains
everything the document row does and usually more -- the partner's bank details,
commercial terms, signatures. It is not a column, it is a page.

**The bytes are not here.** This table holds metadata; the object lives in
S3-compatible storage under a key derived in `storage.py`. What that storage
actually is -- bucket per tenant or prefix per tenant, how URLs are signed, what
the size and type limits are, whether files are scanned, what happens at
`archived` -- is OD-52 and open. The contract is written; the provider is not
chosen.
"""

from __future__ import annotations

import uuid

from django.db import models


class Attachment(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    tenant = models.ForeignKey("tenancy.Tenant", on_delete=models.PROTECT, db_column="tenant_id")
    company = models.ForeignKey("tenancy.Company", on_delete=models.PROTECT, db_column="company_id")

    #: Nullable, and the reason is a real workflow rather than laxity. A scan
    #: often arrives before anybody has decided which document it is -- that is
    #: the whole shape of the e-Factura-plus-scanned-PDF deduplication case in
    #: R20 -- and an upload that had to name its document first would force the
    #: user to guess, or force the code to create a placeholder document.
    document = models.ForeignKey(
        "documents.Document",
        on_delete=models.PROTECT,
        db_column="document_id",
        null=True,
        blank=True,
        related_name="attachments",
    )

    #: Derived by `storage.object_key`, never from user input. Unique because two
    #: rows pointing at one object make deletion unsafe: removing either would
    #: break the other.
    storage_key = models.TextField(unique=True)

    #: Kept so a download can return the name the user recognises. Deliberately
    #: not part of the key -- a filename that reaches a path is how directory
    #: traversal gets written.
    original_filename = models.TextField()
    content_type = models.TextField()
    byte_size = models.BigIntegerField()

    #: Makes duplication visible: the same file uploaded to two companies gives
    #: two rows with one fingerprint. ADR-030 accepts the duplication and keeps
    #: the option of deduplicating at the storage layer later, without touching
    #: the access boundary. Also the integrity check on download.
    checksum_sha256 = models.CharField(max_length=64)

    uploaded_by_user_id = models.UUIDField()
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "attachment_metadata"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(byte_size__gt=0), name="attachment_size_positive"
            ),
            # 64 lowercase hex characters. A checksum stored in some other shape
            # compares unequal to a correctly computed one, which reads as
            # corruption on every download.
            models.CheckConstraint(
                condition=models.Q(checksum_sha256__regex=r"^[0-9a-f]{64}$"),
                name="attachment_checksum_shape",
            ),
        ]
        indexes = [
            # Leads with the tenant context, then company: every query starts
            # there because every policy does (R22 discipline).
            models.Index(fields=["tenant", "company", "uploaded_at"], name="attachment_scope_idx"),
            models.Index(fields=["document"], name="attachment_document_idx"),
            # Duplicate detection is per company, because that is the boundary
            # ADR-030 fixed: the same file in two companies is two attachments,
            # not one seen twice.
            models.Index(fields=["company", "checksum_sha256"], name="attachment_checksum_idx"),
        ]

    def __str__(self) -> str:
        return self.original_filename
