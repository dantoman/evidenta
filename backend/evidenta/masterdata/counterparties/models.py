"""The global counterparty registry -- amendment section C.1.

A public register keyed on IDNO, fed from public sources. Global, with no tenant
column, and one of the enumerated exceptions to R1.

It earns its place three times over, and the third is the one that matters:

* validation at entry -- the IDNO exists, the name matches, the VAT status is real
* resolving the counterparty when an invoice arrives through e-Factura, by
  identifier rather than by matching text
* **the network effect**: when issuer and recipient are both in Evidenta, the
  invoice appears in the recipient's inbox already structured

The amendment calls the third potentially worth more commercially than any module
in phases 5 and up. It costs little now and a great deal after thousands of
tenants have created partners freely -- which is the whole argument for building
the registry before the partners rather than after.

**What is not here.** The network effect itself is a path by which one tenant's
data reaches another, and it appears in neither the read models nor the
enumerated privileged paths. That is OD-12, open. This module builds the register;
it does not build the flow.
"""

from __future__ import annotations

import uuid

from django.db import models


class CounterpartyStatus(models.TextChoices):
    ACTIVE = "active"
    STRUCK_OFF = "struck_off"
    UNKNOWN = "unknown"


class CounterpartyRegistry(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    # The key the whole register turns on. A code, so byte ordering (C34).
    idno = models.TextField(unique=True)

    legal_name = models.TextField()
    legal_form = models.TextField(null=True, blank=True)

    vat_registered = models.BooleanField(default=False)
    vat_code = models.TextField(null=True, blank=True)

    registered_address = models.JSONField(null=True, blank=True)
    status = models.TextField(
        choices=CounterpartyStatus.choices, default=CounterpartyStatus.UNKNOWN
    )

    # Where this row came from and when it was last confirmed. A register whose
    # rows cannot be dated is a register nobody can decide to trust: "the VAT
    # status says registered" means nothing without "as of when".
    source = models.TextField()
    source_reference = models.TextField(null=True, blank=True)
    fetched_at = models.DateTimeField()

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "counterparty_registry"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(status__in=CounterpartyStatus.values),
                name="counterparty_registry_status_valid",
            ),
        ]
        indexes = [
            models.Index(fields=["legal_name"], name="counterparty_name_idx"),
            models.Index(fields=["status"], name="counterparty_status_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.idno} {self.legal_name}"
