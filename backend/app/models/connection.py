"""Connection models for sources and destinations."""

from datetime import datetime
from typing import Optional
from sqlalchemy import String, Text, Boolean, DateTime, Enum as SQLEnum, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
import enum

from ..db.base import Base


class SourceType(str, enum.Enum):
    """Supported source types."""
    REDSHIFT = "redshift"
    DUCKDB = "duckdb"


class DestinationType(str, enum.Enum):
    """Supported destination types."""
    BRAZE = "braze"
    ATTENTIVE = "attentive"


class SourceConnection(Base):
    """Source connection configuration (Redshift/DuckDB)."""
    
    __tablename__ = "source_connections"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    source_type: Mapped[SourceType] = mapped_column(SQLEnum(SourceType), nullable=False)
    
    # Connection details (encrypted)
    host: Mapped[Optional[str]] = mapped_column(String(255))
    port: Mapped[Optional[int]] = mapped_column()
    database: Mapped[Optional[str]] = mapped_column(String(255))
    username: Mapped[Optional[str]] = mapped_column(String(255))
    password_encrypted: Mapped[Optional[str]] = mapped_column(Text)  # Encrypted
    
    # DuckDB specific
    duckdb_path: Mapped[Optional[str]] = mapped_column(String(512))
    
    # Additional config
    extra_config: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_tested_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_test_success: Mapped[Optional[bool]] = mapped_column(Boolean)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sync_jobs = relationship("SyncJob", back_populates="source_connection")


class DestinationConnection(Base):
    """Destination connection configuration (Braze/Attentive)."""
    
    __tablename__ = "destination_connections"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    destination_type: Mapped[DestinationType] = mapped_column(SQLEnum(DestinationType), nullable=False)
    
    # API credentials (encrypted)
    api_key_encrypted: Mapped[Optional[str]] = mapped_column(Text)  # Encrypted
    api_endpoint: Mapped[Optional[str]] = mapped_column(String(512))
    
    # Braze specific
    braze_app_id: Mapped[Optional[str]] = mapped_column(String(255))
    
    # Attentive specific  
    attentive_api_url: Mapped[Optional[str]] = mapped_column(String(512))
    
    # Additional config
    extra_config: Mapped[Optional[dict]] = mapped_column(JSON, default=dict)
    
    # Rate limiting
    rate_limit_per_second: Mapped[Optional[int]] = mapped_column(default=100)
    batch_size: Mapped[Optional[int]] = mapped_column(default=75)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_tested_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    last_test_success: Mapped[Optional[bool]] = mapped_column(Boolean)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    sync_jobs = relationship("SyncJob", back_populates="destination_connection")
