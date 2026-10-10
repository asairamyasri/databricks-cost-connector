# Databricks Cost Connector

A Python connector for discovering, collecting, and normalizing Databricks cost-management data from system tables and Account APIs.

## Features

- **System Table Extraction:** Retrieves DBU usage and list-price records from `system.billing.usage` and `system.billing.list_prices` using the official `databricks-sql-connector`.
- **Coverage Tracking:** Tracks the collection status of required cost categories using `collected`, `empty`, `permission_denied`, and `unavailable_in_account`.
- **Data Normalization:** Converts raw records into standardized UTC/ISO-8601 formats while preserving exact decimal precision for usage quantities.
- **Error Handling:** Handles stringified metadata, null values, and restricted or unsupported account features without unnecessarily interrupting the pipeline.
- **Unit Testing:** Tests normalization logic, decimal precision, and null-value handling using pytest.

## Project Structure

```text
databricks-cost-connector/
├── client.py
├── normalizer.py
├── main.py
├── test_normalizer.py
├── requirements.txt
├── .env.example
├── .gitignore
└── data/
    ├── raw/
    └── normalized/
```

### File Overview

- `client.py` — Establishes the Databricks SQL connection and executes system table queries.
- `normalizer.py` — Defines Pydantic schemas and handles timestamp, decimal, and metadata normalization.
- `main.py` — Orchestrates data collection, normalization, output generation, and coverage reporting.
- `test_normalizer.py` — Contains unit tests for normalization, decimal precision, and null fallbacks.
- `requirements.txt` — Lists the Python dependencies required to run the project.
- `.env.example` — Provides a template for the required environment variables without exposing credentials.
- `.gitignore` — Excludes environment files, virtual environments, and local cache files.
- `data/raw/` — Stores raw extraction artifacts.
- `data/normalized/` — Stores normalized JSON outputs.

## Setup and Execution

### 1. Create the Virtual Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Create a `.env` file using `.env.example` as a template and provide your Databricks workspace credentials.

```dotenv
DATABRICKS_HOST=https://<your-workspace-instance>.cloud.databricks.com
DATABRICKS_TOKEN=<your-access-token>
DATABRICKS_HTTP_PATH=/sql/1.0/warehouses/<warehouse-id>
START_TIME=2026-10-01T00:00:00Z
END_TIME=2026-10-09T23:59:59Z
```

Keep `.env` out of version control. Never commit access tokens or other credentials.

### 3. Run the Connector

Execute the pipeline to collect data, normalize the records, generate JSON outputs, and display the coverage report.

```bash
python main.py
```

### 4. Run Unit Tests

Run the normalization test suite with verbose output:

```bash
pytest test_normalizer.py -v
```

## Output

The pipeline generates the following artifacts:

- `data/raw/` — Raw data extracted from Databricks.
- `data/normalized/` — Normalized records in JSON format.
- **Coverage Report** — Reports the collection status of the required cost categories.

## Requirements

- Python 3
- Databricks workspace access
- A SQL warehouse with the necessary permissions to query billing system tables
- Appropriate permissions for any Account APIs used by the connector
