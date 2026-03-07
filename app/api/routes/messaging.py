"""Internal Messaging API - Secure lawyer-client messaging."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_, func
from typing import Optional
from pydantic import BaseModel, Field
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.messaging import Message, Conversation
from app.core.socketio import emit_message, emit_unread_count
from app.api.routes.notifications import create_and_emit_notification

router = APIRouter(prefix="/messaging", tags=["Messaging"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ConversationResponse(BaseModel):
    id: int
    participant_ids: list[int]
    participant_names: list[str]
    last_message: Optional[str] = None
    last_message_at: Optional[datetime] = None
    unread_count: int = 0

class MessageResponse(BaseModel):
    id: int
    conversation_id: int
    sender_id: int
    sender_name: str
    content: str
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

class SendMessageRequest(BaseModel):
    recipient_id: int
    content: str = Field(..., min_length=1, max_length=10000)

class ReplyRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/conversations", summary="List user conversations")
async def list_conversations(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Conversation).where(
            or_(
                Conversation.user1_id == current_user.id,
                Conversation.user2_id == current_user.id,
            )
        ).order_by(Conversation.updated_at.desc())
    )
    conversations = result.scalars().all()

    items = []
    for conv in conversations:
        other_id = conv.user2_id if conv.user1_id == current_user.id else conv.user1_id
        other_user = (await db.execute(select(User).where(User.id == other_id))).scalar_one_or_none()

        unread = (await db.execute(
            select(func.count(Message.id)).where(
                Message.conversation_id == conv.id,
                Message.sender_id != current_user.id,
                Message.is_read == False,
            )
        )).scalar() or 0

        last_msg = (await db.execute(
            select(Message).where(Message.conversation_id == conv.id)
            .order_by(Message.created_at.desc()).limit(1)
        )).scalar_one_or_none()

        items.append({
            "id": conv.id,
            "participant_ids": [conv.user1_id, conv.user2_id],
            "participant_names": [
                current_user.full_name,
                other_user.full_name if other_user else "Unknown",
            ],
            "other_user": {
                "id": other_id,
                "name": other_user.full_name if other_user else "Unknown",
                "role": other_user.role.value if other_user else "",
            },
            "last_message": last_msg.content[:100] if last_msg else None,
            "last_message_at": str(last_msg.created_at) if last_msg else None,
            "unread_count": unread,
        })

    return items


@router.post("/send", summary="Send a message (creates conversation if needed)")
async def send_message(
    request: SendMessageRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if request.recipient_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot message yourself")

    recipient = (await db.execute(select(User).where(User.id == request.recipient_id))).scalar_one_or_none()
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")

    # Find or create conversation
    u1, u2 = sorted([current_user.id, request.recipient_id])
    result = await db.execute(
        select(Conversation).where(Conversation.user1_id == u1, Conversation.user2_id == u2)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        conv = Conversation(user1_id=u1, user2_id=u2)
        db.add(conv)
        await db.flush()

    msg = Message(
        conversation_id=conv.id,
        sender_id=current_user.id,
        content=request.content,
    )
    db.add(msg)
    conv.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(msg)

    msg_data = {
        "id": msg.id,
        "conversation_id": conv.id,
        "sender_id": current_user.id,
        "sender_name": current_user.full_name,
        "content": msg.content,
        "is_read": False,
        "created_at": str(msg.created_at),
    }

    # Emit real-time message to conversation room
    await emit_message(conv.id, msg_data, exclude_user_id=current_user.id)

    # Emit unread count update to recipient
    recipient_convs = (await db.execute(
        select(Conversation.id).where(
            or_(Conversation.user1_id == request.recipient_id, Conversation.user2_id == request.recipient_id)
        )
    )).scalars().all()
    if recipient_convs:
        unread = (await db.execute(
            select(func.count(Message.id)).where(
                Message.conversation_id.in_(recipient_convs),
                Message.sender_id != request.recipient_id,
                Message.is_read == False,
            )
        )).scalar() or 0
        await emit_unread_count(request.recipient_id, unread)

    # Send notification to recipient
    await create_and_emit_notification(
        user_id=request.recipient_id,
        title="New Message",
        message=f"{current_user.full_name}: {request.content[:100]}",
        link="/messaging",
    )

    return msg_data


@router.get("/conversations/{conversation_id}/messages", summary="Get messages in conversation")
async def get_messages(
    conversation_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    conv = (await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            or_(Conversation.user1_id == current_user.id, Conversation.user2_id == current_user.id),
        )
    )).scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Mark messages as read
    unread_msgs = (await db.execute(
        select(Message).where(
            Message.conversation_id == conversation_id,
            Message.sender_id != current_user.id,
            Message.is_read == False,
        )
    )).scalars().all()
    for m in unread_msgs:
        m.is_read = True

    result = await db.execute(
        select(Message).where(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.desc()).offset(skip).limit(limit)
    )
    messages = result.scalars().all()

    items = []
    for msg in reversed(messages):
        sender = (await db.execute(select(User).where(User.id == msg.sender_id))).scalar_one_or_none()
        items.append({
            "id": msg.id,
            "conversation_id": msg.conversation_id,
            "sender_id": msg.sender_id,
            "sender_name": sender.full_name if sender else "Unknown",
            "content": msg.content,
            "is_read": msg.is_read,
            "created_at": str(msg.created_at),
        })

    return items


@router.get("/unread-count", summary="Get total unread message count")
async def unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Get all conversations for this user
    convs = (await db.execute(
        select(Conversation.id).where(
            or_(Conversation.user1_id == current_user.id, Conversation.user2_id == current_user.id)
        )
    )).scalars().all()

    count = 0
    if convs:
        count = (await db.execute(
            select(func.count(Message.id)).where(
                Message.conversation_id.in_(convs),
                Message.sender_id != current_user.id,
                Message.is_read == False,
            )
        )).scalar() or 0

    return {"unread_count": count}
