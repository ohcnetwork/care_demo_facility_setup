from __future__ import annotations

import zlib
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal

from django.utils import timezone

from care_demo_facility_setup.models import SeedRunStep
from care_demo_facility_setup.services.care_seed_client import CareSeedClient
from care_demo_facility_setup.services.seed_artifacts import SeedArtifactStore, get_value
from care_demo_facility_setup.services.seed_errors import SeedRunExecutionError

GST_INCLUSIVE_DIVISOR = Decimal("1.05")
MONEY = Decimal("0.01")
TAX_SYSTEM = "http://ohc.network/codes/monetary/tax"
MRP_SYSTEM = "http://ohc.network/codes/monetary/informational"
STORE_REF = "location:main_store"
PHARMACY_REF = "location:main_pharmacy"


class InventorySeeder:
    def __init__(
        self,
        *,
        client: CareSeedClient,
        artifacts: SeedArtifactStore,
        run_id: int,
    ):
        self.client = client
        self.artifacts = artifacts
        self.run_id = run_id

    def seed(
        self,
        *,
        step: SeedRunStep,
        items_config: list,
        facility_template: dict,
    ) -> tuple[str, dict]:
        facility_id = self.artifacts.external_id(facility_template.get("ref", "facility:main"))
        store_id = self.artifacts.external_id(STORE_REF)
        pharmacy_id = self.artifacts.external_id(PHARMACY_REF)

        supplier = self.client.create_organization(
            {
                "name": f"Demo Inventory Supplier {self.run_id}",
                "org_type": "product_supplier",
                "active": True,
            }
        )
        supplier_payload = self.artifacts.store(
            step=step,
            ref="supplier:inventory",
            resource_type="Organization",
            payload=supplier,
        )
        supplier_id = self.artifacts.payload_external_id(supplier_payload, "supplier:inventory")

        category_slugs, categories_created = self._ensure_categories(step, facility_id, items_config)

        created = 0
        received = []
        for item in items_config:
            slug = item["slug"]
            knowledge = dict(item["product_knowledge"])
            category_name = item.get("resource_category_name") or "Medicines"
            knowledge["facility"] = facility_id
            knowledge["category"] = category_slugs[category_name]["product_knowledge"]
            product_knowledge = self.client.create_product_knowledge(knowledge)
            stored_knowledge = self.artifacts.store(
                step=step,
                ref=f"product_knowledge:{slug}",
                resource_type="ProductKnowledge",
                payload=product_knowledge,
            )
            received.append(
                {
                    "item": item,
                    "slug": slug,
                    "receive": _resolve_receive_inputs(item, slug, self.run_id),
                    "pk_id": self.artifacts.payload_external_id(stored_knowledge, f"product_knowledge:{slug}"),
                    "pk_slug": stored_knowledge["slug"],
                    "cid_category": category_slugs[category_name]["charge_item_definition"],
                }
            )
            created += 1

        request_order = self.client.create_request_order(
            facility_id,
            {
                "name": f"Initial Stock Request {self.run_id}",
                "destination": store_id,
                "supplier": supplier_id,
            },
        )
        request_order_id = get_value(request_order, "id")
        delivery_order = self.client.create_delivery_order(
            facility_id,
            {
                "name": f"Initial Stock Delivery {self.run_id}",
                "destination": store_id,
                "supplier": supplier_id,
            },
        )
        delivery_order_id = get_value(delivery_order, "id")

        products_received = 0
        for row in received:
            supply_request = self.client.create_supply_request(
                {
                    "order": request_order_id,
                    "item": row["pk_id"],
                    "quantity": row["receive"]["quantity"],
                }
            )
            charge = self.client.create_charge_item_definition(
                facility_id,
                _charge_item_definition_payload(row),
            )
            product = self.client.create_product(
                facility_id,
                {
                    "product_knowledge_slug": row["pk_slug"],
                    **row["item"].get("product_extras", {}),
                    "charge_item_definition": get_value(charge, "slug"),
                    "batch": {"lot_number": row["receive"]["lot_number"]},
                    "expiration_date": row["receive"]["expiration_date"],
                    "purchase_price": str(row["receive"]["purchase_price"]),
                    "standard_pack_size": row["receive"]["pack_size"],
                },
            )
            stored_product = self.artifacts.store(
                step=step,
                ref=f"product:{row['slug']}",
                resource_type="Product",
                payload=product,
            )
            product_id = self.artifacts.payload_external_id(stored_product, f"product:{row['slug']}")
            delivery = self.client.create_supply_delivery(
                {
                    "order": delivery_order_id,
                    "supplied_item_quantity": row["receive"]["quantity"],
                    "supplied_item": product_id,
                    "supply_request": get_value(supply_request, "id"),
                    "supplied_item_pack_size": row["receive"]["pack_size"],
                    "total_purchase_price": float(row["receive"]["purchase_price"] * row["receive"]["quantity"]),
                }
            )
            self.client.update_supply_delivery(
                get_value(delivery, "id"),
                {"status": "completed", "order": delivery_order_id},
            )
            row["product_id"] = product_id
            products_received += 1

        self._complete_order_headers(
            facility_id,
            request_order=request_order,
            delivery_order=delivery_order,
        )

        transfer_request = self.client.create_request_order(
            facility_id,
            {
                "name": f"Pharmacy Transfer Request {self.run_id}",
                "origin": store_id,
                "destination": pharmacy_id,
            },
        )
        transfer_request_id = get_value(transfer_request, "id")
        transfer_delivery_order = self.client.create_delivery_order(
            facility_id,
            {
                "name": f"Pharmacy Transfer Delivery {self.run_id}",
                "origin": store_id,
                "destination": pharmacy_id,
            },
        )
        transfer_delivery_order_id = get_value(transfer_delivery_order, "id")

        transferred = 0
        for row in received:
            transfer_qty = _pharmacy_transfer_quantity(row["receive"]["quantity"])
            if transfer_qty < 1:
                continue
            inventory_item_id = self._store_inventory_item_id(facility_id, store_id, row)
            supply_request = self.client.create_supply_request(
                {
                    "order": transfer_request_id,
                    "item": row["pk_id"],
                    "quantity": transfer_qty,
                }
            )
            delivery = self.client.create_supply_delivery(
                {
                    "order": transfer_delivery_order_id,
                    "supplied_item_quantity": transfer_qty,
                    "supplied_inventory_item": inventory_item_id,
                    "supply_request": get_value(supply_request, "id"),
                }
            )
            self.client.update_supply_delivery(
                get_value(delivery, "id"),
                {"status": "completed", "order": transfer_delivery_order_id},
            )
            transferred += 1

        self._complete_order_headers(
            facility_id,
            request_order=transfer_request,
            delivery_order=transfer_delivery_order,
        )

        message = (
            f"Created {created} product knowledges, received {products_received} products at Main Store, "
            f"and transferred {transferred} lots to Main Pharmacy."
        )
        return message, {
            "created": created,
            "categories_created": categories_created,
            "products_received": products_received,
            "transferred": transferred,
        }

    def _ensure_categories(self, step: SeedRunStep, facility_id: str, items_config: list) -> tuple[dict, int]:
        names: list[str] = []
        seen: set[str] = set()
        for item in items_config:
            name = item.get("resource_category_name") or "Medicines"
            if name not in seen:
                seen.add(name)
                names.append(name)

        category_slugs: dict[str, dict[str, str]] = {}
        created = 0
        for name in names:
            pk_category = self.client.create_resource_category(
                facility_id,
                {"title": name, "resource_type": "product_knowledge"},
            )
            cid_category = self.client.create_resource_category(
                facility_id,
                {"title": name, "resource_type": "charge_item_definition"},
            )
            self.artifacts.store(
                step=step,
                ref=f"resource_category:product_knowledge:{name}",
                resource_type="ResourceCategory",
                payload=pk_category,
            )
            self.artifacts.store(
                step=step,
                ref=f"resource_category:charge_item_definition:{name}",
                resource_type="ResourceCategory",
                payload=cid_category,
            )
            category_slugs[name] = {
                "product_knowledge": get_value(pk_category, "slug"),
                "charge_item_definition": get_value(cid_category, "slug"),
            }
            created += 2
        return category_slugs, created

    def _store_inventory_item_id(self, facility_id: str, store_id: str, row: dict) -> str:
        items = self.client.list_inventory_items(
            facility_id,
            store_id,
            product_knowledge=row["pk_id"],
        )
        match = next(
            (
                inventory_item
                for inventory_item in items
                if str(get_value(get_value(inventory_item, "product"), "id")) == row["product_id"]
            ),
            None,
        )
        if match is None:
            raise SeedRunExecutionError(f"No Main Store inventory item for {row['slug']}.")
        inventory_id = get_value(match, "id")
        if not inventory_id:
            raise SeedRunExecutionError(f"Main Store inventory item for {row['slug']} has no id.")
        return str(inventory_id)

    def _complete_order_headers(self, facility_id: str, *, request_order, delivery_order) -> None:
        """Mark RequestOrder / DeliveryOrder headers completed after line deliveries succeed."""
        self.client.update_request_order(
            facility_id,
            get_value(request_order, "id"),
            {
                "status": "completed",
                "name": get_value(request_order, "name"),
                "intent": get_value(request_order, "intent"),
                "category": get_value(request_order, "category"),
                "priority": get_value(request_order, "priority"),
                "reason": get_value(request_order, "reason"),
            },
        )
        self.client.update_delivery_order(
            facility_id,
            get_value(delivery_order, "id"),
            {
                "status": "completed",
                "name": get_value(delivery_order, "name"),
            },
        )


def _pharmacy_transfer_quantity(stock_quantity: int) -> int:
    if stock_quantity >= 1000:
        return min(500, stock_quantity // 2)
    return max(1, stock_quantity // 4)


def _money(value) -> Decimal:
    return Decimal(str(value)).quantize(MONEY, rounding=ROUND_HALF_UP)


def _formula_mrp(slug: str, run_id: int) -> Decimal:
    n = zlib.crc32(f"{slug}:{run_id}".encode()) & 0xFFFFFFFF
    rupees = 20 + (n % 181)
    paise = n % 100
    return _money(f"{rupees}.{paise:02d}")


def _resolve_receive_inputs(item: dict, slug: str, run_id: int) -> dict:
    pack_size = item.get("pack_size", 1)
    mrp = item.get("mrp_per_pack")
    mrp = _formula_mrp(slug, run_id) if mrp is None else _money(mrp)
    purchase = item.get("purchase_price", item.get("purchase_per_pack"))
    purchase = _money(mrp * Decimal("0.6")) if purchase is None else _money(purchase)
    unit_price = item.get("unit_price")
    unit_price = _money(mrp / Decimal(pack_size) / GST_INCLUSIVE_DIVISOR) if unit_price is None else _money(unit_price)
    lot_prefix = item.get("lot_prefix") or slug
    expiration_date = item.get("expiration_date") or (timezone.now() + timedelta(days=730)).isoformat()
    return {
        "quantity": item["stock_quantity"],
        "pack_size": pack_size,
        "mrp": mrp,
        "purchase_price": purchase,
        "unit_price": unit_price,
        "lot_number": f"{lot_prefix}-{run_id}",
        "expiration_date": expiration_date,
    }


def _charge_item_definition_payload(row: dict) -> dict:
    receive = row["receive"]
    name = row["item"]["product_knowledge"]["name"]
    return {
        "title": f"{name} - {receive['lot_number']}",
        "slug_value": f"{row['slug']}-recv",
        "status": "active",
        "category": row["cid_category"],
        "can_edit_charge_item": False,
        "discount_configuration": None,
        "price_components": [
            {"amount": float(receive["unit_price"]), "monetary_component_type": "base"},
            {
                "amount": float(receive["mrp"]),
                "monetary_component_type": "informational",
                "code": {"code": "mrp", "display": "MRP", "system": MRP_SYSTEM},
            },
            {
                "factor": 2.5,
                "monetary_component_type": "tax",
                "code": {"code": "cgst", "display": "CGST", "system": TAX_SYSTEM},
            },
            {
                "factor": 2.5,
                "monetary_component_type": "tax",
                "code": {"code": "sgst", "display": "SGST", "system": TAX_SYSTEM},
            },
        ],
    }
