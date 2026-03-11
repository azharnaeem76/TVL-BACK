from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    APP_NAME: str = "TVL - The Value of Law"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:123@localhost:5432/tvl_db"
    SYNC_DATABASE_URL: str = "postgresql://postgres:123@localhost:5432/tvl_db"

    # Auth
    SECRET_KEY: str = "change-this-secret-key-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours

    # Ollama (local LLM - free, no API key needed)
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen2.5:7b"

    # Embedding model (runs locally, free)
    EMBEDDING_MODEL: str = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
    EMBEDDING_DIMENSION: int = 384

    # Model storage path (HuggingFace models cache)
    HF_HOME: str = "D:\\AI_Models\\huggingface"

    # Google OAuth (optional)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # Email (optional - SMTP)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""
    FROM_EMAIL: str = "noreply@tvl.pk"
    FROM_NAME: str = "TVL - The Value of Law"

    # Redis (optional, for caching)
    REDIS_URL: str = "redis://localhost:6379/0"

    # Vector search
    SIMILARITY_THRESHOLD: float = 0.3
    MAX_SEARCH_RESULTS: int = 10

    class Config:
        env_file = ".env"
        extra = "allow"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
