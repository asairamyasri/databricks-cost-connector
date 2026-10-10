# Databricks Cost Connector

A production-grade Python connector built to discover, collect, and normalize cost management data from Databricks system tables (`system.billing.usage`, `system.billing.list_prices`) and Account APIs.

## Features

- **Live System Table Extraction**: Queries active DBU usage and list price records via the official `databricks-sql-connector`.
- **Full Coverage Discovery**: Investigates all required cost categories with explicit status tracking (`collected`, `empty`, `permission_denied`, `unavailable_in_account`).
- **Data Normalization**: Converts raw records into standardized UTC/ISO-8601 schemas with exact `Decimal` precision for usage quantities.
- **Resilient Pipeline**: Gracefully handles stringified metadata columns and restricted/unsupported account features without pipeline interruption.

## Repository Structure

├── client.py              # Databricks connection & system table query execution
├── normalizer.py          # Pydantic schemas & UTC/Decimal normalizer logic
├── main.py                # Pipeline orchestrator & Coverage Report table generator
├── test_normalizer.py     # Unit test suite covering precision and null fallbacks
├── data/
│   ├── raw/               # Raw JSON extraction artifacts
│   └── normalized/        # Standardized output JSON artifacts
├── .env.example           # Sanitized environment template
├── .gitignore             # Excludes .env, venv, and local caches
├── requirements.txt       # Project dependencies
└── README.md

## Setup Instructions

### 1. Initialize Environment
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

### 2. Configure Credentials
Copy `.env.example` to `.env` and populate your Databricks workspace details:
DATABRICKS_HOST=https://<your-workspace-instance>.cloud.databricks.com
DATABRICKS_TOKEN=dapi...
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/<warehouse-id>
START_TIME=2026-10-01T00:00:00Z
END_TIME=2026-10-09T23:59:59Z

### 3. Run Pipeline
Execute the main script to fetch data, generate normalized JSON outputs, and print the coverage report:
python main.py

### 4. Run Automated Tests
Verify data transformation and schema handling:
pytest test_normalizer.py -v
