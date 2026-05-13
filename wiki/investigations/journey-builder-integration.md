# Journey Builder Integration

## Context

The app embeds the Dittofeed lite dashboard under `frontend/src/pages/JourneyBuilder.tsx`, with nginx routing `/dashboard/*` to the `journeys-lite` service. This is the current Laudspeaker-compatible journey orchestration layer for CDP.

Native CDP Journey Builder surfaces live under `/api/v1/journey-builder/*` and proxy Dittofeed APIs through `backend/app/services/dittofeed_client.py`.

## 2026-05-13 Fix

- The native Deliveries API was failing because `dittofeed_client.py` attempted workspace discovery at `GET /api/workspaces`, which returns 404 in the current `dittofeed/dittofeed-lite:v0.24.0-alpha.17` image.
- The client now falls back to loading `/dashboard/journeys` and extracting the active single-tenant `workspaceId` from the dashboard payload.
- The existing `DittofeedAdapter` was registered in the backend, but Journey Builder was not exposed as a destination in the API metadata or frontend destination form.
- The Destinations UI now allows creating a `dittofeed` Journey Builder destination, using the adapter that sends Segment-style `identify` and `track` batch events to `/api/public/apps/batch`.
- The embedded Journeys page also needed CSS updates because Dittofeed lite renders its sidebar as a Material UI drawer (`.MuiDrawer-root`) plus a backdrop (`.MuiBackdrop-root`), not only a `nav` element. `journeys/dashboard-overrides.css` now hides the drawer/backdrop so the Journey table is visible inside the CDP shell.
- The iframe shell now cancels the full responsive `Layout` padding for the Journey Builder page and renders the reload affordance as an overlay. The embedded app bar is reset to span the iframe instead of preserving the hidden drawer offset.
- The Dittofeed dashboard pages are styled through `journeys/dashboard-overrides.css` to match the CDP shell: Proxima Nova typography, black primary actions, square controls, white surfaces, mercury borders, and shell-like table/input/menu treatments. The shared override applies to Journeys, Templates, and Broadcasts.
- The unified nginx proxy must reserve exact `/dashboard` and `/dashboard/` for the CDP React app. Dittofeed still owns `/dashboard/*` for iframe internals, but allowing the prefix location to catch exact `/dashboard` creates a redirect loop between nginx and Dittofeed's Next.js trailing-slash handling.
- Fresh local stacks can start before the warehouse gold marts exist. `PostgresCustomerService` now returns empty customer list/stats/timeline responses for missing customer/order mart tables instead of crashing dashboard requests.

## Verification

- `GET /api/v1/journey-builder/deliveries?limit=1` returns `{workspaceId, items: []}` against the running local stack.
- `GET /api/v1/destinations/types/available` includes `dittofeed`.
- Frontend build passes with the Journey Builder destination option.
- Browser verification at `/journey-builder/journeys` shows the embedded Journey table and `New Journey` button.
- Browser verification after the spacing fix shows no large outer gap around the embedded iframe and no console errors.
- Browser spot checks at `/journey-builder/templates` and `/journey-builder/broadcasts` confirm the same embedded shell and Ditto content render under the shared style override.
- HTTP verification after the proxy fix shows `/dashboard` and `/dashboard/` return the CDP React app, while `/dashboard/journeys` still returns Dittofeed with `dashboard-overrides.css`.
- Dashboard dependency checks show `/api/v1/activations/dashboard`, `/api/v1/customers/stats`, `/api/v1/customers`, `/api/v1/sources`, `/api/v1/destinations`, `/api/v1/syncs`, `/api/v1/runs`, and `/api/v1/runs/stats/summary` return HTTP 200 on a fresh stack.
