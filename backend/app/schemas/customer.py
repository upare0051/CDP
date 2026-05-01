"""Pydantic schemas for Customer 360."""

from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


# ============ Attribute Schemas ============

class CustomerAttributeBase(BaseModel):
    """Base schema for customer attributes."""
    attribute_name: str
    attribute_value: Optional[str] = None
    attribute_type: str = "string"


class CustomerAttributeCreate(CustomerAttributeBase):
    """Schema for creating a customer attribute."""
    source_connection_id: Optional[int] = None
    source_field: Optional[str] = None


class CustomerAttributeResponse(CustomerAttributeBase):
    """Schema for customer attribute response."""
    id: int
    customer_id: int
    source_connection_id: Optional[int] = None
    source_field: Optional[str] = None
    source_name: Optional[str] = None  # Populated from relationship
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ============ Event Schemas ============

class CustomerEventBase(BaseModel):
    """Base schema for customer events."""
    event_type: str
    event_category: str = "system"
    title: Optional[str] = None
    description: Optional[str] = None
    event_data: Optional[Dict[str, Any]] = None


class CustomerEventCreate(CustomerEventBase):
    """Schema for creating a customer event."""
    customer_id: int
    source_connection_id: Optional[int] = None
    destination_connection_id: Optional[int] = None
    sync_run_id: Optional[str] = None
    occurred_at: Optional[datetime] = None


class CustomerEventResponse(CustomerEventBase):
    """Schema for customer event response."""
    id: int
    customer_id: int
    source_connection_id: Optional[int] = None
    destination_connection_id: Optional[int] = None
    sync_run_id: Optional[str] = None
    occurred_at: datetime
    source_name: Optional[str] = None
    destination_name: Optional[str] = None
    
    class Config:
        from_attributes = True


# ============ Identity Schemas ============

class CustomerIdentityResponse(BaseModel):
    """Schema for customer identity response."""
    id: int
    identity_type: str
    identity_value: str
    source_connection_id: Optional[int] = None
    source_name: Optional[str] = None
    is_primary: bool = False
    verified: bool = False
    created_at: datetime
    
    class Config:
        from_attributes = True


# ============ Profile Schemas ============

class CustomerProfileBase(BaseModel):
    """Base schema for customer profile."""
    external_id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class CustomerProfileCreate(CustomerProfileBase):
    """Schema for creating a customer profile."""
    pass


class CustomerProfileUpdate(BaseModel):
    """Schema for updating a customer profile."""
    email: Optional[str] = None
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None


class CustomerProfileSummary(BaseModel):
    """Summary schema for customer list views."""
    id: int
    external_id: str
    email: Optional[str] = None
    phone: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    full_name: str
    source_count: int = 1
    first_seen_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    last_synced_at: Optional[datetime] = None
    
    # Quick access attributes (populated from key attributes)
    lifetime_value: Optional[float] = None
    total_orders: Optional[int] = None
    city: Optional[str] = None
    country: Optional[str] = None
    
    class Config:
        from_attributes = True


class CustomerProfileDetail(CustomerProfileSummary):
    """Detailed schema for customer profile page."""
    attributes: List[CustomerAttributeResponse] = []
    recent_events: List[CustomerEventResponse] = []
    identities: List[CustomerIdentityResponse] = []
    
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


# ============ List/Search Schemas ============

class CustomerListParams(BaseModel):
    """Parameters for customer list/search."""
    search: Optional[str] = None  # Search in email, name, external_id
    source_id: Optional[int] = None  # Filter by source connection
    attribute_filter: Optional[Dict[str, str]] = None  # Filter by attributes
    sort_by: str = "last_seen_at"
    sort_order: str = "desc"
    page: int = 1
    page_size: int = 50


class CustomerListResponse(BaseModel):
    """Paginated customer list response."""
    customers: List[CustomerProfileSummary]
    total: int
    page: int
    page_size: int
    total_pages: int


# ============ Stats Schemas ============

class CustomerStats(BaseModel):
    """Customer dashboard statistics."""
    total_customers: int
    customers_added_today: int
    customers_added_this_week: int
    customers_synced_today: int
    avg_attributes_per_customer: float
    top_sources: List[Dict[str, Any]]  # [{source_name, customer_count}]


# ============ Profile Builder Schemas ============

class ProfileBuildRequest(BaseModel):
    """Request to build/update customer profiles from sync data."""
    sync_job_id: int
    sync_run_id: str
    records: List[Dict[str, Any]]
    source_connection_id: int


class ProfileBuildResult(BaseModel):
    """Result of profile building."""
    profiles_created: int
    profiles_updated: int
    attributes_added: int
    events_created: int
    errors: List[str] = []
