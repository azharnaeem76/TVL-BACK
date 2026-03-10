"""AI Tools API - Summarizer, Opinion, Predictor, Contract Analyzer, Citation Finder."""
import json
import logging
import os
import tempfile
import httpx
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.security import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User
from app.services.embedding_service import generate_embedding
from app.services.search_service import _vector_search_cases

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

AI_TOOLS_SYSTEM = (
    "You are a Pakistani law expert. Respond ONLY in English. "
    "NEVER respond in Chinese, Arabic, Hindi, or any other language. "
    "Always return valid JSON when asked for JSON output."
)


async def _call_ollama(prompt: str) -> str:
    """Call Ollama and return the response text. Uses streaming internally to avoid timeouts."""
    try:
        full_response = []
        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream(
                "POST",
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "messages": [
                        {"role": "system", "content": AI_TOOLS_SYSTEM},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": True,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 2048,
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
                                raise HTTPException(status_code=503, detail=f"AI model error: {data['error']}")
                            text = data.get("message", {}).get("content", "")
                            if text:
                                full_response.append(text)
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue
        result = "".join(full_response)
        if not result.strip():
            raise HTTPException(status_code=503, detail="AI model returned empty response. It may be loading — please try again.")
        return result
    except HTTPException:
        raise
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="AI model server (Ollama) is not running. Please start it with 'ollama serve'.")
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


async def _get_db_context(db: AsyncSession, query: str, limit: int = 5) -> str:
    """Search database for relevant case laws to ground AI responses."""
    context_parts = []
    try:
        embedding = generate_embedding(query)
        cases = await _vector_search_cases(db=db, embedding=embedding, limit=limit)
        for cl in cases:
            context_parts.append(
                f"- {cl.citation} | {cl.title} | Court: {cl.court.value if cl.court else 'N/A'} | "
                f"Year: {cl.year}\n  Summary: {cl.summary_en or ''}\n  Sections: {cl.sections_applied or ''}"
            )
    except Exception as e:
        logger.warning(f"Vector search failed for AI tools context: {e}")
    return "\n".join(context_parts)


# ---------------------------------------------------------------------------
# AI Case Summarizer
# ---------------------------------------------------------------------------

@router.post("/summarize", response_model=AISummarizerResponse, summary="Summarize a legal judgment")
async def ai_summarize(
    request: AISummarizerRequest,
    db: AsyncSession = Depends(get_db),
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_context = await _get_db_context(db, f"{request.area_of_law} {request.facts[:200]}")

    prompt = f"""You are a senior Pakistani lawyer. Based on the facts provided, generate a preliminary legal opinion.
Area of law: {request.area_of_law}

CRITICAL: Your opinion MUST be grounded in actual Pakistani law. Cite real sections and case precedents only.

{f"Relevant Pakistani case laws from our database:{chr(10)}{db_context}" if db_context else ""}

Return your response as JSON:
{{
  "opinion": "detailed legal opinion (3-5 paragraphs) citing specific Pakistani law",
  "applicable_laws": ["Pakistan Penal Code Section 302", "CrPC Section 154"],
  "strengths": ["strength 1", "strength 2"],
  "weaknesses": ["weakness 1", "weakness 2"],
  "recommendation": "recommended course of action under Pakistani law"
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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_context = await _get_db_context(db, f"{request.area_of_law} {request.case_description[:200]}")

    prompt = f"""You are a Pakistani legal analyst. Based on this case description and Pakistani legal precedents, predict the likely outcome.
Area of law: {request.area_of_law}

CRITICAL: Use ONLY actual Pakistani case precedents. Do NOT fabricate case citations.

{f"Relevant Pakistani case laws from our database:{chr(10)}{db_context}" if db_context else ""}

Return your response as JSON:
{{
  "prediction": "likely outcome analysis (2-3 paragraphs) based on Pakistani precedents",
  "confidence": "High/Medium/Low",
  "factors_for": ["factor favoring success 1", "factor 2"],
  "factors_against": ["factor against 1", "factor 2"],
  "similar_cases": ["cite actual cases from the data above"]
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


def _extract_text_from_file(file_path: str, content_type: str) -> str:
    """Extract text from uploaded document (PDF, image, Word)."""
    ext = os.path.splitext(file_path)[1].lower()

    # PDF
    if ext == ".pdf" or "pdf" in content_type:
        import pdfplumber
        text_parts = []
        with pdfplumber.open(file_path) as pdf:
            for page in pdf.pages[:50]:  # limit to 50 pages
                page_text = page.extract_text()
                if page_text:
                    text_parts.append(page_text)
        return "\n".join(text_parts)

    # Word documents
    if ext in (".docx", ".doc") or "word" in content_type or "document" in content_type:
        from docx import Document
        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs if p.text.strip())

    # Images (OCR)
    if ext in (".png", ".jpg", ".jpeg", ".tiff", ".bmp", ".webp") or "image" in content_type:
        from PIL import Image
        import pytesseract
        img = Image.open(file_path)
        return pytesseract.image_to_string(img)

    # Plain text
    if ext in (".txt", ".text") or "text/plain" in content_type:
        with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    raise ValueError(f"Unsupported file type: {ext or content_type}")


@router.post("/analyze-contract-upload", response_model=AIContractResponse, summary="Upload document for contract analysis")
async def ai_analyze_contract_upload(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_user),
):
    allowed_types = [
        "application/pdf", "application/msword",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "image/png", "image/jpeg", "image/jpg", "image/tiff", "image/bmp", "image/webp",
        "text/plain",
    ]
    if file.content_type and not any(t in file.content_type for t in ["pdf", "word", "image", "text", "document", "msword"]):
        raise HTTPException(status_code=400, detail=f"Unsupported file type: {file.content_type}. Upload PDF, Word, image, or text files.")

    if file.size and file.size > 20 * 1024 * 1024:  # 20MB limit
        raise HTTPException(status_code=400, detail="File too large. Maximum 20MB.")

    # Save to temp file and extract text
    suffix = os.path.splitext(file.filename or "")[1] or ".pdf"
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        extracted_text = _extract_text_from_file(tmp_path, file.content_type or "")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Text extraction failed: {e}")
        raise HTTPException(status_code=400, detail="Could not extract text from file. Try pasting the text manually.")
    finally:
        try:
            os.unlink(tmp_path)
        except Exception:
            pass

    if not extracted_text or len(extracted_text.strip()) < 10:
        raise HTTPException(status_code=400, detail="Could not extract meaningful text from the file. Try a clearer scan or paste text manually.")

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
{extracted_text[:6000]}"""

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
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_context = await _get_db_context(db, f"{request.area_of_law} {request.legal_principle[:200]}", limit=8)

    prompt = f"""You are a Pakistani legal researcher. Find relevant case citations and statutes for this legal principle.
Area of law: {request.area_of_law}

CRITICAL: ONLY cite cases that exist in the database below. Do NOT fabricate citations.

{f"Pakistani case laws from our database:{chr(10)}{db_context}" if db_context else ""}

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
