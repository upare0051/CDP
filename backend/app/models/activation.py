"""
Segment Activation models - tracks segment syncs to destinations.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from ..db.base import Base


class ActivationStatus(str, enum.Enum):
    """Status of an activation."""
    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"


class ActivationFrequency(str, enum.Enum):
    """How often to sync the segment."""
    MANUAL = "manual"
    HOURLY = "hourly"
    DAILY = "daily"
    WEEKLY = "weekly"


class SegmentActivation(Base):
    """
    Links a segment to a destination for ongoing sync.
    This is the "activation" that pushes segment members to a marketing tool.
    """
    __tablename__ = "segment_activations"

    id = Column(Integer, primary_key=True, index=True)
    
    # What segment to activate
    segment_id = Column(Integer, ForeignKey("segments.id", ondelete="CASCADE"), nullable=False)
    
    # Where to send it
    destination_id = Column(Integer, ForeignKey("destination_connections.id", ondelete="CASCADE"), nullable=False)
    
    # Configuration
    name = Column(String(255), nullable=True)  # Optional friendly name
    
    # Sync frequency
    frequency = Column(String(50), default=ActivationFrequency.MANUAL.value)
    
    # Status
    status = Column(String(50), default=ActivationStatus.PENDING.value)
    
    # Field mappings specific to this activation
    # Maps segment/customer fields to destination fields
    field_mappings = Column(JSON, default=[])
    
    # Sync stats
    last_sync_at = Column(DateTime, nullable=True)
    last_sync_count = Column(Integer, nullable=True)
    total_synced = Column(Integer, default=0)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    segment = relationship("Segment", backref="activations")
    destination = relationship("DestinationConnection", backref="segment_activations")


class ActivationRun(Base):
    """
    A single run of syncing a segment to a destination.
    """
    __tablename__ = "activation_runs"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(String(36), unique=True, nullable=False)  # UUID
    
    activation_id = Column(Integer, ForeignKey("segment_activations.id", ondelete="CASCADE"), nullable=False)
    
    # Run details
    status = Column(String(50), default="pending")
    
    # Counts
    total_customers = Column(Integer, default=0)
    synced_count = Column(Integer, default=0)
    failed_count = Column(Integer, default=0)
    skipped_count = Column(Integer, default=0)
    
    # Timing
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    error_details = Column(JSON, nullable=True)
    
    # Relationships
    activation = relationship("SegmentActivation", backref="runs")


class SegmentExport(Base):
    """
    Tracks CSV exports of segments.
    """
    __tablename__ = "segment_exports"

    id = Column(Integer, primary_key=True, index=True)
    
    segment_id = Column(Integer, ForeignKey("segments.id", ondelete="CASCADE"), nullable=False)
    
    # Export details
    file_name = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=True)  # S3 path or local path
    file_size = Column(Integer, nullable=True)
    
    # Stats
    row_count = Column(Integer, default=0)
    
    # Fields included
    included_fields = Column(JSON, default=[])
    
    # Timing
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=True)  # When the download link expires
    
    # Relationships
    segment = relationship("Segment", backref="exports")
