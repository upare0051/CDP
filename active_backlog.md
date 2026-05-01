# Active Backlog

## Explorer / Query Studio

- Add favorites / saved snippets in Query Studio:
  - save query snippets
  - list saved snippets
  - run a saved snippet
  - delete a saved snippet
  - optional tags for organization

## Phase 5.2C - Team Consumption

- Add drill-down actions on Operational View cards:
  - click card to auto-load scoped SQL in Query Studio
  - support CS/Sales/DA/DS card-specific filters

- Add saved operational queries by team:
  - reusable query set for CS/Sales/DA/DS
  - quick apply/run from team context

## Website Admin / Product Admin Split

- Split admin surfaces:
  - Website admin (visitor + lead analytics, outreach workflows, landing content controls)
  - Product admin (customer-facing product settings and safe customization controls)
  - define role model + access boundaries across both surfaces

- Outreach acceleration:
  - add one-click "copy personalized first message" per lead
  - personalize template by detected industry source + use case

## SEO / Indexing Ops

- Post-release Google indexing checklist:
  - run URL Inspection + Request Indexing for homepage and key industry routes
  - submit/refresh sitemap and verify canonical coverage
  - monitor snippet quality and title/description adoption in Search Console

## Reorg / Multi-Tenant Foundation

- Migrate from current runtime folders to split app topology:
  - website app (owner-only admin)
  - product app (customer-admin managed)
  - control-plane for tenant lifecycle

- One-click tenant install automation:
  - Terraform tenant-template + secrets + deploy pipeline
  - provisioning target: install new customer in minutes

- Config-first platform baseline:
  - remove hardcoded content/config paths
  - enforce schema-validated config versions per app/tenant
  - use Ollama as the local-first AI provider
