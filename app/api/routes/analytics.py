"""Analytics Dashboard API - Rich analytics for the TVL platform."""
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, extract, case as sql_case
from datetime import datetime, timedelta
import random
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.features import (
    TrackedCase, CaseStatus,
    Client,
    Consultation, ConsultationStatus,
)

router = APIRouter(prefix="/analytics", tags=["Analytics"])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _month_label(month: int) -> str:
    """Return short month name."""
    return [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ][month - 1]


# ---------------------------------------------------------------------------
# 1. GET /analytics/dashboard  -- Main dashboard overview
# ---------------------------------------------------------------------------

@router.get("/dashboard", summary="Main dashboard analytics")
async def dashboard(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        # Total cases
        total_cases = (await db.execute(
            select(func.count(TrackedCase.id)).where(TrackedCase.user_id == user.id)
        )).scalar() or 0

        # Cases by status
        status_rows = (await db.execute(
            select(TrackedCase.status, func.count(TrackedCase.id))
            .where(TrackedCase.user_id == user.id)
            .group_by(TrackedCase.status)
        )).all()
        cases_by_status = {str(s.value) if hasattr(s, "value") else str(s): c for s, c in status_rows}

        active_cases = cases_by_status.get(CaseStatus.ACTIVE.value, 0) + cases_by_status.get(CaseStatus.APPEALED.value, 0)
    except Exception:
        total_cases = 0
        cases_by_status = {}
        active_cases = 0

    try:
        # Total clients
        total_clients = (await db.execute(
            select(func.count(Client.id)).where(Client.lawyer_id == user.id)
        )).scalar() or 0
    except Exception:
        total_clients = 0

    try:
        # Total consultations & revenue
        consult_q = select(
            func.count(Consultation.id),
            func.coalesce(func.sum(Consultation.fee), 0),
        ).where(
            (Consultation.lawyer_user_id == user.id) | (Consultation.client_user_id == user.id)
        )
        consult_row = (await db.execute(consult_q)).one()
        total_consultations = consult_row[0] or 0
        total_revenue = float(consult_row[1] or 0)

        # Completed-only revenue
        completed_rev = (await db.execute(
            select(func.coalesce(func.sum(Consultation.fee), 0)).where(
                ((Consultation.lawyer_user_id == user.id) | (Consultation.client_user_id == user.id)),
                Consultation.status == ConsultationStatus.COMPLETED,
            )
        )).scalar() or 0
        completed_revenue = float(completed_rev)
    except Exception:
        total_consultations = 0
        total_revenue = 0
        completed_revenue = 0

    # Monthly trends (last 12 months)
    monthly_trends = []
    try:
        now = datetime.utcnow()
        for i in range(11, -1, -1):
            dt = now - timedelta(days=30 * i)
            month = dt.month
            year = dt.year
            cnt = (await db.execute(
                select(func.count(TrackedCase.id)).where(
                    TrackedCase.user_id == user.id,
                    extract("month", TrackedCase.created_at) == month,
                    extract("year", TrackedCase.created_at) == year,
                )
            )).scalar() or 0
            monthly_trends.append({
                "month": _month_label(month),
                "year": year,
                "count": cnt,
            })
    except Exception:
        monthly_trends = [{"month": _month_label((datetime.utcnow().month - 11 + i) % 12 + 1), "year": datetime.utcnow().year, "count": 0} for i in range(12)]

    # Win rate (disposed = won for simplicity)
    disposed = cases_by_status.get(CaseStatus.DISPOSED.value, 0)
    closed = cases_by_status.get(CaseStatus.CLOSED.value, 0)
    finished = disposed + closed
    win_rate = round((disposed / finished * 100) if finished > 0 else 0, 1)

    return {
        "total_cases": total_cases,
        "active_cases": active_cases,
        "total_clients": total_clients,
        "total_consultations": total_consultations,
        "total_revenue": total_revenue,
        "completed_revenue": completed_revenue,
        "win_rate": win_rate,
        "cases_by_status": cases_by_status,
        "monthly_trends": monthly_trends,
    }


# ---------------------------------------------------------------------------
# 2. GET /analytics/case-stats  -- Detailed case statistics
# ---------------------------------------------------------------------------

@router.get("/case-stats", summary="Detailed case statistics")
async def case_stats(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        base = select(TrackedCase).where(TrackedCase.user_id == user.id)
        cases = (await db.execute(base.order_by(TrackedCase.created_at.desc()))).scalars().all()
    except Exception:
        cases = []

    # Status counts
    status_counts = {}
    for c in cases:
        key = c.status.value if hasattr(c.status, "value") else str(c.status)
        status_counts[key] = status_counts.get(key, 0) + 1

    # Cases by category (area of law)
    by_category = {}
    for c in cases:
        cat = c.category or "Uncategorized"
        by_category[cat] = by_category.get(cat, 0) + 1

    # Cases by court
    by_court = {}
    for c in cases:
        court = c.court or "Not specified"
        by_court[court] = by_court.get(court, 0) + 1

    # Average case duration (created_at to updated_at for closed/disposed)
    durations = []
    for c in cases:
        if c.status in (CaseStatus.CLOSED, CaseStatus.DISPOSED) and c.created_at and c.updated_at:
            delta = (c.updated_at - c.created_at).days
            if delta >= 0:
                durations.append(delta)
    avg_duration_days = round(sum(durations) / len(durations), 1) if durations else 0

    # Win / Loss / Settled / Pending breakdown
    disposed_count = status_counts.get(CaseStatus.DISPOSED.value, 0)
    closed_count = status_counts.get(CaseStatus.CLOSED.value, 0)
    pending_count = status_counts.get(CaseStatus.PENDING.value, 0)
    active_count = status_counts.get(CaseStatus.ACTIVE.value, 0)

    return {
        "total": len(cases),
        "status_counts": status_counts,
        "won": disposed_count,
        "lost": closed_count,
        "settled": 0,
        "pending": pending_count + active_count,
        "by_category": by_category,
        "by_court": by_court,
        "avg_duration_days": avg_duration_days,
    }


# ---------------------------------------------------------------------------
# 3. GET /analytics/activity-heatmap  -- Daily activity for past year
# ---------------------------------------------------------------------------

@router.get("/activity-heatmap", summary="Activity heatmap data")
async def activity_heatmap(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    today = datetime.utcnow().date()
    start = today - timedelta(days=364)

    # Aggregate real activity from cases, clients, consultations
    activity: dict[str, int] = {}

    try:
        case_rows = (await db.execute(
            select(
                func.date(TrackedCase.created_at).label("d"),
                func.count(TrackedCase.id),
            )
            .where(TrackedCase.user_id == user.id, TrackedCase.created_at >= datetime.combine(start, datetime.min.time()))
            .group_by(func.date(TrackedCase.created_at))
        )).all()
        for d, cnt in case_rows:
            ds = str(d)
            activity[ds] = activity.get(ds, 0) + cnt
    except Exception:
        pass

    try:
        client_rows = (await db.execute(
            select(
                func.date(Client.created_at).label("d"),
                func.count(Client.id),
            )
            .where(Client.lawyer_id == user.id, Client.created_at >= datetime.combine(start, datetime.min.time()))
            .group_by(func.date(Client.created_at))
        )).all()
        for d, cnt in client_rows:
            ds = str(d)
            activity[ds] = activity.get(ds, 0) + cnt
    except Exception:
        pass

    try:
        consult_rows = (await db.execute(
            select(
                func.date(Consultation.created_at).label("d"),
                func.count(Consultation.id),
            )
            .where(
                ((Consultation.lawyer_user_id == user.id) | (Consultation.client_user_id == user.id)),
                Consultation.created_at >= datetime.combine(start, datetime.min.time()),
            )
            .group_by(func.date(Consultation.created_at))
        )).all()
        for d, cnt in consult_rows:
            ds = str(d)
            activity[ds] = activity.get(ds, 0) + cnt
    except Exception:
        pass

    # Build full 365-day array
    data = []
    for i in range(365):
        d = start + timedelta(days=i)
        ds = str(d)
        data.append({"date": ds, "count": activity.get(ds, 0)})

    return data


# ---------------------------------------------------------------------------
# 4. GET /analytics/performance  -- Lawyer performance metrics
# ---------------------------------------------------------------------------

@router.get("/performance", summary="Performance metrics")
async def performance(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    try:
        cases = (await db.execute(
            select(TrackedCase).where(TrackedCase.user_id == user.id)
        )).scalars().all()
    except Exception:
        cases = []

    total_handled = len(cases)
    disposed = sum(1 for c in cases if c.status == CaseStatus.DISPOSED)
    closed = sum(1 for c in cases if c.status == CaseStatus.CLOSED)
    finished = disposed + closed
    success_rate = round((disposed / finished * 100) if finished > 0 else 0, 1)

    # Average case duration
    durations = []
    for c in cases:
        if c.status in (CaseStatus.CLOSED, CaseStatus.DISPOSED) and c.created_at and c.updated_at:
            delta = (c.updated_at - c.created_at).days
            if delta >= 0:
                durations.append(delta)
    avg_duration = round(sum(durations) / len(durations), 1) if durations else 0

    # Revenue from consultations
    try:
        rev = (await db.execute(
            select(func.coalesce(func.sum(Consultation.fee), 0)).where(
                Consultation.lawyer_user_id == user.id,
                Consultation.status == ConsultationStatus.COMPLETED,
            )
        )).scalar() or 0
        revenue = float(rev)
    except Exception:
        revenue = 0

    # Consultation counts
    try:
        total_consults = (await db.execute(
            select(func.count(Consultation.id)).where(
                (Consultation.lawyer_user_id == user.id) | (Consultation.client_user_id == user.id)
            )
        )).scalar() or 0
        completed_consults = (await db.execute(
            select(func.count(Consultation.id)).where(
                (Consultation.lawyer_user_id == user.id) | (Consultation.client_user_id == user.id),
                Consultation.status == ConsultationStatus.COMPLETED,
            )
        )).scalar() or 0
    except Exception:
        total_consults = 0
        completed_consults = 0

    # Client satisfaction (placeholder -- no reviews table yet)
    client_satisfaction = 4.5 if total_handled > 0 else 0

    return {
        "cases_handled": total_handled,
        "cases_won": disposed,
        "cases_lost": closed,
        "success_rate": success_rate,
        "avg_case_duration_days": avg_duration,
        "revenue_generated": revenue,
        "total_consultations": total_consults,
        "completed_consultations": completed_consults,
        "client_satisfaction": client_satisfaction,
    }
