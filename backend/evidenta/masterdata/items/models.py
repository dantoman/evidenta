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

    Five kinds, and the list is the one an entity here actually keeps: goods
    bought to resell, materials consumed in production, products made, services,
    and `OMVSD` -- *obiecte de mica valoare si scurta durata*, the category SNC
    treats separately from fixed assets. The English identifier spells it out
    because `C15` puts code in English while the legal term keeps its own form;
    the label a user sees comes from the resource files (`C32`), never from here.

    **What this enum does not decide.** Which account a kind resolves to is not a
    property of the catalogue and is not here. The kind is a documentary and
    inventory fact; the correspondence is an accounting one.
    """

    GOODS = "goods"
    MATERIAL = "material"
    PRODUCT = "product"
    SERVICE = "service"
    LOW_VALUE_SHORT_LIVED = "low_value_short_lived"


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

    #: What appears on a document, in a register and in an export (`C39`,
    #: ADR-034). The only name any of those three may read.
    name = models.TextField()

    #: The user's own name for the item, in whatever alphabet they work in.
    #: Shown in lists, matched by search, accepted by importers -- and **never**
    #: printed on a document (ADR-034). Adding it now is what keeps the answer to
    #: `OD-40` from requiring a catalogue to be retyped, in either direction.
    internal_name = models.TextField(null=True, blank=True)

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

    #: The key under which this item's default VAT rate is registered in the
    #: fiscal nomenclature -- **a key, never a rate**. A percentage stored here
    #: would be a fiscal parameter compiled into master data, which `R15` calls a
    #: critical defect, and it would not move when the law does.
    vat_rate_key = models.TextField(null=True, blank=True)

    #: The tariff heading -- *pozitia tarifara* of the Nomenclatura combinata a
    #: marfurilor. Needed on a customs declaration and on an e-Factura line for
    #: goods, and stored as the code it is: this module does not carry the
    #: nomenclature and does not validate against one it does not have.
    tariff_code = models.TextField(null=True, blank=True)

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
            models.Index(fields=["tenant", "internal_name"], name="item_internal_name_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.sku} {self.name}"


class ItemUnit(models.Model):
    """An alternative unit this item is handled in, and what it comes to.

    Distinct from `unit_conversion`, which is general: a box holds twelve of
    *this* item and six of another, so the coefficient belongs to the pair, not
    to the units. Both exist, and conflating them would make every catalogue
    entry that packs differently from the tenant default wrong.

    Stored as a ratio for the reason `unit_conversion` gives: a box of twelve is
    exact, a kilogram of a liquid in litres is not, and rounding the second into
    a single decimal factor at definition time loses precision every later
    quantity inherits.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    item = models.ForeignKey(
        Item, on_delete=models.CASCADE, db_column="item_id", related_name="units"
    )
    #: Lazy reference rather than an import, for the reason `Item.base_unit`
    #: gives: the foreign key is schema composition, the import would be the
    #: coupling `D6` exists to stop.
    unit = models.ForeignKey(
        "uom.UnitOfMeasure", on_delete=models.PROTECT, db_column="unit_id", related_name="+"
    )

    #: ``numerator`` base units make ``denominator`` of this unit.
    numerator = models.DecimalField(max_digits=20, decimal_places=6)
    denominator = models.DecimalField(max_digits=20, decimal_places=6)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "item_unit"
        constraints = [
            models.UniqueConstraint(fields=["item", "unit"], name="item_unit_unique"),
            models.CheckConstraint(
                condition=models.Q(numerator__gt=0) & models.Q(denominator__gt=0),
                name="item_unit_positive",
            ),
        ]
        indexes = [
            models.Index(fields=["tenant", "item"], name="item_unit_idx"),
        ]

    def __str__(self) -> str:
        return f"{self.item_id}:{self.unit_id}"


class ItemBarcode(models.Model):
    """One of the codes that resolve to this item when scanned.

    A table rather than a column, because an item routinely has several -- one on
    the piece, one on the box, an old supplier code that still turns up on
    deliveries. A single column meant the second one had nowhere to go, and the
    usual workaround is a comma-separated list nobody can index.

    Unique **within the tenant**, not within the item: the whole purpose of a
    barcode is that scanning it identifies exactly one thing, and a code that
    resolved to two items would be found by whoever scanned it into a document.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.PROTECT, db_column="tenant_id")
    item = models.ForeignKey(
        Item, on_delete=models.CASCADE, db_column="item_id", related_name="barcodes"
    )

    barcode = models.TextField()

    #: Which packing the code identifies, when it identifies one. Null means the
    #: base unit -- the piece.
    unit = models.ForeignKey(
        "uom.UnitOfMeasure",
        on_delete=models.PROTECT,
        db_column="unit_id",
        null=True,
        blank=True,
        related_name="+",
    )

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "item_barcode"
        constraints = [
            models.UniqueConstraint(fields=["tenant", "barcode"], name="item_barcode_unique"),
            models.CheckConstraint(condition=~models.Q(barcode=""), name="item_barcode_nonempty"),
        ]
        indexes = [
            models.Index(fields=["tenant", "item"], name="item_barcode_item_idx"),
        ]

    def __str__(self) -> str:
        return self.barcode
