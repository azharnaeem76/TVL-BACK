"""Feature flags API - admin can toggle features on/off."""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from pydantic import BaseModel
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.models.features import FeatureFlag, FeatureCategory

router = APIRouter(prefix="/features", tags=["Feature Flags"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class FeatureFlagResponse(BaseModel):
    id: int
    key: str
    name: str
    description: Optional[str] = None
    category: FeatureCategory
    enabled: bool
    config: Optional[dict] = None

    class Config:
        from_attributes = True


class FeatureFlagUpdate(BaseModel):
    enabled: Optional[bool] = None
    config: Optional[dict] = None


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin required")
    return current_user


# ---------------------------------------------------------------------------
# Public: Get enabled features (for frontend to check)
# ---------------------------------------------------------------------------

@router.get("/", response_model=list[FeatureFlagResponse], summary="List all features")
async def list_features(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FeatureFlag).order_by(FeatureFlag.category, FeatureFlag.name))
    return [FeatureFlagResponse.model_validate(f) for f in result.scalars().all()]


@router.get("/enabled", response_model=dict, summary="Get enabled feature keys (public)")
async def get_enabled_features(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(FeatureFlag.key).where(FeatureFlag.enabled == True))
    keys = [row[0] for row in result.all()]
    return {"enabled": keys}


# ---------------------------------------------------------------------------
# Admin: Toggle features
# ---------------------------------------------------------------------------

@router.put("/{feature_key}", response_model=FeatureFlagResponse, summary="Toggle a feature (admin)")
async def update_feature(
    feature_key: str,
    payload: FeatureFlagUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(FeatureFlag).where(FeatureFlag.key == feature_key))
    feature = result.scalar_one_or_none()
    if not feature:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Feature '{feature_key}' not found")

    if payload.enabled is not None:
        feature.enabled = payload.enabled
    if payload.config is not None:
        feature.config = payload.config

    await db.flush()
    await db.refresh(feature)
    return FeatureFlagResponse.model_validate(feature)


# ---------------------------------------------------------------------------
# Seed default features (called on startup)
# ---------------------------------------------------------------------------

DEFAULT_FEATURES = [
    # Core
    {"key": "case_laws", "name": "Case Laws Browser", "description": "Browse and search Pakistani case laws", "category": "core", "enabled": True},
    {"key": "statutes", "name": "Statutes Browser", "description": "Browse Pakistani statutes and sections", "category": "core", "enabled": True},
    {"key": "search", "name": "Scenario Search", "description": "AI-powered legal scenario search", "category": "core", "enabled": True},
    {"key": "drafting", "name": "Document Drafting", "description": "Professional legal document drafting", "category": "core", "enabled": True},
    {"key": "calendar", "name": "Legal Calendar", "description": "Court dates and event management", "category": "core", "enabled": True},
    {"key": "news", "name": "Legal News", "description": "Latest legal news and updates", "category": "core", "enabled": True},
    {"key": "chat", "name": "AI Legal Chat", "description": "Interactive AI-powered legal chat", "category": "core", "enabled": True},

    # AI
    {"key": "ai_summarizer", "name": "AI Case Summarizer", "description": "Upload judgments for AI-generated summaries", "category": "ai", "enabled": False},
    {"key": "ai_opinion", "name": "AI Legal Opinion", "description": "Generate preliminary legal opinions from facts", "category": "ai", "enabled": False},
    {"key": "ai_predictor", "name": "Case Outcome Predictor", "description": "Predict case outcomes based on similar precedents", "category": "ai", "enabled": False},
    {"key": "ai_contract", "name": "Contract Analyzer", "description": "AI analysis of contracts for risky clauses", "category": "ai", "enabled": False},
    {"key": "citation_finder", "name": "Citation Finder", "description": "Find relevant citations from legal principles", "category": "ai", "enabled": False},

    # Collaboration
    {"key": "case_tracker", "name": "Case Tracker", "description": "Track active court cases with hearing dates", "category": "collaboration", "enabled": True},
    {"key": "client_crm", "name": "Client Management", "description": "Manage clients, documents, and billing", "category": "collaboration", "enabled": True},
    {"key": "lawyer_directory", "name": "Lawyer Directory", "description": "Searchable directory of legal professionals", "category": "collaboration", "enabled": True},
    {"key": "document_analysis", "name": "Document Upload & Analysis", "description": "Upload legal documents for AI extraction of key info", "category": "ai", "enabled": True},
    {"key": "bookmarks", "name": "Bookmarks", "description": "Save and manage bookmarked case laws", "category": "core", "enabled": True},
    {"key": "messaging", "name": "Internal Messaging", "description": "Secure lawyer-client messaging", "category": "collaboration", "enabled": False},
    {"key": "team_workspaces", "name": "Team Workspaces", "description": "Law firm team collaboration", "category": "collaboration", "enabled": False},

    # Business
    {"key": "consultation_booking", "name": "Consultation Booking", "description": "Book and manage legal consultations", "category": "business", "enabled": False},
    {"key": "payments", "name": "Payment Integration", "description": "JazzCash/Easypaisa/Stripe payments", "category": "business", "enabled": False},
    {"key": "subscriptions", "name": "Subscription Plans", "description": "Free, Pro, and Firm subscription tiers", "category": "business", "enabled": False},

    # Student
    {"key": "quiz", "name": "Legal Quiz", "description": "Test legal knowledge with quizzes", "category": "student", "enabled": True},
    {"key": "learn", "name": "Learning Center", "description": "Legal study topics and tutorials", "category": "student", "enabled": True},
    {"key": "moot_court", "name": "Moot Court Simulator", "description": "Practice arguing cases with AI", "category": "student", "enabled": False},
    {"key": "exam_prep", "name": "Exam Preparation", "description": "LLB/Bar exam past papers and model answers", "category": "student", "enabled": False},

    # Notifications
    {"key": "email_notifications", "name": "Email Notifications", "description": "Send email alerts for hearings, updates", "category": "notifications", "enabled": True},
    {"key": "push_notifications", "name": "Push Notifications", "description": "Browser push notifications", "category": "notifications", "enabled": False},
    {"key": "audit_logs", "name": "Audit Logs", "description": "Track all admin and user actions", "category": "notifications", "enabled": True},
]


async def seed_features(db: AsyncSession):
    """Seed default feature flags if they don't exist."""
    for feat in DEFAULT_FEATURES:
        existing = (await db.execute(
            select(FeatureFlag).where(FeatureFlag.key == feat["key"])
        )).scalar_one_or_none()
        if not existing:
            db.add(FeatureFlag(
                key=feat["key"],
                name=feat["name"],
                description=feat["description"],
                category=FeatureCategory(feat["category"]),
                enabled=feat["enabled"],
            ))
    await db.flush()
