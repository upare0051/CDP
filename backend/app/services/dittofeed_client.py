"""Dittofeed API client.

Centralizes talking to Dittofeed from the backend. Keeps workspaceId and
any auth key server-side so the browser doesn't need them. cdp-main routes
under `/api/v1/journey-builder/*` proxy through this client so the frontend
calls cdp-main, cdp-main calls Dittofeed.

This is Phase 0 of the journey-builder headless rebuild — start with
Deliveries (read-only table) and grow from here.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)
settings = get_settings()


class DittofeedError(Exception):
    """Generic Dittofeed call failure."""


class DittofeedUnavailableError(DittofeedError):
    """Transport-level failure (network, timeout)."""


def _base_url() -> str:
    return (settings.dittofeed_api_url or "http://journeys-lite:3000").rstrip("/")


def _headers() -> Dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if settings.dittofeed_api_key:
        headers["Authorization"] = f"Bearer {settings.dittofeed_api_key}"
    return headers


_cached_workspace_id: Optional[str] = None


def _workspace_id() -> str:
    """Resolve the active Dittofeed workspace ID.

    Order:
      1. settings.dittofeed_workspace_id (explicit env var)
      2. cached lookup from a previous call
      3. live discovery: GET /api/workspaces — pick the first one
         (zero-config for the single-workspace demo setup)
    """
    global _cached_workspace_id
    if settings.dittofeed_workspace_id:
        return settings.dittofeed_workspace_id
    if _cached_workspace_id:
        return _cached_workspace_id
    try:
        url = f"{_base_url()}/api/workspaces"
        with httpx.Client(timeout=10, headers=_headers()) as client:
            resp = client.get(url)
        if resp.is_success:
            data = resp.json()
            workspaces = data.get("workspaces") or data.get("items") or (data if isinstance(data, list) else [])
            if workspaces:
                ws = workspaces[0]
                _cached_workspace_id = ws.get("id") if isinstance(ws, dict) else None
                if _cached_workspace_id:
                    return _cached_workspace_id
    except Exception as e:
        logger.warning("dittofeed workspace auto-discovery failed", error=str(e))
    raise DittofeedError(
        "Could not resolve Dittofeed workspace ID. Set DITTOFEED_WORKSPACE_ID or "
        "ensure GET /api/workspaces returns at least one workspace."
    )


def _request(method: str, path: str, *, params: Optional[Dict[str, Any]] = None,
             json: Optional[Dict[str, Any]] = None, timeout: float = 30.0) -> Any:
    """Issue a single request to Dittofeed. Auto-injects workspaceId."""
    q = dict(params or {})
    q.setdefault("workspaceId", _workspace_id())
    url = f"{_base_url()}{path}"
    try:
        with httpx.Client(timeout=timeout, headers=_headers()) as client:
            resp = client.request(method, url, params=q, json=json)
    except httpx.HTTPError as e:
        raise DittofeedUnavailableError(str(e))

    if not resp.is_success:
        raise DittofeedError(f"{method} {path} -> HTTP {resp.status_code}: {resp.text[:300]}")
    try:
        return resp.json()
    except Exception as e:
        raise DittofeedError(f"non-JSON response from {path}: {e}")


# ---------------------------------------------------------------------------
# Deliveries
# ---------------------------------------------------------------------------


def search_deliveries(
    *,
    limit: int = 50,
    cursor: Optional[str] = None,
    journey_id: Optional[str] = None,
    broadcast_id: Optional[str] = None,
    user_id: Optional[str] = None,
    template_ids: Optional[list[str]] = None,
    channels: Optional[list[str]] = None,
    statuses: Optional[list[str]] = None,
    sort_by: Optional[str] = None,
    sort_direction: Optional[str] = None,
) -> Dict[str, Any]:
    """Return up to `limit` delivery records, optionally filtered.

    Mirrors Dittofeed's `GET /api/deliveries` query surface. Returns the full
    response shape: `{workspaceId, items: [...], cursor?: str, previousCursor?: str}`.
    """
    params: Dict[str, Any] = {"limit": limit}
    if cursor:
        params["cursor"] = cursor
    if journey_id:
        params["journeyId"] = journey_id
    if broadcast_id:
        params["broadcastId"] = broadcast_id
    if user_id:
        params["userId"] = user_id
    if template_ids:
        params["templateIds"] = template_ids
    if channels:
        params["channels"] = channels
    if statuses:
        params["statuses"] = statuses
    if sort_by:
        params["sortBy"] = sort_by
    if sort_direction:
        params["sortDirection"] = sort_direction
    return _request("GET", "/api/deliveries", params=params)


def count_deliveries(**filters: Any) -> Dict[str, Any]:
    """Return `{count: int}` matching the same filters as search_deliveries."""
    return _request("GET", "/api/deliveries/count", params=filters)
