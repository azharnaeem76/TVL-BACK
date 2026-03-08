"""Moot Court Simulator & Exam Preparation API."""
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
router = APIRouter(prefix="/student-tools", tags=["Student Tools"])


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

async def _call_ollama(prompt: str) -> str:
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
        raise HTTPException(status_code=503, detail="AI model (Ollama) is not running.")
    except Exception as e:
        logger.error(f"Ollama error: {e}")
        raise HTTPException(status_code=500, detail="AI processing failed")


def _parse_json(text: str) -> dict:
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
    current_user: User = Depends(get_current_user),
):
    prompt = f"""You are a Pakistani law professor creating a moot court exercise.
Topic: {request.topic}
Student's side: {request.side}

Return JSON:
{{
  "scenario": "detailed moot court scenario (2-3 paragraphs) based on Pakistani law",
  "your_arguments": ["argument 1 for {request.side}", "argument 2", "argument 3"],
  "opposing_arguments": ["counter-argument 1", "counter-argument 2"],
  "judge_questions": ["question a judge might ask 1", "question 2", "question 3"],
  "relevant_cases": ["PLD 2020 SC 1 - brief", "2019 SCMR 123 - brief"],
  "tips": ["tip for arguing this case 1", "tip 2"]
}}"""

    ai_text = await _call_ollama(prompt)
    parsed = _parse_json(ai_text)

    return MootCourtResponse(
        scenario=parsed.get("scenario", ai_text[:2000] if ai_text else "Could not generate scenario."),
        your_arguments=parsed.get("your_arguments", []),
        opposing_arguments=parsed.get("opposing_arguments", []),
        judge_questions=parsed.get("judge_questions", []),
        relevant_cases=parsed.get("relevant_cases", []),
        tips=parsed.get("tips", []),
    )


@router.post("/moot-court/evaluate", response_model=MootCourtFeedback, summary="Evaluate moot court argument")
async def evaluate_argument(
    request: MootCourtArgumentRequest,
    current_user: User = Depends(get_current_user),
):
    prompt = f"""You are a Pakistani law professor evaluating a moot court argument.

Scenario: {request.scenario[:2000]}
Student's side: {request.side}
Student's argument: {request.your_argument[:3000]}

Return JSON:
{{
  "score": 75,
  "feedback": "overall assessment of the argument",
  "strengths": ["strength 1", "strength 2"],
  "improvements": ["area for improvement 1", "area 2"],
  "model_answer": "a model answer for this scenario (2-3 paragraphs)"
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
    current_user: User = Depends(get_current_user),
):
    exam_info = EXAM_TYPES.get(request.exam_type, EXAM_TYPES["llb"])
    topic_str = f" on topic: {request.topic}" if request.topic else ""
    prompt = f"""You are a Pakistani law examiner. Generate {request.num_questions} multiple-choice questions for {request.subject}{topic_str}.
These should be {exam_info['name']} level questions based on Pakistani law. Exam context: {exam_info['description']}.

Return JSON:
{{
  "questions": [
    {{
      "question": "question text",
      "options": ["A) option 1", "B) option 2", "C) option 3", "D) option 4"],
      "correct_answer": "A",
      "explanation": "why this is correct, citing relevant law"
    }}
  ]
}}"""

    ai_text = await _call_ollama(prompt)
    parsed = _parse_json(ai_text)

    questions = []
    for q in parsed.get("questions", parsed.get("items", [])):
        if isinstance(q, dict):
            questions.append(ExamQuestion(
                question=q.get("question", ""),
                options=q.get("options", []),
                correct_answer=q.get("correct_answer", ""),
                explanation=q.get("explanation", ""),
            ))

    return ExamPrepResponse(subject=request.subject, questions=questions)


@router.post("/exam-prep/evaluate", response_model=ExamAnswerFeedback, summary="Evaluate student answer")
async def evaluate_exam_answer(
    request: ExamAnswerRequest,
    current_user: User = Depends(get_current_user),
):
    prompt = f"""You are a Pakistani law examiner. Evaluate this answer.
Subject: {request.subject}
Question: {request.question}
Student's answer: {request.student_answer}

Return JSON:
{{
  "is_correct": true,
  "score": 85,
  "feedback": "detailed feedback",
  "correct_answer": "the correct answer",
  "explanation": "detailed explanation citing Pakistani law"
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
