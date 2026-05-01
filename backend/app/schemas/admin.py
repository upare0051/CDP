"""Schemas for admin analytics APIs."""

from datetime import date, datetime
from typing import List, Optional

from pydantic import BaseModel


class DailyMetric(BaseModel):
    day: date
    visits: int
    leads: int


class IndustryLeadMetric(BaseModel):
    industry: str
    leads: int


class AdminAnalyticsSummary(BaseModel):
    days: int
    visitors_today: int
    visitors_last_7d: int
    leads_today: int
    leads_last_7d: int
    lead_conversion_rate_last_7d: float
    leads_by_industry_last_7d: List[IndustryLeadMetric]
    recent_daily_metrics: List[DailyMetric]


class AdminLeadItem(BaseModel):
    id: int
    email: str
    full_name: Optional[str]
    company: Optional[str]
    use_case: Optional[str]
    source: str
    created_at: datetime


class AdminLeadListResponse(BaseModel):
    items: List[AdminLeadItem]
    total: int
    page: int
    page_size: int


