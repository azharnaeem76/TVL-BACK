"""
Batch generate embeddings for all case laws and statutes that don't have them.
Run from backend directory: python generate_embeddings.py
"""

import asyncio
import json
import os
import sys

# Ensure the app modules are importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.core.database import async_session
from app.models.legal import CaseLaw, Statute
from app.services.embedding_service import generate_embeddings_batch
from sqlalchemy import select, func


BATCH_SIZE = 32


def build_case_text(case) -> str:
    """Build a searchable text from case law fields."""
    parts = []
    if case.title:
        parts.append(case.title)
    if case.summary_en:
        parts.append(case.summary_en)
    if case.headnotes:
        parts.append(case.headnotes[:500])
    if case.sections_applied:
        parts.append(case.sections_applied)
    if case.relevant_statutes:
        parts.append(case.relevant_statutes)
    return " | ".join(parts) if parts else case.title or ""


def build_statute_text(statute) -> str:
    """Build a searchable text from statute fields."""
    parts = []
    if statute.title:
        parts.append(statute.title)
    if statute.summary_en:
        parts.append(statute.summary_en[:500])
    return " | ".join(parts) if parts else statute.title or ""


async def generate_case_law_embeddings():
    """Generate embeddings for all case laws missing them."""
    async with async_session() as session:
        # Count total and missing
        total = (await session.execute(select(func.count(CaseLaw.id)))).scalar()
        missing = (await session.execute(
            select(func.count(CaseLaw.id)).where(CaseLaw.embedding.is_(None))
        )).scalar()

        print(f"\nCase Laws: {total} total, {missing} missing embeddings")
        if missing == 0:
            print("All case laws already have embeddings!")
            return

        # Fetch all cases without embeddings
        result = await session.execute(
            select(CaseLaw).where(CaseLaw.embedding.is_(None)).order_by(CaseLaw.id)
        )
        cases = list(result.scalars().all())

        processed = 0
        for i in range(0, len(cases), BATCH_SIZE):
            batch = cases[i:i + BATCH_SIZE]
            texts = [build_case_text(c) for c in batch]

            try:
                embeddings = generate_embeddings_batch(texts)

                for case, emb in zip(batch, embeddings):
                    case.embedding = json.dumps(emb)

                await session.commit()
                processed += len(batch)
                print(f"  Case laws: {processed}/{missing} done ({processed*100//missing}%)")
            except Exception as e:
                print(f"  Error on batch {i}: {e}")
                await session.rollback()
                # Re-fetch session state
                async with async_session() as session2:
                    session = session2

    print(f"Case law embeddings complete: {processed} generated")


async def generate_statute_embeddings():
    """Generate embeddings for all statutes missing them."""
    async with async_session() as session:
        total = (await session.execute(select(func.count(Statute.id)))).scalar()
        missing = (await session.execute(
            select(func.count(Statute.id)).where(Statute.embedding.is_(None))
        )).scalar()

        print(f"\nStatutes: {total} total, {missing} missing embeddings")
        if missing == 0:
            print("All statutes already have embeddings!")
            return

        result = await session.execute(
            select(Statute).where(Statute.embedding.is_(None)).order_by(Statute.id)
        )
        statutes = list(result.scalars().all())

        texts = [build_statute_text(s) for s in statutes]
        embeddings = generate_embeddings_batch(texts)

        for statute, emb in zip(statutes, embeddings):
            statute.embedding = json.dumps(emb)

        await session.commit()
        print(f"Statute embeddings complete: {len(statutes)} generated")


async def main():
    print("=" * 60)
    print("TVL Embedding Generator")
    print("=" * 60)

    await generate_case_law_embeddings()
    await generate_statute_embeddings()

    print("\nDone! All embeddings generated.")


if __name__ == "__main__":
    asyncio.run(main())
