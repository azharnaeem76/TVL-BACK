from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from contextlib import asynccontextmanager
from app.api.routes import auth, search, chat, case_law, ingestion, admin, features, notifications, case_tracker, clients, directory, documents, ai_tools, messaging, consultation, audit, moot_court, subscriptions, support, forum, study_content, workspaces, inheritance, analytics, legal_research, marketplace
from app.core.database import engine, Base, async_session
from app.api.routes.features import seed_features
from app.api.routes.study_content import seed_study_content
from app.data.seed_case_laws import seed_case_laws
from app.data.seed_statutes import seed_statutes
from app.data.seed_sections import seed_sections
from app.data.seed_study_content_data import seed_study_content_from_json
from app.data.seed_pakistan_laws import seed_pakistan_law_statutes
import socketio as socketio_lib
from app.core.socketio import sio

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Import all models so tables are created
    import app.models.user  # noqa
    import app.models.legal  # noqa
    import app.models.features  # noqa
    import app.models.documents  # noqa
    import app.models.messaging  # noqa
    import app.models.support  # noqa
    import app.models.forum  # noqa
    import app.models.study_content  # noqa
    import app.models.workspace  # noqa
    import app.api.routes.marketplace  # noqa – marketplace models
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Add config column to feature_flags if missing (create_all doesn't ALTER existing tables)
        from sqlalchemy import text, inspect as sa_inspect
        def _check_and_add_columns(sync_conn):
            insp = sa_inspect(sync_conn)
            if insp.has_table("feature_flags"):
                cols = [c["name"] for c in insp.get_columns("feature_flags")]
                if "config" not in cols:
                    sync_conn.execute(text("ALTER TABLE feature_flags ADD COLUMN config JSON"))
                if "applicable_roles" not in cols:
                    sync_conn.execute(text("ALTER TABLE feature_flags ADD COLUMN applicable_roles JSON"))
            if insp.has_table("messages"):
                cols = [c["name"] for c in insp.get_columns("messages")]
                for col, typ in [("message_type", "VARCHAR(50)"), ("file_url", "VARCHAR(500)"), ("file_name", "VARCHAR(500)"), ("file_size", "INTEGER"), ("duration", "INTEGER"), ("status", "VARCHAR(20)")]:
                    if col not in cols:
                        sync_conn.execute(text(f"ALTER TABLE messages ADD COLUMN {col} {typ}"))
            if insp.has_table("users"):
                cols = [c["name"] for c in insp.get_columns("users")]
                if "profile_picture" not in cols:
                    sync_conn.execute(text("ALTER TABLE users ADD COLUMN profile_picture VARCHAR(500)"))
        await conn.run_sync(_check_and_add_columns)
    # Data seeding disabled - using existing DB data only
    # To re-seed, uncomment the block below and restart:
    # try:
    #     async with async_session() as session:
    #         await seed_features(session)
    #         await seed_study_content(session)
    #         await seed_case_laws(session)
    #         await seed_statutes(session)
    #         await seed_sections(session)
    #         await seed_study_content_from_json(session)
    #         await seed_pakistan_law_statutes(session)
    #         await session.commit()
    # except Exception as e:
    #     print(f"Seeding skipped: {e}")
    yield


app = FastAPI(
    lifespan=lifespan,
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## TVL - The Value of Law API

AI-powered legal assistance platform for Pakistani law.

### Core Modules:
- **Scenario Search**: Describe a legal scenario in English, Urdu, or Roman Urdu and get relevant case laws with AI analysis
- **Interactive Chat**: Have conversations about legal matters with AI-powered citations
- **Legal Database**: Browse and search Pakistani case laws, statutes, and sections
- **Data Ingestion**: Admin module to upload court judgment PDFs (50-60+ pages) for automatic summarization and indexing

### Authentication:
All endpoints (except guest search) require a Bearer JWT token. Get one via `/api/v1/auth/login`.

### Demo Credentials:
- **Lawyer**: lawyer@tvl.pk / demo123
- **Judge**: judge@tvl.pk / demo123
- **Student**: student@tvl.pk / demo123
- **Client**: client@tvl.pk / demo123
    """,
    openapi_tags=[
        {"name": "Authentication", "description": "User registration, login, and profile management"},
        {"name": "Scenario Search", "description": "The core module - search legal scenarios in English, Urdu, or Roman Urdu"},
        {"name": "Interactive Chat", "description": "AI-powered legal chat with case law citations"},
        {"name": "Legal Database", "description": "Browse and search case laws, statutes, and sections"},
        {"name": "Data Ingestion (Admin)", "description": "Upload court judgment PDFs for automatic summarization and indexing"},
        {"name": "Admin", "description": "Admin dashboard, CRUD for case laws, statutes, sections, and users"},
        {"name": "Feature Flags", "description": "Toggle platform features on/off"},
        {"name": "Notifications", "description": "User notifications management"},
        {"name": "Case Tracker", "description": "Track active court cases and hearing dates"},
        {"name": "Client Management", "description": "Lawyer client CRM"},
        {"name": "Lawyer Directory", "description": "Search legal professionals across Pakistan"},
        {"name": "Documents", "description": "Upload and AI-analyze legal documents"},
        {"name": "AI Tools", "description": "AI Summarizer, Opinion, Predictor, Contract Analyzer, Citation Finder"},
        {"name": "Messaging", "description": "Secure internal messaging between users"},
        {"name": "Consultations", "description": "Book and manage legal consultations"},
        {"name": "Audit Logs", "description": "Track admin and user actions"},
        {"name": "Student Tools", "description": "Moot Court Simulator and Exam Preparation"},
        {"name": "Subscriptions", "description": "Plan management and limits"},
        {"name": "Support", "description": "Help desk and support tickets"},
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(search.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(case_law.router, prefix="/api/v1")
app.include_router(ingestion.router, prefix="/api/v1")
app.include_router(admin.router, prefix="/api/v1")
app.include_router(features.router, prefix="/api/v1")
app.include_router(notifications.router, prefix="/api/v1")
app.include_router(case_tracker.router, prefix="/api/v1")
app.include_router(clients.router, prefix="/api/v1")
app.include_router(directory.router, prefix="/api/v1")
app.include_router(documents.router, prefix="/api/v1")
app.include_router(ai_tools.router, prefix="/api/v1")
app.include_router(messaging.router, prefix="/api/v1")
app.include_router(consultation.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(moot_court.router, prefix="/api/v1")
app.include_router(subscriptions.router, prefix="/api/v1")
app.include_router(support.router, prefix="/api/v1")
app.include_router(forum.router, prefix="/api/v1")
app.include_router(study_content.router, prefix="/api/v1")
app.include_router(workspaces.router, prefix="/api/v1")
app.include_router(inheritance.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(legal_research.router, prefix="/api/v1")
app.include_router(marketplace.router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health")
async def health():
    return {"status": "healthy"}


# Wrap FastAPI with Socket.IO ASGI app
socket_app = socketio_lib.ASGIApp(sio, other_asgi_app=app)

# To run: uvicorn app.main:socket_app --reload
# This serves both the FastAPI app and Socket.IO on the same port
