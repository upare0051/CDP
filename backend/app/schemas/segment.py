"""
Pydantic schemas for Segment API.
"""
from datetime import datetime
from typing import List, Optional, Any, Dict, Literal
from pydantic import BaseModel, Field


class FilterCondition(BaseModel):
    """A single filter condition."""
    field: str
    operator: str
    value: Any = None
    value2: Any = None  # For "between" operator


class FilterConfig(BaseModel):
    """Configuration of filters for a segment."""
    filters: List[FilterCondition] = []
    logic: Literal["AND", "OR"] = "AND"


class SegmentBase(BaseModel):
    """Base segment schema."""
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    # source_type drives which of (filter_config, cube_query) is authoritative.
    source_type: Literal["legacy", "cube"] = "legacy"
    filter_config: FilterConfig = FilterConfig()
    # Cube query payload (Cube REST /load body shape). Required when source_type=cube.
    cube_query: Optional[Dict[str, Any]] = None
    tags: List[str] = []


class SegmentCreate(SegmentBase):
    """Schema for creating a segment."""
    ai_generated: bool = False
    ai_prompt: Optional[str] = None


class SegmentUpdate(BaseModel):
    """Schema for updating a segment."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    source_type: Optional[Literal["legacy", "cube"]] = None
    filter_config: Optional[FilterConfig] = None
    cube_query: Optional[Dict[str, Any]] = None
    status: Optional[str] = None
    tags: Optional[List[str]] = None


class SegmentResponse(SegmentBase):
    """Schema for segment response."""
    id: int
    status: str
    estimated_count: Optional[int] = None
    last_count_at: Optional[datetime] = None
    ai_generated: bool = False
    ai_prompt: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    created_by: Optional[str] = None
    dittofeed_segment_id: Optional[str] = None

    class Config:
        from_attributes = True


class SegmentListResponse(BaseModel):
    """Schema for listing segments."""
    items: List[SegmentResponse]
    total: int
    page: int
    page_size: int


class SegmentPreviewRequest(BaseModel):
    """Request schema for previewing segment count.

    Provide either filter_config (legacy) or cube_query (cube). Honors
    source_type when both are present.
    """
    source_type: Literal["legacy", "cube"] = "legacy"
    filter_config: Optional[FilterConfig] = None
    cube_query: Optional[Dict[str, Any]] = None


class SegmentPreviewResponse(BaseModel):
    """Response schema for segment preview."""
    count: int
    sample_customers: List[Dict[str, Any]] = []
    query_time_ms: float
    source_type: Literal["legacy", "cube"] = "legacy"


class SegmentFieldInfo(BaseModel):
    """Information about a segmentable field."""
    name: str
    label: str
    type: str
    category: str


class SegmentOperatorInfo(BaseModel):
    """Information about a filter operator."""
    value: str
    label: str


class SegmentSchemaResponse(BaseModel):
    """Schema information for building segment filters."""
    fields: List[SegmentFieldInfo]
    operators_by_type: Dict[str, List[SegmentOperatorInfo]]


class SegmentFromAIRequest(BaseModel):
    """Request to create segment from natural language."""
    query: str = Field(..., min_length=3)
    save: bool = False  # Whether to save as a new segment


class SegmentFromAIResponse(BaseModel):
    """Response from AI segment generation."""
    name: str
    description: str
    filter_config: FilterConfig
    estimated_count: Optional[int] = None
    segment_id: Optional[int] = None  # If saved
