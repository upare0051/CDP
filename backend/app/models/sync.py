"""Sync job and run models."""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import String, Text, Boolean, DateTime, Integer, BigInteger, ForeignKey, Enum as SQLEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from ..db.base import Base


class SyncMode(str, enum.Enum):
    """Sync mode options."""
    FULL_REFRESH = "full_refresh"
    INCREMENTAL = "incremental"


class SyncStatus(str, enum.Enum):
    """Sync run status."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ScheduleType(str, enum.Enum):
    """Schedule type options."""
    MANUAL = "manual"
    CRON = "cron"


class SyncJob(Base):
    """Sync job configuration."""
    
    __tablename__ = "sync_jobs"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Source configuration
    source_connection_id: Mapped[int] = mapped_column(ForeignKey("source_connections.id"), nullable=False)
    source_schema: Mapped[str] = mapped_column(String(255), nullable=False)
    source_table: Mapped[str] = mapped_column(String(255), nullable=False)
    source_query: Mapped[Optional[str]] = mapped_column(Text)  # Custom SQL query (optional)
    
    # Destination configuration
    destination_connection_id: Mapped[int] = mapped_column(ForeignKey("destination_connections.id"), nullable=False)
    
    # Sync configuration
    sync_mode: Mapped[SyncMode] = mapped_column(SQLEnum(SyncMode), default=SyncMode.FULL_REFRESH)
    sync_key: Mapped[str] = mapped_column(String(255), nullable=False)  # external_id, email, phone
    
    # Incremental sync configuration
    incremental_column: Mapped[Optional[str]] = mapped_column(String(255))  # e.g., updated_at
    last_checkpoint_value: Mapped[Optional[str]] = mapped_column(String(255))  # Last synced value
    
    # Schedule configuration
    schedule_type: Mapped[ScheduleType] = mapped_column(SQLEnum(ScheduleType), default=ScheduleType.MANUAL)
    cron_expression: Mapped[Optional[str]] = mapped_column(String(100))  # e.g., "0 */6 * * *"
    
    # Airflow integration
    airflow_dag_id: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_paused: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Schema tracking
    source_schema_hash: Mapped[Optional[str]] = mapped_column(String(64))  # For schema change detection
    last_schema_check_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    source_connection = relationship("SourceConnection", back_populates="sync_jobs")
    destination_connection = relationship("DestinationConnection", back_populates="sync_jobs")
    field_mappings: Mapped[List["FieldMapping"]] = relationship("FieldMapping", back_populates="sync_job", cascade="all, delete-orphan")
    sync_runs: Mapped[List["SyncRun"]] = relationship("SyncRun", back_populates="sync_job", cascade="all, delete-orphan")


class FieldMapping(Base):
    """Field mapping from source to destination."""
    
    __tablename__ = "field_mappings"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sync_job_id: Mapped[int] = mapped_column(ForeignKey("sync_jobs.id"), nullable=False)
    
    # Source field
    source_field: Mapped[str] = mapped_column(String(255), nullable=False)
    source_field_type: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Destination field
    destination_field: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Transformation (optional)
    transformation: Mapped[Optional[str]] = mapped_column(Text)  # e.g., "UPPER", "DATE_FORMAT"
    
    # Flags
    is_sync_key: Mapped[bool] = mapped_column(Boolean, default=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    
    # Relationships
    sync_job = relationship("SyncJob", back_populates="field_mappings")


class SyncRun(Base):
    """Individual sync run execution."""
    
    __tablename__ = "sync_runs"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    sync_job_id: Mapped[int] = mapped_column(ForeignKey("sync_jobs.id"), nullable=False)
    
    # Run identification
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)  # UUID
    airflow_run_id: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Status
    status: Mapped[SyncStatus] = mapped_column(SQLEnum(SyncStatus), default=SyncStatus.PENDING)
    
    # Timing
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    duration_seconds: Mapped[Optional[int]] = mapped_column(Integer)
    
    # Metrics
    rows_read: Mapped[int] = mapped_column(BigInteger, default=0)
    rows_synced: Mapped[int] = mapped_column(BigInteger, default=0)
    rows_failed: Mapped[int] = mapped_column(BigInteger, default=0)
    rows_skipped: Mapped[int] = mapped_column(BigInteger, default=0)
    
    # Incremental sync tracking
    checkpoint_value: Mapped[Optional[str]] = mapped_column(String(255))  # Value at start of run
    new_checkpoint_value: Mapped[Optional[str]] = mapped_column(String(255))  # Value at end (only saved on success)
    
    # Error handling
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    error_details: Mapped[Optional[dict]] = mapped_column(JSON)
    retry_count: Mapped[int] = mapped_column(Integer, default=0)
    
    # Logs
    logs: Mapped[Optional[str]] = mapped_column(Text)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sync_job = relationship("SyncJob", back_populates="sync_runs")
