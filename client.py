
import os
from urllib.parse import urlparse

from databricks import sql


# Keep the existing three-field structure for compatibility with main.py.
# These are categories to investigate, not proof that each was collected.
CATEGORIES = [
    (
        "billing_and_usage",
        "Tracks DBU consumption and billing usage records",
        "System Table: system.billing.usage",
    ),
    (
        "account_and_workspace_consumption",
        "Workspace and account-level consumption",
        "Billing records and Account/Workspace APIs, where available",
    ),
    (
        "cluster_and_compute_consumption",
        "Compute and cluster consumption",
        "Billing records and compute metadata, where available",
    ),
    (
        "sql_warehouse_consumption",
        "SQL warehouse consumption",
        "Billing records and SQL warehouse metadata, where available",
    ),
    (
        "jobs_and_pipeline_consumption",
        "Job and pipeline consumption",
        "Billing records and Jobs/Pipelines APIs, where available",
    ),
    (
        "serverless_consumption",
        "Serverless workload consumption",
        "Billing records and workload metadata, where available",
    ),
    (
        "storage_related_usage",
        "Storage-related consumption",
        "Billing records and storage metadata, where available",
    ),
    (
        "data_transfer_and_network_usage",
        "Data transfer and network-related usage",
        "Billing records and applicable usage sources",
    ),
    (
        "sku_and_pricing_information",
        "SKU details and list pricing",
        "System Table: system.billing.list_prices",
    ),
    (
        "list_cost_calculations",
        "Estimated list cost derived from usage and list prices",
        "Derived from compatible usage and pricing records",
    ),
    (
        "resource_and_workload_attribution",
        "Resource and workload attribution",
        "Billing metadata and applicable APIs",
    ),
    (
        "user_and_service_principal_attribution",
        "User and service-principal attribution",
        "Billing identity metadata and applicable APIs",
    ),
    (
        "tags_and_allocation_metadata",
        "Tags and cost-allocation metadata",
        "Billing custom_tags and applicable APIs",
    ),
    (
        "budgets_alerts_and_cost_controls",
        "Budget policies, alerts, and cost controls",
        "Applicable Account APIs",
    ),
    (
        "corrections_and_restatements",
        "Billing corrections, retractions, and restatements",
        "System Table: system.billing.usage",
    ),
    (
        "optimization_and_cost_saving",
        "Cost optimization and saving opportunities",
        "Applicable optimization APIs or system tables",
    ),
    (
        "contract_commitment_discount",
        "Contract pricing, commitments, and discounts",
        "Applicable Account APIs and billing sources",
    ),
]


class DatabricksCostCollector:
    """Collect billing and pricing data from a Databricks SQL warehouse."""

    def __init__(self):
        raw_host = os.getenv("DATABRICKS_HOST", "").strip()
        self.token = os.getenv("DATABRICKS_TOKEN", "").strip()
        self.http_path = os.getenv("DATABRICKS_HTTP_PATH", "").strip()

        # Accept either a hostname or a full HTTPS URL.
        if raw_host.startswith(("https://", "http://")):
            parsed = urlparse(raw_host)
            self.host = parsed.netloc
        else:
            self.host = raw_host.rstrip("/")

        self.host = self.host.rstrip("/")

    def _validate_config(self):
        """Fail clearly when required connection settings are missing."""
        missing = []

        if not self.host:
            missing.append("DATABRICKS_HOST")
        if not self.token:
            missing.append("DATABRICKS_TOKEN")
        if not self.http_path:
            missing.append("DATABRICKS_HTTP_PATH")

        if missing:
            raise ValueError(
                "Missing required environment variables: "
                + ", ".join(missing)
            )

    def _connect(self):
        """Create a connection using the official Databricks SQL connector."""
        self._validate_config()

        return sql.connect(
            server_hostname=self.host,
            http_path=self.http_path,
            access_token=self.token,
        )

    @staticmethod
    def _classify_error(error):
        """
        Return a conservative status and a useful error explanation.

        Do not classify every failed query as a permission error.
        """
        message = str(error)
        lowered = message.lower()

        permission_markers = (
            "permission_denied",
            "permission denied",
            "access_denied",
            "access denied",
            "unauthorized",
            "forbidden",
            "insufficient privileges",
        )

        if any(marker in lowered for marker in permission_markers):
            return "permission_denied", message

        # Only report an unavailable table when the error actually
        # indicates that the requested object cannot be found.
        not_found_markers = (
            "table_or_view_not_found",
            "table or view not found",
            "table not found",
            "cannot_find_table",
            "cannot find table",
        )

        if any(marker in lowered for marker in not_found_markers):
            return "unavailable_in_account", message

        return "failed", message

    @staticmethod
    def _fetch_all(cursor, batch_size=1000):
        """Fetch every returned row in batches and preserve column names."""
        if cursor.description is None:
            return []

        columns = [description[0] for description in cursor.description]
        records = []

        while True:
            batch = cursor.fetchmany(batch_size)

            if not batch:
                break

            for row in batch:
                records.append(dict(zip(columns, row)))

        return records

    def collect_billing_usage(self, start_time: str, end_time: str):
        """
        Collect usage records overlapping the requested time window.

        Timestamps should be supplied in ISO-8601 format with a timezone,
        preferably UTC, for example 2026-10-01T00:00:00Z.
        """
        query = """
            SELECT
                account_id,
                workspace_id,
                record_id,
                sku_name,
                cloud,
                usage_start_time,
                usage_end_time,
                usage_quantity,
                usage_unit,
                identity_metadata,
                custom_tags,
                usage_metadata
            FROM system.billing.usage
            WHERE usage_start_time < ?
              AND usage_end_time > ?
        """

        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    # Parameter binding avoids inserting timestamps
                    # directly into the SQL query string.
                    cursor.execute(query, (end_time, start_time))
                    records = self._fetch_all(cursor)

            if not records:
                return "empty", [], None

            return "collected", records, None

        except ValueError as error:
            return "failed", [], str(error)

        except Exception as error:
            status, explanation = self._classify_error(error)
            return status, [], explanation

    def collect_list_prices(self):
        """Collect all list-price rows returned by the system table."""
        query = """
            SELECT *
            FROM system.billing.list_prices
        """

        try:
            with self._connect() as connection:
                with connection.cursor() as cursor:
                    cursor.execute(query)
                    records = self._fetch_all(cursor)

            if not records:
                return "empty", [], None

            return "collected", records, None

        except ValueError as error:
            return "failed", [], str(error)

        except Exception as error:
            status, explanation = self._classify_error(error)
            return status, [], explanation

    def collect_account_budgets(self):
        """
        Placeholder: budget collection requires an implemented,
        account-appropriate API integration.

        Do not report permission_denied without an actual access attempt.
        """
        return (
            "unsupported",
            [],
            "Account budget API collection is not implemented yet; "
            "the source must be investigated and access verified.",
        )

    def collect_commitments(self):
        """
        Placeholder: investigate supported contract and commitment
        sources before determining their availability.
        """
        return (
            "unsupported",
            [],
            "Contract and commitment collection is not implemented yet; "
            "availability has not been verified.",
        )
