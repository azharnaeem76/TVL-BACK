"""
Embedding Service using sentence-transformers (free, runs locally).

Uses paraphrase-multilingual-MiniLM-L12-v2 which supports:
- English, Urdu, and 50+ other languages
- 384-dimensional embeddings
- Excellent for semantic similarity search
"""

import numpy as np
from functools import lru_cache
from sentence_transformers import SentenceTransformer
from app.core.config import get_settings

settings = get_settings()


@lru_cache(maxsize=1)
def get_model() -> SentenceTransformer:
    """Load the multilingual embedding model (cached singleton)."""
    print(f"Loading embedding model: {settings.EMBEDDING_MODEL}")
    model = SentenceTransformer(settings.EMBEDDING_MODEL)
    print("Embedding model loaded successfully.")
    return model


def generate_embedding(text: str) -> list[float]:
    """Generate embedding vector for a given text."""
    model = get_model()
    embedding = model.encode(text, normalize_embeddings=True)
    return embedding.tolist()


def generate_embeddings_batch(texts: list[str]) -> list[list[float]]:
    """Generate embeddings for a batch of texts (more efficient)."""
    model = get_model()
    embeddings = model.encode(texts, normalize_embeddings=True, batch_size=32, show_progress_bar=True)
    return embeddings.tolist()


def compute_similarity(embedding1: list[float], embedding2: list[float]) -> float:
    """Compute cosine similarity between two embeddings."""
    a = np.array(embedding1)
    b = np.array(embedding2)
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b)))
