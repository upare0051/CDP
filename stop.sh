#!/usr/bin/env bash
# Stop and remove containers for the full local CDP stack (same compose files as start.sh).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

COMPOSE_FILES=(
  -f docker-compose.yml
  -f cube/docker-compose.cube.yml
  -f journeys/docker-compose.journeys.yml
)

if ! docker compose version >/dev/null 2>&1; then
  echo "error: 'docker compose' not found." >&2
  exit 1
fi

echo "Stopping stack from $ROOT ..."
docker compose "${COMPOSE_FILES[@]}" down

echo "Done."
