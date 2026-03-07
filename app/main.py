from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from contextlib import asynccontextmanager
from app.api.routes import auth, search, chat, case_law, ingestion, admin, features, notifications, case_tracker, clients, directory, documents, ai_tools, messaging, consultation, audit, moot_court
from app.core.database import engine, Base, async_session
from app.api.routes.features import seed_features
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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Seed feature flags
    try:
        async with async_session() as session:
            await seed_features(session)
            await session.commit()
    except Exception as e:
        print(f"Feature seeding skipped: {e}")
    yield


app = FastAPI(
    lifespan=lifespan,
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="""
## TVL - The Virtual Lawyer API

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
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001"],
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
