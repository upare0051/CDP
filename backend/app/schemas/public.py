"""Schemas for public landing-page APIs."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class LeadCaptureCreate(BaseModel):
    email: str = Field(..., min_length=5, max_length=255)
    full_name: Optional[str] = Field(default=None, max_length=255)
    company: Optional[str] = Field(default=None, max_length=255)
    use_case: Optional[str] = Field(default=None, max_length=1000)
    primary_use_case: Optional[str] = Field(default=None, max_length=255)
    company_size: Optional[str] = Field(default=None, max_length=255)
    stack: Optional[str] = Field(default=None, max_length=500)
    consent_follow_up: bool = Field(default=False)
    request_demo_call: bool = Field(default=False)
    intent_choice: Optional[str] = Field(default=None, max_length=255)
    source: str = Field(default="landing_page", max_length=100)


class LeadCaptureResponse(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    company: Optional[str]
    use_case: Optional[str]
    source: str
    created_at: datetime
    demo_url: str
    message: str

    class Config:
        from_attributes = True


class VisitCaptureCreate(BaseModel):
    session_id: str = Field(..., min_length=8, max_length=64)
    page_path: str = Field(default="/", max_length=255)
    referrer: Optional[str] = Field(default=None, max_length=1024)
    source: str = Field(default="landing_page", max_length=100)


class VisitCaptureResponse(BaseModel):
    id: int
    session_id: str
    created_at: datetime
    message: str

    class Config:
        from_attributes = True
