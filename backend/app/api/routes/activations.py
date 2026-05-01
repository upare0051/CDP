"""
API routes for segment activation management.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, Response
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
import io

from ...db import get_db
from ...schemas.activation import (
    ActivationCreate, ActivationUpdate, ActivationResponse, ActivationListResponse,
    ActivationRunResponse, TriggerActivationResponse, ExportRequest, ExportResponse,
    DashboardStats
)
from ...services.activation_service import ActivationService, ExportService, DashboardService
from ...core.logging import get_logger

router = APIRouter(prefix="/activations", tags=["activations"])
logger = get_logger(__name__)


# ============================================================================
# Dashboard
# ============================================================================

@router.get("/dashboard", response_model=DashboardStats)
def get_dashboard_stats(db: Session = Depends(get_db)):
    """
    Get comprehensive dashboard statistics including:
    - Customer counts and trends
    - Segment metrics
    - Activation status
    - Recent activity
    """
    service = DashboardService(db)
    return service.get_dashboard_stats()


# ============================================================================
# Activations CRUD
# ============================================================================

@router.get("", response_model=ActivationListResponse)
def list_activations(
    segment_id: Optional[int] = Query(default=None),
    destination_id: Optional[int] = Query(default=None),
    status: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    List all activations with optional filtering.
    """
    service = ActivationService(db)
    activations, total = service.list_activations(
        segment_id=segment_id,
        destination_id=destination_id,
        status=status,
    )
    
    return ActivationListResponse(
        items=[service.to_response(a) for a in activations],
        total=total,
    )


@router.post("", response_model=ActivationResponse)
def create_activation(
    data: ActivationCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new segment activation.
    Links a segment to a destination for syncing.
    """
    service = ActivationService(db)
    try:
        activation = service.create_activation(data)
        return service.to_response(activation)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{activation_id}", response_model=ActivationResponse)
def get_activation(
    activation_id: int,
    db: Session = Depends(get_db),
):
    """
    Get an activation by ID.
    """
    service = ActivationService(db)
    activation = service.get_activation(activation_id)
    
    if not activation:
        raise HTTPException(status_code=404, detail="Activation not found")
    
    return service.to_response(activation)


@router.patch("/{activation_id}", response_model=ActivationResponse)
def update_activation(
    activation_id: int,
    data: ActivationUpdate,
    db: Session = Depends(get_db),
):
    """
    Update an activation.
    """
    service = ActivationService(db)
    activation = service.update_activation(activation_id, data)
    
    if not activation:
        raise HTTPException(status_code=404, detail="Activation not found")
    
    return service.to_response(activation)


@router.delete("/{activation_id}")
def delete_activation(
    activation_id: int,
    db: Session = Depends(get_db),
):
    """
    Delete an activation.
    """
    service = ActivationService(db)
    success = service.delete_activation(activation_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Activation not found")
    
    return {"message": "Activation deleted successfully"}


# ============================================================================
# Activation Runs
# ============================================================================

@router.post("/{activation_id}/trigger", response_model=TriggerActivationResponse)
def trigger_activation(
    activation_id: int,
    db: Session = Depends(get_db),
):
    """
    Trigger a sync run for an activation.
    Syncs current segment members to the destination.
    """
    service = ActivationService(db)
    
    try:
        run = service.trigger_activation(activation_id)
        return TriggerActivationResponse(
            run_id=run.run_id,
            status=run.status,
            message=f"Synced {run.synced_count} customers to destination",
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{activation_id}/runs", response_model=list[ActivationRunResponse])
def get_activation_runs(
    activation_id: int,
    limit: int = Query(default=10, le=50),
    db: Session = Depends(get_db),
):
    """
    Get recent runs for an activation.
    """
    service = ActivationService(db)
    
    # Verify activation exists
    if not service.get_activation(activation_id):
        raise HTTPException(status_code=404, detail="Activation not found")
    
    runs = service.get_activation_runs(activation_id, limit)
    return [ActivationRunResponse.model_validate(r) for r in runs]


@router.post("/{activation_id}/pause", response_model=ActivationResponse)
def pause_activation(
    activation_id: int,
    db: Session = Depends(get_db),
):
    """
    Pause an activation (stop scheduled syncs).
    """
    service = ActivationService(db)
    activation = service.update_activation(activation_id, ActivationUpdate(status="paused"))
    
    if not activation:
        raise HTTPException(status_code=404, detail="Activation not found")
    
    return service.to_response(activation)


@router.post("/{activation_id}/resume", response_model=ActivationResponse)
def resume_activation(
    activation_id: int,
    db: Session = Depends(get_db),
):
    """
    Resume a paused activation.
    """
    service = ActivationService(db)
    activation = service.update_activation(activation_id, ActivationUpdate(status="active"))
    
    if not activation:
        raise HTTPException(status_code=404, detail="Activation not found")
    
    return service.to_response(activation)


# ============================================================================
# Segment Export
# ============================================================================

@router.post("/segments/{segment_id}/export")
def export_segment(
    segment_id: int,
    request: ExportRequest = ExportRequest(),
    db: Session = Depends(get_db),
):
    """
    Export segment customers to CSV.
    Returns a downloadable CSV file.
    """
    service = ExportService(db)
    
    try:
        filename, csv_bytes, row_count = service.export_segment_to_csv(segment_id, request)
        
        return StreamingResponse(
            io.BytesIO(csv_bytes),
            media_type="text/csv",
            headers={
                "Content-Disposition": f"attachment; filename={filename}",
                "X-Row-Count": str(row_count),
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/segments/{segment_id}/exports", response_model=list[ExportResponse])
def get_segment_exports(
    segment_id: int,
    limit: int = Query(default=10, le=50),
    db: Session = Depends(get_db),
):
    """
    Get recent exports for a segment.
    """
    service = ExportService(db)
    exports = service.get_segment_exports(segment_id, limit)
    return [ExportResponse.model_validate(e) for e in exports]
