"""
Scenario Search Service - The core module.

Pipeline:
1. User types scenario (English / Urdu / Roman Urdu)
2. Detect language
3. Normalize to English for embedding search
4. Generate query embedding
5. Cosine similarity search on stored embeddings
6. Filter by category/court/year if specified
7. Generate AI analysis with citations
8. Return results in user's preferred language
"""

import json
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_
from app.models.legal import CaseLaw, Statute, Section, SearchHistory, LawCategory, Court
from app.services.language_service import detect_language, normalize_to_english
from app.services.embedding_service import generate_embedding
from app.services.llm_service import generate_scenario_analysis
from app.schemas.legal import ScenarioSearchRequest, SearchResponse, CaseLawResponse
from app.core.config import get_settings

settings = get_settings()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a_arr = np.array(a)
    b_arr = np.array(b)
    norm = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
    if norm == 0:
        return 0.0
    return float(np.dot(a_arr, b_arr) / norm)


async def scenario_search(
    request: ScenarioSearchRequest,
    db: AsyncSession,
    user_id: int = None,
) -> SearchResponse:
    """Main scenario search pipeline."""

    # Step 1: Detect language
    language = detect_language(request.query)

    # Step 2: Normalize query
    normalized = normalize_to_english(request.query, language)

    # Step 3: Generate embedding
    query_embedding = generate_embedding(normalized)

    # Step 4: Vector similarity search for case laws
    case_laws = await _vector_search_cases(
        db=db,
        embedding=query_embedding,
        category=request.category,
        court=request.court,
        year_from=request.year_from,
        year_to=request.year_to,
        limit=request.max_results,
    )

    # Step 5: Also search relevant statutes
    statutes = await _vector_search_statutes(
        db=db,
        embedding=query_embedding,
        category=request.category,
        limit=5,
    )

    # Step 6: Generate AI analysis
    case_law_dicts = [
        {
            "citation": cl.citation,
            "title": cl.title,
            "court": cl.court.value if cl.court else "N/A",
            "year": cl.year,
            "summary_en": cl.summary_en,
            "headnotes": cl.headnotes,
        }
        for cl in case_laws
    ]

    statute_dicts = [
        {
            "title": st.title,
            "act_number": st.act_number,
            "year": st.year,
            "summary_en": st.summary_en,
        }
        for st in statutes
    ]

    ai_analysis = await generate_scenario_analysis(
        scenario=request.query,
        case_laws=case_law_dicts,
        statutes=statute_dicts,
        language=language,
    )

    # Step 7: Save search history
    history = SearchHistory(
        user_id=user_id,
        query_text=request.query,
        detected_language=language,
        normalized_query=normalized,
        results_count=len(case_laws),
    )
    db.add(history)

    # Step 8: Build response
    results = [
        CaseLawResponse(
            id=cl.id,
            citation=cl.citation,
            title=cl.title,
            court=cl.court,
            category=cl.category,
            year=cl.year,
            judge_name=cl.judge_name,
            summary_en=cl.summary_en,
            summary_ur=cl.summary_ur,
            headnotes=cl.headnotes,
            relevant_statutes=cl.relevant_statutes,
            sections_applied=cl.sections_applied,
            similarity_score=getattr(cl, "_similarity", None),
        )
        for cl in case_laws
    ]

    return SearchResponse(
        query=request.query,
        detected_language=language,
        normalized_query=normalized,
        results=results,
        ai_analysis=ai_analysis,
        total_results=len(results),
    )


async def _vector_search_cases(
    db: AsyncSession,
    embedding: list[float],
    category: LawCategory = None,
    court: Court = None,
    year_from: int = None,
    year_to: int = None,
    limit: int = 10,
) -> list[CaseLaw]:
    """Perform cosine similarity search on case laws."""
    # Build filters
    conditions = [CaseLaw.embedding.isnot(None)]
    if category:
        conditions.append(CaseLaw.category == category)
    if court:
        conditions.append(CaseLaw.court == court)
    if year_from:
        conditions.append(CaseLaw.year >= year_from)
    if year_to:
        conditions.append(CaseLaw.year <= year_to)

    stmt = select(CaseLaw).where(and_(*conditions))
    result = await db.execute(stmt)
    rows = result.scalars().all()

    # Compute similarity in Python
    scored = []
    for cl in rows:
        try:
            stored_emb = json.loads(cl.embedding) if isinstance(cl.embedding, str) else cl.embedding
            sim = _cosine_similarity(embedding, stored_emb)
            if sim >= settings.SIMILARITY_THRESHOLD:
                cl._similarity = sim
                scored.append((sim, cl))
        except (json.JSONDecodeError, TypeError):
            continue

    # Sort by similarity descending, take top N
    scored.sort(key=lambda x: x[0], reverse=True)
    return [cl for _, cl in scored[:limit]]


async def _vector_search_statutes(
    db: AsyncSession,
    embedding: list[float],
    category: LawCategory = None,
    limit: int = 5,
) -> list[Statute]:
    """Perform cosine similarity search on statutes."""
    conditions = [Statute.embedding.isnot(None)]
    if category:
        conditions.append(Statute.category == category)

    stmt = select(Statute).where(and_(*conditions))
    result = await db.execute(stmt)
    rows = result.scalars().all()

    scored = []
    for st in rows:
        try:
            stored_emb = json.loads(st.embedding) if isinstance(st.embedding, str) else st.embedding
            sim = _cosine_similarity(embedding, stored_emb)
            scored.append((sim, st))
        except (json.JSONDecodeError, TypeError):
            continue

    scored.sort(key=lambda x: x[0], reverse=True)
    return [st for _, st in scored[:limit]]
