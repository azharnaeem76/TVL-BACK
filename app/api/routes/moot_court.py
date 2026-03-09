"""Moot Court Simulator & Exam Preparation API."""
import json
import logging
import httpx
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from app.core.security import get_current_user
from app.core.config import get_settings
from app.core.database import get_db
from app.models.user import User
from app.models.legal import CaseLaw, Statute, Section
from app.services.embedding_service import generate_embedding
from app.services.search_service import _vector_search_cases

logger = logging.getLogger(__name__)
settings = get_settings()
router = APIRouter(prefix="/student-tools", tags=["Student Tools"])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _call_ollama(prompt: str) -> str:
    """Call Ollama using streaming to avoid timeouts. Raises HTTPException on failure."""
    try:
        full_response = []
        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream(
                "POST",
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": True,
                    "options": {"temperature": 0.3, "num_predict": 4096},
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
                            text = data.get("response", "")
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
        raise HTTPException(status_code=503, detail="AI model (Ollama) is not running. Please start it with 'ollama serve'.")
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        raise HTTPException(status_code=500, detail=f"AI processing failed: {str(e)}")


def _parse_json(text: str) -> dict:
    # Try to find JSON object
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    # Try array
    start = text.find("[")
    end = text.rfind("]") + 1
    if start >= 0 and end > start:
        try:
            return {"items": json.loads(text[start:end])}
        except json.JSONDecodeError:
            pass
    return {}


async def _get_relevant_context(db: AsyncSession, topic: str, limit: int = 5) -> str:
    """Search database for relevant case laws and statutes to ground AI responses."""
    context_parts = []
    try:
        embedding = generate_embedding(topic)
        cases = await _vector_search_cases(db=db, embedding=embedding, limit=limit)
        for cl in cases:
            context_parts.append(
                f"- {cl.citation} | {cl.title} | Court: {cl.court.value if cl.court else 'N/A'} | "
                f"Year: {cl.year}\n  Summary: {cl.summary_en or ''}\n  Sections: {cl.sections_applied or ''}"
            )
    except Exception as e:
        logger.warning(f"Vector search failed, falling back to text search: {e}")
        # Fallback to text search
        try:
            result = await db.execute(
                select(CaseLaw)
                .where(
                    CaseLaw.title.ilike(f"%{topic.split()[0] if topic.split() else topic}%")
                    | CaseLaw.headnotes.ilike(f"%{topic.split()[0] if topic.split() else topic}%")
                )
                .limit(limit)
            )
            for cl in result.scalars().all():
                context_parts.append(
                    f"- {cl.citation} | {cl.title} | Court: {cl.court.value if cl.court else 'N/A'} | "
                    f"Year: {cl.year}\n  Summary: {cl.summary_en or ''}"
                )
        except Exception:
            pass

    # Also get relevant statute sections
    try:
        words = [w for w in topic.split() if len(w) > 3][:3]
        for word in words:
            result = await db.execute(
                select(Section)
                .where(Section.content.ilike(f"%{word}%"))
                .limit(3)
            )
            for sec in result.scalars().all():
                context_parts.append(f"- Section {sec.section_number}: {sec.content[:200]}")
    except Exception:
        pass

    return "\n".join(context_parts)


# ---------------------------------------------------------------------------
# Moot Court Simulator
# ---------------------------------------------------------------------------

class MootCourtRequest(BaseModel):
    topic: str = Field(..., min_length=3, max_length=1000)
    side: str = Field("petitioner", pattern=r"^(petitioner|respondent)$")
    language: str = "english"

class MootCourtResponse(BaseModel):
    scenario: str
    your_arguments: list[str]
    opposing_arguments: list[str]
    judge_questions: list[str]
    relevant_cases: list[str]
    tips: list[str]

class MootCourtArgumentRequest(BaseModel):
    scenario: str = Field(..., min_length=10, max_length=10000)
    your_argument: str = Field(..., min_length=10, max_length=20000)
    side: str = Field("petitioner", pattern=r"^(petitioner|respondent)$")

class MootCourtFeedback(BaseModel):
    score: int
    feedback: str
    strengths: list[str]
    improvements: list[str]
    model_answer: str


@router.post("/moot-court/scenario", response_model=MootCourtResponse, summary="Generate moot court scenario")
async def generate_moot_scenario(
    request: MootCourtRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Get relevant case laws from database
    db_context = await _get_relevant_context(db, request.topic)

    prompt = f"""You are a Pakistani law professor creating a moot court exercise.
Topic: {request.topic}
Student's side: {request.side}

IMPORTANT: Base your scenario on ACTUAL Pakistani law. Use ONLY real Pakistani case citations and statutes.

{f"Relevant Pakistani case laws and statutes from our database:{chr(10)}{db_context}" if db_context else ""}

Return ONLY valid JSON (no markdown, no extra text):
{{
  "scenario": "detailed moot court scenario (2-3 paragraphs) based on Pakistani law with specific legal provisions",
  "your_arguments": ["argument 1 for {request.side} citing specific Pakistani law", "argument 2", "argument 3"],
  "opposing_arguments": ["counter-argument 1 with legal basis", "counter-argument 2"],
  "judge_questions": ["question a Pakistani judge might ask 1", "question 2", "question 3"],
  "relevant_cases": ["PLD 2020 SC 1 - brief", "2019 SCMR 123 - brief"],
  "tips": ["tip for arguing this case 1", "tip 2"]
}}"""

    ai_text = await _call_ollama(prompt)
    parsed = _parse_json(ai_text)

    if not parsed.get("scenario"):
        raise HTTPException(status_code=500, detail="AI could not generate a valid scenario. Please try again.")

    return MootCourtResponse(
        scenario=parsed.get("scenario", ""),
        your_arguments=parsed.get("your_arguments", []),
        opposing_arguments=parsed.get("opposing_arguments", []),
        judge_questions=parsed.get("judge_questions", []),
        relevant_cases=parsed.get("relevant_cases", []),
        tips=parsed.get("tips", []),
    )


@router.post("/moot-court/evaluate", response_model=MootCourtFeedback, summary="Evaluate moot court argument")
async def evaluate_argument(
    request: MootCourtArgumentRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_context = await _get_relevant_context(db, request.scenario[:200])

    prompt = f"""You are a Pakistani law professor evaluating a moot court argument.

Scenario: {request.scenario[:2000]}
Student's side: {request.side}
Student's argument: {request.your_argument[:3000]}

{f"Relevant Pakistani case laws for reference:{chr(10)}{db_context}" if db_context else ""}

Evaluate the argument based on Pakistani law. Check if citations are accurate and arguments are legally sound.

Return ONLY valid JSON (no markdown, no extra text):
{{
  "score": 75,
  "feedback": "overall assessment of the argument under Pakistani law",
  "strengths": ["strength 1", "strength 2"],
  "improvements": ["area for improvement 1", "area 2"],
  "model_answer": "a model answer for this scenario citing specific Pakistani law (2-3 paragraphs)"
}}"""

    ai_text = await _call_ollama(prompt)
    parsed = _parse_json(ai_text)

    return MootCourtFeedback(
        score=parsed.get("score", 50),
        feedback=parsed.get("feedback", ai_text[:2000] if ai_text else "Could not evaluate."),
        strengths=parsed.get("strengths", []),
        improvements=parsed.get("improvements", []),
        model_answer=parsed.get("model_answer", ""),
    )


# ---------------------------------------------------------------------------
# Exam Preparation
# ---------------------------------------------------------------------------

EXAM_TYPES = {
    "llb": {"name": "LLB (Bachelor of Laws)", "description": "5-year law degree examination"},
    "bar": {"name": "Bar Council Exam", "description": "Pakistan Bar Council licensing exam"},
    "lat": {"name": "LAT (Law Admission Test)", "description": "HEC Law Admission Test for entry into LLB programs"},
    "gat_general": {"name": "GAT General", "description": "NTS Graduate Assessment Test (General) for post-graduate admissions"},
    "gat_law": {"name": "GAT Subject (Law)", "description": "NTS Graduate Assessment Test - Law subject for LLM/PhD admissions"},
    "css_law": {"name": "CSS (Law & Constitutional)", "description": "Central Superior Services - Law, Constitutional Law & Jurisprudence papers"},
    "pms_law": {"name": "PMS (Law Papers)", "description": "Provincial Management Services - Law elective papers"},
    "judiciary": {"name": "Judiciary Exam", "description": "Civil Judge / Additional Sessions Judge competitive exam"},
    "nts_law": {"name": "NTS Law Lecturer", "description": "NTS test for Law Lecturer positions"},
    "llm": {"name": "LLM Entrance", "description": "Master of Laws entrance exam for universities"},
}


class ExamPrepRequest(BaseModel):
    subject: str = Field(..., min_length=2, max_length=200)
    exam_type: str = Field("llb", description="Type of exam: llb, bar, lat, gat_general, gat_law, css_law, pms_law, judiciary, nts_law, llm")
    topic: Optional[str] = Field(None, max_length=500)
    num_questions: int = Field(5, ge=1, le=20)

class ExamQuestion(BaseModel):
    question: str
    options: list[str]
    correct_answer: str
    explanation: str

class ExamPrepResponse(BaseModel):
    subject: str
    questions: list[ExamQuestion]

class ExamAnswerRequest(BaseModel):
    question: str = Field(..., min_length=5, max_length=5000)
    student_answer: str = Field(..., min_length=1, max_length=10000)
    subject: str = Field(..., min_length=2, max_length=200)

class ExamAnswerFeedback(BaseModel):
    is_correct: bool
    score: int
    feedback: str
    correct_answer: str
    explanation: str


@router.get("/exam-types", summary="List available exam types")
async def list_exam_types(current_user: User = Depends(get_current_user)):
    return [{"key": k, "name": v["name"], "description": v["description"]} for k, v in EXAM_TYPES.items()]


@router.post("/exam-prep/generate", response_model=ExamPrepResponse, summary="Generate exam questions")
async def generate_exam_questions(
    request: ExamPrepRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    exam_info = EXAM_TYPES.get(request.exam_type, EXAM_TYPES["llb"])
    topic_str = f" on topic: {request.topic}" if request.topic else ""

    # Get relevant sections from database for grounding
    db_context = await _get_relevant_context(db, f"{request.subject} {request.topic or ''}")

    prompt = f"""You are a Pakistani law examiner preparing {exam_info['name']} level questions.
Subject: {request.subject}{topic_str}
Exam context: {exam_info['description']}

IMPORTANT: All questions MUST be based on actual Pakistani law. Cite specific sections, articles, and case precedents.

{f"Relevant Pakistani law data from our database:{chr(10)}{db_context}" if db_context else ""}

Generate exactly {request.num_questions} multiple-choice questions.

Return ONLY valid JSON (no markdown, no code blocks, no extra text):
{{
  "questions": [
    {{
      "question": "Under Section ___ of the Pakistan Penal Code, what is the punishment for...?",
      "options": ["A) option based on actual law", "B) option 2", "C) option 3", "D) option 4"],
      "correct_answer": "A",
      "explanation": "Section ___ of PPC states that... This was also held in PLD 20XX SC XX"
    }}
  ]
}}"""

    ai_text = await _call_ollama(prompt)
    parsed = _parse_json(ai_text)

    questions = []
    for q in parsed.get("questions", parsed.get("items", [])):
        if isinstance(q, dict) and q.get("question"):
            questions.append(ExamQuestion(
                question=q.get("question", ""),
                options=q.get("options", []),
                correct_answer=q.get("correct_answer", ""),
                explanation=q.get("explanation", ""),
            ))

    if not questions:
        raise HTTPException(status_code=500, detail="AI could not generate valid questions. Please try again.")

    return ExamPrepResponse(subject=request.subject, questions=questions)


@router.post("/exam-prep/evaluate", response_model=ExamAnswerFeedback, summary="Evaluate student answer")
async def evaluate_exam_answer(
    request: ExamAnswerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    db_context = await _get_relevant_context(db, f"{request.subject} {request.question[:100]}")

    prompt = f"""You are a Pakistani law examiner. Evaluate this answer strictly based on Pakistani law.
Subject: {request.subject}
Question: {request.question}
Student's answer: {request.student_answer}

{f"Reference data from our Pakistani law database:{chr(10)}{db_context}" if db_context else ""}

IMPORTANT: Your evaluation MUST be grounded in actual Pakistani law. Cite specific sections and case precedents.

Return ONLY valid JSON (no markdown, no extra text):
{{
  "is_correct": true,
  "score": 85,
  "feedback": "detailed feedback citing specific Pakistani law provisions",
  "correct_answer": "the correct answer with legal basis",
  "explanation": "detailed explanation citing Pakistani law sections and relevant case precedents"
}}"""

    ai_text = await _call_ollama(prompt)
    parsed = _parse_json(ai_text)

    return ExamAnswerFeedback(
        is_correct=parsed.get("is_correct", False),
        score=parsed.get("score", 0),
        feedback=parsed.get("feedback", ai_text[:2000] if ai_text else "Could not evaluate."),
        correct_answer=parsed.get("correct_answer", ""),
        explanation=parsed.get("explanation", ""),
    )
