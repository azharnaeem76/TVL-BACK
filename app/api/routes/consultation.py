"""Consultation Booking API."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, or_
from typing import Optional
from pydantic import BaseModel, Field
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.models.features import Consultation, ConsultationStatus

router = APIRouter(prefix="/consultations", tags=["Consultations"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ConsultationCreate(BaseModel):
    lawyer_user_id: int
    scheduled_at: datetime
    duration_minutes: int = Field(30, ge=15, le=180)
    topic: Optional[str] = Field(None, max_length=500)
    notes: Optional[str] = Field(None, max_length=5000)
    fee: Optional[float] = Field(None, ge=0, le=10000000)

class ConsultationUpdate(BaseModel):
    status: Optional[ConsultationStatus] = None
    scheduled_at: Optional[datetime] = None
    notes: Optional[str] = None

class ConsultationResponse(BaseModel):
    id: int
    client_user_id: int
    lawyer_user_id: int
    client_name: Optional[str] = None
    lawyer_name: Optional[str] = None
    scheduled_at: datetime
    duration_minutes: int
    topic: Optional[str] = None
    notes: Optional[str] = None
    status: ConsultationStatus
    fee: Optional[float] = None
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("/", summary="List consultations")
async def list_consultations(
    status_filter: Optional[ConsultationStatus] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(Consultation).where(
        or_(
            Consultation.client_user_id == current_user.id,
            Consultation.lawyer_user_id == current_user.id,
        )
    )
    if status_filter:
        query = query.where(Consultation.status == status_filter)
    query = query.order_by(Consultation.scheduled_at.desc())

    result = await db.execute(query)
    consultations = result.scalars().all()

    items = []
    for c in consultations:
        client = (await db.execute(select(User).where(User.id == c.client_user_id))).scalar_one_or_none()
        lawyer = (await db.execute(select(User).where(User.id == c.lawyer_user_id))).scalar_one_or_none()
        items.append({
            "id": c.id,
            "client_user_id": c.client_user_id,
            "lawyer_user_id": c.lawyer_user_id,
            "client_name": client.full_name if client else "Unknown",
            "lawyer_name": lawyer.full_name if lawyer else "Unknown",
            "scheduled_at": str(c.scheduled_at),
            "duration_minutes": c.duration_minutes,
            "topic": c.topic,
            "notes": c.notes,
            "status": c.status.value,
            "fee": c.fee,
            "created_at": str(c.created_at),
        })
    return items


@router.post("/", summary="Book a consultation")
async def create_consultation(
    request: ConsultationCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    lawyer = (await db.execute(select(User).where(User.id == request.lawyer_user_id))).scalar_one_or_none()
    if not lawyer:
        raise HTTPException(status_code=404, detail="Lawyer not found")
    if lawyer.role != UserRole.LAWYER:
        raise HTTPException(status_code=400, detail="Selected user is not a lawyer")

    consultation = Consultation(
        client_user_id=current_user.id,
        lawyer_user_id=request.lawyer_user_id,
        scheduled_at=request.scheduled_at,
        duration_minutes=request.duration_minutes,
        topic=request.topic,
        notes=request.notes,
        fee=request.fee,
    )
    db.add(consultation)
    await db.flush()
    await db.refresh(consultation)

    return {
        "id": consultation.id,
        "client_user_id": consultation.client_user_id,
        "lawyer_user_id": consultation.lawyer_user_id,
        "scheduled_at": str(consultation.scheduled_at),
        "duration_minutes": consultation.duration_minutes,
        "topic": consultation.topic,
        "notes": consultation.notes,
        "status": consultation.status.value,
        "fee": consultation.fee,
        "created_at": str(consultation.created_at),
    }


@router.put("/{consultation_id}", summary="Update consultation")
async def update_consultation(
    consultation_id: int,
    request: ConsultationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Consultation).where(
            Consultation.id == consultation_id,
            or_(
                Consultation.client_user_id == current_user.id,
                Consultation.lawyer_user_id == current_user.id,
            ),
        )
    )
    consultation = result.scalar_one_or_none()
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")

    if request.status is not None:
        consultation.status = request.status
    if request.scheduled_at is not None:
        consultation.scheduled_at = request.scheduled_at
    if request.notes is not None:
        consultation.notes = request.notes

    await db.flush()
    await db.refresh(consultation)

    return {
        "id": consultation.id,
        "status": consultation.status.value,
        "scheduled_at": str(consultation.scheduled_at),
        "notes": consultation.notes,
    }


@router.delete("/{consultation_id}", status_code=204, summary="Cancel consultation")
async def delete_consultation(
    consultation_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Consultation).where(
            Consultation.id == consultation_id,
            or_(
                Consultation.client_user_id == current_user.id,
                Consultation.lawyer_user_id == current_user.id,
            ),
        )
    )
    consultation = result.scalar_one_or_none()
    if not consultation:
        raise HTTPException(status_code=404, detail="Consultation not found")
    await db.delete(consultation)
    await db.flush()


@router.get("/lawyers", summary="List available lawyers for booking")
async def list_available_lawyers(
    search: Optional[str] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = select(User).where(User.role == UserRole.LAWYER, User.is_active == True)
    if search:
        query = query.where(User.full_name.ilike(f"%{search}%"))
    result = await db.execute(query.order_by(User.full_name))
    lawyers = result.scalars().all()
    return [
        {"id": l.id, "name": l.full_name, "city": l.city, "phone": l.phone}
        for l in lawyers
    ]
