
import os
import json
from dotenv import load_dotenv
from client import DatabricksCostCollector, CATEGORIES
from normalizer import normalize_system_usage_record

load_dotenv()


def write_json(path, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, default=str)


def run_pipeline():
    start = os.getenv("START_TIME", "2026-10-01T00:00:00Z")
    end = os.getenv("END_TIME", "2026-10-09T23:59:59Z")

    collector = DatabricksCostCollector()

    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("data/normalized", exist_ok=True)

    report_rows = []
    all_raw = {}
    all_normalized = []
    normalization_errors = []

    print("=" * 55)
    print("DATABRICKS COST CONNECTOR EXECUTION")
    print("=" * 55)

       # Collect billing usage.
    status, records, err = collector.collect_billing_usage(start, end)
    all_raw["billing_and_usage"] = records

    # Collect pricing before normalization so list costs can be calculated.
    p_status, pricing_records, p_err = collector.collect_list_prices()
    all_raw["sku_and_pricing_information"] = pricing_records

    timestamps = [
        (str(r.get("usage_start_time")), str(r.get("usage_end_time")))
        for r in records
        if r.get("usage_start_time") and r.get("usage_end_time")
    ]

    earliest = min((x[0] for x in timestamps), default="N/A")
    latest = max((x[1] for x in timestamps), default="N/A")

    for index, raw in enumerate(records):
        try:
            normalized = normalize_system_usage_record(
                raw, pricing_records
            )
            all_normalized.append(normalized.model_dump(mode="json"))
        except Exception as exc:
            normalization_errors.append({
                "record_index": index,
                "error": str(exc)
            })

    # Collect pricing separately.
    p_status, pricing_records, p_err = collector.collect_list_prices()
    all_raw["sku_and_pricing_information"] = pricing_records

    # Build one coverage row for every declared category.
    for cat_name, purpose, perm in CATEGORIES:
        
    # Build evidence-based coverage rows.
        usage_records = all_raw.get("billing_and_usage", [])
        pricing_records = all_raw.get("sku_and_pricing_information", [])

        def as_dict(value):
            if isinstance(value, dict):
                return value
            if isinstance(value, str):
                try:
                    parsed = json.loads(value)
                    return parsed if isinstance(parsed, dict) else {}
                except (ValueError, TypeError):
                    return {}
            return {}

        metadata_counts = {
            "cluster_and_compute_consumption": lambda r: any(
                as_dict(r.get("usage_metadata")).get(k)
                for k in ("cluster_id", "node_type", "instance_pool_id")
            ),
            "sql_warehouse_consumption": lambda r: bool(
                as_dict(r.get("usage_metadata")).get("warehouse_id")
            ),
            "jobs_and_pipeline_consumption": lambda r: any(
                as_dict(r.get("usage_metadata")).get(k)
                for k in ("job_id", "job_run_id", "dlt_pipeline_id")
            ),
            "serverless_consumption": lambda r: any(
                as_dict(r.get("usage_metadata")).get(k)
                for k in ("serverless_compute_id", "ai_runtime_pool_id",
                        "ai_runtime_workload_id")
            ),
            "storage_related_usage": lambda r: any(
                as_dict(r.get("usage_metadata")).get(k)
                for k in ("table_id", "database_instance_id", "storage_api_type",
                        "uc_table_name")
            ),
            "resource_and_workload_attribution": lambda r: any(
                as_dict(r.get("usage_metadata")).get(k)
                for k in ("cluster_id", "warehouse_id", "job_id", "endpoint_id",
                        "app_id", "dlt_pipeline_id")
            ),
            "user_and_service_principal_attribution": lambda r: any(
                as_dict(r.get("identity_metadata")).get(k)
                for k in ("created_by", "owned_by", "run_as", "run_by")
            ),
            "tags_and_allocation_metadata": lambda r: bool(
                as_dict(r.get("custom_tags"))
            ),
        }

        report_rows = []
        for cat_name, purpose, perm in CATEGORIES:
            if cat_name == "billing_and_usage":
                row = {
                    "category": cat_name, "purpose": purpose,
                    "status": status, "record_count": len(usage_records),
                    "earliest_timestamp": earliest, "latest_timestamp": latest,
                    "required_permission": perm,
                    "explanation": err or
                        f"Queried system.billing.usage for {start} to {end}."
                }
            elif cat_name == "sku_and_pricing_information":
                row = {
                    "category": cat_name, "purpose": purpose,
                    "status": p_status, "record_count": len(pricing_records),
                    "earliest_timestamp": "N/A", "latest_timestamp": "N/A",
                    "required_permission": perm,
                    "explanation": p_err or
                        "Queried system.billing.list_prices."
                }
            elif cat_name == "list_cost_calculations":
                matched = sum(r.get("list_cost") is not None
                            for r in all_normalized)
                unmatched = len(all_normalized) - matched
                row = {
                    "category": cat_name, "purpose": purpose,
                    "status": "collected" if matched else "empty",
                    "record_count": matched,
                    "earliest_timestamp": "N/A", "latest_timestamp": "N/A",
                    "required_permission": "Billing usage and pricing data",
                    "explanation": (
                        f"Calculated list cost for {matched} normalized usage "
                        f"records. {unmatched} records had no matching price; "
                        "their costs were left null."
                    )
                }
            elif cat_name in metadata_counts:
                count = sum(bool(metadata_counts[cat_name](r))
                            for r in usage_records)
                row = {
                    "category": cat_name, "purpose": purpose,
                    "status": "collected" if count else "empty",
                    "record_count": count,
                    "earliest_timestamp": earliest if count else "N/A",
                    "latest_timestamp": latest if count else "N/A",
                    "required_permission": perm,
                    "explanation": (
                        f"Derived from system.billing.usage metadata; "
                        f"{count} of {len(usage_records)} usage records "
                        "contained relevant metadata. This is not a separate "
                        "source-table collection."
                    )
                }
            else:
                row = {
                    "category": cat_name, "purpose": purpose,
                    "status": "unsupported", "record_count": 0,
                    "earliest_timestamp": "N/A", "latest_timestamp": "N/A",
                    "required_permission": perm,
                    "explanation": (
                        "A category-specific source/API collector has not been "
                        "implemented or its availability has not been verified. "
                        "This status does not mean the feature is absent "
                        "from the account."
                    )
                }
            report_rows.append(row)


    # Save raw data, normalized data, coverage and normalization errors.
    write_json("data/raw/raw_sample.json", all_raw)
    write_json(
        "data/normalized/normalized_sample.json",
        all_normalized
    )
    write_json("data/coverage_report.json", report_rows)
    write_json(
        "data/normalization_errors.json",
        normalization_errors
    )

    print("\nCOVERAGE REPORT")
    print("-" * 55)

    for row in report_rows:
        print(
            f"{row['category']}: {row['status']} "
            f"({row['record_count']} records)"
        )
        if row["explanation"]:
            print(f"  {row['explanation']}")

    print("\nSummary:")
    print(f"Billing records collected: {len(records)}")
    print(f"Normalized records: {len(all_normalized)}")
    print(f"Normalization errors: {len(normalization_errors)}")
    print(f"Coverage categories: {len(report_rows)}")
    print("Coverage report: data/coverage_report.json")


if __name__ == "__main__":
    run_pipeline()
