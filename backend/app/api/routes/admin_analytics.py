"""Admin analytics APIs for lead and visit tracking."""

from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from ...core.config import get_settings
from ...db import get_db
from ...models.lead import LeadCapture, WebsiteVisit
from ...schemas.admin import (
    AdminAnalyticsSummary,
    AdminLeadItem,
    AdminLeadListResponse,
    DailyMetric,
    IndustryLeadMetric,
)

router = APIRouter(prefix="/admin/analytics", tags=["admin"])
settings = get_settings()


def _require_admin_key(x_admin_key: Optional[str] = Header(default=None)) -> None:
    expected = (settings.admin_analytics_key or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="Admin analytics key is not configured.")
    if x_admin_key != expected:
        raise HTTPException(status_code=403, detail="Forbidden")


def _to_day(value) -> Optional[date]:
    """Normalize DB date/datetime/string values into a date for chart aggregation."""
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return value
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, str):
        # Handles both 'YYYY-MM-DD' and datetime-like strings.
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    return None


def _industry_from_source(source: Optional[str]) -> str:
    value = (source or "").lower()
    if "industry_ecommerce" in value:
        return "E-Commerce & Retail"
    if "industry_fintech" in value:
        return "Financial Services & FinTech"
    if "industry_media" in value:
        return "Media & Entertainment"
    if "industry_qsr" in value:
        return "QSR & On-Demand Food"
    return "Landing"


@router.get("/summary", response_model=AdminAnalyticsSummary, dependencies=[Depends(_require_admin_key)])
def get_summary(
    days: int = Query(default=14, ge=1, le=90),
    db: Session = Depends(get_db),
):
    today = date.today()
    today_start = datetime.combine(today, datetime.min.time())
    tomorrow_start = today_start + timedelta(days=1)
    week_start = datetime.combine(today - timedelta(days=6), datetime.min.time())
    days_start = datetime.combine(today - timedelta(days=days - 1), datetime.min.time())

    visitors_today = (
        db.query(func.count(func.distinct(WebsiteVisit.session_id)))
        .filter(WebsiteVisit.created_at >= today_start, WebsiteVisit.created_at < tomorrow_start)
        .scalar()
        or 0
    )
    visitors_last_7d = (
        db.query(func.count(func.distinct(WebsiteVisit.session_id)))
        .filter(WebsiteVisit.created_at >= week_start)
        .scalar()
        or 0
    )
    leads_today = (
        db.query(func.count(LeadCapture.id))
        .filter(LeadCapture.created_at >= today_start, LeadCapture.created_at < tomorrow_start)
        .scalar()
        or 0
    )
    leads_last_7d = (
        db.query(func.count(LeadCapture.id))
        .filter(LeadCapture.created_at >= week_start)
        .scalar()
        or 0
    )
    source_breakdown_rows = (
        db.query(
            LeadCapture.source.label("source"),
            func.count(LeadCapture.id).label("leads"),
        )
        .filter(LeadCapture.created_at >= week_start)
        .group_by(LeadCapture.source)
        .all()
    )

    visit_by_day_rows = (
        db.query(
            func.date(WebsiteVisit.created_at).label("day"),
            func.count(func.distinct(WebsiteVisit.session_id)).label("visits"),
        )
        .filter(WebsiteVisit.created_at >= days_start)
        .group_by(func.date(WebsiteVisit.created_at))
        .all()
    )
    lead_by_day_rows = (
        db.query(
            func.date(LeadCapture.created_at).label("day"),
            func.count(LeadCapture.id).label("leads"),
        )
        .filter(LeadCapture.created_at >= days_start)
        .group_by(func.date(LeadCapture.created_at))
        .all()
    )

    visit_map = {}
    for row in visit_by_day_rows:
        day_value = _to_day(row.day)
        if day_value is not None:
            visit_map[day_value] = int(row.visits or 0)

    lead_map = {}
    for row in lead_by_day_rows:
        day_value = _to_day(row.day)
        if day_value is not None:
            lead_map[day_value] = int(row.leads or 0)

    metrics = []
    for i in range(days):
        d = today - timedelta(days=(days - 1 - i))
        metrics.append(
            DailyMetric(
                day=d,
                visits=visit_map.get(d, 0),
                leads=lead_map.get(d, 0),
            )
        )

    industry_counts = {
        "E-Commerce & Retail": 0,
        "Financial Services & FinTech": 0,
        "Media & Entertainment": 0,
        "QSR & On-Demand Food": 0,
        "Landing": 0,
    }
    for row in source_breakdown_rows:
        industry = _industry_from_source(row.source)
        industry_counts[industry] = industry_counts.get(industry, 0) + int(row.leads or 0)
    industry_metrics = [
        IndustryLeadMetric(industry=name, leads=count)
        for name, count in industry_counts.items()
    ]

    conversion = (leads_last_7d / visitors_last_7d * 100.0) if visitors_last_7d else 0.0

    return AdminAnalyticsSummary(
        days=days,
        visitors_today=int(visitors_today),
        visitors_last_7d=int(visitors_last_7d),
        leads_today=int(leads_today),
        leads_last_7d=int(leads_last_7d),
        lead_conversion_rate_last_7d=round(conversion, 2),
        leads_by_industry_last_7d=industry_metrics,
        recent_daily_metrics=metrics,
    )


@router.get("/leads", response_model=AdminLeadListResponse, dependencies=[Depends(_require_admin_key)])
def list_leads(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    search: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(LeadCapture)
    if search:
        like_value = f"%{search.strip().lower()}%"
        query = query.filter(func.lower(LeadCapture.email).like(like_value))

    total = query.count()
    rows = (
        query.order_by(LeadCapture.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )

    return AdminLeadListResponse(
        items=[
            AdminLeadItem(
                id=row.id,
                email=row.email,
                full_name=row.full_name,
                company=row.company,
                use_case=row.use_case,
                source=row.source,
                created_at=row.created_at,
            )
            for row in rows
        ],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/leads/export.csv", dependencies=[Depends(_require_admin_key)])
def export_leads_csv(db: Session = Depends(get_db)):
    rows = db.query(LeadCapture).order_by(LeadCapture.created_at.desc()).all()

    header = "id,email,full_name,company,use_case,source,created_at\n"
    lines = [header]
    for row in rows:
        full_name = (row.full_name or "").replace('"', '""')
        company = (row.company or "").replace('"', '""')
        use_case = (row.use_case or "").replace('"', '""')
        lines.append(
            f'{row.id},"{row.email}","{full_name}","{company}","{use_case}","{row.source}","{row.created_at.isoformat()}"\n'
        )

    content = "".join(lines)
    return StreamingResponse(
        iter([content]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=lead_captures.csv"},
    )
