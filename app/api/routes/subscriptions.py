"""Subscription management API."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole, SubscriptionPlan

router = APIRouter(prefix="/subscriptions", tags=["Subscriptions"])


# ---------------------------------------------------------------------------
# Plan limits configuration
# ---------------------------------------------------------------------------

PLAN_LIMITS = {
    SubscriptionPlan.FREE: {
        "ai_chat_daily": 5,
        "search_results": 10,
        "document_analysis_monthly": 0,
        "ai_tools": False,
        "case_tracker": False,
        "client_crm": False,
        "citation_finder": False,
        "team_workspaces": 0,
        "messaging": False,
        "consultation_booking": False,
        "audit_logs": False,
        "exam_prep": True,
    },
    SubscriptionPlan.PRO: {
        "ai_chat_daily": -1,  # unlimited
        "search_results": -1,
        "document_analysis_monthly": 20,
        "ai_tools": True,
        "case_tracker": True,
        "client_crm": True,
        "citation_finder": True,
        "team_workspaces": 0,
        "messaging": False,
        "consultation_booking": False,
        "audit_logs": False,
        "exam_prep": True,
    },
    SubscriptionPlan.FIRM: {
        "ai_chat_daily": -1,
        "search_results": -1,
        "document_analysis_monthly": -1,
        "ai_tools": True,
        "case_tracker": True,
        "client_crm": True,
        "citation_finder": True,
        "team_workspaces": 10,
        "messaging": True,
        "consultation_booking": True,
        "audit_logs": True,
        "exam_prep": True,
    },
}


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PlanInfo(BaseModel):
    plan: str
    expires_at: str | None = None
    limits: dict


class UpgradeRequest(BaseModel):
    plan: str


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/my-plan", summary="Get current subscription plan and limits")
async def get_my_plan(current_user: User = Depends(get_current_user)):
    plan = getattr(current_user, 'plan', None) or SubscriptionPlan.FREE
    limits = PLAN_LIMITS.get(plan, PLAN_LIMITS[SubscriptionPlan.FREE])
    expires_at = getattr(current_user, 'plan_expires_at', None)

    return {
        "plan": plan.value if hasattr(plan, 'value') else str(plan),
        "expires_at": str(expires_at) if expires_at else None,
        "limits": limits,
    }


@router.post("/upgrade", summary="Request plan upgrade (admin processes)")
async def request_upgrade(
    request: UpgradeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        new_plan = SubscriptionPlan(request.plan)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid plan")

    current_plan = getattr(current_user, 'plan', SubscriptionPlan.FREE)
    if new_plan == current_plan:
        raise HTTPException(status_code=400, detail="Already on this plan")

    # For now, admin manually upgrades. This creates a notification.
    from app.api.routes.notifications import create_and_emit_notification
    from app.models.features import NotificationType

    # Notify admins
    admins = (await db.execute(
        select(User).where(User.role == UserRole.ADMIN)
    )).scalars().all()

    for admin in admins:
        await create_and_emit_notification(
            user_id=admin.id,
            title="Plan Upgrade Request",
            message=f"{current_user.full_name} ({current_user.email}) requested upgrade to {new_plan.value.upper()} plan.",
            notif_type=NotificationType.SYSTEM,
            link="/admin",
        )

    return {"message": f"Upgrade request to {new_plan.value.upper()} submitted. Admin will process your request."}


@router.put("/set-plan/{user_id}", summary="Admin: set user plan")
async def admin_set_plan(
    user_id: int,
    request: UpgradeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role not in (UserRole.ADMIN, UserRole.SUPPORT):
        raise HTTPException(status_code=403, detail="Admin or support only")

    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    try:
        new_plan = SubscriptionPlan(request.plan)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid plan")

    user.plan = new_plan
    await db.flush()

    from app.api.routes.notifications import create_and_emit_notification
    from app.models.features import NotificationType
    await create_and_emit_notification(
        user_id=user.id,
        title="Plan Updated",
        message=f"Your subscription has been updated to {new_plan.value.upper()}.",
        notif_type=NotificationType.SYSTEM,
        link="/subscriptions",
    )

    return {"message": f"User {user.full_name} upgraded to {new_plan.value.upper()}"}
