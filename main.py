
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
        if cat_name == "billing_and_usage":
            row_status = status
            count = len(records)
            first = earliest
            last = latest
            explanation = err or (
                f"Queried system.billing.usage for {start} to {end}."
            )

        elif cat_name == "sku_and_pricing_information":
            row_status = p_status
            count = len(pricing_records)
            first = "N/A"
            last = "N/A"
            explanation = p_err or (
                "Queried system.billing.list_prices."
            )

        elif cat_name in (
            "budgets_alerts_and_cost_controls",
            "contract_commitment_discount",
        ):
            if cat_name == "budgets_alerts_and_cost_controls":
                row_status, _, category_err = (
                    collector.collect_account_budgets()
                )
            else:
                row_status, _, category_err = (
                    collector.collect_commitments()
                )

            count = 0
            first = "N/A"
            last = "N/A"
            explanation = category_err or "No records returned."

        else:
            # Do not claim that categories were collected by searching
            # for their names inside unrelated billing records.
            row_status = "unsupported"
            count = 0
            first = "N/A"
            last = "N/A"
            explanation = (
                "No category-specific collector/query is implemented; "
                "billing usage records do not independently verify "
                "coverage for this category."
            )

        report_rows.append({
            "category": cat_name,
            "purpose": purpose,
            "status": row_status,
            "record_count": count,
            "earliest_timestamp": first,
            "latest_timestamp": last,
            "required_permission": perm,
            "explanation": explanation,
        })

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
