"""Sync run API routes."""

from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...db import get_db
from ...schemas.sync import SyncRunResponse, SyncRunDetail
from ...services.sync_service import SyncService
from ...core.logging import get_logger

logger = get_logger(__name__)
router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=List[SyncRunResponse])
def list_runs(
    job_id: Optional[int] = Query(None, description="Filter by sync job ID"),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    """List sync runs."""
    service = SyncService(db)
    runs = service.list_sync_runs(job_id=job_id, limit=limit)
    
    results = []
    for run in runs:
        response = SyncRunResponse.model_validate(run)
        response.sync_job_name = run.sync_job.name
        results.append(response)
    
    return results


@router.get("/{run_id}", response_model=SyncRunDetail)
def get_run(
    run_id: str,
    db: Session = Depends(get_db),
):
    """Get a sync run by ID."""
    service = SyncService(db)
    run = service.get_sync_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Sync run not found")
    
    response = SyncRunDetail.model_validate(run)
    response.sync_job_name = run.sync_job.name
    return response


@router.get("/job/{job_id}/latest", response_model=SyncRunResponse)
def get_latest_run(
    job_id: int,
    db: Session = Depends(get_db),
):
    """Get the latest run for a job."""
    service = SyncService(db)
    run = service.get_latest_run(job_id)
    if not run:
        raise HTTPException(status_code=404, detail="No runs found for this job")
    
    response = SyncRunResponse.model_validate(run)
    response.sync_job_name = run.sync_job.name
    return response


@router.get("/stats/summary")
def get_run_stats(
    db: Session = Depends(get_db),
):
    """Get run statistics summary."""
    service = SyncService(db)
    
    all_runs = service.list_sync_runs(limit=1000)
    
    from collections import Counter
    from datetime import datetime, timedelta
    
    status_counts = Counter(run.status.value for run in all_runs)
    
    # Last 24 hours
    yesterday = datetime.utcnow() - timedelta(days=1)
    recent_runs = [r for r in all_runs if r.created_at and r.created_at > yesterday]
    
    total_rows_synced = sum(r.rows_synced for r in all_runs)
    total_rows_failed = sum(r.rows_failed for r in all_runs)
    
    return {
        "total_runs": len(all_runs),
        "runs_last_24h": len(recent_runs),
        "status_breakdown": dict(status_counts),
        "total_rows_synced": total_rows_synced,
        "total_rows_failed": total_rows_failed,
        "success_rate": (
            status_counts.get("completed", 0) / len(all_runs) * 100
            if all_runs else 0
        ),
    }
