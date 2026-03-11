"""
AI Legal Research Agent - Deep Research Tool.

Users input a legal scenario and the AI finds relevant case laws, statutes,
and builds full legal arguments with citations.
"""

import json
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User
from app.services.embedding_service import generate_embedding
from app.services.search_service import (
    _vector_search_cases,
    _vector_search_statutes,
    _text_search_cases,
    _text_search_statutes,
)

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/legal-research", tags=["Legal Research Agent"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class DeepResearchRequest(BaseModel):
    scenario: str = Field(..., min_length=10, max_length=50000)
    area_of_law: str = Field("general", max_length=100)
    research_depth: str = Field("standard", pattern="^(quick|standard|deep)$")
    language: str = "english"


class CaseResult(BaseModel):
    citation: str
    title: str
    court: Optional[str] = None
    year: Optional[int] = None
    relevance_score: Optional[float] = None
    summary: Optional[str] = None
    headnotes: Optional[str] = None
    sections_applied: Optional[str] = None


class StatuteResult(BaseModel):
    title: str
    act_number: Optional[str] = None
    year: Optional[int] = None
    summary: Optional[str] = None


class DeepResearchResponse(BaseModel):
    legal_analysis: str
    arguments_for: list[str]
    arguments_against: list[str]
    relevant_cases: list[CaseResult]
    applicable_statutes: list[StatuteResult]
    recommended_strategy: str
    risk_assessment: str
    confidence_level: str


class FindPrecedentsRequest(BaseModel):
    case_description: str = Field(..., min_length=10, max_length=30000)
    jurisdiction: Optional[str] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None


class FindPrecedentsResponse(BaseModel):
    precedents: list[CaseResult]
    total_found: int


class BuildArgumentRequest(BaseModel):
    position: str = Field(..., min_length=10, max_length=20000)
    supporting_facts: list[str] = Field(..., min_length=1)
    area_of_law: str = Field("general", max_length=100)


class BuildArgumentResponse(BaseModel):
    argument: str
    legal_basis: list[str]
    cited_cases: list[str]
    cited_statutes: list[str]
    counter_arguments: list[str]
    strength_rating: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RESEARCH_SYSTEM = (
    "You are a senior Pakistani legal research agent with deep expertise in "
    "Pakistani law, case precedents, and statutory interpretation. "
    "Respond ONLY in English. NEVER respond in Chinese, Arabic, Hindi, or any "
    "other language. Always return valid JSON when asked for JSON output. "
    "Ground all analysis in actual Pakistani law. Do NOT fabricate citations."
)


async def _call_ollama_research(prompt: str, max_tokens: int = 4096) -> str:
    """Call Ollama with streaming to avoid timeouts. Extended for deep research."""
    try:
        full_response = []
        async with httpx.AsyncClient(timeout=300.0) as client:
            async with client.stream(
                "POST",
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "messages": [
                        {"role": "system", "content": RESEARCH_SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": True,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": max_tokens,
                    },
                },
            ) as resp:
                if resp.status_code != 200:
                    body = await resp.aread()
                    try:
                        err = json.loads(body).get("error", "Unknown error")
                    except Exception:
                        err = body.decode("utf-8", errors="replace")[:200]
                    raise HTTPException(status_code=503, detail=f"AI model error: {err}")

                async for line in resp.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            if "error" in data:
                                raise HTTPException(
                                    status_code=503,
                                    detail=f"AI model error: {data['error']}",
                                )
                            text = data.get("message", {}).get("content", "")
                            if text:
                                full_response.append(text)
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
        result = "".join(full_response)
        if not result.strip():
            raise HTTPException(
                status_code=503,
                detail="AI model returned empty response. It may be loading — please try again.",
            )
        return result
    except HTTPException:
        raise
    except httpx.ConnectError:
        raise HTTPException(
            status_code=503,
            detail="AI model server (Ollama) is not running. Please start it with 'ollama serve'.",
        )
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        raise HTTPException(status_code=500, detail=f"AI processing failed: {str(e)}")


def _parse_json(text: str) -> dict:
    """Extract JSON from AI response text."""
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    return {}


def _depth_to_limits(depth: str) -> tuple[int, int, int]:
    """Return (case_limit, statute_limit, max_tokens) based on research depth."""
    if depth == "quick":
        return 5, 3, 2048
    elif depth == "deep":
        return 20, 10, 4096
    else:  # standard
        return 10, 5, 3072


async def _gather_research_context(
    db: AsyncSession,
    query: str,
    area_of_law: str,
    case_limit: int,
    statute_limit: int,
) -> tuple[list, list, str, str]:
    """Search for relevant cases and statutes, return raw objects and context strings."""
    search_query = f"{area_of_law} {query[:500]}"

    # Generate embedding
    try:
        embedding = generate_embedding(search_query)
    except Exception:
        embedding = None

    # Search cases
    cases = []
    if embedding:
        cases = await _vector_search_cases(db=db, embedding=embedding, limit=case_limit)
    if not cases:
        cases = await _text_search_cases(db=db, query=search_query, limit=case_limit)

    # Search statutes
    statutes = []
    if embedding:
        statutes = await _vector_search_statutes(db=db, embedding=embedding, limit=statute_limit)
    if not statutes:
        statutes = await _text_search_statutes(db=db, query=search_query, limit=statute_limit)

    # Build context strings
    case_context_parts = []
    for cl in cases:
        score = getattr(cl, "_similarity", 0)
        case_context_parts.append(
            f"- [{score:.0%} relevance] {cl.citation} | {cl.title} | "
            f"Court: {cl.court.value if cl.court else 'N/A'} | Year: {cl.year}\n"
            f"  Summary: {cl.summary_en or ''}\n"
            f"  Headnotes: {cl.headnotes or ''}\n"
            f"  Sections: {cl.sections_applied or ''}"
        )
    case_context = "\n".join(case_context_parts)

    statute_context_parts = []
    for st in statutes:
        statute_context_parts.append(
            f"- {st.title} (Act {st.act_number or 'N/A'}, {st.year or 'N/A'})\n"
            f"  Summary: {st.summary_en or ''}"
        )
    statute_context = "\n".join(statute_context_parts)

    return cases, statutes, case_context, statute_context


# ---------------------------------------------------------------------------
# 1. POST /legal-research/research - Main Deep Research
# ---------------------------------------------------------------------------

@router.post(
    "/research",
    response_model=DeepResearchResponse,
    summary="Deep legal research on a scenario",
)
async def deep_research(
    request: DeepResearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Comprehensive legal research agent. Searches for relevant case laws and
    statutes, then builds structured legal arguments with citations.
    """
    case_limit, statute_limit, max_tokens = _depth_to_limits(request.research_depth)

    cases, statutes, case_context, statute_context = await _gather_research_context(
        db=db,
        query=request.scenario,
        area_of_law=request.area_of_law,
        case_limit=case_limit,
        statute_limit=statute_limit,
    )

    prompt = f"""You are a senior Pakistani legal research agent conducting {request.research_depth} research.
Area of Law: {request.area_of_law}

RELEVANT CASE LAWS FROM DATABASE:
{case_context if case_context else "(No matching cases found in database)"}

RELEVANT STATUTES FROM DATABASE:
{statute_context if statute_context else "(No matching statutes found in database)"}

Based on the above legal sources and your expertise in Pakistani law, conduct a comprehensive
legal research analysis of the following scenario. ONLY cite cases and statutes from the data above.

Return your response as JSON:
{{
  "legal_analysis": "Comprehensive legal analysis (3-6 paragraphs) covering the legal position, applicable framework, and precedent analysis under Pakistani law",
  "arguments_for": ["Strong argument 1 with citation", "Argument 2 with citation", "..."],
  "arguments_against": ["Counter-argument 1 with citation", "Counter-argument 2 with citation", "..."],
  "recommended_strategy": "Detailed recommended legal strategy (2-3 paragraphs)",
  "risk_assessment": "Assessment of legal risks and likelihood of success",
  "confidence_level": "High/Medium/Low based on strength of available precedents"
}}

SCENARIO:
{request.scenario[:8000]}"""

    ai_text = await _call_ollama_research(prompt, max_tokens=max_tokens)
    parsed = _parse_json(ai_text)

    # Build case results
    relevant_cases = [
        CaseResult(
            citation=cl.citation,
            title=cl.title,
            court=cl.court.value if cl.court else None,
            year=cl.year,
            relevance_score=round(getattr(cl, "_similarity", 0), 3),
            summary=cl.summary_en,
            headnotes=cl.headnotes,
            sections_applied=cl.sections_applied,
        )
        for cl in cases
    ]

    # Build statute results
    applicable_statutes = [
        StatuteResult(
            title=st.title,
            act_number=st.act_number if hasattr(st, "act_number") else None,
            year=st.year,
            summary=st.summary_en,
        )
        for st in statutes
    ]

    return DeepResearchResponse(
        legal_analysis=parsed.get(
            "legal_analysis",
            ai_text[:4000] if ai_text else "Could not generate analysis.",
        ),
        arguments_for=parsed.get("arguments_for", []),
        arguments_against=parsed.get("arguments_against", []),
        relevant_cases=relevant_cases,
        applicable_statutes=applicable_statutes,
        recommended_strategy=parsed.get(
            "recommended_strategy",
            "Please review the analysis above and consult a qualified lawyer.",
        ),
        risk_assessment=parsed.get(
            "risk_assessment",
            "Unable to assess risk. Please consult a qualified lawyer.",
        ),
        confidence_level=parsed.get("confidence_level", "Medium"),
    )


# ---------------------------------------------------------------------------
# 2. POST /legal-research/find-precedents - Find Similar Precedents
# ---------------------------------------------------------------------------

@router.post(
    "/find-precedents",
    response_model=FindPrecedentsResponse,
    summary="Find similar legal precedents",
)
async def find_precedents(
    request: FindPrecedentsRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Vector search for similar case law precedents ranked by relevance.
    """
    try:
        embedding = generate_embedding(request.case_description)
    except Exception:
        embedding = None

    cases = []
    if embedding:
        cases = await _vector_search_cases(
            db=db,
            embedding=embedding,
            year_from=request.year_from,
            year_to=request.year_to,
            limit=20,
        )
    if not cases:
        cases = await _text_search_cases(
            db=db,
            query=request.case_description,
            year_from=request.year_from,
            year_to=request.year_to,
            limit=20,
        )

    precedents = [
        CaseResult(
            citation=cl.citation,
            title=cl.title,
            court=cl.court.value if cl.court else None,
            year=cl.year,
            relevance_score=round(getattr(cl, "_similarity", 0), 3),
            summary=cl.summary_en,
            headnotes=cl.headnotes,
            sections_applied=cl.sections_applied,
        )
        for cl in cases
    ]

    return FindPrecedentsResponse(
        precedents=precedents,
        total_found=len(precedents),
    )


# ---------------------------------------------------------------------------
# 3. POST /legal-research/build-argument - Build Legal Argument
# ---------------------------------------------------------------------------

@router.post(
    "/build-argument",
    response_model=BuildArgumentResponse,
    summary="Build a structured legal argument",
)
async def build_argument(
    request: BuildArgumentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    AI builds a structured legal argument with citations from the database.
    """
    combined_query = f"{request.area_of_law} {request.position}"
    cases, statutes, case_context, statute_context = await _gather_research_context(
        db=db,
        query=combined_query,
        area_of_law=request.area_of_law,
        case_limit=10,
        statute_limit=5,
    )

    facts_str = "\n".join(f"- {fact}" for fact in request.supporting_facts)

    prompt = f"""You are a senior Pakistani litigation lawyer building a legal argument.
Area of Law: {request.area_of_law}

RELEVANT CASE LAWS FROM DATABASE:
{case_context if case_context else "(No matching cases found)"}

RELEVANT STATUTES FROM DATABASE:
{statute_context if statute_context else "(No matching statutes found)"}

Build a comprehensive legal argument for the following position, using ONLY the cases
and statutes from the data above. Structure it as a formal legal submission.

Return your response as JSON:
{{
  "argument": "Full structured legal argument (4-8 paragraphs) with proper citations in Pakistani legal format. Include introduction, legal framework, application of law to facts, and conclusion.",
  "legal_basis": ["Section X of Y Act", "Article Z of Constitution"],
  "cited_cases": ["PLD 2020 SC 1 - Case Title", "2019 SCMR 456 - Case Title"],
  "cited_statutes": ["Pakistan Penal Code 1860", "Code of Criminal Procedure 1898"],
  "counter_arguments": ["Potential counter-argument 1 and how to rebut it", "Counter-argument 2"],
  "strength_rating": "Strong/Moderate/Weak"
}}

POSITION TO ARGUE:
{request.position[:4000]}

SUPPORTING FACTS:
{facts_str[:3000]}"""

    ai_text = await _call_ollama_research(prompt, max_tokens=3072)
    parsed = _parse_json(ai_text)

    return BuildArgumentResponse(
        argument=parsed.get(
            "argument",
            ai_text[:5000] if ai_text else "Could not build argument.",
        ),
        legal_basis=parsed.get("legal_basis", []),
        cited_cases=parsed.get("cited_cases", []),
        cited_statutes=parsed.get("cited_statutes", []),
        counter_arguments=parsed.get("counter_arguments", []),
        strength_rating=parsed.get("strength_rating", "Moderate"),
    )


# ---------------------------------------------------------------------------
# 4. GET /legal-research/history - Research History (stub)
# ---------------------------------------------------------------------------

@router.get(
    "/history",
    summary="Get research history",
)
async def get_research_history(
    current_user: User = Depends(get_current_user),
):
    """
    Get the current user's legal research history.
    Stub endpoint — full implementation with DB persistence coming soon.
    """
    return {
        "history": [],
        "total": 0,
        "message": "Research history tracking coming soon.",
    }
