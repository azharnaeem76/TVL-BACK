"""Client Management (CRM) API."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from pydantic import BaseModel
from datetime import datetime
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.features import Client

router = APIRouter(prefix="/clients", tags=["Client Management"])


class ClientCreate(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    cnic: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None


class ClientUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    cnic: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    is_active: Optional[bool] = None


class ClientResponse(BaseModel):
    id: int
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    cnic: Optional[str] = None
    address: Optional[str] = None
    notes: Optional[str] = None
    is_active: bool
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True


@router.get("/", response_model=dict, summary="List clients")
async def list_clients(
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    base = select(Client).where(Client.lawyer_id == user.id)
    count_q = select(func.count(Client.id)).where(Client.lawyer_id == user.id)
    if search:
        like = f"%{search}%"
        cond = Client.name.ilike(like) | Client.email.ilike(like) | Client.phone.ilike(like)
        base = base.where(cond)
        count_q = count_q.where(cond)

    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(base.order_by(Client.created_at.desc()).offset(skip).limit(limit))).scalars().all()
    return {"items": [ClientResponse.model_validate(c) for c in rows], "total": total}


@router.post("/", response_model=ClientResponse, status_code=201, summary="Add a client")
async def create_client(payload: ClientCreate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    client = Client(lawyer_id=user.id, **payload.model_dump())
    db.add(client)
    await db.flush()
    await db.refresh(client)
    return ClientResponse.model_validate(client)


@router.put("/{client_id}", response_model=ClientResponse, summary="Update a client")
async def update_client(client_id: int, payload: ClientUpdate, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Client).where(Client.id == client_id, Client.lawyer_id == user.id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(client, field, value)
    await db.flush()
    await db.refresh(client)
    return ClientResponse.model_validate(client)


@router.delete("/{client_id}", status_code=204, summary="Delete a client")
async def delete_client(client_id: int, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    result = await db.execute(select(Client).where(Client.id == client_id, Client.lawyer_id == user.id))
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    await db.delete(client)
    await db.flush()
