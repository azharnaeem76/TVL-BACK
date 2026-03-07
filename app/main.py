from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import get_settings
from contextlib import asynccontextmanager
from app.api.routes import auth, search, chat, case_law, ingestion, admin, features, notifications, case_tracker, clients, directory
from app.core.database import engine, Base, async_session
from app.api.routes.features import seed_features

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Import all models so tables are created
    import app.models.user  # noqa
    import app.models.legal  # noqa
    import app.models.features  # noqa
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Seed feature flags
    async with async_session() as session:
        await seed_features(session)
        await session.commit()
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
