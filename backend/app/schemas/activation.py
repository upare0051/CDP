"""
Pydantic schemas for Segment Activation API.
"""
from datetime import datetime
from typing import List, Optional, Any, Dict, Literal
from pydantic import BaseModel, Field


class FieldMappingItem(BaseModel):
    """Maps a customer/segment field to a destination field."""
    source_field: str
    destination_field: str
    transform: Optional[str] = None  # Optional transformation


class ActivationCreate(BaseModel):
    """Schema for creating an activation."""
    segment_id: int
    destination_id: int
    name: Optional[str] = None
    frequency: Literal["manual", "hourly", "daily", "weekly"] = "manual"
    field_mappings: List[FieldMappingItem] = []


class ActivationUpdate(BaseModel):
    """Schema for updating an activation."""
    name: Optional[str] = None
    frequency: Optional[Literal["manual", "hourly", "daily", "weekly"]] = None
    status: Optional[Literal["pending", "active", "paused"]] = None
    field_mappings: Optional[List[FieldMappingItem]] = None


class ActivationResponse(BaseModel):
    """Schema for activation response."""
    id: int
    segment_id: int
    destination_id: int
    name: Optional[str] = None
    frequency: str
    status: str
    field_mappings: List[Dict[str, Any]]
    last_sync_at: Optional[datetime] = None
    last_sync_count: Optional[int] = None
    total_synced: int
    created_at: datetime
    updated_at: datetime
    
    # Include related entity names
    segment_name: Optional[str] = None
    destination_name: Optional[str] = None
    destination_type: Optional[str] = None

    class Config:
        from_attributes = True


class ActivationListResponse(BaseModel):
    """Schema for listing activations."""
    items: List[ActivationResponse]
    total: int


class ActivationRunResponse(BaseModel):
    """Schema for activation run response."""
    id: int
    run_id: str
    activation_id: int
    status: str
    total_customers: int
    synced_count: int
    failed_count: int
    skipped_count: int
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class TriggerActivationResponse(BaseModel):
    """Response when triggering an activation run."""
    run_id: str
    status: str
    message: str


class ExportRequest(BaseModel):
    """Request to export segment to CSV."""
    included_fields: List[str] = []  # Empty means all fields
    include_attributes: bool = True


class ExportResponse(BaseModel):
    """Response for segment export."""
    id: int
    segment_id: int
    file_name: str
    file_path: Optional[str] = None
    file_size: Optional[int] = None
    row_count: int
    download_url: Optional[str] = None
    created_at: datetime
    expires_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DashboardStats(BaseModel):
    """Dashboard statistics."""
    total_customers: int
    total_segments: int
    active_segments: int
    total_activations: int
    active_activations: int
    
    # Recent activity
    customers_added_today: int
    customers_added_week: int
    segments_created_week: int
    syncs_today: int
    
    # Top segments by size
    top_segments: List[Dict[str, Any]]
    
    # Recent syncs
    recent_activations: List[Dict[str, Any]]


class SegmentTrend(BaseModel):
    """Segment size trend over time."""
    date: str
    count: int


class SegmentMetrics(BaseModel):
    """Detailed metrics for a segment."""
    segment_id: int
    segment_name: str
    current_count: int
    count_change_day: int
    count_change_week: int
    count_change_pct: float
    trends: List[SegmentTrend]
    activation_count: int
    last_activated: Optional[datetime] = None
