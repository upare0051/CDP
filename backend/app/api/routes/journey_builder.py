"""Journey Builder routes — native cdp-main surfaces backed by Dittofeed's API.

Phase 0 of the headless rebuild. cdp-main owns the UI; Dittofeed continues to
run the journey execution engine + ClickHouse delivery log. The frontend hits
these endpoints (not Dittofeed directly), so workspaceId stays server-side and
we have a hook for future governance / RLS.

Surfaces:
  - Deliveries (this commit) — read-only message log
  - Templates  (TBD)         — CRUD on email/SMS templates
  - Broadcasts (TBD)         — one-off audience sends
  - Analytics  (TBD)         — journey & message metrics
  - Journeys   (TBD)         — react-flow canvas
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from app.core.logging import get_logger
from app.services import dittofeed_client

logger = get_logger(__name__)
router = APIRouter(prefix="/journey-builder", tags=["journey-builder"])


@router.get("/deliveries")
def list_deliveries(
    limit: int = Query(default=50, ge=1, le=200),
    cursor: Optional[str] = None,
    journey_id: Optional[str] = Query(default=None, alias="journeyId"),
    broadcast_id: Optional[str] = Query(default=None, alias="broadcastId"),
    user_id: Optional[str] = Query(default=None, alias="userId"),
    template_ids: Optional[List[str]] = Query(default=None, alias="templateIds"),
    channels: Optional[List[str]] = None,
    statuses: Optional[List[str]] = None,
    sort_by: Optional[str] = Query(default=None, alias="sortBy"),
    sort_direction: Optional[str] = Query(default=None, alias="sortDirection"),
) -> Dict[str, Any]:
    """List delivered messages with optional filters + cursor pagination."""
    try:
        return dittofeed_client.search_deliveries(
            limit=limit,
            cursor=cursor,
            journey_id=journey_id,
            broadcast_id=broadcast_id,
            user_id=user_id,
            template_ids=template_ids,
            channels=channels,
            statuses=statuses,
            sort_by=sort_by,
            sort_direction=sort_direction,
        )
    except dittofeed_client.DittofeedUnavailableError as e:
        raise HTTPException(status_code=503, detail=f"Dittofeed unavailable: {e}")
    except dittofeed_client.DittofeedError as e:
        raise HTTPException(status_code=502, detail=str(e))


@router.get("/deliveries/count")
def count_deliveries(
    journey_id: Optional[str] = Query(default=None, alias="journeyId"),
    broadcast_id: Optional[str] = Query(default=None, alias="broadcastId"),
    user_id: Optional[str] = Query(default=None, alias="userId"),
    channels: Optional[List[str]] = None,
    statuses: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Total count of deliveries matching the same filter shape."""
    params: Dict[str, Any] = {}
    if journey_id:
        params["journeyId"] = journey_id
    if broadcast_id:
        params["broadcastId"] = broadcast_id
    if user_id:
        params["userId"] = user_id
    if channels:
        params["channels"] = channels
    if statuses:
        params["statuses"] = statuses
    try:
        return dittofeed_client.count_deliveries(**params)
    except dittofeed_client.DittofeedUnavailableError as e:
        raise HTTPException(status_code=503, detail=f"Dittofeed unavailable: {e}")
    except dittofeed_client.DittofeedError as e:
        raise HTTPException(status_code=502, detail=str(e))
