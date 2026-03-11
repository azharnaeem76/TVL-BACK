"""
Scenario Search Service - The core module.

Pipeline:
1. User types scenario (English / Urdu / Roman Urdu)
2. Detect language
3. Normalize to English for embedding search
4. Generate query embedding
5. Hybrid search: combine vector similarity + text/section matches
6. Filter by category/court/year if specified
7. Generate AI analysis with citations
8. Return results in user's preferred language
"""

import re
import json
import time
import logging
import numpy as np
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, text
from app.models.legal import CaseLaw, Statute, Section, SearchHistory, LawCategory, Court
from app.services.language_service import detect_language, normalize_to_english
from app.services.embedding_service import generate_embedding
from app.services.llm_service import generate_scenario_analysis
from app.schemas.legal import ScenarioSearchRequest, SearchResponse, CaseLawResponse
from app.core.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


# ── In-memory embedding cache for fast vector search ──
class _EmbeddingCache:
    """Caches embeddings as a numpy matrix for batch cosine similarity."""

    def __init__(self):
        self.case_ids: list[int] = []
        self.case_matrix: np.ndarray | None = None  # shape (N, dim)
        self.case_norms: np.ndarray | None = None
        self.case_meta: dict[int, dict] = {}  # id -> {category, court, year}
        self.case_loaded_at: float = 0

        self.statute_ids: list[int] = []
        self.statute_matrix: np.ndarray | None = None
        self.statute_norms: np.ndarray | None = None
        self.statute_meta: dict[int, dict] = {}
        self.statute_loaded_at: float = 0

        self._ttl = 300  # refresh every 5 minutes

    def case_stale(self) -> bool:
        return self.case_matrix is None or (time.time() - self.case_loaded_at) > self._ttl

    def statute_stale(self) -> bool:
        return self.statute_matrix is None or (time.time() - self.statute_loaded_at) > self._ttl


_cache = _EmbeddingCache()


async def _load_case_embeddings(db: AsyncSession):
    """Load all case embeddings into a numpy matrix for batch search."""
    stmt = text("SELECT id, embedding, category, court, year FROM case_laws WHERE embedding IS NOT NULL")
    result = await db.execute(stmt)
    rows = result.fetchall()

    ids = []
    embeddings = []
    meta = {}
    for row in rows:
        try:
            emb = json.loads(row[1]) if isinstance(row[1], str) else row[1]
            if emb and len(emb) > 0:
                ids.append(row[0])
                embeddings.append(emb)
                meta[row[0]] = {"category": row[2], "court": row[3], "year": row[4]}
        except (json.JSONDecodeError, TypeError):
            continue

    if embeddings:
        matrix = np.array(embeddings, dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0  # avoid division by zero
        _cache.case_ids = ids
        _cache.case_matrix = matrix
        _cache.case_norms = norms
        _cache.case_meta = meta
    _cache.case_loaded_at = time.time()
    logger.info(f"Loaded {len(ids)} case embeddings into cache")


async def _load_statute_embeddings(db: AsyncSession):
    """Load all statute embeddings into a numpy matrix."""
    stmt = text("SELECT id, embedding, category FROM statutes WHERE embedding IS NOT NULL")
    result = await db.execute(stmt)
    rows = result.fetchall()

    ids = []
    embeddings = []
    meta = {}
    for row in rows:
        try:
            emb = json.loads(row[1]) if isinstance(row[1], str) else row[1]
            if emb and len(emb) > 0:
                ids.append(row[0])
                embeddings.append(emb)
                meta[row[0]] = {"category": row[2]}
        except (json.JSONDecodeError, TypeError):
            continue

    if embeddings:
        matrix = np.array(embeddings, dtype=np.float32)
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        _cache.statute_ids = ids
        _cache.statute_matrix = matrix
        _cache.statute_norms = norms
        _cache.statute_meta = meta
    _cache.statute_loaded_at = time.time()
    logger.info(f"Loaded {len(ids)} statute embeddings into cache")


def _clean_summary(en: str | None, ur: str | None) -> str:
    """Return the best available summary, treating placeholder values like '.' as empty."""
    placeholders = {'.', '()', '', '-', 'N/A', 'n/a'}
    if en and en.strip() not in placeholders:
        return en[:300]
    if ur and ur.strip() not in placeholders:
        return ur[:300]
    return 'N/A'


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    """Compute cosine similarity between two vectors."""
    a_arr = np.array(a)
    b_arr = np.array(b)
    norm = np.linalg.norm(a_arr) * np.linalg.norm(b_arr)
    if norm == 0:
        return 0.0
    return float(np.dot(a_arr, b_arr) / norm)


def _extract_section_numbers(text: str) -> list[str]:
    """Extract legal section numbers from query (e.g., '489-F', '302', '10-A')."""
    # Match patterns like: 489-F, 302, 10A, 265-K, S.302, Section 489-F
    patterns = re.findall(r'\b(?:section\s*|s\.?\s*)?(\d{1,4}\s*[-]?\s*[a-zA-Z]?)\b', text, re.IGNORECASE)
    sections = []
    for p in patterns:
        s = re.sub(r'\s+', '', p).upper()  # Normalize: "489 f" -> "489F", "489-F" stays
        if s and len(s) >= 2:  # At least a 2-digit section number
            sections.append(s)
            # Also add variant with/without hyphen: 489F <-> 489-F
            if '-' in s:
                sections.append(s.replace('-', ''))
            elif re.match(r'^\d+[A-Z]$', s):
                sections.append(s[:-1] + '-' + s[-1])
    return list(set(sections))


def _extract_keywords(text: str) -> list[str]:
    """Extract meaningful keywords from a query for text-based search."""
    # Common legal stop words to ignore
    stop_words = {
        'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'been', 'being',
        'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would', 'could',
        'should', 'may', 'might', 'shall', 'can', 'in', 'on', 'at', 'to',
        'for', 'of', 'with', 'by', 'from', 'as', 'into', 'about', 'between',
        'through', 'during', 'before', 'after', 'above', 'below', 'and', 'or',
        'but', 'not', 'no', 'if', 'then', 'than', 'that', 'this', 'what',
        'which', 'who', 'whom', 'how', 'when', 'where', 'why', 'i', 'me',
        'my', 'he', 'she', 'it', 'we', 'they', 'them', 'his', 'her', 'its',
        'our', 'their', 'wants', 'want', 'does', 'without', 'any', 'also',
        'been', 'living', 'years', 'year', 'case', 'laws', 'law', 'section',
    }
    words = text.lower().split()
    # Keep words longer than 2 chars that aren't stop words
    keywords = [w.strip('.,?!;:()[]"\'') for w in words if len(w) > 2 and w.lower().strip('.,?!;:()[]"\'') not in stop_words]
    return keywords[:10]  # Max 10 keywords


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
    try:
        query_embedding = generate_embedding(normalized)
    except Exception:
        query_embedding = None

    # Step 4: Hybrid search — combine text matches (especially section numbers) with vector search
    section_nums = _extract_section_numbers(request.query)

    # 4a: Text/section search (high priority — exact matches)
    text_results = await _text_search_cases(
        db=db,
        query=normalized,
        category=request.category,
        court=request.court,
        year_from=request.year_from,
        year_to=request.year_to,
        limit=request.max_results,
        section_numbers=section_nums,
    )

    # 4b: Vector similarity search
    vector_results = []
    if query_embedding:
        vector_results = await _vector_search_cases(
            db=db,
            embedding=query_embedding,
            category=request.category,
            court=request.court,
            year_from=request.year_from,
            year_to=request.year_to,
            limit=request.max_results,
        )

    # 4c: Merge results — text/section matches first, then vector results (deduped)
    seen_ids = set()
    case_laws = []
    # Text matches get priority (especially section number matches)
    for cl in text_results:
        if cl.id not in seen_ids:
            seen_ids.add(cl.id)
            if not hasattr(cl, '_similarity') or cl._similarity is None:
                cl._similarity = 0.90  # High score for exact text/section matches
            case_laws.append(cl)
    # Then add vector results that weren't already found
    for cl in vector_results:
        if cl.id not in seen_ids:
            seen_ids.add(cl.id)
            case_laws.append(cl)

    # Limit to max_results
    case_laws = case_laws[:request.max_results]

    # Step 5: Also search relevant statutes
    statutes = []
    if query_embedding:
        statutes = await _vector_search_statutes(
            db=db,
            embedding=query_embedding,
            category=request.category,
            limit=5,
        )

    if not statutes:
        statutes = await _text_search_statutes(
            db=db,
            query=normalized,
            category=request.category,
            limit=5,
        )

    # Step 6: Generate AI analysis — send full summaries (both EN and UR) to LLM
    case_law_dicts = [
        {
            "citation": cl.citation,
            "title": cl.title,
            "court": cl.court.value if cl.court else "N/A",
            "year": cl.year,
            "judge_name": cl.judge_name or "N/A",
            "summary": cl.summary_en or "",
            "summary_ur": cl.summary_ur or "",
            "headnotes": cl.headnotes,
            "sections_applied": cl.sections_applied,
            "relevant_statutes": cl.relevant_statutes,
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

    try:
        ai_analysis = await generate_scenario_analysis(
            scenario=request.query,
            case_laws=case_law_dicts,
            statutes=statute_dicts,
            language=language,
        )
    except Exception:
        ai_analysis = (
            "AI analysis is temporarily unavailable. "
            "Below are the matching legal references."
        )

    # Step 7: Build response BEFORE commit (commit can expire ORM objects)
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

    response = SearchResponse(
        query=request.query,
        detected_language=language,
        normalized_query=normalized,
        results=results,
        ai_analysis=ai_analysis,
        total_results=len(results),
    )

    # Step 8: Save search history (after building response, non-blocking)
    try:
        history = SearchHistory(
            user_id=user_id,
            query_text=request.query,
            detected_language=language,
            normalized_query=normalized,
            results_count=len(case_laws),
        )
        db.add(history)
        await db.commit()
    except Exception:
        pass  # Don't fail the response if history save fails

    return response


async def _vector_search_cases(
    db: AsyncSession,
    embedding: list[float],
    category: LawCategory = None,
    court: Court = None,
    year_from: int = None,
    year_to: int = None,
    limit: int = 10,
) -> list[CaseLaw]:
    """Batch cosine similarity search using cached numpy matrix (~50x faster)."""
    # Ensure cache is loaded
    if _cache.case_stale():
        await _load_case_embeddings(db)

    if _cache.case_matrix is None or len(_cache.case_ids) == 0:
        return []

    # Build filter mask over cached metadata
    mask = np.ones(len(_cache.case_ids), dtype=bool)
    for i, cid in enumerate(_cache.case_ids):
        meta = _cache.case_meta.get(cid, {})
        if category and meta.get("category") != category.value:
            mask[i] = False
        if court and meta.get("court") != court.value:
            mask[i] = False
        if year_from and (meta.get("year") or 0) < year_from:
            mask[i] = False
        if year_to and (meta.get("year") or 9999) > year_to:
            mask[i] = False

    if not mask.any():
        return []

    # Batch cosine similarity: dot(query, matrix^T) / (||query|| * ||rows||)
    query_vec = np.array(embedding, dtype=np.float32).reshape(1, -1)
    query_norm = np.linalg.norm(query_vec)
    if query_norm == 0:
        return []

    filtered_matrix = _cache.case_matrix[mask]
    filtered_norms = _cache.case_norms[mask]
    filtered_ids = np.array(_cache.case_ids)[mask]

    similarities = (filtered_matrix @ query_vec.T).flatten() / (filtered_norms.flatten() * query_norm)

    # Get top results above threshold
    above_thresh = similarities >= settings.SIMILARITY_THRESHOLD
    if not above_thresh.any():
        return []

    valid_sims = similarities[above_thresh]
    valid_ids = filtered_ids[above_thresh]

    # Get top-k indices
    top_k = min(limit, len(valid_sims))
    top_indices = np.argpartition(-valid_sims, top_k)[:top_k]
    top_indices = top_indices[np.argsort(-valid_sims[top_indices])]

    top_case_ids = [int(valid_ids[i]) for i in top_indices]
    top_scores = {int(valid_ids[i]): float(valid_sims[i]) for i in top_indices}

    # Fetch full ORM objects only for top results
    stmt = select(CaseLaw).where(CaseLaw.id.in_(top_case_ids))
    result = await db.execute(stmt)
    cases_by_id = {cl.id: cl for cl in result.scalars().all()}

    # Return in score order
    results = []
    for cid in top_case_ids:
        if cid in cases_by_id:
            cl = cases_by_id[cid]
            cl._similarity = top_scores[cid]
            results.append(cl)

    return results


async def _text_search_cases(
    db: AsyncSession,
    query: str,
    category: LawCategory = None,
    court: Court = None,
    year_from: int = None,
    year_to: int = None,
    limit: int = 10,
    section_numbers: list[str] = None,
) -> list[CaseLaw]:
    """Hybrid text-based search: prioritizes section number matches, then keyword matches."""
    results = []
    seen_ids = set()

    filter_conditions = []
    if category:
        filter_conditions.append(CaseLaw.category == category)
    if court:
        filter_conditions.append(CaseLaw.court == court)
    if year_from:
        filter_conditions.append(CaseLaw.year >= year_from)
    if year_to:
        filter_conditions.append(CaseLaw.year <= year_to)

    # Priority 1: Search by section numbers (e.g., "489-F", "302")
    if section_numbers:
        section_conditions = []
        for sec in section_numbers:
            pattern = f"%{sec}%"
            section_conditions.append(
                or_(
                    CaseLaw.sections_applied.ilike(pattern),
                    CaseLaw.headnotes.ilike(pattern),
                    CaseLaw.summary_en.ilike(pattern),
                    CaseLaw.summary_ur.ilike(pattern),
                    CaseLaw.title.ilike(pattern),
                )
            )
        stmt = (
            select(CaseLaw)
            .where(and_(*filter_conditions, or_(*section_conditions)))
            .order_by(CaseLaw.year.desc())
            .limit(limit)
        )
        result = await db.execute(stmt)
        for cl in result.scalars().all():
            if cl.id not in seen_ids:
                seen_ids.add(cl.id)
                cl._similarity = 0.95  # Very high score for section matches
                results.append(cl)

    # Priority 2: Keyword search
    keywords = _extract_keywords(query)
    if keywords and len(results) < limit:
        keyword_conditions = []
        for kw in keywords:
            pattern = f"%{kw}%"
            keyword_conditions.append(
                or_(
                    CaseLaw.title.ilike(pattern),
                    CaseLaw.summary_en.ilike(pattern),
                    CaseLaw.headnotes.ilike(pattern),
                    CaseLaw.sections_applied.ilike(pattern),
                    CaseLaw.relevant_statutes.ilike(pattern),
                )
            )

        if keyword_conditions:
            conditions = list(filter_conditions) + [or_(*keyword_conditions)]
            stmt = select(CaseLaw).where(and_(*conditions)).order_by(CaseLaw.year.desc()).limit(limit)
            result = await db.execute(stmt)
            for cl in result.scalars().all():
                if cl.id not in seen_ids:
                    seen_ids.add(cl.id)
                    cl._similarity = 0.85  # Good score for keyword matches
                    results.append(cl)

    return results[:limit]


async def _vector_search_statutes(
    db: AsyncSession,
    embedding: list[float],
    category: LawCategory = None,
    limit: int = 5,
) -> list[Statute]:
    """Batch cosine similarity search on statutes using cached numpy matrix."""
    if _cache.statute_stale():
        await _load_statute_embeddings(db)

    if _cache.statute_matrix is None or len(_cache.statute_ids) == 0:
        return []

    # Build filter mask
    mask = np.ones(len(_cache.statute_ids), dtype=bool)
    if category:
        for i, sid in enumerate(_cache.statute_ids):
            meta = _cache.statute_meta.get(sid, {})
            if meta.get("category") != category.value:
                mask[i] = False

    if not mask.any():
        return []

    query_vec = np.array(embedding, dtype=np.float32).reshape(1, -1)
    query_norm = np.linalg.norm(query_vec)
    if query_norm == 0:
        return []

    filtered_matrix = _cache.statute_matrix[mask]
    filtered_norms = _cache.statute_norms[mask]
    filtered_ids = np.array(_cache.statute_ids)[mask]

    similarities = (filtered_matrix @ query_vec.T).flatten() / (filtered_norms.flatten() * query_norm)

    top_k = min(limit, len(similarities))
    top_indices = np.argpartition(-similarities, top_k)[:top_k]
    top_indices = top_indices[np.argsort(-similarities[top_indices])]

    top_statute_ids = [int(filtered_ids[i]) for i in top_indices]
    top_scores = {int(filtered_ids[i]): float(similarities[i]) for i in top_indices}

    stmt = select(Statute).where(Statute.id.in_(top_statute_ids))
    result = await db.execute(stmt)
    statutes_by_id = {st.id: st for st in result.scalars().all()}

    results = []
    for sid in top_statute_ids:
        if sid in statutes_by_id:
            results.append(statutes_by_id[sid])

    return results


async def _text_search_statutes(
    db: AsyncSession,
    query: str,
    category: LawCategory = None,
    limit: int = 5,
) -> list[Statute]:
    """Fallback text-based search for statutes."""
    keywords = _extract_keywords(query)
    if not keywords:
        return []

    conditions = []
    if category:
        conditions.append(Statute.category == category)

    keyword_conditions = []
    for kw in keywords:
        pattern = f"%{kw}%"
        keyword_conditions.append(
            or_(
                Statute.title.ilike(pattern),
                Statute.summary_en.ilike(pattern),
            )
        )

    if keyword_conditions:
        conditions.append(or_(*keyword_conditions))

    stmt = select(Statute).where(and_(*conditions)).order_by(Statute.year.desc()).limit(limit)
    result = await db.execute(stmt)
    return list(result.scalars().all())
