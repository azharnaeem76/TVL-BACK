"""Lawyer Directory API - searchable directory of legal professionals."""
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from pydantic import BaseModel
from app.core.database import get_db
from app.models.user import User, UserRole

router = APIRouter(prefix="/directory", tags=["Lawyer Directory"])


class LawyerProfile(BaseModel):
    id: int
    full_name: str
    role: UserRole
    city: Optional[str] = None
    specialization: Optional[str] = None
    bio: Optional[str] = None
    bar_number: Optional[str] = None

    class Config:
        from_attributes = True


@router.get("/", response_model=dict, summary="Search lawyer directory")
async def search_directory(
    search: Optional[str] = Query(None),
    city: Optional[str] = Query(None),
    specialization: Optional[str] = Query(None),
    role: Optional[UserRole] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    # Only show lawyers and judges in directory
    allowed_roles = [UserRole.LAWYER, UserRole.JUDGE, UserRole.PARALEGAL]
    base = select(User).where(User.role.in_(allowed_roles), User.is_active == True)
    count_q = select(func.count(User.id)).where(User.role.in_(allowed_roles), User.is_active == True)

    if role:
        base = base.where(User.role == role)
        count_q = count_q.where(User.role == role)
    if city:
        base = base.where(User.city.ilike(f"%{city}%"))
        count_q = count_q.where(User.city.ilike(f"%{city}%"))
    if specialization:
        base = base.where(User.specialization.ilike(f"%{specialization}%"))
        count_q = count_q.where(User.specialization.ilike(f"%{specialization}%"))
    if search:
        like = f"%{search}%"
        cond = User.full_name.ilike(like) | User.specialization.ilike(like) | User.city.ilike(like)
        base = base.where(cond)
        count_q = count_q.where(cond)

    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(base.order_by(User.full_name).offset(skip).limit(limit))).scalars().all()

    return {
        "items": [LawyerProfile.model_validate(u) for u in rows],
        "total": total,
    }
