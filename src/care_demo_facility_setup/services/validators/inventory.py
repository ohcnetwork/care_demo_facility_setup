from __future__ import annotations

from care_demo_facility_setup.services.validators.base import (
    SeedValidationContext,
    ValidationAccumulator,
)

OPTIONAL_PRICE_FIELDS = ("mrp_per_pack", "purchase_price", "purchase_per_pack", "unit_price")


def validate_inventory_items(context: SeedValidationContext, accumulator: ValidationAccumulator) -> None:
    items = context.pack.get("inventory_items")
    expected = context.counts.get("inventory_items")

    if not isinstance(items, list):
        accumulator.error("The seed pack must contain inventory_items.json with a list of inventory items.")
        return

    if expected is not None and len(items) != expected:
        accumulator.error(f"The seed pack must contain exactly {expected} inventory items.")

    slugs: set[str] = set()
    for index, item in enumerate(items, start=1):
        if not isinstance(item, dict):
            accumulator.error(f"Inventory item #{index} must be an object.")
            continue

        product_knowledge = item.get("product_knowledge")
        if not isinstance(product_knowledge, dict) or not product_knowledge:
            accumulator.error(f"Inventory item #{index} is missing product_knowledge.")
        else:
            for field in ("name", "slug_value", "base_unit"):
                if not product_knowledge.get(field):
                    accumulator.error(f"Inventory item #{index} product_knowledge is missing {field}.")

        slug = item.get("slug") or (
            product_knowledge.get("slug_value") if isinstance(product_knowledge, dict) else None
        )
        if not slug:
            accumulator.error(f"Inventory item #{index} is missing slug.")
        elif slug in slugs:
            accumulator.error(f"Inventory item #{index} has duplicate slug '{slug}'.")
        else:
            slugs.add(slug)

        quantity = item.get("stock_quantity")
        if not _is_positive_int(quantity):
            accumulator.error(f"Inventory item #{index} stock_quantity must be an integer greater than 0.")

        if "pack_size" in item and not _is_positive_int(item.get("pack_size")):
            accumulator.error(f"Inventory item #{index} pack_size must be an integer greater than 0.")

        for field in OPTIONAL_PRICE_FIELDS:
            if field in item and not _is_positive_number(item.get(field)):
                accumulator.error(f"Inventory item #{index} {field} must be a positive number.")

        if "lot_prefix" in item and not item.get("lot_prefix"):
            accumulator.error(f"Inventory item #{index} lot_prefix must be a non-empty string.")

        if "expiration_date" in item and not item.get("expiration_date"):
            accumulator.error(f"Inventory item #{index} expiration_date must be a non-empty string.")


def _is_positive_int(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_positive_number(value) -> bool:
    return isinstance(value, int | float) and not isinstance(value, bool) and value > 0
