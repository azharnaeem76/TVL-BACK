"""Internal Messaging API - Secure lawyer-client messaging."""
import os
import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile, File, Form
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

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads", "messages")
os.makedirs(UPLOAD_DIR, exist_ok=True)

ALLOWED_IMAGE_TYPES = {"image/jpeg", "image/png", "image/gif", "image/webp"}
ALLOWED_VIDEO_TYPES = {"video/mp4", "video/webm", "video/quicktime"}
ALLOWED_AUDIO_TYPES = {"audio/webm", "audio/ogg", "audio/mp4", "audio/mpeg", "audio/wav"}
MAX_FILE_SIZE = 25 * 1024 * 1024  # 25MB


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
    content: Optional[str] = None
    message_type: str = "text"
    file_url: Optional[str] = None
    file_name: Optional[str] = None
    file_size: Optional[int] = None
    duration: Optional[int] = None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True

class SendMessageRequest(BaseModel):
    recipient_id: int
    content: str = Field(..., min_length=1, max_length=10000)

class ReplyRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=10000)


def _msg_to_dict(msg: Message, sender_name: str) -> dict:
    return {
        "id": msg.id,
        "conversation_id": msg.conversation_id,
        "sender_id": msg.sender_id,
        "sender_name": sender_name,
        "content": msg.content,
        "message_type": msg.message_type or "text",
        "file_url": msg.file_url,
        "file_name": msg.file_name,
        "file_size": msg.file_size,
        "duration": msg.duration,
        "is_read": msg.is_read,
        "created_at": str(msg.created_at),
    }


async def _get_or_create_conv(db: AsyncSession, user1_id: int, user2_id: int) -> Conversation:
    u1, u2 = sorted([user1_id, user2_id])
    result = await db.execute(
        select(Conversation).where(Conversation.user1_id == u1, Conversation.user2_id == u2)
    )
    conv = result.scalar_one_or_none()
    if not conv:
        conv = Conversation(user1_id=u1, user2_id=u2)
        db.add(conv)
        await db.flush()
    return conv


async def _emit_after_send(db: AsyncSession, conv: Conversation, msg: Message, current_user: User, recipient_id: int):
    msg_data = _msg_to_dict(msg, current_user.full_name)

    await emit_message(conv.id, msg_data, exclude_user_id=current_user.id)

    recipient_convs = (await db.execute(
        select(Conversation.id).where(
            or_(Conversation.user1_id == recipient_id, Conversation.user2_id == recipient_id)
        )
    )).scalars().all()
    if recipient_convs:
        unread = (await db.execute(
            select(func.count(Message.id)).where(
                Message.conversation_id.in_(recipient_convs),
                Message.sender_id != recipient_id,
                Message.is_read == False,
            )
        )).scalar() or 0
        await emit_unread_count(recipient_id, unread)

    preview = msg.content[:100] if msg.content else f"[{msg.message_type}]"
    await create_and_emit_notification(
        user_id=recipient_id,
        title="New Message",
        message=f"{current_user.full_name}: {preview}",
        link="/messaging",
    )

    return msg_data


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

        last_preview = None
        if last_msg:
            if last_msg.message_type == "text":
                last_preview = last_msg.content[:100] if last_msg.content else None
            else:
                last_preview = f"[{last_msg.message_type}]"

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
            "last_message": last_preview,
            "last_message_at": str(last_msg.created_at) if last_msg else None,
            "unread_count": unread,
        })

    return items


@router.post("/send", summary="Send a text message (creates conversation if needed)")
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

    conv = await _get_or_create_conv(db, current_user.id, request.recipient_id)

    msg = Message(
        conversation_id=conv.id,
        sender_id=current_user.id,
        content=request.content,
        message_type="text",
    )
    db.add(msg)
    conv.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(msg)

    return await _emit_after_send(db, conv, msg, current_user, request.recipient_id)


@router.post("/send-file", summary="Send a file/image/video/voice message")
async def send_file_message(
    recipient_id: int = Form(...),
    file: UploadFile = File(...),
    message_type: str = Form("file"),
    duration: Optional[int] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if recipient_id == current_user.id:
        raise HTTPException(status_code=400, detail="Cannot message yourself")

    recipient = (await db.execute(select(User).where(User.id == recipient_id))).scalar_one_or_none()
    if not recipient:
        raise HTTPException(status_code=404, detail="Recipient not found")

    # Validate file type
    content_type = file.content_type or ""
    if message_type == "image" and content_type not in ALLOWED_IMAGE_TYPES:
        raise HTTPException(status_code=400, detail="Invalid image type. Allowed: JPEG, PNG, GIF, WebP")
    if message_type == "video" and content_type not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(status_code=400, detail="Invalid video type. Allowed: MP4, WebM")
    if message_type == "voice" and content_type not in ALLOWED_AUDIO_TYPES:
        raise HTTPException(status_code=400, detail="Invalid audio type")

    # Read and validate size
    file_bytes = await file.read()
    if len(file_bytes) > MAX_FILE_SIZE:
        raise HTTPException(status_code=400, detail="File too large. Max 25MB")

    # Save file
    ext = os.path.splitext(file.filename or "file")[1] or ".bin"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    file_path = os.path.join(UPLOAD_DIR, unique_name)

    with open(file_path, "wb") as f:
        f.write(file_bytes)

    file_url = f"/api/v1/messaging/files/{unique_name}"

    conv = await _get_or_create_conv(db, current_user.id, recipient_id)

    msg = Message(
        conversation_id=conv.id,
        sender_id=current_user.id,
        content=None,
        message_type=message_type,
        file_url=file_url,
        file_name=file.filename,
        file_size=len(file_bytes),
        duration=duration,
    )
    db.add(msg)
    conv.updated_at = datetime.utcnow()
    await db.flush()
    await db.refresh(msg)

    return await _emit_after_send(db, conv, msg, current_user, recipient_id)


@router.get("/files/{filename}", summary="Serve uploaded file")
async def serve_file(filename: str):
    from fastapi.responses import FileResponse

    file_path = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="File not found")

    # Security: prevent directory traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")

    return FileResponse(file_path)


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
        items.append(_msg_to_dict(msg, sender.full_name if sender else "Unknown"))

    return items


@router.get("/unread-count", summary="Get total unread message count")
async def unread_count(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
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
