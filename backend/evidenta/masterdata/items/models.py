"""The item catalogue -- F0.7.

Built now, used from F2 and F4. What matters at F0 is not the functionality but
the shape: ``tracks_lots`` and ``tracks_serials`` exist here even though lot and
serial handling is F4, because adding them afterwards means touching every stock
movement ever recorded.

That is the rule from the implementation spec, in its own words: modelling
something in F0 means the current phase does not make the future module
impossible -- not that the module exists.
"""

from __future__ import annotations

import uuid

from django.db import models

from evidenta.platform.tenancy.models import Tenant


class ItemKind(models.TextChoices):
    """What the item is, which decides what can be done with it.

    A service has no stock and no warehouse; goods have both. Posting resolves
    differently for each, so the distinction belongs in the catalogue rather than
    in each document that references it.
    """

    GOODS = "goods"
    SERVICE = "service"
    PRODUCT = "product"


class ItemCategory(models.Model):
    """Grouping, and the level valuation policy attaches to.

    Amendment C.4 puts the inventory valuation method here: a default per company,
    overridden per category. SNC 2 follows IAS 2, which allows different formulas
    for stocks of different nature or use and asks for consistency within a
    category -- so the category is the level the standard itself names.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")

    code = models.TextField()
    name = models.TextField()
    parent = models.ForeignKey(
        "self", on_delete=models.PROTECT, db_column="parent_id", null=True, blank=True
    )

    # Left unset here. The vocabulary of methods is FIFO and weighted average
    # (amendment C.4), but the accounting confirmation is OD-06 and the schema is
    # F4 -- so the column that will carry it belongs with the inventory module,
    # not with a guess made now.
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "item_category"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "code"], name="item_category_code_unique"),
        ]

    def __str__(self) -> str:
        return self.code


class Item(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")

    sku = models.TextField()
    name = models.TextField()
    kind = models.TextField(choices=ItemKind.choices, default=ItemKind.GOODS)

    category = models.ForeignKey(
        ItemCategory,
        on_delete=models.PROTECT,
        db_column="category_id",
        null=True,
        blank=True,
    )
    # Lazy reference rather than an import, for the same reason as
    # partners.registry_entry: the key is schema composition, the import would be
    # the coupling D6 exists to stop.
    base_unit = models.ForeignKey(
        "uom.UnitOfMeasure", on_delete=models.PROTECT, db_column="base_unit_id"
    )

    # Modelled at F0, handled at F4. Changing these on an item that already has
    # movements is not a settings change -- it is a restatement of stock, which is
    # why they are here from the start rather than added when lots arrive.
    tracks_lots = models.BooleanField(default=False)
    tracks_serials = models.BooleanField(default=False)

    barcode = models.TextField(null=True, blank=True)
    vat_rate_key = models.TextField(null=True, blank=True)

    is_active = models.BooleanField(default=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "item"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "sku"], name="item_sku_unique"),
            models.CheckConstraint(
                condition=models.Q(kind__in=ItemKind.values), name="item_kind_valid"
            ),
            # A service has no stock, so tracking lots or serials on one is a
            # setting that can never be honoured.
            models.CheckConstraint(
                condition=~models.Q(kind=ItemKind.SERVICE)
                | models.Q(tracks_lots=False, tracks_serials=False),
                name="item_service_tracks_nothing",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "name"], name="item_name_idx"),
            models.Index(fields=["tenant", "is_active"], name="item_active_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.sku} {self.name}"
