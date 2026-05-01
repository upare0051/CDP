# BridgeSync - Reverse ETL Platform

A production-style MVP for a Reverse ETL platform that syncs customer data from data warehouses (Redshift/DuckDB) to marketing platforms (Braze/Attentive).

## Workspace Reorganization (In Progress)

To safely support long-term goals (website + product split, customer one-click deployment, config-first architecture), a non-breaking scaffold has been added:

- `apps/website/*` (future website frontend/backend/admin-config)
- `apps/product/*` (future product frontend/backend/admin-config)
- `control-plane/*` (future tenant lifecycle automation)
- `infra/terraform/*` (future reusable IaC modules and tenant stacks)
- `packages/shared-config-schema/*` (shared config contracts)
- `.env.templates/*` (environment templates)

Current production runtime remains on existing folders (`frontend/`, `backend/`) until migration cutover.

## Features

- **Source Connections**: Connect to Redshift (production) or DuckDB (local development)
- **Destination Connectors**: Braze and Attentive with proper payload builders
- **Sync Modes**: Full refresh and incremental sync with checkpoint tracking
- **Field Mapping**: UI-driven column mapping from source to destination
- **Airflow Integration**: DAGs for scheduled sync job orchestration
- **Run History**: Complete sync run tracking with logs and error details
- **Schema Change Detection**: Automatic detection of source table changes
- **Secure Credentials**: Encrypted storage for API keys and passwords

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        BridgeSync                                │
├─────────────────────────────────────────────────────────────────┤
│  Frontend (React)                                                │
│  └── Dashboard, Sources, Destinations, Syncs, Runs              │
├─────────────────────────────────────────────────────────────────┤
│  Backend (FastAPI)                                               │
│  ├── API Routes (sources, destinations, syncs, runs)            │
│  ├── Services (connection, sync, engine)                        │
│  └── Adapters (sources: DuckDB/Redshift, destinations: Braze/Attentive)│
├─────────────────────────────────────────────────────────────────┤
│  Database (PostgreSQL)                                           │
│  └── Connections, Sync Jobs, Field Mappings, Sync Runs          │
├─────────────────────────────────────────────────────────────────┤
│  Scheduler (Airflow)                                             │
│  └── DAGs for sync job orchestration                            │
└─────────────────────────────────────────────────────────────────┘
```

## Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+
- PostgreSQL (optional, SQLite fallback available)
- Apache Airflow (optional, for scheduling)

### Backend Setup

```bash
# Create virtual environment
python -m venv venv
source venv/bin/activate  # Linux/Mac
# or: .\venv\Scripts\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
# Edit .env with your settings

# Run backend
cd backend
python main.py
```

Backend runs at: http://localhost:8000
API docs: http://localhost:8000/api/docs

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Run development server
npm run dev
```

Frontend runs at: http://localhost:5173

### Airflow Setup (Optional)

```bash
# Initialize Airflow database
airflow db init

# Create admin user
airflow users create \
    --username admin \
    --firstname Admin \
    --lastname User \
    --role Admin \
    --email admin@example.com \
    --password admin

# Set Airflow variables
airflow variables set bridgesync_api_url http://localhost:8000/api/v1

# Copy DAGs
cp airflow/dags/*.py $AIRFLOW_HOME/dags/

# Start Airflow
airflow webserver --port 8080 &
airflow scheduler &
```

### dbt Transformations (Phase 5)

```bash
cd platform/dbt

# Create dedicated virtual environment for dbt
python -m venv .venv
source .venv/bin/activate

# Install dbt dependencies
pip install -r requirements.txt
dbt deps

# Configure profile
cp profiles.yml.example ~/.dbt/profiles.yml

# Validate and run
dbt debug
dbt build
```

The dbt project produces marts for:
- `mart_customer_360`
- `mart_segment_base`
- `mart_activation_performance`
- `mart_ai_customer_insights_team`
- `mart_ai_audience_recommendations_team`

## API Endpoints

### Sources
- `GET /api/v1/sources` - List source connections
- `POST /api/v1/sources` - Create source connection
- `POST /api/v1/sources/{id}/test` - Test source connection
- `GET /api/v1/sources/{id}/schemas` - Get schemas
- `GET /api/v1/sources/{id}/schemas/{schema}/tables` - Get tables

### Destinations
- `GET /api/v1/destinations` - List destination connections
- `POST /api/v1/destinations` - Create destination connection
- `POST /api/v1/destinations/{id}/test` - Test destination connection

### Syncs
- `GET /api/v1/syncs` - List sync jobs
- `POST /api/v1/syncs` - Create sync job
- `POST /api/v1/syncs/{id}/trigger` - Trigger sync run
- `PUT /api/v1/syncs/{id}/mappings` - Update field mappings
- `POST /api/v1/syncs/{id}/pause` - Pause sync job
- `POST /api/v1/syncs/{id}/resume` - Resume sync job

### Runs
- `GET /api/v1/runs` - List sync runs
- `GET /api/v1/runs/{run_id}` - Get run details
- `GET /api/v1/runs/stats/summary` - Get run statistics

## Sync Modes

### Full Refresh
- Reads all data from source
- Sends complete dataset to destination
- No checkpoint tracking

### Incremental
- Requires `incremental_column` (e.g., `updated_at`)
- Tracks last synced value as checkpoint
- Only syncs records where `incremental_column > checkpoint`
- Checkpoint only saved on successful completion

## Destination Payload Formats

### Braze
```json
{
  "attributes": [
    {
      "external_id": "user_123",
      "email": "user@example.com",
      "first_name": "John",
      "custom_attribute": "value"
    }
  ]
}
```

### Attentive
```json
{
  "subscribers": [
    {
      "phone": "+14155551234",
      "email": "user@example.com",
      "externalId": "user_123",
      "customAttributes": {}
    }
  ]
}
```

## Project Structure

```
BridgeSync/
├── backend/
│   ├── app/
│   │   ├── adapters/
│   │   │   ├── sources/       # DuckDB, Redshift adapters
│   │   │   └── destinations/  # Braze, Attentive adapters
│   │   ├── api/routes/        # FastAPI routes
│   │   ├── core/              # Config, security, logging
│   │   ├── db/                # SQLAlchemy setup
│   │   ├── models/            # SQLAlchemy models
│   │   ├── schemas/           # Pydantic schemas
│   │   └── services/          # Business logic
│   └── main.py
├── frontend/
│   ├── src/
│   │   ├── components/        # React components
│   │   ├── pages/             # Page components
│   │   ├── lib/               # API client, utils
│   │   └── types/             # TypeScript types
│   └── package.json
├── airflow/
│   └── dags/                  # Airflow DAGs
├── requirements.txt
└── README.md
```

## Configuration

| Variable | Description | Default |
|----------|-------------|---------|
| `WAREHOUSE_MODE` | Warehouse mode: `redshift` (live) or `duckdb` (demo snapshot) | `redshift` |
| `DUCKDB_PATH` | DuckDB database path | `:memory:` |
| `POSTGRES_*` | PostgreSQL connection settings | localhost |
| `ENCRYPTION_KEY` | Key for encrypting credentials | Required |
| `MAX_RETRIES` | Max retry attempts for failed syncs | 3 |
| `SYNC_BATCH_SIZE` | Records per batch | 1000 |

## Development

### Local demo snapshot (Redshift → DuckDB)

Production/dev is **Redshift live**. For local demos (or offline-ish exploration), generate a DuckDB snapshot from the same allowlisted marts used by Ask/Reference:

First ensure your Redshift tunnel is running (so `localhost:10005` is reachable).

```bash
python3 scripts/snapshot_redshift_to_duckdb.py --out data/demo/activationos_demo.duckdb --max-rows-per-table 5000
```

Then run the app with:

```bash
export WAREHOUSE_MODE=duckdb
export DUCKDB_PATH=data/demo/activationos_demo.duckdb
```

### Testing

```bash
# Run tests
pytest

# With coverage
pytest --cov=app
```

## License

MIT
