"""Customer 360 profile models."""

from datetime import datetime
from typing import Optional, List
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON, Index
from sqlalchemy.orm import relationship

from ..db import Base


class CustomerProfile(Base):
    """
    Unified customer profile aggregated from all sources.
    This is the "golden record" for each customer.
    """
    __tablename__ = "customer_profiles"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Canonical identifier - typically the external_id from syncs
    external_id = Column(String(255), unique=True, nullable=False, index=True)
    
    # Core profile fields (denormalized for quick access)
    email = Column(String(255), index=True)
    phone = Column(String(50), index=True)
    first_name = Column(String(100))
    last_name = Column(String(100))
    
    # Metadata
    source_count = Column(Integer, default=1)  # Number of sources this customer appears in
    first_seen_at = Column(DateTime, default=datetime.utcnow)
    last_seen_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_synced_at = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    attributes = relationship("CustomerAttribute", back_populates="customer", cascade="all, delete-orphan")
    events = relationship("CustomerEvent", back_populates="customer", cascade="all, delete-orphan", order_by="desc(CustomerEvent.occurred_at)")
    identities = relationship("CustomerIdentity", back_populates="customer", cascade="all, delete-orphan")
    
    @property
    def full_name(self) -> str:
        """Get full name."""
        parts = [self.first_name, self.last_name]
        return " ".join(p for p in parts if p) or "Unknown"
    
    def __repr__(self):
        return f"<CustomerProfile(id={self.id}, external_id='{self.external_id}', email='{self.email}')>"


class CustomerAttribute(Base):
    """
    Flexible key-value attributes for customers.
    Allows storing any attribute from any source.
    """
    __tablename__ = "customer_attributes"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customer_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Attribute definition
    attribute_name = Column(String(100), nullable=False)
    attribute_value = Column(Text)  # Stored as string, can be parsed based on type
    attribute_type = Column(String(20), default="string")  # string, number, boolean, date, json
    
    # Source tracking (for data lineage)
    source_connection_id = Column(Integer, ForeignKey("source_connections.id", ondelete="SET NULL"))
    source_field = Column(String(100))  # Original field name in source
    
    # Metadata
    confidence_score = Column(Integer, default=100)  # 0-100, for future ML-based resolution
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    customer = relationship("CustomerProfile", back_populates="attributes")
    source_connection = relationship("SourceConnection")
    
    # Composite index for efficient lookups
    __table_args__ = (
        Index("ix_customer_attr_lookup", "customer_id", "attribute_name"),
    )
    
    def __repr__(self):
        return f"<CustomerAttribute(customer_id={self.customer_id}, {self.attribute_name}='{self.attribute_value}')>"


class CustomerEvent(Base):
    """
    Activity timeline for customers.
    Tracks all events related to a customer (syncs, updates, etc.)
    """
    __tablename__ = "customer_events"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customer_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Event details
    event_type = Column(String(50), nullable=False)  # profile_created, attribute_updated, synced_to_destination, etc.
    event_category = Column(String(50), default="system")  # system, sync, manual, integration
    title = Column(String(255))
    description = Column(Text)
    event_data = Column(JSON)  # Additional event-specific data
    
    # Source tracking
    source_connection_id = Column(Integer, ForeignKey("source_connections.id", ondelete="SET NULL"))
    destination_connection_id = Column(Integer, ForeignKey("destination_connections.id", ondelete="SET NULL"))
    sync_run_id = Column(String(36))  # UUID of the sync run that triggered this event
    
    # Timestamp
    occurred_at = Column(DateTime, default=datetime.utcnow, index=True)
    
    # Relationships
    customer = relationship("CustomerProfile", back_populates="events")
    source_connection = relationship("SourceConnection")
    destination_connection = relationship("DestinationConnection")
    
    def __repr__(self):
        return f"<CustomerEvent(customer_id={self.customer_id}, type='{self.event_type}', at={self.occurred_at})>"


class CustomerIdentity(Base):
    """
    Links customer profiles to their identities in source systems.
    Enables future identity resolution across sources.
    """
    __tablename__ = "customer_identities"
    
    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customer_profiles.id", ondelete="CASCADE"), nullable=False, index=True)
    
    # Identity in source system
    identity_type = Column(String(50), nullable=False)  # external_id, email, phone, device_id, etc.
    identity_value = Column(String(255), nullable=False)
    
    # Source tracking
    source_connection_id = Column(Integer, ForeignKey("source_connections.id", ondelete="SET NULL"))
    
    # Metadata
    is_primary = Column(Integer, default=0)  # 1 if this is the primary identifier
    verified = Column(Integer, default=0)  # 1 if verified
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    customer = relationship("CustomerProfile", back_populates="identities")
    source_connection = relationship("SourceConnection")
    
    # Index for identity lookups
    __table_args__ = (
        Index("ix_customer_identity_lookup", "identity_type", "identity_value"),
    )
    
    def __repr__(self):
        return f"<CustomerIdentity(customer_id={self.customer_id}, {self.identity_type}='{self.identity_value}')>"
