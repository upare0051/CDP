# Client One — Clienteling Intelligence Platform

A lightweight Flask web app that gives store associates a real-time 360° view of any customer: purchase history, loyalty status, communication preferences, and AI-generated conversation starters.

## Architecture

```
Browser  ──►  Flask (port 5050)
                ├── /api/customers/*   ──►  ActivationOS backend (port 8000)
                │                              └── Cube semantic layer → Redshift
                └── /api/customers/*/purchases  ──►  Redshift (port 10005, direct)
                                                       └── gold.gold_omni_order_line_item_detail
```

## Prerequisites

| Requirement | Version | Notes |
|---|---|---|
| Python | 3.11+ | 3.14 tested |
| ActivationOS backend | running | `http://localhost:8000` by default |
| Redshift dev tunnel | localhost:10005 | SSH tunnel or `kubectl port-forward` to Redshift dev |

### Python dependencies

```
flask>=3.0
requests>=2.31
redshift_connector>=2.1
```

Installed automatically by `run.sh` on first launch.

### Redshift tunnel

The Purchases tab queries `gold.gold_omni_order_line_item_detail` directly. You need a live tunnel to the Redshift dev cluster on **localhost:10005** before starting the app.

Using the dbt profile (`~/.dbt/profiles.yml`, profile `warehouse`, target `local`):

```yaml
local:
  type: redshift
  host: localhost
  port: 10005
  dbname: dev
  user: <your-iam-user>
  password: <your-password>
  sslmode: disable
```

Override at runtime with environment variables:

```bash
export REDSHIFT_HOST=localhost
export REDSHIFT_PORT=10005
export REDSHIFT_DATABASE=dev
export REDSHIFT_USER=your.name
export REDSHIFT_PASSWORD=yourpassword
```

## Running locally

```bash
cd apps/client-one
./run.sh            # default port 5050, backend http://localhost:8000

# Override port or backend
PORT=5051 BACKEND_URL=http://localhost:8000 ./run.sh
```

The virtual environment (`.venv/`) is created automatically on first run.

## Features

| Tab | Data source | Description |
|---|---|---|
| **Overview** | Cube `customer_360` | Loyalty tier, order recency, location, contact preferences, reachability |
| **Purchases** | Redshift `gold.gold_omni_order_line_item_detail` | Full order line history with channel, store, price |
| **SA Intel** | Derived from Cube data | AI-generated conversation starters, behavioral signals, dos/don'ts |

### Search modes

| Input | Behavior |
|---|---|
| `@` in query | Email search (`email_norm` contains) |
| 7+ digits | Phone search (`phone_norm` contains) |
| Two words | AND match on first + last name |
| One word | OR match on first OR last name |

## Environment variables

| Variable | Default | Description |
|---|---|---|
| `BACKEND_URL` | `http://localhost:8000` | ActivationOS backend base URL |
| `PORT` | `5050` | Flask listen port |
| `REDSHIFT_HOST` | `localhost` | Redshift host |
| `REDSHIFT_PORT` | `10005` | Redshift port |
| `REDSHIFT_DATABASE` | `dev` | Redshift database |
| `REDSHIFT_USER` | *(from dbt profile)* | Redshift IAM user |
| `REDSHIFT_PASSWORD` | *(from dbt profile)* | Redshift password |
