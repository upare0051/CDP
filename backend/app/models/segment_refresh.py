"""Segment warehouse refresh run tracking."""

from datetime import datetime
from typing import Optional
from sqlalchemy import DateTime, ForeignKey, String, Text, BigInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db.base import Base


class SegmentRefreshRun(Base):
    """App-side audit row for materializing a segment into the warehouse."""

    __tablename__ = "segment_refresh_runs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    segment_id: Mapped[int] = mapped_column(ForeignKey("segments.id", ondelete="CASCADE"), nullable=False, index=True)
    run_id: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)

    target: Mapped[str] = mapped_column(String(50), default="redshift", nullable=False)
    status: Mapped[str] = mapped_column(String(50), default="running", nullable=False)
    trigger: Mapped[str] = mapped_column(String(50), default="manual", nullable=False)

    row_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text)

    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    segment = relationship("Segment", backref="refresh_runs")
