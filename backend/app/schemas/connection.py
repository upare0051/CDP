"""Pydantic schemas for connections."""

from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator

from ..models.connection import SourceType, DestinationType


# Source Connection Schemas
class SourceConnectionBase(BaseModel):
    """Base schema for source connection."""
    name: str = Field(..., min_length=1, max_length=255)
    source_type: SourceType
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    duckdb_path: Optional[str] = None
    extra_config: Optional[Dict[str, Any]] = None


class SourceConnectionCreate(SourceConnectionBase):
    """Schema for creating source connection."""
    password: Optional[str] = None  # Plain text, will be encrypted
    
    @field_validator("port")
    @classmethod
    def validate_port(cls, v):
        if v is not None and (v < 1 or v > 65535):
            raise ValueError("Port must be between 1 and 65535")
        return v


class SourceConnectionUpdate(BaseModel):
    """Schema for updating source connection."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    host: Optional[str] = None
    port: Optional[int] = None
    database: Optional[str] = None
    username: Optional[str] = None
    password: Optional[str] = None
    duckdb_path: Optional[str] = None
    extra_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class SourceConnectionResponse(SourceConnectionBase):
    """Schema for source connection response."""
    id: int
    is_active: bool
    last_tested_at: Optional[datetime] = None
    last_test_success: Optional[bool] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class SourceConnectionTestResult(BaseModel):
    """Schema for connection test result."""
    success: bool
    message: str
    tables_found: Optional[int] = None
    error: Optional[str] = None


# Destination Connection Schemas
class DestinationConnectionBase(BaseModel):
    """Base schema for destination connection."""
    name: str = Field(..., min_length=1, max_length=255)
    destination_type: DestinationType
    api_endpoint: Optional[str] = None
    braze_app_id: Optional[str] = None
    attentive_api_url: Optional[str] = None
    rate_limit_per_second: Optional[int] = Field(default=100, ge=1, le=1000)
    batch_size: Optional[int] = Field(default=75, ge=1, le=500)
    extra_config: Optional[Dict[str, Any]] = None


class DestinationConnectionCreate(DestinationConnectionBase):
    """Schema for creating destination connection."""
    api_key: str = Field(..., min_length=1)  # Plain text, will be encrypted


class DestinationConnectionUpdate(BaseModel):
    """Schema for updating destination connection."""
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    api_key: Optional[str] = None
    api_endpoint: Optional[str] = None
    braze_app_id: Optional[str] = None
    attentive_api_url: Optional[str] = None
    rate_limit_per_second: Optional[int] = Field(None, ge=1, le=1000)
    batch_size: Optional[int] = Field(None, ge=1, le=500)
    extra_config: Optional[Dict[str, Any]] = None
    is_active: Optional[bool] = None


class DestinationConnectionResponse(DestinationConnectionBase):
    """Schema for destination connection response."""
    id: int
    is_active: bool
    last_tested_at: Optional[datetime] = None
    last_test_success: Optional[bool] = None
    created_at: datetime
    updated_at: datetime
    api_key_masked: Optional[str] = None  # Masked for display
    
    class Config:
        from_attributes = True


class DestinationConnectionTestResult(BaseModel):
    """Schema for destination test result."""
    success: bool
    message: str
    error: Optional[str] = None


# Schema Discovery
class TableInfo(BaseModel):
    """Table information from source."""
    schema_name: str
    table_name: str
    row_count: Optional[int] = None


class ColumnInfo(BaseModel):
    """Column information from source."""
    column_name: str
    data_type: str
    is_nullable: bool = True
    is_primary_key: bool = False


class TableSchema(BaseModel):
    """Full table schema."""
    schema_name: str
    table_name: str
    columns: list[ColumnInfo]
    row_count: Optional[int] = None
