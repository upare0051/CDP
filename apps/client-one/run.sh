#!/usr/bin/env bash
# Start Client One Flask app.
# Usage: ./run.sh [port]
#
# Environment variables:
#   BACKEND_URL  - ActivationOS backend (default: http://localhost:8000)
#   PORT         - Port to listen on (default: 5050)

set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

PORT="${1:-${PORT:-5050}}"
export BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"

if [ ! -d ".venv" ]; then
  echo "Creating virtual environment…"
  python3 -m venv .venv
  .venv/bin/pip install -q flask requests
fi

echo "Starting Client One on http://localhost:$PORT"
echo "  Backend: $BACKEND_URL"
PORT="$PORT" .venv/bin/python app.py
