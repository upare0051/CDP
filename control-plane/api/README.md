# Control Plane API (Phase 1 Scaffold)

This service is the start of an internal control-plane to support one-click customer installs.

Current endpoints:

- `GET /health` -> service health
- `POST /v1/tenants/plan` -> returns a tenant deployment plan (non-mutating)

## Run locally

```bash
cd control-plane/api
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --port 9100
```

## Example request

```bash
curl -s -X POST http://localhost:9100/v1/tenants/plan \
  -H "Content-Type: application/json" \
  -d '{
    "tenant_slug": "customer-a",
    "company_name": "Customer A Inc",
    "contact_email": "admin@customera.com",
    "cloud_project_id": "my-gcp-project"
  }'
```
# Control Plane API

Future endpoints:
- `POST /tenants`
- `POST /tenants/{id}/deploy`
- `POST /tenants/{id}/rotate-secrets`
