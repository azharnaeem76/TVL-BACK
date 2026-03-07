"""
Scenario Search API - The main module.

Accepts legal scenarios in English, Urdu, or Roman Urdu.
Returns relevant case laws, statutes, and AI-generated analysis.
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.legal import LawCategory, Court
from app.schemas.legal import ScenarioSearchRequest, SearchResponse
from app.services.search_service import scenario_search
from app.services.language_service import detect_language, normalize_to_english

router = APIRouter(prefix="/search", tags=["Scenario Search"])


@router.post(
    "/scenario",
    response_model=SearchResponse,
    summary="Search legal scenario (authenticated)",
    response_description="Search results with AI analysis, detected language, and matching case laws",
)
async def search_scenario(
    request: ScenarioSearchRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Search for relevant case laws and legal references based on a scenario description.

    The scenario can be written in:
    - English: "What are the rights of a tenant if landlord wants to evict?"
    - Urdu: "کرایہ دار کے حقوق کیا ہیں اگر مالک مکان نکالنا چاہے؟"
    - Roman Urdu: "kirayedar ke huqooq kya hain agar malik makan nikalna chahe?"

    The system will:
    1. Detect the input language
    2. Understand the legal scenario
    3. Search relevant case laws and statutes
    4. Provide AI-powered analysis with citations
    """
    return await scenario_search(request, db, user_id=current_user.id)


@router.post(
    "/scenario/guest",
    response_model=SearchResponse,
    summary="Search legal scenario (guest, limited)",
    description="Search without authentication. Limited to 5 results. For full access, register and login.",
)
async def search_scenario_guest(
    request: ScenarioSearchRequest,
    db: AsyncSession = Depends(get_db),
):
    request.max_results = min(request.max_results, 5)  # Limit for guests
    return await scenario_search(request, db, user_id=None)


@router.get(
    "/detect-language",
    summary="Detect input language",
    description="Detect whether input text is English, Urdu (script), or Roman Urdu, and return the normalized English form.",
)
async def detect_input_language(text: str = Query(..., description="Text to detect language of")):
    language = detect_language(text)
    normalized = normalize_to_english(text, language)
    return {
        "original": text,
        "detected_language": language,
        "normalized": normalized,
    }


@router.get("/categories", summary="List all law categories", description="Returns all available law categories (criminal, family, property, etc.).")
async def get_categories():
    return [{"value": c.value, "label": c.value.replace("_", " ").title()} for c in LawCategory]


@router.get("/courts", summary="List all courts", description="Returns all Pakistani courts (Supreme Court, High Courts, District Courts, etc.).")
async def get_courts():
    return [{"value": c.value, "label": c.value.replace("_", " ").title()} for c in Court]
