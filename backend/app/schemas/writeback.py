"""Schemas for controlled write-back jobs."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, model_validator


class WritebackValueMapping(BaseModel):
    mode: Literal["static", "field"] = "static"
    value: Optional[str] = None
    field: Optional[str] = None

    @model_validator(mode="after")
    def validate_mapping(self):
        if self.mode == "static" and self.value is None:
            raise ValueError("value is required when mode='static'")
        if self.mode == "field" and not self.field:
            raise ValueError("field is required when mode='field'")
        return self


class WritebackJobCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None
    source_type: Literal["ai_customer_insights"] = "ai_customer_insights"
    source_filters: Dict[str, Any] = Field(default_factory=dict)
    target_type: Literal["customer_attributes"] = "customer_attributes"
    attribute_name: str = Field(..., min_length=1, max_length=100)
    attribute_type: Literal["string", "number", "boolean", "date", "json"] = "string"
    value_mapping: WritebackValueMapping
    created_by: Optional[str] = None


class WritebackJobUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    description: Optional[str] = None
    source_filters: Optional[Dict[str, Any]] = None
    attribute_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    attribute_type: Optional[Literal["string", "number", "boolean", "date", "json"]] = None
    value_mapping: Optional[WritebackValueMapping] = None
    status: Optional[Literal["draft", "active", "archived"]] = None


class WritebackJobResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    source_type: str
    source_filters: Dict[str, Any]
    target_type: str
    attribute_name: str
    attribute_type: str
    value_mapping: Dict[str, Any]
    status: str
    created_by: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class WritebackPreviewResponse(BaseModel):
    total_candidates: int
    sample_rows: List[Dict[str, Any]]
    attribute_name: str
    attribute_type: str


class WritebackApplyResponse(BaseModel):
    run_id: int
    status: str
    total_candidates: int
    total_updates: int
    total_inserts: int
    total_failed: int


class WritebackRunResponse(BaseModel):
    id: int
    job_id: int
    run_type: str
    status: str
    total_candidates: int
    total_updates: int
    total_inserts: int
    total_failed: int
    sample_preview: Optional[List[Dict[str, Any]]]
    error_message: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    created_at: datetime

    class Config:
        from_attributes = True
