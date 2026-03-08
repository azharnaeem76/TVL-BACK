import os
import uuid
import httpx
import logging
from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from pydantic import BaseModel
from typing import Optional
from app.core.database import get_db
from app.core.config import get_settings
from app.core.security import hash_password, verify_password, create_access_token, get_current_user
from app.models.user import User, UserRole
from app.models.features import Notification, NotificationType
import secrets
from app.schemas.user import UserCreate, UserLogin, UserResponse, TokenResponse, ALLOWED_REGISTRATION_ROLES
from app.services.email_service import send_welcome_email

AVATAR_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads", "avatars")
os.makedirs(AVATAR_DIR, exist_ok=True)

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/auth", tags=["Authentication"])


# ---------------------------------------------------------------------------
# Google OAuth schema
# ---------------------------------------------------------------------------

class GoogleLoginRequest(BaseModel):
    token: str  # Google ID token or access token
    role: Optional[UserRole] = UserRole.CLIENT


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
    description="Create a new account with role selection. Returns JWT token and user profile.",
)
async def register(user_data: UserCreate, db: AsyncSession = Depends(get_db)):
    if user_data.role not in ALLOWED_REGISTRATION_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role for registration")

    result = await db.execute(select(User).where(User.email == user_data.email))
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = User(
        email=user_data.email,
        full_name=user_data.full_name,
        hashed_password=hash_password(user_data.password),
        role=user_data.role,
        phone=user_data.phone,
        city=user_data.city,
        bar_number=user_data.bar_number,
        specialization=user_data.specialization,
        preferred_language=user_data.preferred_language,
    )
    db.add(user)
    await db.flush()

    # Send welcome email (non-blocking, won't fail registration)
    try:
        send_welcome_email(user.email, user.full_name, user.role.value)
    except Exception as e:
        logger.warning(f"Welcome email failed: {e}")

    # Create welcome notification
    db.add(Notification(
        user_id=user.id,
        type=NotificationType.WELCOME,
        title="Welcome to TVL!",
        message=f"Welcome {user.full_name}! Your account has been created. Explore the platform and start your legal research.",
        link="/dashboard",
    ))
    await db.flush()

    token = create_access_token({"sub": user.id})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Login with email and password",
    description="Authenticate and receive a JWT token. Demo: lawyer@tvl.pk / demo123",
)
async def login(credentials: UserLogin, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.email == credentials.email))
    user = result.scalar_one_or_none()

    if not user or not verify_password(credentials.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    if getattr(user, 'is_suspended', False):
        reason = getattr(user, 'suspension_reason', None) or "Contact support for details"
        raise HTTPException(status_code=403, detail=f"Account is suspended: {reason}")

    # Ensure user has at least a welcome notification (backfill for existing users)
    notif_count = (await db.execute(
        select(func.count(Notification.id)).where(Notification.user_id == user.id)
    )).scalar() or 0
    if notif_count == 0:
        db.add(Notification(
            user_id=user.id,
            type=NotificationType.WELCOME,
            title="Welcome to TVL!",
            message=f"Welcome {user.full_name}! Explore the platform and start your legal research.",
            link="/dashboard",
        ))
        await db.flush()

    token = create_access_token({"sub": user.id})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


# ---------------------------------------------------------------------------
# Google OAuth
# ---------------------------------------------------------------------------

@router.post(
    "/google",
    response_model=TokenResponse,
    summary="Login or register with Google",
    description="Authenticate using a Google OAuth token. Creates account if new user.",
)
async def google_login(payload: GoogleLoginRequest, db: AsyncSession = Depends(get_db)):
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(status_code=501, detail="Google login is not configured")

    # Verify the Google token
    try:
        async with httpx.AsyncClient() as client:
            resp = await client.get(
                f"https://www.googleapis.com/oauth2/v3/tokeninfo?id_token={payload.token}"
            )
            if resp.status_code != 200:
                # Try as access token
                resp = await client.get(
                    "https://www.googleapis.com/oauth2/v3/userinfo",
                    headers={"Authorization": f"Bearer {payload.token}"},
                )
            if resp.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid Google token")

            google_data = resp.json()
    except httpx.HTTPError:
        raise HTTPException(status_code=401, detail="Failed to verify Google token")

    email = google_data.get("email")
    name = google_data.get("name") or google_data.get("given_name", "User")

    if not email:
        raise HTTPException(status_code=400, detail="Google account has no email")

    if payload.role not in ALLOWED_REGISTRATION_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role for registration")

    # Check if user exists
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if user:
        # Existing user - login
        if not user.is_active:
            raise HTTPException(status_code=403, detail="Account is deactivated")
        if getattr(user, 'is_suspended', False):
            reason = getattr(user, 'suspension_reason', None) or "Contact support for details"
            raise HTTPException(status_code=403, detail=f"Account is suspended: {reason}")
    else:
        # New user - register
        user = User(
            email=email,
            full_name=name,
            hashed_password=hash_password(secrets.token_urlsafe(32)),  # Random password for OAuth users
            role=payload.role,
        )
        db.add(user)
        await db.flush()

        # Send welcome email
        try:
            send_welcome_email(email, name, payload.role.value)
        except Exception as e:
            logger.warning(f"Welcome email failed: {e}")

        # Welcome notification
        db.add(Notification(
            user_id=user.id,
            type=NotificationType.WELCOME,
            title="Welcome to TVL!",
            message=f"Welcome {name}! Your account has been created via Google. Explore the platform!",
            link="/dashboard",
        ))
        await db.flush()

    token = create_access_token({"sub": user.id})
    return TokenResponse(
        access_token=token,
        user=UserResponse.model_validate(user),
    )


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Get current user profile",
    description="Returns the profile of the currently authenticated user.",
)
async def get_me(current_user: User = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)


# ---------------------------------------------------------------------------
# Profile Update
# ---------------------------------------------------------------------------

class ProfileUpdate(BaseModel):
    full_name: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    specialization: Optional[str] = None
    bar_number: Optional[str] = None
    bio: Optional[str] = None
    preferred_language: Optional[str] = None


@router.put(
    "/me",
    response_model=UserResponse,
    summary="Update current user profile",
    description="Update profile fields like name, phone, city, specialization.",
)
async def update_me(
    payload: ProfileUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(current_user, field, value)
    await db.flush()
    await db.refresh(current_user)
    # Update localStorage user data on next request
    return UserResponse.model_validate(current_user)


# ---------------------------------------------------------------------------
# Profile Picture Upload
# ---------------------------------------------------------------------------

@router.post(
    "/me/avatar",
    response_model=UserResponse,
    summary="Upload profile picture",
)
async def upload_avatar(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    allowed = {"image/jpeg", "image/png", "image/gif", "image/webp"}
    if file.content_type not in allowed:
        raise HTTPException(status_code=400, detail="Only JPEG, PNG, GIF, WebP images are allowed")
    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Image too large. Max 5MB")
    ext = os.path.splitext(file.filename or "avatar.jpg")[1] or ".jpg"
    unique_name = f"{uuid.uuid4().hex}{ext}"
    with open(os.path.join(AVATAR_DIR, unique_name), "wb") as f:
        f.write(data)
    current_user.profile_picture = f"/api/v1/auth/avatars/{unique_name}"
    await db.flush()
    await db.refresh(current_user)
    return UserResponse.model_validate(current_user)


@router.get("/avatars/{filename}", summary="Serve avatar image")
async def serve_avatar(filename: str):
    from fastapi.responses import FileResponse
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = os.path.join(AVATAR_DIR, filename)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="Not found")
    return FileResponse(path)


# ---------------------------------------------------------------------------
# Password Change
# ---------------------------------------------------------------------------

class PasswordChange(BaseModel):
    current_password: str
    new_password: str


@router.put(
    "/change-password",
    summary="Change password",
    description="Change password for the currently authenticated user.",
)
async def change_password(
    payload: PasswordChange,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not verify_password(payload.current_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="New password must be at least 6 characters")
    current_user.hashed_password = hash_password(payload.new_password)
    await db.flush()
    return {"ok": True, "message": "Password changed successfully"}


# ---------------------------------------------------------------------------
# Password Reset (forgot password)
# ---------------------------------------------------------------------------

class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    token: str
    new_password: str


@router.post(
    "/forgot-password",
    summary="Request password reset",
    description="Send a password reset link to the user's email.",
)
async def forgot_password(
    payload: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.email == payload.email))
    user = result.scalar_one_or_none()
    # Always return success to prevent email enumeration
    if not user:
        return {"ok": True, "message": "If the email exists, a reset link has been sent."}

    # Generate a short-lived reset token (15 min)
    reset_token = create_access_token({"sub": user.id, "type": "reset"})

    # Send reset email
    try:
        from app.services.email_service import send_password_reset_email
        send_password_reset_email(user.email, user.full_name, reset_token)
    except Exception as e:
        logger.warning(f"Reset email failed: {e}")

    return {"ok": True, "message": "If the email exists, a reset link has been sent."}


@router.post(
    "/reset-password",
    summary="Reset password with token",
    description="Reset password using the token from the reset email.",
)
async def reset_password(
    payload: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    from jose import JWTError, jwt as jose_jwt

    try:
        decoded = jose_jwt.decode(payload.token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        if decoded.get("type") != "reset":
            raise HTTPException(status_code=400, detail="Invalid reset token")
        user_id = int(decoded.get("sub", 0))
    except (JWTError, ValueError):
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=400, detail="Invalid reset token")

    if len(payload.new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")

    user.hashed_password = hash_password(payload.new_password)
    await db.flush()
    return {"ok": True, "message": "Password has been reset. You can now sign in."}
