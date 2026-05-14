"""Cached segment preview results."""

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, DateTime, Float, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db.base import Base


class SegmentPreviewCache(Base):
    """Saved Cube preview result keyed by a normalized query hash."""

    __tablename__ = "segment_preview_cache"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    query_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    source_type: Mapped[str] = mapped_column(String(50), default="cube", nullable=False, index=True)
    query_payload: Mapped[dict] = mapped_column(JSON, nullable=False)

    count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    sample_customers: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    query_time_ms: Mapped[float] = mapped_column(Float, default=0, nullable=False)

    hit_count: Mapped[int] = mapped_column(BigInteger, default=0, nullable=False)
    last_error: Mapped[Optional[str]] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, index=True)
