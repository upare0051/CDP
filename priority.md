# Day 2 Priority Plan

## P0 - Deploy and validate production path

1. Configure GCP + GitHub secrets from `docs/deploy-gcp.md`.
2. Run first deployment from `.github/workflows/deploy-gcp.yml`.
3. Map domains in GoDaddy:
   - `activationos.local` -> frontend
   - `api.activationos.local` -> backend
4. Validate:
   - landing page loads
   - lead capture writes to DB
   - demo link works
   - health endpoint returns healthy

## P1 - Team consumption depth (Phase 5.2C continuation)

1. Operational view card drill-down:
   - click card -> inject scoped SQL in Query Studio.
2. Saved operational queries:
   - save/list/run/delete by team (CS/Sales/DA/DS).
3. Add simple usage tracking:
   - template usage count
   - top queries run.

## P1 - AI segment builder UX

1. Add persistent inline error panel for AI generation.
2. Add “Use fallback template” suggestion when AI is unavailable.
3. Add “copy generated filters” + “explain result” quick actions.

## P2 - Sync & activation hardening

1. Expose detailed destination error payload in Run History details.
2. Add partial-success status (completed_with_errors) for better visibility.
3. Add destination mock-mode badge in UI.

## P2 - Product growth instrumentation

1. Add lead funnel events:
   - landing_view
   - demo_click
   - lead_submit_success/fail
2. Add daily lead summary endpoint/table for GTM review.
3. Add email notification webhook for new inbound leads.

## Definition of done for Day 2

- Public URL live with working reverse ETL console.
- CI/CD deployment green on push to `main`.
- Team operational drill-down and saved queries available in Explorer.
