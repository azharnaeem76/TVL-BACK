"""Support Ticket API."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import Optional
from pydantic import BaseModel, Field
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.models.support import SupportTicket, TicketReply, TicketStatus, TicketPriority

router = APIRouter(prefix="/support", tags=["Support"])

CATEGORIES = ["general", "bug", "feature_request", "billing", "account", "legal_content", "other"]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class CreateTicketRequest(BaseModel):
    subject: str = Field(..., min_length=3, max_length=500)
    description: str = Field(..., min_length=10, max_length=10000)
    category: str = "general"
    priority: str = "medium"


class ReplyRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=10000)


class UpdateTicketRequest(BaseModel):
    status: Optional[str] = None
    priority: Optional[str] = None
    assigned_to: Optional[int] = None
    resolution_note: Optional[str] = None


def _is_staff(user: User) -> bool:
    return user.role in (UserRole.ADMIN, UserRole.SUPPORT)


# ---------------------------------------------------------------------------
# User Routes
# ---------------------------------------------------------------------------

@router.post("/tickets", summary="Create a support ticket")
async def create_ticket(
    request: CreateTicketRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = SupportTicket(
        user_id=current_user.id,
        subject=request.subject,
        description=request.description,
        category=request.category if request.category in CATEGORIES else "general",
        priority=TicketPriority(request.priority) if request.priority in [p.value for p in TicketPriority] else TicketPriority.MEDIUM,
    )
    db.add(ticket)
    await db.flush()
    await db.refresh(ticket)

    # Notify support/admin
    from app.api.routes.notifications import create_and_emit_notification
    from app.models.features import NotificationType
    staff = (await db.execute(
        select(User).where(User.role.in_([UserRole.ADMIN, UserRole.SUPPORT]))
    )).scalars().all()
    for s in staff:
        await create_and_emit_notification(
            user_id=s.id,
            title="New Support Ticket",
            message=f"#{ticket.id}: {ticket.subject} (from {current_user.full_name})",
            notif_type=NotificationType.SYSTEM,
            link="/support",
        )

    return {
        "id": ticket.id,
        "subject": ticket.subject,
        "status": ticket.status.value,
        "created_at": str(ticket.created_at),
    }


@router.get("/tickets", summary="List tickets (user sees own, staff sees all)")
async def list_tickets(
    status_filter: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base = select(SupportTicket)
    count_q = select(func.count(SupportTicket.id))

    if _is_staff(current_user):
        pass  # staff sees all
    else:
        base = base.where(SupportTicket.user_id == current_user.id)
        count_q = count_q.where(SupportTicket.user_id == current_user.id)

    if status_filter:
        try:
            st = TicketStatus(status_filter)
            base = base.where(SupportTicket.status == st)
            count_q = count_q.where(SupportTicket.status == st)
        except ValueError:
            pass

    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(
        base.order_by(SupportTicket.updated_at.desc()).offset(skip).limit(limit)
    )).scalars().all()

    items = []
    for t in rows:
        user = (await db.execute(select(User).where(User.id == t.user_id))).scalar_one_or_none()
        assigned = None
        if t.assigned_to:
            assigned_user = (await db.execute(select(User).where(User.id == t.assigned_to))).scalar_one_or_none()
            assigned = assigned_user.full_name if assigned_user else None
        items.append({
            "id": t.id,
            "user_id": t.user_id,
            "user_name": user.full_name if user else "Unknown",
            "user_email": user.email if user else "",
            "subject": t.subject,
            "description": t.description,
            "category": t.category,
            "status": t.status.value,
            "priority": t.priority.value,
            "assigned_to": t.assigned_to,
            "assigned_name": assigned,
            "resolution_note": t.resolution_note,
            "created_at": str(t.created_at),
            "updated_at": str(t.updated_at),
        })

    return {"items": items, "total": total}


@router.get("/tickets/{ticket_id}", summary="Get ticket details with replies")
async def get_ticket(
    ticket_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = (await db.execute(
        select(SupportTicket).where(SupportTicket.id == ticket_id)
    )).scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if not _is_staff(current_user) and ticket.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    user = (await db.execute(select(User).where(User.id == ticket.user_id))).scalar_one_or_none()

    replies_rows = (await db.execute(
        select(TicketReply).where(TicketReply.ticket_id == ticket_id)
        .order_by(TicketReply.created_at.asc())
    )).scalars().all()

    replies = []
    for r in replies_rows:
        reply_user = (await db.execute(select(User).where(User.id == r.user_id))).scalar_one_or_none()
        replies.append({
            "id": r.id,
            "user_id": r.user_id,
            "user_name": reply_user.full_name if reply_user else "Unknown",
            "message": r.message,
            "is_staff": r.is_staff,
            "created_at": str(r.created_at),
        })

    return {
        "id": ticket.id,
        "user_id": ticket.user_id,
        "user_name": user.full_name if user else "Unknown",
        "user_email": user.email if user else "",
        "subject": ticket.subject,
        "description": ticket.description,
        "category": ticket.category,
        "status": ticket.status.value,
        "priority": ticket.priority.value,
        "assigned_to": ticket.assigned_to,
        "resolution_note": ticket.resolution_note,
        "created_at": str(ticket.created_at),
        "updated_at": str(ticket.updated_at),
        "replies": replies,
    }


@router.post("/tickets/{ticket_id}/reply", summary="Reply to a ticket")
async def reply_to_ticket(
    ticket_id: int,
    request: ReplyRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = (await db.execute(
        select(SupportTicket).where(SupportTicket.id == ticket_id)
    )).scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if not _is_staff(current_user) and ticket.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Access denied")

    reply = TicketReply(
        ticket_id=ticket_id,
        user_id=current_user.id,
        message=request.message,
        is_staff=_is_staff(current_user),
    )
    db.add(reply)

    # If staff replies, set to in_progress if still open
    if _is_staff(current_user) and ticket.status == TicketStatus.OPEN:
        ticket.status = TicketStatus.IN_PROGRESS
        if not ticket.assigned_to:
            ticket.assigned_to = current_user.id

    await db.flush()
    await db.refresh(reply)

    # Notify the other party
    from app.api.routes.notifications import create_and_emit_notification
    from app.models.features import NotificationType
    notify_user_id = ticket.user_id if _is_staff(current_user) else None
    if notify_user_id:
        await create_and_emit_notification(
            user_id=notify_user_id,
            title="Support Reply",
            message=f"New reply on ticket #{ticket.id}: {ticket.subject}",
            notif_type=NotificationType.SYSTEM,
            link="/support",
        )

    return {
        "id": reply.id,
        "message": reply.message,
        "is_staff": reply.is_staff,
        "created_at": str(reply.created_at),
    }


@router.put("/tickets/{ticket_id}", summary="Update ticket (staff only for status/assignment)")
async def update_ticket(
    ticket_id: int,
    request: UpdateTicketRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    ticket = (await db.execute(
        select(SupportTicket).where(SupportTicket.id == ticket_id)
    )).scalar_one_or_none()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    if not _is_staff(current_user):
        raise HTTPException(status_code=403, detail="Staff only")

    if request.status:
        try:
            ticket.status = TicketStatus(request.status)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid status")
    if request.priority:
        try:
            ticket.priority = TicketPriority(request.priority)
        except ValueError:
            pass
    if request.assigned_to is not None:
        ticket.assigned_to = request.assigned_to
    if request.resolution_note is not None:
        ticket.resolution_note = request.resolution_note

    await db.flush()

    # Notify user if resolved
    if request.status in ("resolved", "closed"):
        from app.api.routes.notifications import create_and_emit_notification
        from app.models.features import NotificationType
        await create_and_emit_notification(
            user_id=ticket.user_id,
            title=f"Ticket {request.status.title()}",
            message=f"Your ticket #{ticket.id} ({ticket.subject}) has been {request.status}.",
            notif_type=NotificationType.SYSTEM,
            link="/support",
        )

    return {"ok": True}


@router.get("/categories", summary="List ticket categories")
async def get_categories():
    return CATEGORIES


# ---------------------------------------------------------------------------
# Support role: switch view role
# ---------------------------------------------------------------------------

@router.post("/switch-role", summary="Support: temporarily view system as another role")
async def switch_view_role(
    role: str = Query(...),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.SUPPORT:
        raise HTTPException(status_code=403, detail="Support role only")

    # Cannot switch to admin
    if role == "admin":
        raise HTTPException(status_code=403, detail="Cannot impersonate admin")

    allowed = [r.value for r in UserRole if r not in (UserRole.ADMIN, UserRole.SUPPORT)]
    if role not in allowed:
        raise HTTPException(status_code=400, detail=f"Invalid role. Allowed: {allowed}")

    # Return a new token with the role claim but same user id
    from app.core.security import create_access_token
    token = create_access_token({"sub": current_user.id, "view_as": role})
    return {
        "token": token,
        "view_as": role,
        "message": f"Viewing system as {role}. Use this token to browse as that role.",
    }
