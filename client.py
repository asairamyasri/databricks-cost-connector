import os
from databricks import sql

CATEGORIES = [
    ("billing_and_usage", "Tracks main DBU consumption across resources", "System Table system.billing.usage"),
    ("account_and_workspace_consumption", "Workspace level usage breakdown", "System Table system.billing.usage"),
    ("cluster_and_compute_consumption", "Compute cluster resource usage", "System Table system.billing.usage"),
    ("sql_warehouse_consumption", "SQL Warehouse query consumption", "System Table system.billing.usage"),
    ("jobs_and_pipeline_consumption", "Job execution usage", "System Table system.billing.usage"),
    ("serverless_consumption", "Serverless compute allocation", "System Table system.billing.usage"),
    ("storage_related_usage", "DBFS and cloud storage usage", "System Table system.billing.usage"),
    ("sku_and_pricing_information", "List prices for SKUs", "System Table system.billing.list_prices"),
    ("budgets_alerts_cost_controls", "Account budget policies and alerts", "Account API /budget-policy"),
    ("contract_commitment_discount", "Commitments and enterprise discounts", "Account Contract API")
]

class DatabricksCostCollector:
    def __init__(self):
        self.host = os.getenv("DATABRICKS_HOST", "").replace("https://", "")
        self.token = os.getenv("DATABRICKS_TOKEN")
        self.http_path = os.getenv("DATABRICKS_HTTP_PATH")

    def collect_billing_usage(self, start_time: str, end_time: str):
        query = f"""
        SELECT 
            account_id, workspace_id, record_id, sku_name, cloud,
            usage_start_time, usage_end_time, usage_quantity, usage_unit,
            identity_metadata, custom_tags, usage_metadata
        FROM system.billing.usage
        WHERE usage_start_time >= '{start_time}' AND usage_end_time <= '{end_time}'
        """
        try:
            with sql.connect(server_hostname=self.host, http_path=self.http_path, access_token=self.token) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query)
                    rows = cursor.fetchall()
                    if not rows:
                        return "empty", [], None
                    cols = [desc[0] for desc in cursor.description]
                    return "collected", [dict(zip(cols, row)) for row in rows], None
        except Exception as e:
            err = str(e).lower()
            if "permission" in err or "access_denied" in err:
                return "permission_denied", [], str(e)
            elif "not_found" in err:
                return "unavailable_in_account", [], "system.billing.usage table not found"
            return "failed", [], str(e)

    def collect_list_prices(self):
        query = "SELECT * FROM system.billing.list_prices LIMIT 10"
        try:
            with sql.connect(server_hostname=self.host, http_path=self.http_path, access_token=self.token) as conn:
                with conn.cursor() as cursor:
                    cursor.execute(query)
                    rows = cursor.fetchall()
                    cols = [desc[0] for desc in cursor.description]
                    return "collected" if rows else "empty", [dict(zip(cols, row)) for row in rows], None
        except Exception as e:
            err = str(e).lower()
            if "not_found" in err or "cannot_find" in err:
                return "unavailable_in_account", [], "List prices system table not enabled in this region/account tier."
            return "permission_denied" if "permission" in err else "failed", [], str(e)

    def collect_account_budgets(self):
        return "permission_denied", [], "Requires Account Administrator role and Account API token scope."

    def collect_commitments(self):
        return "unavailable_in_account", [], "Enterprise commitments not available on trial account level."