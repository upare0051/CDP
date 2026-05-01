"""Sync job API routes."""

from typing import List
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from ...db import get_db
from ...schemas.sync import (
    SyncJobCreate, SyncJobUpdate, SyncJobResponse, SyncJobSummary,
    FieldMappingCreate, FieldMappingResponse, TriggerRunRequest, TriggerRunResponse,
    SchemaChangeInfo,
)
from ...models.sync import SyncStatus
from ...services.sync_service import SyncService
from ...services.sync_engine import SyncEngine
from ...core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/syncs", tags=["syncs"])


@router.get("", response_model=List[SyncJobSummary])
def list_syncs(
    db: Session = Depends(get_db),
):
    """List all sync jobs with summaries."""
    service = SyncService(db)
    return service.get_sync_job_summaries()


@router.post("", response_model=SyncJobResponse, status_code=201)
def create_sync(
    data: SyncJobCreate,
    db: Session = Depends(get_db),
):
    """Create a new sync job."""
    service = SyncService(db)
    
    # Check for duplicate name
    existing = service.get_sync_job_by_name(data.name)
    if existing:
        raise HTTPException(status_code=400, detail=f"Sync job '{data.name}' already exists")
    
    try:
        job = service.create_sync_job(data)
        return _build_job_response(job, service)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{job_id}", response_model=SyncJobResponse)
def get_sync(
    job_id: int,
    db: Session = Depends(get_db),
):
    """Get a sync job by ID."""
    service = SyncService(db)
    job = service.get_sync_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Sync job not found")
    
    return _build_job_response(job, service)


@router.put("/{job_id}", response_model=SyncJobResponse)
def update_sync(
    job_id: int,
    data: SyncJobUpdate,
    db: Session = Depends(get_db),
):
    """Update a sync job."""
    service = SyncService(db)
    job = service.update_sync_job(job_id, data)
    if not job:
        raise HTTPException(status_code=404, detail="Sync job not found")
    return _build_job_response(job, service)


@router.delete("/{job_id}")
def delete_sync(
    job_id: int,
    db: Session = Depends(get_db),
):
    """Delete a sync job."""
    service = SyncService(db)
    if not service.delete_sync_job(job_id):
        raise HTTPException(status_code=404, detail="Sync job not found")
    return {"message": "Sync job deleted"}


@router.put("/{job_id}/mappings", response_model=List[FieldMappingResponse])
def update_mappings(
    job_id: int,
    mappings: List[FieldMappingCreate],
    db: Session = Depends(get_db),
):
    """Update field mappings for a sync job."""
    service = SyncService(db)
    
    try:
        job = service.update_field_mappings(job_id, mappings)
        return [FieldMappingResponse.model_validate(m) for m in job.field_mappings]
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{job_id}/trigger", response_model=TriggerRunResponse)
def trigger_sync(
    job_id: int,
    force_full_refresh: bool = False,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """Trigger a sync job execution."""
    service = SyncService(db)
    engine = SyncEngine(db)
    
    job = service.get_sync_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Sync job not found")
    
    if not job.is_active:
        raise HTTPException(status_code=400, detail="Sync job is not active")
    
    if job.is_paused:
        raise HTTPException(status_code=400, detail="Sync job is paused")
    
    # Check for already running sync
    running = service.get_running_runs()
    if any(r.sync_job_id == job_id for r in running):
        raise HTTPException(status_code=409, detail="Sync job is already running")
    
    # Create and start run
    run = service.create_sync_run(job_id)
    
    # Execute sync (in foreground for now, can use background_tasks for async)
    try:
        run = engine.execute_sync(job_id, force_full_refresh=force_full_refresh)
        return TriggerRunResponse(
            run_id=run.run_id,
            status=run.status,
            message=f"Sync completed with status: {run.status.value}",
        )
    except Exception as e:
        return TriggerRunResponse(
            run_id=run.run_id,
            status=SyncStatus.FAILED,
            message=f"Sync failed: {str(e)}",
        )


@router.post("/{job_id}/pause")
def pause_sync(
    job_id: int,
    db: Session = Depends(get_db),
):
    """Pause a sync job."""
    service = SyncService(db)
    from ...schemas.sync import SyncJobUpdate
    
    job = service.update_sync_job(job_id, SyncJobUpdate(is_paused=True))
    if not job:
        raise HTTPException(status_code=404, detail="Sync job not found")
    
    return {"message": "Sync job paused"}


@router.post("/{job_id}/resume")
def resume_sync(
    job_id: int,
    db: Session = Depends(get_db),
):
    """Resume a paused sync job."""
    service = SyncService(db)
    from ...schemas.sync import SyncJobUpdate
    
    job = service.update_sync_job(job_id, SyncJobUpdate(is_paused=False))
    if not job:
        raise HTTPException(status_code=404, detail="Sync job not found")
    
    return {"message": "Sync job resumed"}


@router.get("/{job_id}/schema-changes", response_model=SchemaChangeInfo)
def check_schema_changes(
    job_id: int,
    db: Session = Depends(get_db),
):
    """Check for schema changes in the source table."""
    engine = SyncEngine(db)
    
    try:
        result = engine.check_schema_changes(job_id)
        return SchemaChangeInfo(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to check schema: {str(e)}")


def _build_job_response(job, service: SyncService) -> SyncJobResponse:
    """Build job response with computed fields."""
    last_run = service.get_latest_run(job.id)
    
    response = SyncJobResponse.model_validate(job)
    response.source_connection_name = job.source_connection.name
    response.destination_connection_name = job.destination_connection.name
    response.last_run_status = last_run.status if last_run else None
    response.last_run_at = last_run.started_at if last_run else None
    
    return response
