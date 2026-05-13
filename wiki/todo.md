# CDP Wiki TODO

Top-level, cross-cutting follow-ups that don't belong to a single
investigation. One line per item; link to the page with full context.
Append new items at the bottom; check them off in place. Drop completed
items once they're noted in `log.md`.

- [ ] **Start the `compute-properties-queue-workflow` on the
  dittofeed-lite workspace.** Until this runs, mirrored segments appear
  in the journey builder's Wait For dropdown but membership pushes fail
  inside Temporal (`WorkflowNotFoundError: sql: no rows in result set`),
  so Wait For never advances users. Likely fix: configure the workflow
  at stack start, or upgrade off `dittofeed-lite:v0.24.0-alpha.17` to an
  image that bootstraps it. Context:
  [investigations/segment-dittofeed-mirror.md](investigations/segment-dittofeed-mirror.md).
