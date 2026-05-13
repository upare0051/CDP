# CDP Wiki Index

LLM-maintained catalog for the Alo ActivationOS (CDP) repo. Every wiki page is listed here once with a one-line summary. Read this first; update on every page change.

## Open items

- [todo](todo.md) — Cross-cutting follow-ups not tied to a single investigation.

## Entities

- [overview](entities/overview.md) — High-level architecture: FastAPI backend, React frontend, Postgres metadata, Redshift/DuckDB sources, Braze/Attentive destinations, Airflow scheduler, dbt marts, Cube semantic layer.

## Decisions

_(none yet)_

## Investigations

- [journey-builder-integration](investigations/journey-builder-integration.md) — Notes on the Dittofeed/Laudspeaker-compatible Journey Builder embed, native API proxy, workspace discovery, destination adapter exposure, shell-matched iframe styling, and `/dashboard` proxy routing.
- [segment-dittofeed-mirror](investigations/segment-dittofeed-mirror.md) — Mirroring active CDP segments into Dittofeed as Manual segments so they appear in the journey builder's "Wait For" dropdown; identifier contract and dittofeed-lite compute-workflow caveat.

## References

_(none yet)_
