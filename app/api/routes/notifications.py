"""Notifications API."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, update
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from app.core.database import get_db, async_session
from app.core.security import get_current_user
from app.models.user import User
from app.models.features import Notification, NotificationType
from app.core.socketio import emit_notification

router = APIRouter(prefix="/notifications", tags=["Notifications"])


class NotificationResponse(BaseModel):
    id: int
    type: NotificationType
    title: str
    message: str
    is_read: bool
    link: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class NotificationCreate(BaseModel):
    type: NotificationType = NotificationType.SYSTEM
    title: str
    message: str
    link: Optional[str] = None


@router.get("/", response_model=dict, summary="Get user notifications")
async def get_notifications(
    unread_only: bool = Query(False),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    base = select(Notification).where(Notification.user_id == user.id)
    count_q = select(func.count(Notification.id)).where(Notification.user_id == user.id)

    if unread_only:
        base = base.where(Notification.is_read == False)
        count_q = count_q.where(Notification.is_read == False)

    total = (await db.execute(count_q)).scalar() or 0
    unread = (await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user.id, Notification.is_read == False
        )
    )).scalar() or 0

    rows = (await db.execute(
        base.order_by(Notification.created_at.desc()).offset(skip).limit(limit)
    )).scalars().all()

    return {
        "items": [NotificationResponse.model_validate(n) for n in rows],
        "total": total,
        "unread": unread,
    }


@router.put("/read-all", summary="Mark all notifications as read")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await db.execute(
        update(Notification).where(
            Notification.user_id == user.id, Notification.is_read == False
        ).values(is_read=True)
    )
    await db.flush()
    return {"ok": True}


@router.put("/{notification_id}/read", summary="Mark notification as read")
async def mark_as_read(
    notification_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Notification).where(Notification.id == notification_id, Notification.user_id == user.id)
    )
    notif = result.scalar_one_or_none()
    if not notif:
        raise HTTPException(status_code=404, detail="Notification not found")
    notif.is_read = True
    await db.flush()
    return {"ok": True}


@router.get("/unread-count", summary="Get unread notification count")
async def unread_count(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    count = (await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == user.id, Notification.is_read == False
        )
    )).scalar() or 0
    return {"unread_count": count}


# ---------------------------------------------------------------------------
# Helper: create a notification and push via Socket.IO
# ---------------------------------------------------------------------------

async def create_and_emit_notification(
    user_id: int,
    title: str,
    message: str,
    notif_type: NotificationType = NotificationType.SYSTEM,
    link: str | None = None,
):
    """Create a notification in DB and emit it via Socket.IO in real time."""
    async with async_session() as session:
        notif = Notification(
            user_id=user_id,
            type=notif_type,
            title=title,
            message=message,
            link=link,
        )
        session.add(notif)
        await session.flush()
        await session.refresh(notif)

        await emit_notification(user_id, {
            "id": notif.id,
            "type": notif.type.value if hasattr(notif.type, 'value') else str(notif.type),
            "title": notif.title,
            "message": notif.message,
            "is_read": False,
            "link": notif.link,
            "created_at": str(notif.created_at),
        })

        await session.commit()
