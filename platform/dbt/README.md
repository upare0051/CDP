# Alo ActivationOS dbt Transformations

This project defines the transformation layer for Alo ActivationOS / BridgeSync.

It turns application tables (`customer_profiles`, `customer_attributes`, `segments`, `segment_activations`, etc.) into analytics-ready marts for:

- Customer 360 views
- Segment-level analytics
- Activation performance reporting

## Structure

```text
platform/dbt/
├── dbt_project.yml
├── packages.yml
├── profiles.yml.example
├── models/
│   ├── sources.yml
│   ├── staging/
│   ├── intermediate/
│   └── marts/
└── requirements.txt
```

## Setup

1. Install dbt dependencies:

```bash
cd platform/dbt
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
dbt deps
```

2. Configure profile:

```bash
cp profiles.yml.example ~/.dbt/profiles.yml
```

3. Set environment variables for DuckDB + attached BridgeSync SQLite DB:

```bash
export DBT_DUCKDB_PATH=/Users/utkarshparekh/BridgeSync/platform/dbt/activationos_transform.duckdb
export DBT_DUCKDB_SCHEMA=main
export DBT_BRIDGESYNC_SQLITE_PATH=/Users/utkarshparekh/BridgeSync/backend/bridgesync.db
export DBT_BRIDGESYNC_SOURCE_DATABASE=bridgesync_src
export DBT_BRIDGESYNC_SCHEMA=main
```

4. Run models and tests:

```bash
dbt debug
dbt build
```

## Models

### Staging
- `stg_customer_profiles`
- `stg_customer_attributes`
- `stg_customer_events`
- `stg_segments`
- `stg_segment_memberships`
- `stg_segment_activations`
- `stg_activation_runs`

### Intermediate
- `int_customer_attributes_pivot`

### Marts
- `mart_customer_360`
- `mart_segment_base`
- `mart_activation_performance`

## Orchestration

Recommended Airflow task order:

1. `dbt deps` (on deployment)
2. `dbt build --select tag:staging`
3. `dbt build --select tag:intermediate`
4. `dbt build --select tag:mart`

For fast local runs:

```bash
dbt build --select mart_customer_360 mart_segment_base mart_activation_performance
```
