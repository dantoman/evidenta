"""What another module may ask about an item, without touching its table.

`D6`: modules talk through services, not through each other's models. A document
line needs four facts about a catalogue entry -- what it is called on a document,
in which unit, under which VAT rate key, and which tariff heading it carries --
and every one of them is a value, not a row.

Handing back a frozen dataclass rather than the `Item` is what makes that true.
An ORM instance is a handle to a table: whoever holds one can follow a relation,
write a field, or filter a queryset off it, and the seam the rule is about is
back. A value cannot do any of that.

Everything reads under the policy, so an item this context cannot see is absent
rather than forbidden (IZ-04).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from evidenta.masterdata.items.models import Item
from evidenta.platform.api.errors import ApiError


class ItemNotFoundError(ApiError):
    code = "items.not_found"
    status = 404


@dataclass(frozen=True, slots=True)
class CatalogueEntry:
    """One item, as everything outside `masterdata` sees it.

    `legal_name` is the name that reaches a document, a register or an export
    (`C39`, ADR-034). The internal name is deliberately **not** here: it exists
    for lists, search and imports, and a field on this dataclass would be an
    invitation to print it.
    """

    id: uuid.UUID
    sku: str
    legal_name: str
    kind: str
    base_unit_id: uuid.UUID
    base_unit_code: str
    #: The **key** the item's default VAT rate is registered under, never a rate.
    #: A percentage in master data is a fiscal parameter compiled into a
    #: catalogue, which `R15` calls a critical defect.
    vat_rate_key: str | None
    tariff_code: str | None
    is_active: bool


def entry_for(item_id: uuid.UUID) -> CatalogueEntry:
    """The catalogue facts for one item, or a refusal."""
    item = Item.objects.filter(id=item_id).select_related("base_unit").first()
    if item is None:
        raise ItemNotFoundError(f"item {item_id} is not visible in this context")
    return CatalogueEntry(
        id=item.id,
        sku=item.sku,
        legal_name=item.name,
        kind=str(item.kind),
        base_unit_id=item.base_unit_id,
        base_unit_code=item.base_unit.code,
        vat_rate_key=item.vat_rate_key,
        tariff_code=item.tariff_code,
        is_active=item.is_active,
    )
