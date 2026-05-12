"""Dittofeed destination adapter.

Pushes audience members into Dittofeed via its public Segment-style API
(`/api/public/apps/identify` and `/api/public/apps/batch`). Once customers
land in Dittofeed, marketers build the multi-step journey UI inside
cdp-main's `/dashboard/journeys` route (served by Dittofeed via the
nginx reverse proxy — see `journeys/nginx.conf`).

Auth is via Dittofeed write key in the `Authorization` header. The write
key is bound to a workspace; create one in the Dittofeed UI under
Settings → API Keys, then store it as the destination's `api_key`.

Mock mode: api_key prefixed with mock-/test-/demo-/local- short-circuits
all HTTP and reports success. Mirrors the BrazeAdapter pattern.
"""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional

import httpx

from .base import (
    DestinationAdapter,
    DestinationAdapterFactory,
    DestinationConfig,
    FieldMapping,
    SyncResult,
)
from ...core.logging import get_logger

logger = get_logger(__name__)


class DittofeedAdapter(DestinationAdapter):
    """Dittofeed destination — push audience customers + optional events."""

    DEFAULT_BASE_URL = "http://cdp-proxy:80"  # nginx-fronted same-origin call
    DEFAULT_EVENT_NAME = "audience_synced"

    def __init__(self, config: DestinationConfig):
        super().__init__(config)
        self.base_url = (config.api_endpoint or self.DEFAULT_BASE_URL).rstrip("/")
        self.batch_size = min(config.batch_size or 100, 200)

        api_key_lower = (config.api_key or "").strip().lower()
        self.mock_mode = (
            api_key_lower in ("mock", "test", "demo", "local")
            or api_key_lower.startswith(("mock-", "test-", "demo-", "local-"))
        )

        extras = (config.extra_config or {}) or {}
        # Optional per-destination event name emitted alongside the identify.
        # Skip event emission entirely with extras["emit_event"] = False.
        self.event_name: Optional[str] = extras.get("event_name", self.DEFAULT_EVENT_NAME)
        self.emit_event: bool = extras.get("emit_event", True)

    # ----------------------------------------------------------------------
    # Connection probe
    # ----------------------------------------------------------------------
    def test_connection(self) -> tuple[bool, str]:
        if self.mock_mode:
            return True, "Connected to Dittofeed (MOCK MODE)"
        try:
            with httpx.Client(timeout=15) as client:
                # `identify` with an empty payload triggers a 400 if reachable
                # and writeKey is recognized; a 401/403 if the key is wrong;
                # an error otherwise.
                resp = client.post(
                    f"{self.base_url}/api/public/apps/identify",
                    headers=self._headers(),
                    json={},
                )
            if resp.status_code in (200, 400):
                return True, f"Connected to Dittofeed at {self.base_url}"
            return False, f"HTTP {resp.status_code}: {resp.text[:200]}"
        except httpx.HTTPError as e:
            return False, f"Connection failed: {e}"

    # ----------------------------------------------------------------------
    # Payload builder
    # ----------------------------------------------------------------------
    def build_payload(
        self,
        records: List[Dict[str, Any]],
        field_mappings: List[FieldMapping],
        sync_key: str,
    ) -> Dict[str, Any]:
        """Build a Dittofeed `/batch` payload.

        Each audience row produces an `identify` operation (sets traits) and,
        optionally, a `track` operation (event that can trigger journeys).
        Dittofeed accepts both in one batch under `batch:[...]`.
        """
        items: List[Dict[str, Any]] = []
        for rec in records:
            mapped = self.apply_field_mapping(rec, field_mappings)
            sync_value = self.get_sync_key_value(rec, field_mappings, sync_key)
            if sync_value is None:
                continue

            # Dittofeed expects userId to be the canonical identifier.
            user_id = str(sync_value)
            traits = {k: v for k, v in mapped.items() if v is not None}

            items.append({
                "type": "identify",
                "userId": user_id,
                "traits": traits,
            })

            if self.emit_event and self.event_name:
                items.append({
                    "type": "track",
                    "userId": user_id,
                    "event": self.event_name,
                    "properties": traits,
                })

        return {"batch": items}

    # ----------------------------------------------------------------------
    # HTTP send
    # ----------------------------------------------------------------------
    def send_batch(self, payload: Dict[str, Any]) -> SyncResult:
        items = payload.get("batch", []) or []
        # Distinct users count (identify ops) — record-level success metric.
        identify_items = [i for i in items if i.get("type") == "identify"]
        sent_target = len(identify_items)

        if self.mock_mode:
            logger.info("dittofeed mock send", users=sent_target, events=len(items) - sent_target)
            return SyncResult(
                success=True,
                records_sent=sent_target,
                response_data={
                    "mocked": True,
                    "users": sent_target,
                    "events": len(items) - sent_target,
                },
            )

        if not items:
            return SyncResult(success=True, records_sent=0)

        try:
            with httpx.Client(timeout=60, headers=self._headers()) as client:
                resp = client.post(
                    f"{self.base_url}/api/public/apps/batch",
                    json=payload,
                )
        except httpx.HTTPError as e:
            return SyncResult(
                success=False,
                records_sent=0,
                records_failed=sent_target,
                errors=[{"phase": "transport", "error": str(e)}],
            )

        if not resp.is_success:
            return SyncResult(
                success=False,
                records_sent=0,
                records_failed=sent_target,
                errors=[{
                    "phase": "batch",
                    "status": resp.status_code,
                    "body": resp.text[:500],
                }],
            )
        return SyncResult(success=True, records_sent=sent_target)

    # ----------------------------------------------------------------------
    # Helpers
    # ----------------------------------------------------------------------
    def _headers(self) -> Dict[str, str]:
        return {
            "Authorization": self.config.api_key,
            "Content-Type": "application/json",
        }


DestinationAdapterFactory.register("dittofeed", DittofeedAdapter)
