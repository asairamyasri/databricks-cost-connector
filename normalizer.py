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
    collection_time: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    additional_source_metadata: Optional[Dict[str, Any]] = None

    @field_serializer(
        "consumed_quantity", "pricing_quantity", "list_unit_price", 
        "list_cost", "contracted_cost", "effective_cost", "billed_cost",
        when_used="always"
    )
    def serialize_decimal(self, value: Optional[Decimal]) -> Optional[str]:
        return str(value) if value is not None else None

def parse_dict_or_str(val: Any) -> dict:
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            return json.loads(val)
        except Exception:
            return {}
    return {}

def normalize_system_usage_record(raw: dict) -> NormalizedCostRecord:
    tags = parse_dict_or_str(raw.get("custom_tags"))
    meta = parse_dict_or_str(raw.get("usage_metadata"))
    identity = parse_dict_or_str(raw.get("identity_metadata"))

    qty = Decimal(str(raw["usage_quantity"])) if raw.get("usage_quantity") is not None else None

    # Parse and convert dates to ISO UTC strings
    u_start = raw.get("usage_start_time")
    u_end = raw.get("usage_end_time")
    
    iso_start = u_start.astimezone(timezone.utc).isoformat() if isinstance(u_start, datetime) else str(u_start) if u_start else None
    iso_end = u_end.astimezone(timezone.utc).isoformat() if isinstance(u_end, datetime) else str(u_end) if u_end else None

    return NormalizedCostRecord(
        billing_account_id=str(raw.get("account_id")) if raw.get("account_id") else None,
        workspace_id=str(raw.get("workspace_id")) if raw.get("workspace_id") else None,
        source_category="billing_and_usage",
        source_record_id=str(raw.get("record_id")) if raw.get("record_id") else None,
        resource_id=meta.get("cluster_id") or meta.get("warehouse_id") or meta.get("job_id"),
        resource_name=meta.get("cluster_name"),
        resource_type="cluster" if "cluster_id" in meta else "sql_warehouse" if "warehouse_id" in meta else "job",
        service_or_product=raw.get("cloud", "databricks"),
        sku=raw.get("sku_name"),
        usage_start=iso_start,
        usage_end=iso_end,
        consumed_quantity=qty,
        consumed_unit=raw.get("usage_unit"),
        user_or_sp_attribution=identity.get("run_as"),
        tags=tags,
        additional_source_metadata=meta
    )