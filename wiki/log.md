# CDP Wiki Log

Chronological, append-only. Newest at the bottom.

## [2026-05-13] ingest | bootstrap wiki

Bootstrapped the LLM wiki for the CDP repo:

- Copied `CLAUDE.md` and `AGENTS.md` from the martech repo to the CDP root.
- Created `wiki/` skeleton with `entities/`, `decisions/`, `investigations/`, `references/`.
- Seeded `entities/overview.md` from `README.md` covering architecture, sync modes, and project structure.
- Initialized `index.md` catalog.

## [2026-05-13] investigation | journey builder integration

Documented the Laudspeaker-compatible Journey Builder integration:

- Native `/api/v1/journey-builder/*` routes proxy Dittofeed APIs through the backend.
- `GET /api/workspaces` is not available in the current lite image, so workspace discovery falls back to the dashboard payload.
- Journey Builder is now exposed as the `dittofeed` destination type in the frontend/API so audience syncs can feed the journey engine.

## [2026-05-13] investigation | journey builder iframe visibility

Fixed the embedded Journeys page visibility issue:

- Dittofeed lite was rendering its sidebar as a Material UI drawer and backdrop, leaving the Journey table obscured inside the CDP iframe.
- Updated `journeys/dashboard-overrides.css` to hide `.MuiDrawer-root`, `.MuiDrawer-paper`, and `.MuiBackdrop-root`.
- Browser verification at `/journey-builder/journeys` shows the Journey table and `New Journey` button.

## [2026-05-13] investigation | journey builder iframe spacing

Tightened the Journey Builder embed spacing:

- Updated `frontend/src/pages/JourneyBuilder.tsx` to cancel the full responsive `Layout` padding and render the reload control as an overlay instead of a dedicated toolbar row.
- Reset Dittofeed's `.MuiAppBar-root` drawer offset and added right-side main padding in `journeys/dashboard-overrides.css`.
- Browser verification at `/journey-builder/journeys` shows the iframe aligned to the CDP content edge with no large outer gap.

## [2026-05-13] investigation | journey builder shell styling

Aligned the embedded Dittofeed pages with the CDP shell:

- Added shared Proxima Nova typography, black primary buttons, square controls, white surfaces, mercury borders, and table/input/menu styling in `journeys/dashboard-overrides.css`.
- Browser verification at `/journey-builder/journeys` shows the Journey table and `New Journey` action using the shell visual treatment with no console errors.
- Spot checks at `/journey-builder/templates` and `/journey-builder/broadcasts` confirm those routes render under the same shell and Ditto override.

## [2026-05-13] investigation | dashboard route loading loop

Fixed a local loading loop at `http://localhost/dashboard`:

- `journeys/nginx.conf` routed `/dashboard/` to Dittofeed for the iframe. nginx auto-redirected exact `/dashboard` to `/dashboard/`, then Dittofeed's Next.js app redirected `/dashboard/` back to `/dashboard`, causing repeated loads.
- Added exact nginx locations for `/dashboard` and `/dashboard/` so the CDP React app owns the shell dashboard route while `/dashboard/journeys` and other Dittofeed iframe paths still route to Dittofeed.
- `backend/app/services/postgres_customer_service.py` now returns empty customer responses when fresh local warehouse mart tables are not present, avoiding a dashboard 500 from `/api/v1/customers/stats`.
- Verified `/dashboard`, `/dashboard/`, `/dashboard/journeys`, and dashboard API dependencies with HTTP checks.
