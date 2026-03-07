"""Socket.IO server integration for real-time notifications and messaging."""
import logging
import socketio
from jose import jwt, JWTError
from sqlalchemy import select
from app.core.config import get_settings
from app.core.database import async_session
from app.models.user import User

logger = logging.getLogger(__name__)
settings = get_settings()

# Create async Socket.IO server
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=["http://localhost:3000", "http://localhost:3001"],
    logger=False,
    engineio_logger=False,
)

# Map user_id -> set of sid(s) (a user can have multiple tabs)
user_sids: dict[int, set[str]] = {}
# Map sid -> user_id
sid_user: dict[str, int] = {}


async def _get_user_from_token(token: str) -> User | None:
    """Validate JWT and return user."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id_str = payload.get("sub")
        if not user_id_str:
            return None
        async with async_session() as session:
            result = await session.execute(select(User).where(User.id == int(user_id_str)))
            return result.scalar_one_or_none()
    except (JWTError, ValueError):
        return None


@sio.event
async def connect(sid, environ, auth):
    """Authenticate on connect using JWT token."""
    token = None
    if auth and isinstance(auth, dict):
        token = auth.get("token")

    if not token:
        logger.warning(f"Socket connect rejected: no token (sid={sid})")
        raise socketio.exceptions.ConnectionRefusedError("Authentication required")

    user = await _get_user_from_token(token)
    if not user:
        logger.warning(f"Socket connect rejected: invalid token (sid={sid})")
        raise socketio.exceptions.ConnectionRefusedError("Invalid token")

    # Track connection
    sid_user[sid] = user.id
    if user.id not in user_sids:
        user_sids[user.id] = set()
    user_sids[user.id].add(sid)

    # Join personal room for targeted events
    await sio.enter_room(sid, f"user_{user.id}")

    logger.info(f"Socket connected: user={user.id} sid={sid}")


@sio.event
async def disconnect(sid):
    """Clean up on disconnect."""
    user_id = sid_user.pop(sid, None)
    if user_id and user_id in user_sids:
        user_sids[user_id].discard(sid)
        if not user_sids[user_id]:
            del user_sids[user_id]
    logger.info(f"Socket disconnected: user={user_id} sid={sid}")


@sio.event
async def join_conversation(sid, data):
    """Join a conversation room for real-time messages."""
    user_id = sid_user.get(sid)
    if not user_id:
        return
    conv_id = data.get("conversation_id") if isinstance(data, dict) else None
    if conv_id:
        await sio.enter_room(sid, f"conv_{conv_id}")


@sio.event
async def leave_conversation(sid, data):
    """Leave a conversation room."""
    conv_id = data.get("conversation_id") if isinstance(data, dict) else None
    if conv_id:
        await sio.leave_room(sid, f"conv_{conv_id}")


# ---------------------------------------------------------------------------
# Helper functions to emit events from backend routes
# ---------------------------------------------------------------------------

async def emit_notification(user_id: int, notification: dict):
    """Send a real-time notification to a specific user."""
    await sio.emit("new_notification", notification, room=f"user_{user_id}")


async def emit_message(conversation_id: int, message: dict, exclude_user_id: int | None = None):
    """Send a real-time message to all users in a conversation."""
    exclude_sids = []
    if exclude_user_id and exclude_user_id in user_sids:
        exclude_sids = list(user_sids[exclude_user_id])

    # Emit to conversation room
    await sio.emit("new_message", message, room=f"conv_{conversation_id}")

    # Also emit unread update to the recipient (via their personal room)
    # The sender already has the message from the API response
    await sio.emit("unread_update", {"conversation_id": conversation_id}, room=f"conv_{conversation_id}")


async def emit_unread_count(user_id: int, count: int):
    """Send updated unread count to a user."""
    await sio.emit("unread_count", {"unread_count": count}, room=f"user_{user_id}")
