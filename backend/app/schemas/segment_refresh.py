"""Schemas for segment warehouse materialization."""

from datetime import datetime
from typing import Literal, Optional
from pydantic import BaseModel


class SegmentRefreshRunResponse(BaseModel):
    """Response shape for a segment refresh run."""

    id: int
    segment_id: int
    run_id: str
    target: str
    status: Literal["running", "succeeded", "failed"]
    trigger: str
    row_count: int
    error_message: Optional[str] = None
    started_at: datetime
    finished_at: Optional[datetime] = None
    created_at: datetime

    class Config:
        from_attributes = True


class SegmentRefreshRunListResponse(BaseModel):
    """List response for segment refresh runs."""

    items: list[SegmentRefreshRunResponse]
