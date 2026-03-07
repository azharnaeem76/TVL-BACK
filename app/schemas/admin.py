from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.models.legal import LawCategory, Court
from app.models.user import UserRole


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

class CategoryCount(BaseModel):
    category: LawCategory
    count: int


class CourtCount(BaseModel):
    court: Court
    count: int


class DailyCount(BaseModel):
    date: str
    count: int


class DashboardStats(BaseModel):
    total_case_laws: int
    total_statutes: int
    total_sections: int
    total_users: int
    cases_per_category: List[CategoryCount]
    cases_per_court: List[CourtCount]
    recent_case_laws: int  # added in last 7 days
    recent_statutes: int
    user_registrations_per_day: List[DailyCount]


# ---------------------------------------------------------------------------
# Case Laws
# ---------------------------------------------------------------------------

class CaseLawCreate(BaseModel):
    citation: str
    title: str
    court: Court
    category: LawCategory
    year: Optional[int] = None
    judge_name: Optional[str] = None
    summary_en: Optional[str] = None
    summary_ur: Optional[str] = None
    full_text: Optional[str] = None
    headnotes: Optional[str] = None
    relevant_statutes: Optional[str] = None
    sections_applied: Optional[str] = None


class CaseLawUpdate(BaseModel):
    citation: Optional[str] = None
    title: Optional[str] = None
    court: Optional[Court] = None
    category: Optional[LawCategory] = None
    year: Optional[int] = None
    judge_name: Optional[str] = None
    summary_en: Optional[str] = None
    summary_ur: Optional[str] = None
    full_text: Optional[str] = None
    headnotes: Optional[str] = None
    relevant_statutes: Optional[str] = None
    sections_applied: Optional[str] = None


class CaseLawAdminResponse(BaseModel):
    id: int
    citation: str
    title: str
    court: Court
    category: LawCategory
    year: Optional[int] = None
    judge_name: Optional[str] = None
    summary_en: Optional[str] = None
    summary_ur: Optional[str] = None
    full_text: Optional[str] = None
    headnotes: Optional[str] = None
    relevant_statutes: Optional[str] = None
    sections_applied: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Statutes
# ---------------------------------------------------------------------------

class StatuteCreate(BaseModel):
    title: str
    short_title: Optional[str] = None
    act_number: Optional[str] = None
    year: Optional[int] = None
    category: LawCategory
    full_text: Optional[str] = None
    summary_en: Optional[str] = None
    summary_ur: Optional[str] = None


class StatuteUpdate(BaseModel):
    title: Optional[str] = None
    short_title: Optional[str] = None
    act_number: Optional[str] = None
    year: Optional[int] = None
    category: Optional[LawCategory] = None
    full_text: Optional[str] = None
    summary_en: Optional[str] = None
    summary_ur: Optional[str] = None


class StatuteAdminResponse(BaseModel):
    id: int
    title: str
    short_title: Optional[str] = None
    act_number: Optional[str] = None
    year: Optional[int] = None
    category: LawCategory
    full_text: Optional[str] = None
    summary_en: Optional[str] = None
    summary_ur: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

class SectionCreate(BaseModel):
    statute_id: int
    section_number: str
    title: Optional[str] = None
    content: str
    content_ur: Optional[str] = None


class SectionUpdate(BaseModel):
    statute_id: Optional[int] = None
    section_number: Optional[str] = None
    title: Optional[str] = None
    content: Optional[str] = None
    content_ur: Optional[str] = None


class SectionAdminResponse(BaseModel):
    id: int
    statute_id: int
    section_number: str
    title: Optional[str] = None
    content: str
    content_ur: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------

class UserAdminUpdate(BaseModel):
    role: Optional[UserRole] = None
    is_active: Optional[bool] = None
    full_name: Optional[str] = None
    phone: Optional[str] = None
    city: Optional[str] = None
    specialization: Optional[str] = None


class UserAdminResponse(BaseModel):
    id: int
    email: str
    full_name: str
    role: UserRole
    phone: Optional[str] = None
    city: Optional[str] = None
    bar_number: Optional[str] = None
    specialization: Optional[str] = None
    preferred_language: str = "en"
    is_active: bool = True
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Bulk Operations
# ---------------------------------------------------------------------------

class BulkCaseLawImport(BaseModel):
    case_laws: List[CaseLawCreate]


class BulkDeleteRequest(BaseModel):
    ids: List[int]


class BulkOperationResult(BaseModel):
    success_count: int
    error_count: int
    errors: List[str] = []


# ---------------------------------------------------------------------------
# Paginated response wrapper
# ---------------------------------------------------------------------------

class PaginatedResponse(BaseModel):
    items: list
    total: int
    skip: int
    limit: int
