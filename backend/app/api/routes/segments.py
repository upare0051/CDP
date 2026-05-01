"""
API routes for segment management.
"""
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ...db import get_db
from ...models.segment import SEGMENT_FIELDS, OPERATORS_BY_TYPE, SegmentStatus
from ...schemas.segment import (
    SegmentCreate, SegmentUpdate, SegmentResponse, SegmentListResponse,
    SegmentPreviewRequest, SegmentPreviewResponse, SegmentSchemaResponse,
    FilterConfig,
    SegmentFieldInfo, SegmentOperatorInfo
)
from ...services.segment_service import SegmentService
from ...core.logging import get_logger

router = APIRouter(prefix="/segments", tags=["segments"])
logger = get_logger(__name__)


@router.get("/schema", response_model=SegmentSchemaResponse)
def get_segment_schema():
    """
    Get the schema for building segment filters.
    Returns available fields and operators.
    """
    fields = [SegmentFieldInfo(**f) for f in SEGMENT_FIELDS]
    operators = {
        k: [SegmentOperatorInfo(**op) for op in v]
        for k, v in OPERATORS_BY_TYPE.items()
    }
    
    return SegmentSchemaResponse(
        fields=fields,
        operators_by_type=operators,
    )


@router.get("", response_model=SegmentListResponse)
def list_segments(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    status: Optional[str] = Query(default=None),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    List all segments with pagination and filtering.
    """
    service = SegmentService(db)
    segments, total = service.list_segments(
        page=page,
        page_size=page_size,
        status=status,
        search=search,
    )
    
    return SegmentListResponse(
        items=[SegmentResponse.model_validate(s) for s in segments],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.post("", response_model=SegmentResponse)
def create_segment(
    data: SegmentCreate,
    db: Session = Depends(get_db),
):
    """
    Create a new segment.
    """
    service = SegmentService(db)
    segment = service.create_segment(data)
    return SegmentResponse.model_validate(segment)


@router.get("/{segment_id}", response_model=SegmentResponse)
def get_segment(
    segment_id: int,
    db: Session = Depends(get_db),
):
    """
    Get a segment by ID.
    """
    service = SegmentService(db)
    segment = service.get_segment(segment_id)
    
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    
    return SegmentResponse.model_validate(segment)


@router.patch("/{segment_id}", response_model=SegmentResponse)
def update_segment(
    segment_id: int,
    data: SegmentUpdate,
    db: Session = Depends(get_db),
):
    """
    Update an existing segment.
    """
    service = SegmentService(db)
    segment = service.update_segment(segment_id, data)
    
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    
    return SegmentResponse.model_validate(segment)


@router.delete("/{segment_id}")
def delete_segment(
    segment_id: int,
    db: Session = Depends(get_db),
):
    """
    Delete a segment.
    """
    service = SegmentService(db)
    success = service.delete_segment(segment_id)
    
    if not success:
        raise HTTPException(status_code=404, detail="Segment not found")
    
    return {"message": "Segment deleted successfully"}


@router.post("/preview", response_model=SegmentPreviewResponse)
def preview_segment(
    data: SegmentPreviewRequest,
    db: Session = Depends(get_db),
):
    """
    Preview segment results without saving.
    Returns count and sample customers.
    """
    service = SegmentService(db)
    result = service.preview_segment(data.filter_config)
    return result


@router.post("/{segment_id}/refresh-count", response_model=SegmentResponse)
def refresh_segment_count(
    segment_id: int,
    db: Session = Depends(get_db),
):
    """
    Refresh the cached count for a segment.
    """
    service = SegmentService(db)
    segment = service.get_segment(segment_id)
    
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    
    # Update count
    service._update_segment_count(segment)
    
    return SegmentResponse.model_validate(segment)


@router.post("/{segment_id}/activate", response_model=SegmentResponse)
def activate_segment(
    segment_id: int,
    db: Session = Depends(get_db),
):
    """
    Activate a segment (make it available for syncs).
    """
    service = SegmentService(db)
    segment = service.activate_segment(segment_id)
    
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    
    return SegmentResponse.model_validate(segment)


@router.post("/{segment_id}/archive", response_model=SegmentResponse)
def archive_segment(
    segment_id: int,
    db: Session = Depends(get_db),
):
    """
    Archive a segment.
    """
    service = SegmentService(db)
    segment = service.archive_segment(segment_id)
    
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    
    return SegmentResponse.model_validate(segment)


@router.post("/{segment_id}/duplicate", response_model=SegmentResponse)
def duplicate_segment(
    segment_id: int,
    new_name: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    """
    Create a copy of an existing segment.
    """
    service = SegmentService(db)
    segment = service.duplicate_segment(segment_id, new_name)
    
    if not segment:
        raise HTTPException(status_code=404, detail="Segment not found")
    
    return SegmentResponse.model_validate(segment)


@router.get("/{segment_id}/customers")
def get_segment_customers(
    segment_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=100),
    db: Session = Depends(get_db),
):
    """
    Get customers matching a segment.
    """
    service = SegmentService(db)
    customers, total = service.get_segment_customers(segment_id, page, page_size)
    
    return {
        "items": [service._customer_to_dict(c) for c in customers],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.post("/from-ai")
def create_segment_from_ai_disabled():
    """
    Previously: AI-powered segment generation.
    This project no longer supports that legacy AI workflow.
    """
    raise HTTPException(status_code=410, detail="AI segment generation is disabled.")
