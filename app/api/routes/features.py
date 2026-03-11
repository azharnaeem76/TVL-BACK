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
    applicable_roles: Optional[list[str]] = None

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

ALL_ROLES = ["admin", "lawyer", "judge", "law_student", "client"]

DEFAULT_FEATURES = [
    # Core
    {"key": "case_laws", "name": "Case Laws Browser", "description": "Browse and search Pakistani case laws", "category": "core", "enabled": True, "applicable_roles": ALL_ROLES},
    {"key": "statutes", "name": "Statutes Browser", "description": "Browse Pakistani statutes and sections", "category": "core", "enabled": True, "applicable_roles": ALL_ROLES},
    {"key": "search", "name": "Scenario Search", "description": "AI-powered legal scenario search", "category": "core", "enabled": True, "applicable_roles": ALL_ROLES},
    {"key": "drafting", "name": "Document Drafting", "description": "Professional legal document drafting", "category": "core", "enabled": True, "applicable_roles": ["lawyer", "judge", "admin"]},
    {"key": "calendar", "name": "Legal Calendar", "description": "Court dates and event management", "category": "core", "enabled": True, "applicable_roles": ["lawyer", "judge", "admin"]},
    {"key": "news", "name": "Legal News", "description": "Latest legal news and updates", "category": "core", "enabled": True, "applicable_roles": ALL_ROLES},
    {"key": "chat", "name": "AI Legal Chat", "description": "Interactive AI-powered legal chat", "category": "core", "enabled": True, "applicable_roles": ALL_ROLES},

    # AI
    {"key": "ai_summarizer", "name": "AI Case Summarizer", "description": "Upload judgments for AI-generated summaries", "category": "ai", "enabled": False, "applicable_roles": ["lawyer", "judge", "admin"]},
    {"key": "ai_opinion", "name": "AI Legal Opinion", "description": "Generate preliminary legal opinions from facts", "category": "ai", "enabled": False, "applicable_roles": ["lawyer", "judge", "admin"]},
    {"key": "ai_predictor", "name": "Case Outcome Predictor", "description": "Predict case outcomes based on similar precedents", "category": "ai", "enabled": False, "applicable_roles": ["lawyer", "judge", "admin"]},
    {"key": "ai_contract", "name": "Contract Analyzer", "description": "AI analysis of contracts for risky clauses", "category": "ai", "enabled": False, "applicable_roles": ["lawyer", "admin"]},
    {"key": "citation_finder", "name": "Citation Finder", "description": "Find relevant citations from legal principles", "category": "ai", "enabled": False, "applicable_roles": ["lawyer", "judge", "law_student", "admin"]},

    # Collaboration
    {"key": "case_tracker", "name": "Case Tracker", "description": "Track active court cases with hearing dates", "category": "collaboration", "enabled": True, "applicable_roles": ["lawyer", "judge", "admin"]},
    {"key": "client_crm", "name": "Client Management", "description": "Manage clients, documents, and billing", "category": "collaboration", "enabled": True, "applicable_roles": ["lawyer", "admin"]},
    {"key": "lawyer_directory", "name": "Lawyer Directory", "description": "Searchable directory of legal professionals", "category": "collaboration", "enabled": True, "applicable_roles": ALL_ROLES},
    {"key": "document_analysis", "name": "Document Upload & Analysis", "description": "Upload legal documents for AI extraction of key info", "category": "ai", "enabled": True, "applicable_roles": ["lawyer", "judge", "admin"]},
    {"key": "bookmarks", "name": "Bookmarks", "description": "Save and manage bookmarked case laws", "category": "core", "enabled": True, "applicable_roles": ALL_ROLES},
    {"key": "messaging", "name": "Internal Messaging", "description": "Secure lawyer-client messaging", "category": "collaboration", "enabled": False, "applicable_roles": ["lawyer", "client", "judge", "admin"]},
    {"key": "team_workspaces", "name": "Team Workspaces", "description": "Law firm team collaboration", "category": "collaboration", "enabled": True, "applicable_roles": ALL_ROLES},

    # Business
    {"key": "consultation_booking", "name": "Consultation Booking", "description": "Book and manage legal consultations", "category": "business", "enabled": False, "applicable_roles": ["lawyer", "client"]},
    {"key": "payments", "name": "Payment Integration", "description": "JazzCash/Easypaisa/Stripe payments", "category": "business", "enabled": False, "applicable_roles": ALL_ROLES},
    {"key": "subscriptions", "name": "Subscription Plans", "description": "Free, Pro, and Firm subscription tiers", "category": "business", "enabled": False, "applicable_roles": ALL_ROLES},

    # Student
    {"key": "quiz", "name": "Legal Quiz", "description": "Test legal knowledge with quizzes", "category": "student", "enabled": True, "applicable_roles": ["law_student"]},
    {"key": "learn", "name": "Learning Center", "description": "Legal study topics and tutorials", "category": "student", "enabled": True, "applicable_roles": ["law_student"]},
    {"key": "moot_court", "name": "Moot Court Simulator", "description": "Practice arguing cases with AI", "category": "student", "enabled": True, "applicable_roles": ["law_student"]},
    {"key": "exam_prep", "name": "Exam Preparation", "description": "LLB, Bar, LAT, GAT, CSS, PMS, Judiciary exam preparation with AI", "category": "student", "enabled": True, "applicable_roles": ["law_student"]},

    # Notifications
    {"key": "email_notifications", "name": "Email Notifications", "description": "Send email alerts for hearings, updates", "category": "notifications", "enabled": True, "applicable_roles": ALL_ROLES},
    {"key": "push_notifications", "name": "Push Notifications", "description": "Browser push notifications", "category": "notifications", "enabled": False, "applicable_roles": ALL_ROLES},
    {"key": "audit_logs", "name": "Audit Logs", "description": "Track all admin and user actions", "category": "notifications", "enabled": True, "applicable_roles": ["admin"]},

    # Community
    {"key": "forum", "name": "Community Forum", "description": "Public discussion forum for legal topics", "category": "collaboration", "enabled": True, "applicable_roles": ALL_ROLES},

    # New Features
    {"key": "inheritance", "name": "Inheritance Calculator", "description": "Calculate inheritance shares per Islamic, Christian, Hindu, Sikh law", "category": "core", "enabled": True, "applicable_roles": ALL_ROLES},
    {"key": "legal_research", "name": "AI Legal Research Agent", "description": "Deep AI research with case law citations and argument building", "category": "ai", "enabled": True, "applicable_roles": ["lawyer", "judge", "law_student", "admin"]},
    {"key": "analytics_v2", "name": "Analytics Dashboard v2", "description": "Advanced analytics with heatmaps, win-rate, revenue tracking", "category": "business", "enabled": True, "applicable_roles": ["lawyer", "judge", "admin"]},
    {"key": "marketplace", "name": "Lawyer Marketplace", "description": "Browse, hire, and review lawyers with service listings", "category": "business", "enabled": True, "applicable_roles": ALL_ROLES},

    # Granular Service Controls (use config JSON for limits)
    {"key": "case_law_downloads", "name": "Case Law Downloads", "description": "Allow users to download case law PDFs", "category": "core", "enabled": True, "config": {"daily_limit": 50, "roles": ["lawyer", "judge", "admin"]}, "applicable_roles": ["lawyer", "judge", "admin"]},
    {"key": "case_law_views", "name": "Case Law View Limit", "description": "Limit case law views per day for free users", "category": "core", "enabled": True, "config": {"free_daily_limit": 20, "pro_daily_limit": 100, "firm_daily_limit": -1}, "applicable_roles": ALL_ROLES},
    {"key": "ai_daily_limit", "name": "AI Usage Limit", "description": "Daily limit for AI tool usage", "category": "ai", "enabled": True, "config": {"free_daily_limit": 5, "pro_daily_limit": 50, "firm_daily_limit": -1}, "applicable_roles": ["lawyer", "judge", "admin"]},
    {"key": "document_upload_limit", "name": "Document Upload Limit", "description": "Max documents per user per day", "category": "core", "enabled": True, "config": {"free_daily_limit": 3, "pro_daily_limit": 20, "firm_daily_limit": -1, "max_file_mb": 25}, "applicable_roles": ["lawyer", "judge", "admin"]},
    {"key": "messaging_limit", "name": "Messaging Limit", "description": "Daily message send limit", "category": "collaboration", "enabled": False, "config": {"free_daily_limit": 20, "pro_daily_limit": 100, "firm_daily_limit": -1}, "applicable_roles": ["lawyer", "client", "judge", "admin"]},
    {"key": "forum_post_limit", "name": "Forum Post Limit", "description": "Daily forum post limit", "category": "collaboration", "enabled": True, "config": {"free_daily_limit": 5, "pro_daily_limit": 20, "firm_daily_limit": -1}, "applicable_roles": ALL_ROLES},
    {"key": "search_limit", "name": "Search Limit", "description": "Daily search query limit", "category": "core", "enabled": True, "config": {"free_daily_limit": 10, "pro_daily_limit": 50, "firm_daily_limit": -1}, "applicable_roles": ALL_ROLES},
    {"key": "export_results", "name": "Export Search Results", "description": "Allow exporting search results to PDF/CSV", "category": "core", "enabled": False, "config": {"roles": ["lawyer", "judge", "admin", "paralegal"]}, "applicable_roles": ["lawyer", "judge", "admin"]},
    {"key": "bulk_download", "name": "Bulk Download", "description": "Download multiple case laws at once", "category": "core", "enabled": False, "config": {"max_items": 10, "roles": ["lawyer", "judge", "admin"]}, "applicable_roles": ["lawyer", "judge", "admin"]},
    {"key": "content_moderation", "name": "Content Moderation", "description": "Auto-filter abusive content in messages and forum", "category": "notifications", "enabled": True, "applicable_roles": ALL_ROLES},
]


async def seed_features(db: AsyncSession):
    """Seed default feature flags if they don't exist, update config if missing."""
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
                config=feat.get("config"),
                applicable_roles=feat.get("applicable_roles"),
            ))
        else:
            # Backfill config and applicable_roles on existing features
            if feat.get("config") and not existing.config:
                existing.config = feat["config"]
            if feat.get("applicable_roles") and not existing.applicable_roles:
                existing.applicable_roles = feat["applicable_roles"]
    await db.flush()
