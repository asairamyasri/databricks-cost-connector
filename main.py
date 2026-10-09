import os
import json
from dotenv import load_dotenv
from client import DatabricksCostCollector, CATEGORIES
from normalizer import normalize_system_usage_record

load_dotenv()

def run_pipeline():
    start = os.getenv("START_TIME", "2026-10-01T00:00:00Z")
    end = os.getenv("END_TIME", "2026-10-09T23:59:59Z")
    
    collector = DatabricksCostCollector()
    
    os.makedirs("data/raw", exist_ok=True)
    os.makedirs("data/normalized", exist_ok=True)
    
    report_rows = []
    all_raw = {}
    all_normalized = []
    
    print("==================================================")
    print("DATABRICKS COST CONNECTOR LIVE EXECUTION")
    print("==================================================")

    status, records, err = collector.collect_billing_usage(start, end)
    all_raw["billing_and_usage"] = records
    
    earliest = min([str(r["usage_start_time"]) for r in records]) if records else "N/A"
    latest = max([str(r["usage_end_time"]) for r in records]) if records else "N/A"

    for raw in records:
        all_normalized.append(normalize_system_usage_record(raw).model_dump(mode="json"))

    usage_subcategories = [
        "billing_and_usage", "account_and_workspace_consumption", 
        "cluster_and_compute_consumption", "sql_warehouse_consumption", 
        "jobs_and_pipeline_consumption", "serverless_consumption", "storage_related_usage"
    ]

    for cat_name, purpose, perm in CATEGORIES:
        if cat_name in usage_subcategories:
            filtered = [r for r in records if cat_name in str(r).lower()] if cat_name != "billing_and_usage" else records
            cat_status = status if cat_name == "billing_and_usage" else ("collected" if filtered else "empty")
            report_rows.append({
                "category": cat_name,
                "purpose": purpose,
                "status": cat_status,
                "record_count": len(filtered) if cat_name != "billing_and_usage" else len(records),
                "earliest_timestamp": earliest,
                "latest_timestamp": latest,
                "required_permission": perm,
                "explanation": err or "Successfully queried system.billing.usage"
            })
        elif cat_name == "sku_and_pricing_information":
            p_status, p_recs, p_err = collector.collect_list_prices()
            all_raw[cat_name] = p_recs
            report_rows.append({
                "category": cat_name,
                "purpose": purpose,
                "status": p_status,
                "record_count": len(p_recs),
                "earliest_timestamp": "N/A",
                "latest_timestamp": "N/A",
                "required_permission": perm,
                "explanation": p_err or "Successfully queried system.billing.list_prices"
            })
        elif cat_name == "budgets_alerts_cost_controls":
            b_status, _, b_err = collector.collect_account_budgets()
            report_rows.append({
                "category": cat_name,
                "purpose": purpose,
                "status": b_status,
                "record_count": 0,
                "earliest_timestamp": "N/A",
                "latest_timestamp": "N/A",
                "required_permission": perm,
                "explanation": b_err
            })
        elif cat_name == "contract_commitment_discount":
            c_status, _, c_err = collector.collect_commitments()
            report_rows.append({
                "category": cat_name,
                "purpose": purpose,
                "status": c_status,
                "record_count": 0,
                "earliest_timestamp": "N/A",
                "latest_timestamp": "N/A",
                "required_permission": perm,
                "explanation": c_err
            })

    with open("data/raw/raw_sample.json", "w") as f:
        json.dump(all_raw, f, indent=2, default=str)

    with open("data/normalized/normalized_sample.json", "w") as f:
        json.dump(all_normalized, f, indent=2)

    print("\n### COVERAGE REPORT\n")
    print("| Category | Purpose | Status | Count | Earliest | Latest | Required Perm | Explanation |")
    print("|---|---|---|---|---|---|---|---|")
    for r in report_rows:
        print(f"| {r['category']} | {r['purpose']} | `{r['status']}` | {r['record_count']} | {r['earliest_timestamp']} | {r['latest_timestamp']} | {r['required_permission']} | {r['explanation']} |")

if __name__ == "__main__":
    run_pipeline()