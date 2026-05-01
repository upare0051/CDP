"""Models for controlled write-back jobs and execution audit."""

from datetime import datetime

from sqlalchemy import Column, Integer, String, Text, DateTime, JSON, ForeignKey
from sqlalchemy.orm import relationship

from ..db.base import Base


class WritebackJob(Base):
    """Write-back job definition (what to write, from where, to where)."""

    __tablename__ = "writeback_jobs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)

    # Source (currently persisted AI insights in DuckDB)
    source_type = Column(String(100), nullable=False, default="ai_customer_insights")
    source_filters = Column(JSON, nullable=False, default={})

    # Target (currently customer_attributes in app DB)
    target_type = Column(String(100), nullable=False, default="customer_attributes")
    attribute_name = Column(String(100), nullable=False)
    attribute_type = Column(String(20), nullable=False, default="string")

    # Value mapping:
    # { "mode": "static", "value": "high" }
    # { "mode": "field", "field": "churn_level" }
    value_mapping = Column(JSON, nullable=False, default={})

    # Metadata
    status = Column(String(50), nullable=False, default="draft")
    created_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    runs = relationship("WritebackRun", back_populates="job", cascade="all, delete-orphan")


class WritebackRun(Base):
    """Execution log for write-back apply/preview operations."""

    __tablename__ = "writeback_runs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("writeback_jobs.id", ondelete="CASCADE"), nullable=False)

    run_type = Column(String(20), nullable=False, default="preview")  # preview | apply
    status = Column(String(50), nullable=False, default="running")  # running | completed | failed

    total_candidates = Column(Integer, nullable=False, default=0)
    total_updates = Column(Integer, nullable=False, default=0)
    total_inserts = Column(Integer, nullable=False, default=0)
    total_failed = Column(Integer, nullable=False, default=0)

    sample_preview = Column(JSON, nullable=True, default=[])
    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    job = relationship("WritebackJob", back_populates="runs")
