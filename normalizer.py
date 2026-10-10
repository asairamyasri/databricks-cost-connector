import json
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional, Dict, Any

from pydantic import BaseModel, Field, ConfigDict, field_serializer


class NormalizedCostRecord(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    platform: str = "databricks"
    billing_account_id: Optional[str] = None
    workspace_id: Optional[str] = None
    source_category: str
    source_record_id: Optional[str] = None

    resource_id: Optional[str] = None
    resource_name: Optional[str] = None
    resource_type: Optional[str] = None

    service_or_product: Optional[str] = None
    sku: Optional[str] = None

    usage_start: Optional[str] = None
    usage_end: Optional[str] = None
    billing_period_start: Optional[str] = None
    billing_period_end: Optional[str] = None

    consumed_quantity: Optional[Decimal] = None
    consumed_unit: Optional[str] = None
    pricing_quantity: Optional[Decimal] = None
    pricing_unit: Optional[str] = None

    list_unit_price: Optional[Decimal] = None
    list_cost: Optional[Decimal] = None
    contracted_cost: Optional[Decimal] = None
    effective_cost: Optional[Decimal] = None
    billed_cost: Optional[Decimal] = None
    currency: Optional[str] = "USD"

    user_or_sp_attribution: Optional[str] = None
    tags: Optional[Dict[str, Any]] = None
    source_update_time: Optional[str] = None
    collection_time: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    additional_source_metadata: Optional[Dict[str, Any]] = None

    @field_serializer(
        "consumed_quantity",
        "pricing_quantity",
        "list_unit_price",
        "list_cost",
        "contracted_cost",
        "effective_cost",
        "billed_cost",
        when_used="always",
    )
    def serialize_decimal(self, value: Optional[Decimal]) -> Optional[str]:
        return str(value) if value is not None else None


def parse_dict_or_str(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (ValueError, TypeError):
            return {}
    return {}


def parse_timestamp(value: Any) -> Optional[datetime]:
    """Parse a datetime or ISO timestamp and normalize it to UTC."""
    if value is None:
        return None

    try:
        if isinstance(value, datetime):
            result = value
        else:
            text = str(value).strip()
            if not text:
                return None
            result = datetime.fromisoformat(text.replace("Z", "+00:00"))

        if result.tzinfo is None:
            result = result.replace(tzinfo=timezone.utc)

        return result.astimezone(timezone.utc)
    except (ValueError, TypeError, OverflowError):
        return None


def timestamp_to_iso(value: Any) -> Optional[str]:
    parsed = parse_timestamp(value)
    return parsed.isoformat() if parsed else None


def get_default_price(pricing: dict) -> Optional[Decimal]:
    """Extract the standard list price, not the promotional price."""
    value = pricing.get("default")

    # Also tolerate nested representations if the source changes.
    if isinstance(value, dict):
        value = value.get("default")

    if value is None:
        return None

    try:
        result = Decimal(str(value))
        return result if result.is_finite() else None
    except (ValueError, TypeError, ArithmeticError):
        return None


def find_list_price(
    raw: dict, pricing_records: list[dict]
) -> Optional[dict]:
    """Find a price matching the usage SKU, cloud, unit, and time."""
    usage_start = parse_timestamp(raw.get("usage_start_time"))
    if usage_start is None:
        return None

    candidates = []

    for price in pricing_records:
        if price.get("sku_name") != raw.get("sku_name"):
            continue
        if price.get("cloud") != raw.get("cloud"):
            continue
        if price.get("usage_unit") != raw.get("usage_unit"):
            continue

        price_start = parse_timestamp(price.get("price_start_time"))
        price_end = parse_timestamp(price.get("price_end_time"))

        if price_start is None or price_start > usage_start:
            continue
        if price_end is not None and usage_start > price_end:
            continue

        pricing = parse_dict_or_str(price.get("pricing"))
        unit_price = get_default_price(pricing)

        if unit_price is None:
            continue

        candidates.append((price_start, price, unit_price))

    if not candidates:
        return None

    # If multiple prices match, choose the most recently effective one.
    _, selected, unit_price = max(candidates, key=lambda item: item[0])

    return {
        "unit_price": unit_price,
        "currency": selected.get("currency_code"),
        "usage_unit": selected.get("usage_unit"),
        "price_start_time": selected.get("price_start_time"),
        "price_end_time": selected.get("price_end_time"),
    }


def normalize_system_usage_record(
    raw: dict,
    pricing_records: Optional[list[dict]] = None,
) -> NormalizedCostRecord:
    if not isinstance(raw, dict):
        raise ValueError("Usage record must be a dictionary")

    tags = parse_dict_or_str(raw.get("custom_tags"))
    meta = parse_dict_or_str(raw.get("usage_metadata"))
    identity = parse_dict_or_str(raw.get("identity_metadata"))

    quantity_value = raw.get("usage_quantity")
    try:
        qty = (
            Decimal(str(quantity_value))
            if quantity_value is not None
            else None
        )
        if qty is not None and not qty.is_finite():
            raise ValueError("Usage quantity must be finite")
    except (ValueError, TypeError, ArithmeticError) as exc:
        raise ValueError(
            f"Invalid usage_quantity: {quantity_value!r}"
        ) from exc

    price = find_list_price(raw, pricing_records or [])

    list_unit_price = price["unit_price"] if price else None
    list_cost = (
        qty * list_unit_price
        if qty is not None and list_unit_price is not None
        else None
    )

    resource_id = (
        meta.get("cluster_id")
        or meta.get("warehouse_id")
        or meta.get("job_id")
    )

    resource_type = (
        "cluster" if meta.get("cluster_id")
        else "sql_warehouse" if meta.get("warehouse_id")
        else "job" if meta.get("job_id")
        else None
    )

    return NormalizedCostRecord(
        billing_account_id=(
            str(raw["account_id"]) if raw.get("account_id") else None
        ),
        workspace_id=(
            str(raw["workspace_id"]) if raw.get("workspace_id") else None
        ),
        source_category="billing_and_usage",
        source_record_id=(
            str(raw["record_id"]) if raw.get("record_id") else None
        ),
        resource_id=str(resource_id) if resource_id else None,
        resource_name=meta.get("cluster_name"),
        resource_type=resource_type,
        service_or_product=raw.get("cloud"),
        sku=raw.get("sku_name"),
        usage_start=timestamp_to_iso(raw.get("usage_start_time")),
        usage_end=timestamp_to_iso(raw.get("usage_end_time")),
        consumed_quantity=qty,
        consumed_unit=raw.get("usage_unit"),
        pricing_quantity=qty if price else None,
        pricing_unit=price["usage_unit"] if price else None,
        list_unit_price=list_unit_price,
        list_cost=list_cost,
        currency=price["currency"] if price else None,
        user_or_sp_attribution=identity.get("run_as"),
        tags=tags,
        additional_source_metadata={
            **meta,
            **(
                {
                    "matched_price_start_time": str(
                        price["price_start_time"]
                    ),
                    "matched_price_end_time": (
                        str(price["price_end_time"])
                        if price["price_end_time"] is not None
                        else None
                    ),
                }
                if price
                else {"list_price_match": "not_found"}
            ),
        },
    )