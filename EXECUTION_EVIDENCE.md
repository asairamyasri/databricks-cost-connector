# Databricks Cost Connector — Execution Evidence

## 1. Environment

- Language: Python
- Connector: Databricks SQL Connector for Python
- Authentication: Credentials supplied through environment variables
- Execution: `python main.py`
- Test command: `pytest -q`

Credentials, access tokens, and sensitive account details are intentionally excluded from this document.

## 2. Live Collection Results

The connector successfully queried the following Databricks system tables:

| Dataset | Status | Records |
|---|---|---:|
| `system.billing.usage` | collected | 38 |
| `system.billing.list_prices` | collected | 887 |

Billing usage was queried for the configured interval:

`2026-10-01T00:00:00Z` to `2026-10-09T23:59:59Z`

The connector preserved raw source records and generated normalized billing records.

## 3. Normalization Results

- Billing records collected: 38
- Normalized records: 38
- Normalization errors: 0
- Records with calculated list cost: 25
- Records without a matching list-price record: 13

The unmatched records use the SKU `GENIE_FREE_USAGE`. No matching SKU was found in the collected pricing dataset. Their list unit price and list cost were left null rather than inventing a price.

List cost calculations use the matched unit price and usage quantity where a valid price match is available. List cost is not the same as billed or effective cost.

## 4. Coverage Reporting

The connector generated a coverage report containing 17 cost-management categories.

The report distinguishes collected data from categories for which a collector has not been implemented or availability has not been verified. Categories marked unsupported should not be interpreted as proof that the corresponding feature is unavailable in the account.

The coverage report is available at `data/coverage_report.json`.

## 5. Generated Artifacts

- Raw records: `data/raw/raw_sample.json`
- Normalized records: `data/normalized/normalized_sample.json`
- Coverage report: `data/coverage_report.json`
- Normalization errors: `data/normalization_errors.json`

## 6. Automated Tests

Command executed:

`pytest -q`

Result: All tests passed.

## 7. Security

Credentials are read from environment variables and are not included in this evidence. The local `.env` file is excluded from Git. Account identifiers and other sensitive values should be redacted from any additional logs or screenshots.

