# Deploy Alo ActivationOS on GCP (Day 1)

This guide sets up:
- frontend landing page + demo CTA on Cloud Run
- backend API on Cloud Run
- CI/CD from GitHub Actions
- domain mapping from GoDaddy

## 1) One-time GCP setup

1. Create/select project:
   - `gcloud config set project <PROJECT_ID>`
2. Enable APIs:
   - `run.googleapis.com`
   - `artifactregistry.googleapis.com`
   - `secretmanager.googleapis.com`
   - `iamcredentials.googleapis.com`
3. Create Artifact Registry repo:
   - `gcloud artifacts repositories create activationos --repository-format=docker --location=<REGION>`

## 2) Create secrets in Secret Manager

Create these secrets:
- `DATABASE_URL`
- `ENCRYPTION_KEY`
- `PUBLIC_DEMO_URL`

Example:
- `echo -n "https://demo.activationos.local/dashboard" | gcloud secrets create PUBLIC_DEMO_URL --data-file=-`

## 3) Configure GitHub OIDC for CI/CD

Use workload identity federation:
- Create workload identity pool + provider
- Create deploy service account
- Grant roles:
  - `roles/run.admin`
  - `roles/artifactregistry.writer`
  - `roles/iam.serviceAccountUser`
  - `roles/secretmanager.secretAccessor`

Add repo secrets in GitHub:
- `GCP_PROJECT_ID`
- `GCP_REGION`
- `GCP_ARTIFACT_REPO` (e.g. `activationos`)
- `GCP_WIF_PROVIDER`
- `GCP_WIF_SERVICE_ACCOUNT`
- `VITE_API_BASE_URL` (e.g. `https://api.activationos.local/api/v1`)

## 4) Deploy from GitHub Actions

Workflow file:
- `.github/workflows/deploy-gcp.yml`

Trigger:
- Push to `main`, or run manually from GitHub Actions.

## 5) Domain mapping (GoDaddy + Cloud Run)

Use two hostnames:
- `activationos.local` -> frontend service
- `api.activationos.local` -> backend service

In Cloud Run:
1. Open service
2. Manage custom domains
3. Add domain mapping
4. Copy DNS records required by Google

In GoDaddy DNS:
- Create the records exactly as shown by GCP verification/mapping flow.

## 6) Day-to-day release flow

1. Commit + push to `main`
2. GitHub Action builds and deploys backend/frontend
3. Verify:
   - `https://activationos.local`
   - `https://api.activationos.local/api/v1/health`

## Notes

- Landing page lead capture endpoint:
  - `POST /api/v1/public/lead-capture`
- Uses work-email validation (blocks common personal domains).
