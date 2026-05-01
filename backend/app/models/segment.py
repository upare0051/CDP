"""
Segment models for audience segmentation.
"""
from datetime import datetime
from typing import List, Optional
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, JSON, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import relationship
import enum

from ..db.base import Base


class SegmentStatus(str, enum.Enum):
    """Status of a segment."""
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


class FilterOperator(str, enum.Enum):
    """Available filter operators."""
    # String operators
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    CONTAINS = "contains"
    NOT_CONTAINS = "not_contains"
    STARTS_WITH = "starts_with"
    ENDS_WITH = "ends_with"
    IS_EMPTY = "is_empty"
    IS_NOT_EMPTY = "is_not_empty"
    
    # Number operators
    GREATER_THAN = "greater_than"
    GREATER_THAN_OR_EQUALS = "greater_than_or_equals"
    LESS_THAN = "less_than"
    LESS_THAN_OR_EQUALS = "less_than_or_equals"
    BETWEEN = "between"
    
    # Date operators
    BEFORE = "before"
    AFTER = "after"
    LAST_N_DAYS = "last_n_days"
    NEXT_N_DAYS = "next_n_days"
    
    # Boolean operators
    IS_TRUE = "is_true"
    IS_FALSE = "is_false"
    
    # List operators
    IN_LIST = "in_list"
    NOT_IN_LIST = "not_in_list"


class Segment(Base):
    """
    A segment represents a filtered subset of customers based on criteria.
    Segments can be used for targeting in syncs/campaigns.
    """
    __tablename__ = "segments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    
    # Filter configuration (JSON structure)
    # Format: {"filters": [...], "logic": "AND" | "OR"}
    filter_config = Column(JSON, nullable=False, default={"filters": [], "logic": "AND"})
    
    # Segment status
    status = Column(String(50), default=SegmentStatus.DRAFT.value)
    
    # Cached count (updated periodically)
    estimated_count = Column(Integer, nullable=True)
    last_count_at = Column(DateTime, nullable=True)
    
    # AI-generated flag
    ai_generated = Column(Boolean, default=False)
    ai_prompt = Column(Text, nullable=True)  # Original NL prompt if AI-generated
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(255), nullable=True)
    
    # Tags for organization
    tags = Column(JSON, default=[])


class SegmentMembership(Base):
    """
    Tracks which customers belong to which segments.
    This is computed/cached for performance.
    """
    __tablename__ = "segment_memberships"

    id = Column(Integer, primary_key=True, index=True)
    segment_id = Column(Integer, ForeignKey("segments.id", ondelete="CASCADE"), nullable=False)
    customer_id = Column(Integer, ForeignKey("customer_profiles.id", ondelete="CASCADE"), nullable=False)
    
    # When this membership was computed
    computed_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    segment = relationship("Segment", backref="memberships")
    customer = relationship("CustomerProfile", backref="segment_memberships")


# Define available fields for segmentation
SEGMENT_FIELDS = [
    # Core customer fields
    {"name": "email", "label": "Email", "type": "string", "category": "contact"},
    {"name": "phone", "label": "Phone", "type": "string", "category": "contact"},
    {"name": "first_name", "label": "First Name", "type": "string", "category": "profile"},
    {"name": "last_name", "label": "Last Name", "type": "string", "category": "profile"},
    {"name": "external_id", "label": "External ID", "type": "string", "category": "profile"},
    
    # Location fields
    {"name": "city", "label": "City", "type": "string", "category": "location"},
    {"name": "state", "label": "State", "type": "string", "category": "location"},
    {"name": "country", "label": "Country", "type": "string", "category": "location"},
    
    # Value metrics
    {"name": "lifetime_value", "label": "Lifetime Value", "type": "number", "category": "metrics"},
    {"name": "total_orders", "label": "Total Orders", "type": "number", "category": "metrics"},
    {"name": "avg_order_value", "label": "Avg Order Value", "type": "number", "category": "metrics"},
    
    # Engagement fields
    {"name": "first_seen_at", "label": "First Seen", "type": "date", "category": "engagement"},
    {"name": "last_seen_at", "label": "Last Seen", "type": "date", "category": "engagement"},
    {"name": "signup_date", "label": "Signup Date", "type": "date", "category": "engagement"},
    {"name": "last_order_date", "label": "Last Order Date", "type": "date", "category": "engagement"},
    
    # Preferences
    {"name": "is_subscribed", "label": "Email Subscribed", "type": "boolean", "category": "preferences"},
    {"name": "acquisition_source", "label": "Acquisition Source", "type": "string", "category": "marketing"},
    {"name": "gender", "label": "Gender", "type": "string", "category": "profile"},
]

# Operators by field type
OPERATORS_BY_TYPE = {
    "string": [
        {"value": "equals", "label": "equals"},
        {"value": "not_equals", "label": "does not equal"},
        {"value": "contains", "label": "contains"},
        {"value": "not_contains", "label": "does not contain"},
        {"value": "starts_with", "label": "starts with"},
        {"value": "ends_with", "label": "ends with"},
        {"value": "is_empty", "label": "is empty"},
        {"value": "is_not_empty", "label": "is not empty"},
        {"value": "in_list", "label": "is in list"},
        {"value": "not_in_list", "label": "is not in list"},
    ],
    "number": [
        {"value": "equals", "label": "equals"},
        {"value": "not_equals", "label": "does not equal"},
        {"value": "greater_than", "label": "is greater than"},
        {"value": "greater_than_or_equals", "label": "is at least"},
        {"value": "less_than", "label": "is less than"},
        {"value": "less_than_or_equals", "label": "is at most"},
        {"value": "between", "label": "is between"},
        {"value": "is_empty", "label": "is empty"},
        {"value": "is_not_empty", "label": "is not empty"},
    ],
    "date": [
        {"value": "equals", "label": "is on"},
        {"value": "before", "label": "is before"},
        {"value": "after", "label": "is after"},
        {"value": "between", "label": "is between"},
        {"value": "last_n_days", "label": "in the last N days"},
        {"value": "next_n_days", "label": "in the next N days"},
        {"value": "is_empty", "label": "is empty"},
        {"value": "is_not_empty", "label": "is not empty"},
    ],
    "boolean": [
        {"value": "is_true", "label": "is true"},
        {"value": "is_false", "label": "is false"},
    ],
}
