"""Dittofeed API client.

Centralizes talking to Dittofeed from the backend. Keeps workspaceId and
any auth key server-side so the browser doesn't need them. cdp-main routes
under `/api/v1/journey-builder/*` proxy through this client so the frontend
calls cdp-main, cdp-main calls Dittofeed.

This is Phase 0 of the journey-builder headless rebuild — start with
Deliveries (read-only table) and grow from here.
"""

from __future__ import annotations

import re
import time
from typing import Any, Dict, List, Optional

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
_WORKSPACE_ID_RE = re.compile(r'"workspaceId"\s*:\s*"([0-9a-fA-F-]{36})"')


def _extract_workspace_id(payload: str) -> Optional[str]:
    match = _WORKSPACE_ID_RE.search(payload)
    return match.group(1) if match else None


def _workspace_id() -> str:
    """Resolve the active Dittofeed workspace ID.

    Order:
      1. settings.dittofeed_workspace_id (explicit env var)
      2. cached lookup from a previous call
      3. live discovery: GET /api/workspaces — pick the first one
         (zero-config for the single-workspace demo setup)
      4. dashboard payload discovery for Dittofeed lite images that do not
         expose /api/workspaces
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

    try:
        url = f"{_base_url()}/dashboard/journeys"
        with httpx.Client(timeout=10, headers=_headers()) as client:
            resp = client.get(url)
        if resp.is_success:
            _cached_workspace_id = _extract_workspace_id(resp.text)
            if _cached_workspace_id:
                return _cached_workspace_id
    except Exception as e:
        logger.warning("dittofeed dashboard workspace discovery failed", error=str(e))

    raise DittofeedError(
        "Could not resolve Dittofeed workspace ID. Set DITTOFEED_WORKSPACE_ID or "
        "ensure the Dittofeed dashboard is reachable."
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


# ---------------------------------------------------------------------------
# Segments — CDP-side segments are mirrored into Dittofeed as Manual segments
# so they appear in the journey builder's "Wait For" dropdown. Membership is
# pushed separately via `update_manual_segment_members`.
# ---------------------------------------------------------------------------


def upsert_manual_segment(
    name: str,
    *,
    existing_id: Optional[str] = None,
) -> str:
    """Create or update a Manual segment in Dittofeed. Returns its UUID.

    Dittofeed's `PUT /api/segments/` accepts an optional `id` to upsert.
    The Manual entry node's `version` is a monotonic counter we bump on each
    write so Dittofeed treats the definition as updated.
    """
    workspace_id = _workspace_id()
    body: Dict[str, Any] = {
        "workspaceId": workspace_id,
        "name": name,
        "definition": {
            "entryNode": {
                "type": "Manual",
                "version": int(time.time() * 1000),
                "id": "1",
            },
            "nodes": [],
        },
    }
    if existing_id:
        body["id"] = existing_id

    url = f"{_base_url()}/api/segments/"
    try:
        with httpx.Client(timeout=30, headers=_headers()) as client:
            resp = client.put(url, json=body)
    except httpx.HTTPError as e:
        raise DittofeedUnavailableError(str(e))

    if not resp.is_success:
        raise DittofeedError(
            f"PUT /api/segments/ -> HTTP {resp.status_code}: {resp.text[:300]}"
        )
    data = resp.json()
    segment_id = data.get("id")
    if not segment_id:
        raise DittofeedError(f"PUT /api/segments/ returned no id: {data}")
    return segment_id


def delete_segment(dittofeed_segment_id: str) -> None:
    """Delete a segment in Dittofeed. No-op if it's already gone.

    Note: Dittofeed's DELETE /api/segments/ takes a JSON *body* with
    workspaceId and id (not query params).
    """
    workspace_id = _workspace_id()
    url = f"{_base_url()}/api/segments/"
    body = {"workspaceId": workspace_id, "id": dittofeed_segment_id}
    try:
        with httpx.Client(timeout=30, headers=_headers()) as client:
            resp = client.request("DELETE", url, json=body)
    except httpx.HTTPError as e:
        raise DittofeedUnavailableError(str(e))

    if resp.status_code == 404:
        return
    if not resp.is_success:
        raise DittofeedError(
            f"DELETE /api/segments/ -> HTTP {resp.status_code}: {resp.text[:300]}"
        )


def update_manual_segment_members(
    dittofeed_segment_id: str,
    user_ids: List[str],
    *,
    append: bool = True,
) -> None:
    """Push a manual-segment membership update.

    `append=True` adds the listed users; `append=False` removes them. The
    Dittofeed lite stack requires its compute-properties workflow to be
    running on the workspace before this call can succeed — see
    wiki/investigations/segment-dittofeed-mirror.md.
    """
    if not user_ids:
        return
    workspace_id = _workspace_id()
    body = {
        "workspaceId": workspace_id,
        "segmentId": dittofeed_segment_id,
        "userIds": user_ids,
        "append": append,
    }
    url = f"{_base_url()}/api/segments/manual-segment/update"
    try:
        with httpx.Client(timeout=60, headers=_headers()) as client:
            resp = client.post(url, json=body)
    except httpx.HTTPError as e:
        raise DittofeedUnavailableError(str(e))

    if not resp.is_success:
        raise DittofeedError(
            f"POST /api/segments/manual-segment/update -> HTTP {resp.status_code}: {resp.text[:300]}"
        )
