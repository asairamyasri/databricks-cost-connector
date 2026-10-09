import pytest
from decimal import Decimal
from datetime import datetime, timezone
from normalizer import normalize_system_usage_record

def test_decimal_precision_preservation():
    raw_record = {
        "account_id": "acc-12345",
        "workspace_id": "ws-67890",
        "record_id": "rec-001",
        "sku_name": "PREMIUM_ALL_PURPOSE_COMPUTE",
        "usage_quantity": 0.001521800000000000,
        "usage_start_time": datetime(2026, 10, 8, 20, 0, 0, tzinfo=timezone.utc),
        "usage_end_time": datetime(2026, 10, 8, 21, 0, 0, tzinfo=timezone.utc),
        "usage_unit": "DSU"
    }

    normalized = normalize_system_usage_record(raw_record)
    
    assert isinstance(normalized.consumed_quantity, Decimal)
    assert normalized.consumed_quantity == Decimal("0.001521800000000000")

def test_utc_timestamp_handling():
    raw_record = {
        "usage_quantity": 1.0,
        "usage_start_time": datetime(2026, 10, 8, 18, 0, 0, tzinfo=timezone.utc),
        "usage_end_time": datetime(2026, 10, 8, 19, 0, 0, tzinfo=timezone.utc),
    }

    normalized = normalize_system_usage_record(raw_record)
    assert "+00:00" in normalized.usage_start or "Z" in normalized.usage_start

def test_null_and_missing_fields_handling():
    raw_record = {
        "usage_quantity": None,
        "usage_start_time": None
    }

    normalized = normalize_system_usage_record(raw_record)
    assert normalized.consumed_quantity is None
    assert normalized.usage_start is None
    assert normalized.platform == "databricks"