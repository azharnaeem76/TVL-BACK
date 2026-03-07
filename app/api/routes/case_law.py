from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import Optional
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.legal import CaseLaw, Statute, Section, LawCategory, Court
from app.schemas.legal import CaseLawResponse, StatuteResponse, SectionResponse

router = APIRouter(prefix="/legal", tags=["Legal Database"])


@router.get(
    "/case-laws",
    response_model=list[CaseLawResponse],
    summary="List case laws with filters",
    description="Browse case laws with optional filtering by category, court, year, and text search on title/citation.",
)
async def list_case_laws(
    category: Optional[LawCategory] = Query(None, description="Filter by law category"),
    court: Optional[Court] = Query(None, description="Filter by court"),
    year: Optional[int] = Query(None, description="Filter by year of judgment"),
    search: Optional[str] = Query(None, description="Search in title and citation"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Results per page (max 100)"),
    db: AsyncSession = Depends(get_db),
):
    query = select(CaseLaw)

    if category:
        query = query.where(CaseLaw.category == category)
    if court:
        query = query.where(CaseLaw.court == court)
    if year:
        query = query.where(CaseLaw.year == year)
    if search:
        query = query.where(
            CaseLaw.title.ilike(f"%{search}%") | CaseLaw.citation.ilike(f"%{search}%")
        )

    query = query.order_by(CaseLaw.year.desc()).offset(skip).limit(limit)
    result = await db.execute(query)
    cases = result.scalars().all()
    return [CaseLawResponse.model_validate(c) for c in cases]


@router.get(
    "/case-laws/{case_id}",
    response_model=CaseLawResponse,
    summary="Get case law by ID",
    description="Get complete details of a specific case law including summaries, headnotes, and applied sections.",
)
async def get_case_law(case_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(CaseLaw).where(CaseLaw.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case law not found")
    return CaseLawResponse.model_validate(case)


@router.get(
    "/statutes",
    response_model=list[StatuteResponse],
    summary="List statutes with filters",
    description="Browse Pakistani statutes (PPC, CrPC, MFLO, PECA, etc.) with optional category and text filters.",
)
async def list_statutes(
    category: Optional[LawCategory] = Query(None, description="Filter by law category"),
    search: Optional[str] = Query(None, description="Search in statute title"),
    skip: int = Query(0, ge=0, description="Pagination offset"),
    limit: int = Query(20, ge=1, le=100, description="Results per page (max 100)"),
    db: AsyncSession = Depends(get_db),
):
    query = select(Statute)
    if category:
        query = query.where(Statute.category == category)
    if search:
        query = query.where(Statute.title.ilike(f"%{search}%"))
    query = query.order_by(Statute.year.desc()).offset(skip).limit(limit)

    result = await db.execute(query)
    statutes = result.scalars().all()
    return [StatuteResponse.model_validate(s) for s in statutes]


@router.get(
    "/statutes/{statute_id}",
    response_model=StatuteResponse,
    summary="Get statute by ID",
    description="Get details of a specific statute including full text and summaries.",
)
async def get_statute(statute_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Statute).where(Statute.id == statute_id))
    statute = result.scalar_one_or_none()
    if not statute:
        raise HTTPException(status_code=404, detail="Statute not found")
    return StatuteResponse.model_validate(statute)


@router.get(
    "/statutes/{statute_id}/sections",
    response_model=list[SectionResponse],
    summary="Get statute sections",
    description="Get all sections of a specific statute (e.g., all sections of PPC), ordered by section number.",
)
async def get_statute_sections(statute_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Section).where(Section.statute_id == statute_id).order_by(Section.section_number)
    )
    sections = result.scalars().all()
    return [SectionResponse.model_validate(s) for s in sections]
