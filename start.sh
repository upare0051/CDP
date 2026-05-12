#!/usr/bin/env bash
# Start the full local CDP stack: app + warehouse + Cube + Journeys + unified proxy.
# Requires Docker Compose v2 (`docker compose`).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

COMPOSE_FILES=(
  -f docker-compose.yml
  -f cube/docker-compose.cube.yml
  -f journeys/docker-compose.journeys.yml
)

if ! docker compose version >/dev/null 2>&1; then
  echo "error: 'docker compose' not found. Install Docker Desktop or Docker Compose v2." >&2
  exit 1
fi

if [[ ! -f cube/.env ]]; then
  echo "cube/.env missing — copying from cube/.env.example"
  cp cube/.env.example cube/.env
fi

echo "Starting stack from $ROOT ..."
docker compose "${COMPOSE_FILES[@]}" up -d --build

echo
echo "Unified UI (nginx):  http://localhost/"
echo "Direct frontend:     http://localhost:5173"
echo "Direct backend API:  http://localhost:8000  (docs: /api/docs)"
echo "Cube playground:     http://localhost:4001"
echo "MinIO console:       http://localhost:9001"
echo
echo "Other host ports: postgres 5432, warehouse postgres 5433, redis 6379,"
echo "  MinIO API 9000, journeys postgres 25432, ClickHouse 8125, Temporal 27233."
echo
echo "Note: cube/docker-compose.cube.yml uses cubejs/cubestore:arm64v8 for Apple Silicon."
echo "      On x86_64 Linux/Intel Mac, edit that image to cubejs/cubestore:latest if pull fails."
