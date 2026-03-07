"""Case Tracker API - Track active court cases."""
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.features import TrackedCase, CaseStatus

router = APIRouter(prefix="/case-tracker", tags=["Case Tracker"])


class TrackedCaseCreate(BaseModel):
    title: str
    case_number: Optional[str] = None
    court: Optional[str] = None
    judge_name: Optional[str] = None
    opposing_counsel: Optional[str] = None
    client_name: Optional[str] = None
    status: CaseStatus = CaseStatus.ACTIVE
    category: Optional[str] = None
    next_hearing: Optional[datetime] = None
    notes: Optional[str] = None


class TrackedCaseUpdate(BaseModel):
    title: Optional[str] = None
    case_number: Optional[str] = None
    court: Optional[str] = None
    judge_name: Optional[str] = None
    opposing_counsel: Optional[str] = None
    client_name: Optional[str] = None
    status: Optional[CaseStatus] = None
    category: Optional[str] = None
    next_hearing: Optional[datetime] = None
    notes: Optional[str] = None


class TrackedCaseResponse(BaseModel):
    id: int
    title: str
    case_number: Optional[str] = None
    court: Optional[str] = None
    judge_name: Optional[str] = None
    opposing_counsel: Optional[str] = None
    client_name: Optional[str] = None
    status: CaseStatus
    category: Optional[str] = None
    next_hearing: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.get("/", response_model=dict, summary="List tracked cases")
async def list_cases(
    status_filter: Optional[CaseStatus] = Query(None, alias="status"),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    base = select(TrackedCase).where(TrackedCase.user_id == user.id)
    count_q = select(func.count(TrackedCase.id)).where(TrackedCase.user_id == user.id)

    if status_filter:
        base = base.where(TrackedCase.status == status_filter)
        count_q = count_q.where(TrackedCase.status == status_filter)
    if search:
        like = f"%{search}%"
        cond = TrackedCase.title.ilike(like) | TrackedCase.case_number.ilike(like)
        base = base.where(cond)
        count_q = count_q.where(cond)

    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(
        base.order_by(TrackedCase.next_hearing.asc().nullslast(), TrackedCase.created_at.desc())
        .offset(skip).limit(limit)
    )).scalars().all()

    return {
        "items": [TrackedCaseResponse.model_validate(c) for c in rows],
        "total": total,
    }


@router.post("/", response_model=TrackedCaseResponse, status_code=201, summary="Add a tracked case")
async def create_case(
    payload: TrackedCaseCreate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    case = TrackedCase(user_id=user.id, **payload.model_dump())
    db.add(case)
    await db.flush()
    await db.refresh(case)
    return TrackedCaseResponse.model_validate(case)


@router.put("/{case_id}", response_model=TrackedCaseResponse, summary="Update a tracked case")
async def update_case(
    case_id: int,
    payload: TrackedCaseUpdate,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TrackedCase).where(TrackedCase.id == case_id, TrackedCase.user_id == user.id)
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(case, field, value)
    await db.flush()
    await db.refresh(case)
    return TrackedCaseResponse.model_validate(case)


@router.delete("/{case_id}", status_code=204, summary="Delete a tracked case")
async def delete_case(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(TrackedCase).where(TrackedCase.id == case_id, TrackedCase.user_id == user.id)
    )
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    await db.delete(case)
    await db.flush()
