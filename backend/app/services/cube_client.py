"""Cube semantic-layer client.

Single source of truth for talking to Cube from the backend (both the
HTTP proxy route at /api/v1/cube/* and the segment service use this).
Handles Cube's async `Continue wait` poll pattern transparently.
"""

from __future__ import annotations

import time
from typing import Any, Dict, Optional

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class CubeUnavailableError(Exception):
    """Cube API was unreachable."""


class CubeQueryError(Exception):
    """Cube returned an error for the submitted query."""


def _cube_url(path: str) -> str:
    base = (settings.cube_api_url or "http://cube-api:4000").rstrip("/")
    return f"{base}{path}"


def _cube_headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.cube_api_secret:
        headers["Authorization"] = settings.cube_api_secret
    return headers


def cube_meta() -> Dict[str, Any]:
    """Fetch /cubejs-api/v1/meta — the model graph (cubes + views + dims + measures)."""
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.get(_cube_url("/cubejs-api/v1/meta"), headers=_cube_headers())
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        raise CubeUnavailableError(str(e))


def cube_load(query: Dict[str, Any], max_wait_seconds: float = 60.0) -> Dict[str, Any]:
    """Execute a Cube query, polling through `Continue wait`.

    Returns the full Cube response dict (with `data`, `annotation`, etc.).
    Raises `CubeQueryError` on Cube-side error and `CubeUnavailableError`
    on transport/connection failure.
    """
    body = {"query": query}
    deadline = time.time() + max_wait_seconds

    with httpx.Client(timeout=30.0) as client:
        while True:
            try:
                resp = client.post(
                    _cube_url("/cubejs-api/v1/load"),
                    json=body,
                    headers=_cube_headers(),
                )
            except httpx.HTTPError as e:
                raise CubeUnavailableError(str(e))

            try:
                data = resp.json()
            except Exception as e:
                raise CubeQueryError(f"Cube returned non-JSON ({resp.status_code}): {e}")

            if data.get("error") == "Continue wait":
                if time.time() >= deadline:
                    raise CubeQueryError(f"Cube query still building after {max_wait_seconds}s")
                time.sleep(1)
                continue

            if not resp.is_success:
                err = data.get("error") or f"HTTP {resp.status_code}"
                raise CubeQueryError(str(err))

            return data


def cube_sql(query: Dict[str, Any]) -> Dict[str, Any]:
    """Return the SQL Cube would execute for a given query (for debugging)."""
    body = {"query": query}
    try:
        with httpx.Client(timeout=30.0) as client:
            resp = client.post(
                _cube_url("/cubejs-api/v1/sql"),
                json=body,
                headers=_cube_headers(),
            )
            resp.raise_for_status()
            return resp.json()
    except httpx.HTTPError as e:
        raise CubeUnavailableError(str(e))


# ---------------------------------------------------------------------------
# Convenience helpers for the segment / sync paths
# ---------------------------------------------------------------------------


def count_query(query: Dict[str, Any]) -> Optional[int]:
    """Run a Cube query and return the integer count of result rows.

    If the query already aggregates (measures only, single result row),
    returns the value of the first measure.
    """
    result = cube_load(query)
    rows = result.get("data", []) or []
    if not rows:
        return 0
    # If the query has measures and dimensions, count rows. If it's a single
    # aggregate (one row, one measure), return that value as the count.
    if len(rows) == 1 and len(query.get("measures") or []) == 1 and not query.get("dimensions"):
        first_measure = query["measures"][0]
        v = rows[0].get(first_measure)
        try:
            return int(float(v)) if v is not None else 0
        except (TypeError, ValueError):
            return None
    return len(rows)
