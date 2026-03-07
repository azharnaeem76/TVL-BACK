"""
Database Seeder - Populates the database with sample Pakistani legal data
and generates vector embeddings for semantic search.
"""

import json
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.core.database import Base
from app.models.legal import CaseLaw, Statute, Section
from app.models.user import User
from app.core.security import hash_password
from app.data.seed_data import SAMPLE_CASE_LAWS, SAMPLE_STATUTES, SAMPLE_SECTIONS

settings = get_settings()


def _try_load_embedding_service():
    """Try to load embedding service; return None if unavailable."""
    try:
        from app.services.embedding_service import generate_embeddings_batch
        return generate_embeddings_batch
    except Exception as e:
        print(f"  Embedding service unavailable ({e}), seeding without embeddings.")
        return None


def _serialize_embedding(embedding):
    """Convert embedding list to JSON string for storage."""
    if embedding is None:
        return None
    return json.dumps(embedding)


def run_seeder():
    """Run the database seeder synchronously."""
    engine = create_engine(settings.SYNC_DATABASE_URL, echo=False)

    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("Tables created successfully.")

    with Session(engine) as session:
        # Check if data already exists
        existing = session.query(CaseLaw).first()
        if existing:
            print("Data already exists. Skipping seed.")
            return

        # Seed demo user
        _seed_demo_users(session)

        # Seed statutes first (case laws reference them)
        statute_map = _seed_statutes(session)

        # Seed sections
        _seed_sections(session, statute_map)

        # Seed case laws
        _seed_case_laws(session)

        session.commit()
        print("\nSeeding complete!")


def _seed_demo_users(session: Session):
    """Create demo users for each role."""
    demo_users = [
        {"email": "lawyer@tvl.pk", "full_name": "Ahmed Ali Khan", "role": "lawyer", "specialization": "Criminal Law", "city": "Lahore", "bar_number": "LHC-2020-1234"},
        {"email": "judge@tvl.pk", "full_name": "Justice Fatima Noor", "role": "judge", "specialization": "Constitutional Law", "city": "Islamabad"},
        {"email": "student@tvl.pk", "full_name": "Sara Malik", "role": "law_student", "city": "Karachi"},
        {"email": "client@tvl.pk", "full_name": "Muhammad Usman", "role": "client", "city": "Peshawar"},
        {"email": "admin@tvl.pk", "full_name": "System Admin", "role": "admin", "city": "Islamabad"},
    ]

    for u in demo_users:
        user = User(
            email=u["email"],
            full_name=u["full_name"],
            hashed_password=hash_password("demo123"),
            role=u["role"],
            specialization=u.get("specialization"),
            city=u.get("city"),
            bar_number=u.get("bar_number"),
            preferred_language="en",
        )
        session.add(user)

    print(f"Created {len(demo_users)} demo users (password: demo123)")


def _seed_statutes(session: Session) -> dict:
    """Seed statutes and return a map of title -> id."""
    print("Seeding statutes...")
    statute_map = {}

    generate_batch = _try_load_embedding_service()
    embeddings = None
    if generate_batch:
        texts = [f"{s['title']} {s['summary_en']}" for s in SAMPLE_STATUTES]
        embeddings = generate_batch(texts)

    for i, s in enumerate(SAMPLE_STATUTES):
        emb = _serialize_embedding(embeddings[i]) if embeddings else None
        statute = Statute(
            title=s["title"],
            short_title=s.get("short_title"),
            act_number=s.get("act_number"),
            year=s.get("year"),
            category=s["category"],
            summary_en=s.get("summary_en"),
            summary_ur=s.get("summary_ur"),
            embedding=emb,
        )
        session.add(statute)
        session.flush()
        statute_map[s["title"]] = statute.id

    print(f"  Seeded {len(SAMPLE_STATUTES)} statutes.")
    return statute_map


def _seed_sections(session: Session, statute_map: dict):
    """Seed statute sections."""
    print("Seeding sections...")

    generate_batch = _try_load_embedding_service()
    embeddings = None
    if generate_batch:
        texts = [f"{s['title']} {s['content']}" for s in SAMPLE_SECTIONS]
        embeddings = generate_batch(texts)

    seeded = 0
    for i, s in enumerate(SAMPLE_SECTIONS):
        statute_id = statute_map.get(s["statute_title"])
        if not statute_id:
            continue

        emb = _serialize_embedding(embeddings[i]) if embeddings else None
        section = Section(
            statute_id=statute_id,
            section_number=s["section_number"],
            title=s.get("title"),
            content=s["content"],
            content_ur=s.get("content_ur"),
            embedding=emb,
        )
        session.add(section)
        seeded += 1

    print(f"  Seeded {seeded} sections.")


def _seed_case_laws(session: Session):
    """Seed case laws with vector embeddings."""
    print("Seeding case laws...")

    generate_batch = _try_load_embedding_service()
    embeddings = None
    if generate_batch:
        texts = [
            f"{cl['title']} {cl['summary_en']} {cl['headnotes']} {cl.get('relevant_statutes', '')}"
            for cl in SAMPLE_CASE_LAWS
        ]
        embeddings = generate_batch(texts)

    for i, cl in enumerate(SAMPLE_CASE_LAWS):
        emb = _serialize_embedding(embeddings[i]) if embeddings else None
        case_law = CaseLaw(
            citation=cl["citation"],
            title=cl["title"],
            court=cl["court"],
            category=cl["category"],
            year=cl["year"],
            judge_name=cl.get("judge_name"),
            summary_en=cl.get("summary_en"),
            summary_ur=cl.get("summary_ur"),
            headnotes=cl.get("headnotes"),
            relevant_statutes=cl.get("relevant_statutes"),
            sections_applied=cl.get("sections_applied"),
            embedding=emb,
        )
        session.add(case_law)

    print(f"  Seeded {len(SAMPLE_CASE_LAWS)} case laws.")


if __name__ == "__main__":
    run_seeder()
