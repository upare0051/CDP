"""API routes for controlled write-back jobs."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...db import get_db
from ...schemas.writeback import (
    WritebackApplyResponse,
    WritebackJobCreate,
    WritebackJobResponse,
    WritebackJobUpdate,
    WritebackPreviewResponse,
    WritebackRunResponse,
)
from ...services.writeback_service import WritebackService

router = APIRouter(prefix="/writeback", tags=["writeback"])


@router.get("/jobs", response_model=list[WritebackJobResponse])
def list_jobs(db: Session = Depends(get_db)):
    service = WritebackService(db)
    jobs = service.list_jobs()
    return [WritebackJobResponse.model_validate(j) for j in jobs]


@router.post("/jobs", response_model=WritebackJobResponse)
def create_job(data: WritebackJobCreate, db: Session = Depends(get_db)):
    service = WritebackService(db)
    try:
        job = service.create_job(data)
        return WritebackJobResponse.model_validate(job)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/jobs/{job_id}", response_model=WritebackJobResponse)
def get_job(job_id: int, db: Session = Depends(get_db)):
    service = WritebackService(db)
    job = service.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Writeback job not found")
    return WritebackJobResponse.model_validate(job)


@router.patch("/jobs/{job_id}", response_model=WritebackJobResponse)
def update_job(job_id: int, data: WritebackJobUpdate, db: Session = Depends(get_db)):
    service = WritebackService(db)
    try:
        job = service.update_job(job_id, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not job:
        raise HTTPException(status_code=404, detail="Writeback job not found")
    return WritebackJobResponse.model_validate(job)


@router.post("/jobs/{job_id}/preview", response_model=WritebackPreviewResponse)
def preview_job(
    job_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = WritebackService(db)
    try:
        run, sample = service.preview_job(job_id=job_id, limit=limit)
        job = service.get_job(job_id)
        return WritebackPreviewResponse(
            total_candidates=run.total_candidates,
            sample_rows=sample,
            attribute_name=job.attribute_name if job else "",
            attribute_type=job.attribute_type if job else "string",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/jobs/{job_id}/apply", response_model=WritebackApplyResponse)
def apply_job(job_id: int, db: Session = Depends(get_db)):
    service = WritebackService(db)
    try:
        run = service.apply_job(job_id=job_id)
        return WritebackApplyResponse(
            run_id=run.id,
            status=run.status,
            total_candidates=run.total_candidates,
            total_updates=run.total_updates,
            total_inserts=run.total_inserts,
            total_failed=run.total_failed,
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/jobs/{job_id}/runs", response_model=list[WritebackRunResponse])
def list_runs(
    job_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    service = WritebackService(db)
    if not service.get_job(job_id):
        raise HTTPException(status_code=404, detail="Writeback job not found")
    runs = service.list_runs(job_id=job_id, limit=limit)
    return [WritebackRunResponse.model_validate(r) for r in runs]
