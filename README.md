# Alo ActivationOS - Reverse ETL Platform

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
│                    Alo ActivationOS                               │
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
# Create virtual environment (repo standard: .venv)
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# or: .\\.venv\\Scripts\\activate  # Windows

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp env.example .env
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

### Full stack with Docker (recommended for local demos)

Prerequisites: **Docker** with **Compose v2** (`docker compose`).

| Action | Command |
|--------|---------|
| Start (app + warehouse + Cube + journeys + nginx) | `./start.sh` |
| Stop (same compose files) | `./stop.sh` |

On first start, if `cube/.env` is missing it is copied from `cube/.env.example`.

**URLs after `./start.sh`**

| Service | URL / port |
|---------|------------|
| Unified UI (nginx: frontend + API + Cube + Journeys on one origin) | http://localhost/ |
| Vite dev server (direct) | http://localhost:5173 |
| FastAPI + OpenAPI | http://localhost:8000 — docs at http://localhost:8000/api/docs |
| Cube (playground / REST) | http://localhost:4001 |
| MinIO console | http://localhost:9001 |
| App metadata Postgres | `localhost:5432` |
| **Warehouse Postgres** (`gold.*` CDP marts) | `localhost:5433` (defaults: db `cdp_warehouse`, user/password `cdp`) |
| Redis | `6379` |
| MinIO S3 API | `9000` |
| Journeys stack (Dittofeed deps) | Postgres `25432`, ClickHouse `8125`, Temporal `27233` |

The backend container uses `WAREHOUSE_MODE=postgres` and reads from **`warehouse-postgres`**. Cube uses the same warehouse. If you have not loaded data, the UI still runs but customer counts and Cube-driven widgets may stay empty until you seed (next section).

**Apple Silicon vs x86:** `cube/docker-compose.cube.yml` pins `cubejs/cubestore:arm64v8`. On Intel Linux or Intel Mac, if Cube Store fails to pull or start, switch that image to `cubejs/cubestore:latest` (see `cube/README.md`).

### Preparing warehouse-postgres (Redshift to local)

`warehouse-postgres` is the local analytic database (host port **5433**). The backend and Cube expect **`gold.*`** tables there when running the Docker stack.

**Fresh data vs stale DuckDB:** Files under `data/demo/*.duckdb` are **snapshots** and fall behind live **Redshift `gold.*`**. Whenever you need **warehouse-postgres** to mirror **current Redshift dev**, refresh from Redshift first (tunnel up), then seed—do not rely only on old DuckDB files checked into the repo.

**Redshift dev tunnel:** Point `.env` at your tunnel (common dev mapping: **`127.0.0.1:10005`** or `localhost:10005` — see `env.example` `REDSHIFT_HOST` / `REDSHIFT_PORT`). The snapshot script checks connectivity before copying.

See also: **`docs/WAREHOUSE_REDSHIFT_CRM_AIRFLOW.md`** (Redshift vs API delivery patterns, Airflow).

**Path A — Redshift → DuckDB → warehouse-postgres (typical for engineers)**

DuckDB here is only a **staging** format for `seed_warehouse_from_duckdb.py`; the **source of truth** for refreshed marts is **Redshift** each time you run the snapshot.

1. Add Redshift (and tunnel) settings to a repo-root **`.env`** — start from `env.example` and follow internal docs for host/port (often `localhost` + tunnel port).

2. Ensure the tunnel or network path to Redshift matches your `.env` (dev example: **`127.0.0.1:10005`** → Redshift, as in `env.example`).

3. Snapshot allowlisted `gold.*` tables into DuckDB (from repo root, with `.venv` activated and `pip install -r requirements.txt`):

   ```bash
   python3 scripts/snapshot_redshift_to_duckdb.py --out data/demo/activationos_demo.duckdb --max-rows-per-table 5000
   ```

4. The warehouse seeder expects **`data/demo/activationos_demo_2.duckdb`**. After a snapshot, align the name:

   ```bash
   mkdir -p data/demo
   cp data/demo/activationos_demo.duckdb data/demo/activationos_demo_2.duckdb
   ```

5. Build the small `order_line_fact` DuckDB used alongside the main demo file (if you do not already have `data/demo/customer_mart.duckdb`):

   ```bash
   python scripts/build_demo_customer_mart_duckdb.py --out data/demo/customer_mart.duckdb
   ```

6. Start Docker (`./start.sh`) so `warehouse-postgres` is up on **5433**.

7. Seed Postgres using DuckDB’s postgres extension (same shell, repo root):

   ```bash
   export WAREHOUSE_POSTGRES_HOST=localhost
   export WAREHOUSE_POSTGRES_PORT=5433
   export WAREHOUSE_POSTGRES_DB=cdp_warehouse
   export WAREHOUSE_POSTGRES_USER=cdp
   export WAREHOUSE_POSTGRES_PASSWORD=cdp
   python cube/scripts/seed_warehouse_from_duckdb.py
   ```

8. *(Recommended)* Apply warehouse indexes for faster slices and extracts:

   ```bash
   docker compose -f docker-compose.yml -f cube/docker-compose.cube.yml exec -T warehouse-postgres \
     psql -U cdp -d cdp_warehouse < cube/scripts/warehouse_indexes.sql
   ```

   Use the same `-f` list you use to run the stack; container names may include a project prefix (check `docker compose ... ps` if `exec` fails).

**Path B — Redshift → warehouse-postgres via Meltano (full ETL parity)**

For incremental replication and the same pipeline shape as production, use the **Meltano** / **alo-meltano** `local-demo` style workflow described in **`cube/README.md`** (Redshift tap → Postgres warehouse). Cube and the backend then consume `warehouse-postgres` without the intermediate DuckDB snapshot.

**Path C — DuckDB-only app (no `warehouse-postgres`)**

To run the API against a **single DuckDB file** instead of warehouse Postgres, use `WAREHOUSE_MODE=duckdb` and set `DUCKDB_PATH` to your snapshot (see **Local demo snapshot (Redshift → DuckDB)** under [Development](#development) below). That path does not populate `warehouse-postgres`; it is aimed at lightweight or offline API use rather than the full Docker + Cube stack.

### Airflow Setup (Optional)

Used for **scheduled** and **on-demand** triggers of sync jobs (API pattern). Set Variable `activationos_api_url` (e.g. `http://localhost:8000/api/v1`). DAGs under `airflow/dags/` call the ActivationOS API (e.g. `activationos_sync_dag.py`). For **materializing tables in Redshift** for a CRM team (warehouse pattern), run **dbt / Meltano / SQL** jobs from Airflow as separate DAGs—see **`docs/WAREHOUSE_REDSHIFT_CRM_AIRFLOW.md`**.

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
airflow variables set activationos_api_url http://localhost:8000/api/v1

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
Alo ActivationOS/
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

For the **Docker stack** with `warehouse-postgres` and Cube, prefer the [Preparing warehouse-postgres](#preparing-warehouse-postgres-redshift-to-local) steps above (snapshot → seed). The following is the **DuckDB-only** backend mode (`WAREHOUSE_MODE=duckdb`).

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
