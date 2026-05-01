"""Pydantic schemas for sync jobs and runs."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator

from ..models.sync import SyncMode, SyncStatus, ScheduleType


# Field Mapping Schemas
class FieldMappingBase(BaseModel):
    """Base schema for field mapping."""
    source_field: str = Field(..., min_length=1, max_length=255)
    source_field_type: Optional[str] = None
    destination_field: str = Field(..., min_length=1, max_length=255)
    transformation: Optional[str] = None
    is_sync_key: bool = False
    is_required: bool = False


class FieldMappingCreate(FieldMappingBase):
    """Schema for creating field mapping."""
    pass


class FieldMappingResponse(FieldMappingBase):
    """Schema for field mapping response."""
    id: int
    sync_job_id: int
    created_at: datetime
    
    class Config:
        from_attributes = True


# Sync Job Schemas
class SyncJobBase(BaseModel):
    """Base schema for sync job."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    source_schema: str = Field(..., min_length=1, max_length=255)
    source_table: str = Field(..., min_length=1, max_length=255)
    source_query: Optional[str] = None
    sync_mode: SyncMode = SyncMode.FULL_REFRESH
    sync_key: str = Field(..., min_length=1, max_length=255)
    incremental_column: Optional[str] = None
    schedule_type: ScheduleType = ScheduleType.MANUAL
    cron_expression: Optional[str] = None
    
    @field_validator("cron_expression")
    @classmethod
    def validate_cron(cls, v, info):
        if info.data.get("schedule_type") == ScheduleType.CRON and not v:
            raise ValueError("cron_expression is required when schedule_type is CRON")
        return v
    
    @field_validator("incremental_column")
    @classmethod
    def validate_incremental(cls, v, info):
        if info.data.get("sync_mode") == SyncMode.INCREMENTAL and not v:
            raise ValueError("incremental_column is required for incremental sync")
        return v


class SyncJobCreate(SyncJobBase):
    """Schema for creating sync job."""
    source_connection_id: int
    destination_connection_id: int
    field_mappings: List[FieldMappingCreate] = []


class SyncJobUpdate(BaseModel):
    """Schema for updating sync job."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    source_schema: Optional[str] = None
    source_table: Optional[str] = None
    source_query: Optional[str] = None
    sync_mode: Optional[SyncMode] = None
    sync_key: Optional[str] = None
    incremental_column: Optional[str] = None
    schedule_type: Optional[ScheduleType] = None
    cron_expression: Optional[str] = None
    is_active: Optional[bool] = None
    is_paused: Optional[bool] = None


class SyncJobResponse(SyncJobBase):
    """Schema for sync job response."""
    id: int
    source_connection_id: int
    destination_connection_id: int
    is_active: bool
    is_paused: bool
    last_checkpoint_value: Optional[str] = None
    source_schema_hash: Optional[str] = None
    last_schema_check_at: Optional[datetime] = None
    airflow_dag_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    field_mappings: List[FieldMappingResponse] = []
    
    # Computed fields
    source_connection_name: Optional[str] = None
    destination_connection_name: Optional[str] = None
    last_run_status: Optional[SyncStatus] = None
    last_run_at: Optional[datetime] = None
    
    class Config:
        from_attributes = True


class SyncJobSummary(BaseModel):
    """Summary schema for sync job list."""
    id: int
    name: str
    source_connection_name: str
    destination_connection_name: str
    sync_mode: SyncMode
    schedule_type: ScheduleType
    is_active: bool
    is_paused: bool
    last_run_status: Optional[SyncStatus] = None
    last_run_at: Optional[datetime] = None
    total_rows_synced: int = 0


# Sync Run Schemas
class SyncRunCreate(BaseModel):
    """Schema for creating sync run."""
    sync_job_id: int
    airflow_run_id: Optional[str] = None


class SyncRunResponse(BaseModel):
    """Schema for sync run response."""
    id: int
    sync_job_id: int
    run_id: str
    airflow_run_id: Optional[str] = None
    status: SyncStatus
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    rows_read: int
    rows_synced: int
    rows_failed: int
    rows_skipped: int
    checkpoint_value: Optional[str] = None
    new_checkpoint_value: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int
    created_at: datetime
    updated_at: datetime
    
    # Computed
    sync_job_name: Optional[str] = None
    
    class Config:
        from_attributes = True


class SyncRunDetail(SyncRunResponse):
    """Detailed sync run with logs."""
    logs: Optional[str] = None
    error_details: Optional[Dict[str, Any]] = None


# Trigger Run
class TriggerRunRequest(BaseModel):
    """Request to trigger a sync run."""
    sync_job_id: int
    force_full_refresh: bool = False


class TriggerRunResponse(BaseModel):
    """Response for triggered run."""
    run_id: str
    status: SyncStatus
    message: str


# Schema Change Detection
class SchemaChangeInfo(BaseModel):
    """Schema change detection result."""
    has_changes: bool
    added_columns: List[str] = []
    removed_columns: List[str] = []
    modified_columns: List[str] = []
    current_hash: str
    previous_hash: Optional[str] = None
