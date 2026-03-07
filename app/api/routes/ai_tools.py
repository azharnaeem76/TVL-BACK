"""AI Tools API - Summarizer, Opinion, Predictor, Contract Analyzer, Citation Finder."""
import json
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from app.core.security import get_current_user
from app.core.config import get_settings
from app.models.user import User

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/ai-tools", tags=["AI Tools"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class AISummarizerRequest(BaseModel):
    text: str = Field(..., min_length=10, max_length=50000)
    language: str = "english"

class AISummarizerResponse(BaseModel):
    summary: str
    key_points: list[str]
    sections_cited: list[str]
    court: Optional[str] = None

class AIOpinionRequest(BaseModel):
    facts: str = Field(..., min_length=10, max_length=30000)
    area_of_law: str = Field("general", max_length=100)
    language: str = "english"

class AIOpinionResponse(BaseModel):
    opinion: str
    applicable_laws: list[str]
    strengths: list[str]
    weaknesses: list[str]
    recommendation: str

class AIPredictorRequest(BaseModel):
    case_description: str = Field(..., min_length=10, max_length=30000)
    area_of_law: str = Field("general", max_length=100)
    language: str = "english"

class AIPredictorResponse(BaseModel):
    prediction: str
    confidence: str
    factors_for: list[str]
    factors_against: list[str]
    similar_cases: list[str]

class AIContractRequest(BaseModel):
    contract_text: str = Field(..., min_length=10, max_length=50000)
    language: str = "english"

class AIContractResponse(BaseModel):
    summary: str
    risky_clauses: list[dict]
    missing_clauses: list[str]
    recommendations: list[str]
    overall_risk: str

class CitationFinderRequest(BaseModel):
    legal_principle: str = Field(..., min_length=5, max_length=20000)
    area_of_law: str = Field("general", max_length=100)
    language: str = "english"

class CitationFinderResponse(BaseModel):
    citations: list[dict]
    statutes: list[str]
    explanation: str


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _call_ollama(prompt: str) -> str:
    """Call Ollama and return the response text."""
    try:
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={"model": settings.OLLAMA_MODEL, "prompt": prompt, "stream": False},
            )
        if resp.status_code == 200:
            return resp.json().get("response", "")
        return ""
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="AI model server (Ollama) is not running. Please start it with 'ollama serve'.")
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        raise HTTPException(status_code=500, detail="AI processing failed")


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


# ---------------------------------------------------------------------------
# AI Case Summarizer
# ---------------------------------------------------------------------------

@router.post("/summarize", response_model=AISummarizerResponse, summary="Summarize a legal judgment")
async def ai_summarize(
    request: AISummarizerRequest,
    current_user: User = Depends(get_current_user),
):
    prompt = f"""You are a Pakistani law expert. Summarize this legal judgment/document.
Return your response as JSON:
{{
  "summary": "comprehensive 3-5 sentence summary",
  "key_points": ["point 1", "point 2", "point 3"],
  "sections_cited": ["Section 302 PPC", "Section 497 CrPC"],
  "court": "name of the court if identifiable"
}}

Text to summarize:
{request.text[:6000]}"""

    ai_text = await _call_ollama(prompt)
    parsed = _parse_json(ai_text)

    return AISummarizerResponse(
        summary=parsed.get("summary", ai_text[:2000] if ai_text else "Could not generate summary."),
        key_points=parsed.get("key_points", []),
        sections_cited=parsed.get("sections_cited", []),
        court=parsed.get("court"),
    )


# ---------------------------------------------------------------------------
# AI Legal Opinion
# ---------------------------------------------------------------------------

@router.post("/opinion", response_model=AIOpinionResponse, summary="Generate preliminary legal opinion")
async def ai_opinion(
    request: AIOpinionRequest,
    current_user: User = Depends(get_current_user),
):
    prompt = f"""You are a senior Pakistani lawyer. Based on the facts provided, generate a preliminary legal opinion.
Area of law: {request.area_of_law}

Return your response as JSON:
{{
  "opinion": "detailed legal opinion (3-5 paragraphs)",
  "applicable_laws": ["Pakistan Penal Code Section 302", "CrPC Section 154"],
  "strengths": ["strength 1", "strength 2"],
  "weaknesses": ["weakness 1", "weakness 2"],
  "recommendation": "recommended course of action"
}}

Facts:
{request.facts[:4000]}"""

    ai_text = await _call_ollama(prompt)
    parsed = _parse_json(ai_text)

    return AIOpinionResponse(
        opinion=parsed.get("opinion", ai_text[:3000] if ai_text else "Could not generate opinion."),
        applicable_laws=parsed.get("applicable_laws", []),
        strengths=parsed.get("strengths", []),
        weaknesses=parsed.get("weaknesses", []),
        recommendation=parsed.get("recommendation", "Please consult a qualified lawyer for specific legal advice."),
    )


# ---------------------------------------------------------------------------
# Case Outcome Predictor
# ---------------------------------------------------------------------------

@router.post("/predict", response_model=AIPredictorResponse, summary="Predict case outcome")
async def ai_predict(
    request: AIPredictorRequest,
    current_user: User = Depends(get_current_user),
):
    prompt = f"""You are a Pakistani legal analyst. Based on this case description and Pakistani legal precedents, predict the likely outcome.
Area of law: {request.area_of_law}

Return your response as JSON:
{{
  "prediction": "likely outcome analysis (2-3 paragraphs)",
  "confidence": "High/Medium/Low",
  "factors_for": ["factor favoring success 1", "factor 2"],
  "factors_against": ["factor against 1", "factor 2"],
  "similar_cases": ["PLD 2020 SC 1 - brief description", "2019 SCMR 123 - brief description"]
}}

Case description:
{request.case_description[:4000]}"""

    ai_text = await _call_ollama(prompt)
    parsed = _parse_json(ai_text)

    return AIPredictorResponse(
        prediction=parsed.get("prediction", ai_text[:3000] if ai_text else "Could not generate prediction."),
        confidence=parsed.get("confidence", "Medium"),
        factors_for=parsed.get("factors_for", []),
        factors_against=parsed.get("factors_against", []),
        similar_cases=parsed.get("similar_cases", []),
    )


# ---------------------------------------------------------------------------
# Contract Analyzer
# ---------------------------------------------------------------------------

@router.post("/analyze-contract", response_model=AIContractResponse, summary="Analyze contract for risks")
async def ai_analyze_contract(
    request: AIContractRequest,
    current_user: User = Depends(get_current_user),
):
    prompt = f"""You are a Pakistani contract law expert. Analyze this contract for risky or unfair clauses under Pakistani law (Contract Act 1872).

Return your response as JSON:
{{
  "summary": "brief summary of the contract",
  "risky_clauses": [
    {{"clause": "quoted clause text", "risk": "description of risk", "severity": "High/Medium/Low"}}
  ],
  "missing_clauses": ["important clause that should be included"],
  "recommendations": ["recommendation 1", "recommendation 2"],
  "overall_risk": "High/Medium/Low"
}}

Contract text:
{request.contract_text[:6000]}"""

    ai_text = await _call_ollama(prompt)
    parsed = _parse_json(ai_text)

    return AIContractResponse(
        summary=parsed.get("summary", ai_text[:2000] if ai_text else "Could not analyze contract."),
        risky_clauses=parsed.get("risky_clauses", []),
        missing_clauses=parsed.get("missing_clauses", []),
        recommendations=parsed.get("recommendations", []),
        overall_risk=parsed.get("overall_risk", "Unknown"),
    )


# ---------------------------------------------------------------------------
# Citation Finder
# ---------------------------------------------------------------------------

@router.post("/find-citations", response_model=CitationFinderResponse, summary="Find citations for legal principle")
async def ai_find_citations(
    request: CitationFinderRequest,
    current_user: User = Depends(get_current_user),
):
    prompt = f"""You are a Pakistani legal researcher. Find relevant case citations and statutes for this legal principle.
Area of law: {request.area_of_law}

Return your response as JSON:
{{
  "citations": [
    {{"citation": "PLD 2020 Supreme Court 1", "title": "State vs Accused", "relevance": "directly relevant because..."}},
    {{"citation": "2019 SCMR 456", "title": "Petitioner vs State", "relevance": "relevant because..."}}
  ],
  "statutes": ["Section 302 PPC", "Article 10-A Constitution of Pakistan"],
  "explanation": "detailed explanation of how these citations relate to the principle"
}}

Legal principle:
{request.legal_principle[:3000]}"""

    ai_text = await _call_ollama(prompt)
    parsed = _parse_json(ai_text)

    return CitationFinderResponse(
        citations=parsed.get("citations", []),
        statutes=parsed.get("statutes", []),
        explanation=parsed.get("explanation", ai_text[:2000] if ai_text else "Could not find citations."),
    )
