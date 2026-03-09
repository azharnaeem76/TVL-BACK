from pydantic import BaseModel
from typing import Optional, List
from app.models.legal import LawCategory, Court


class ScenarioSearchRequest(BaseModel):
    query: str
    category: Optional[LawCategory] = None
    court: Optional[Court] = None
    year_from: Optional[int] = None
    year_to: Optional[int] = None
    max_results: int = 10


class CaseLawResponse(BaseModel):
    id: int
    citation: str
    title: str
    court: Court
    category: LawCategory
    year: Optional[int] = None
    judge_name: Optional[str] = None
    summary_en: Optional[str] = None
    summary_ur: Optional[str] = None
    headnotes: Optional[str] = None
    relevant_statutes: Optional[str] = None
    sections_applied: Optional[str] = None
    similarity_score: Optional[float] = None

    class Config:
        from_attributes = True


class SearchResponse(BaseModel):
    query: str
    detected_language: str
    normalized_query: str
    results: List[CaseLawResponse]
    ai_analysis: str
    total_results: int


class ChatRequest(BaseModel):
    session_id: Optional[int] = None
    message: str


class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    language: Optional[str] = None
    cited_case_ids: Optional[str] = None

    class Config:
        from_attributes = True


class ChatResponse(BaseModel):
    session_id: int
    message: ChatMessageResponse
    cited_cases: List[CaseLawResponse] = []


class StatuteResponse(BaseModel):
    id: int
    title: str
    short_title: Optional[str] = None
    act_number: Optional[str] = None
    year: Optional[int] = None
    category: LawCategory
    full_text: Optional[str] = None
    summary_en: Optional[str] = None
    summary_ur: Optional[str] = None

    class Config:
        from_attributes = True


class SectionResponse(BaseModel):
    id: int
    statute_id: int
    section_number: str
    title: Optional[str] = None
    content: str
    content_ur: Optional[str] = None

    class Config:
        from_attributes = True
