"""Lawyer Marketplace API - browse, compare, and hire lawyers."""
import enum
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Enum as SAEnum, ForeignKey, select, func
from typing import Optional
from pydantic import BaseModel, Field
from app.core.database import Base, get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole

router = APIRouter(prefix="/marketplace", tags=["Marketplace"])


# ---------------------------------------------------------------------------
# DB Models
# ---------------------------------------------------------------------------

class ServiceCategory(str, enum.Enum):
    CRIMINAL = "criminal"
    CIVIL = "civil"
    FAMILY = "family"
    CORPORATE = "corporate"
    PROPERTY = "property"
    TAX = "tax"
    IMMIGRATION = "immigration"
    LABOR = "labor"
    CONSTITUTIONAL = "constitutional"
    BANKING = "banking"
    CYBER = "cyber"
    INTELLECTUAL_PROPERTY = "intellectual_property"
    OTHER = "other"


class HireUrgency(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class HireStatus(str, enum.Enum):
    PENDING = "pending"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class MarketplaceService(Base):
    __tablename__ = "marketplace_services"

    id = Column(Integer, primary_key=True, index=True)
    lawyer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(SAEnum(ServiceCategory), default=ServiceCategory.OTHER, nullable=False)
    hourly_rate = Column(Float, nullable=True)
    fixed_fee = Column(Float, nullable=True)
    availability = Column(String(50), default="available")  # available, busy, unavailable
    areas_of_expertise = Column(Text, nullable=True)  # comma-separated
    is_active = Column(Integer, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class MarketplaceReview(Base):
    __tablename__ = "marketplace_reviews"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    lawyer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    rating = Column(Integer, nullable=False)  # 1-5
    review_text = Column(Text, nullable=True)
    case_type = Column(String(100), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class HireRequest(Base):
    __tablename__ = "hire_requests"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    lawyer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    case_description = Column(Text, nullable=False)
    budget = Column(Float, nullable=True)
    urgency = Column(SAEnum(HireUrgency), default=HireUrgency.MEDIUM, nullable=False)
    status = Column(SAEnum(HireStatus), default=HireStatus.PENDING, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


# ---------------------------------------------------------------------------
# Pydantic Schemas
# ---------------------------------------------------------------------------

class ServiceCreate(BaseModel):
    title: str = Field(..., max_length=255)
    description: Optional[str] = None
    category: ServiceCategory = ServiceCategory.OTHER
    hourly_rate: Optional[float] = Field(None, ge=0)
    fixed_fee: Optional[float] = Field(None, ge=0)
    availability: str = "available"
    areas_of_expertise: Optional[str] = None


class ServiceResponse(BaseModel):
    id: int
    lawyer_id: int
    title: str
    description: Optional[str] = None
    category: ServiceCategory
    hourly_rate: Optional[float] = None
    fixed_fee: Optional[float] = None
    availability: str
    areas_of_expertise: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class ReviewCreate(BaseModel):
    lawyer_id: int
    rating: int = Field(..., ge=1, le=5)
    review_text: Optional[str] = Field(None, max_length=2000)
    case_type: Optional[str] = Field(None, max_length=100)


class ReviewResponse(BaseModel):
    id: int
    client_id: int
    client_name: Optional[str] = None
    lawyer_id: int
    rating: int
    review_text: Optional[str] = None
    case_type: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True


class HireCreate(BaseModel):
    lawyer_id: int
    case_description: str = Field(..., max_length=5000)
    budget: Optional[float] = Field(None, ge=0)
    urgency: HireUrgency = HireUrgency.MEDIUM


class HireResponse(BaseModel):
    id: int
    client_id: int
    lawyer_id: int
    case_description: str
    budget: Optional[float] = None
    urgency: HireUrgency
    status: HireStatus
    created_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# 1. GET /marketplace/lawyers - Browse lawyers with rich filtering
# ---------------------------------------------------------------------------

@router.get("/lawyers", summary="Browse lawyers with filtering")
async def browse_lawyers(
    city: Optional[str] = Query(None),
    specialization: Optional[str] = Query(None),
    min_rating: Optional[float] = Query(None, ge=0, le=5),
    max_hourly_rate: Optional[float] = Query(None, ge=0),
    availability: Optional[str] = Query(None),
    sort_by: Optional[str] = Query("rating", regex="^(rating|price|experience|name)$"),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    # Base query: only active lawyers
    base = select(User).where(User.role == UserRole.LAWYER, User.is_active == True)
    count_q = select(func.count(User.id)).where(User.role == UserRole.LAWYER, User.is_active == True)

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
    base = base.order_by(User.full_name).offset(skip).limit(limit)
    rows = (await db.execute(base)).scalars().all()

    # Enrich each lawyer with marketplace data
    items = []
    for lawyer in rows:
        # Get average rating and review count
        rating_q = select(
            func.avg(MarketplaceReview.rating),
            func.count(MarketplaceReview.id),
        ).where(MarketplaceReview.lawyer_id == lawyer.id)
        rating_result = (await db.execute(rating_q)).first()
        avg_rating = round(float(rating_result[0]), 1) if rating_result[0] else 0.0
        review_count = rating_result[1] or 0

        # Apply min_rating filter
        if min_rating and avg_rating < min_rating:
            total = max(0, total - 1)
            continue

        # Get services for hourly rate
        svc_q = select(MarketplaceService).where(
            MarketplaceService.lawyer_id == lawyer.id,
            MarketplaceService.is_active == 1,
        )
        services = (await db.execute(svc_q)).scalars().all()

        hourly_rate = None
        fixed_fee = None
        svc_availability = "available"
        if services:
            rates = [s.hourly_rate for s in services if s.hourly_rate]
            fees = [s.fixed_fee for s in services if s.fixed_fee]
            hourly_rate = min(rates) if rates else None
            fixed_fee = min(fees) if fees else None
            # Use first service availability
            svc_availability = services[0].availability

        # Apply max_hourly_rate filter
        if max_hourly_rate and hourly_rate and hourly_rate > max_hourly_rate:
            total = max(0, total - 1)
            continue

        # Apply availability filter
        if availability and svc_availability != availability:
            total = max(0, total - 1)
            continue

        # Approximate years of experience from created_at
        years_exp = max(1, (datetime.utcnow() - (lawyer.created_at or datetime.utcnow())).days // 365) if lawyer.created_at else 1

        # Count completed hire requests as proxy for cases won
        cases_won_q = select(func.count(HireRequest.id)).where(
            HireRequest.lawyer_id == lawyer.id,
            HireRequest.status == HireStatus.COMPLETED,
        )
        cases_won = (await db.execute(cases_won_q)).scalar() or 0

        items.append({
            "id": lawyer.id,
            "full_name": lawyer.full_name,
            "email": lawyer.email,
            "city": lawyer.city,
            "specialization": lawyer.specialization,
            "bio": lawyer.bio,
            "bar_number": lawyer.bar_number,
            "profile_picture": lawyer.profile_picture,
            "avg_rating": avg_rating,
            "review_count": review_count,
            "hourly_rate": hourly_rate,
            "fixed_fee": fixed_fee,
            "availability": svc_availability,
            "years_experience": years_exp,
            "cases_won": cases_won,
            "services": [
                {
                    "id": s.id,
                    "title": s.title,
                    "category": s.category.value if s.category else "other",
                    "hourly_rate": s.hourly_rate,
                    "fixed_fee": s.fixed_fee,
                }
                for s in services
            ],
        })

    # Sort items
    if sort_by == "rating":
        items.sort(key=lambda x: x["avg_rating"], reverse=True)
    elif sort_by == "price":
        items.sort(key=lambda x: x["hourly_rate"] or 999999)
    elif sort_by == "experience":
        items.sort(key=lambda x: x["years_experience"], reverse=True)

    return {"items": items, "total": total}


# ---------------------------------------------------------------------------
# 2. GET /marketplace/lawyers/{lawyer_id} - Detailed lawyer profile
# ---------------------------------------------------------------------------

@router.get("/lawyers/{lawyer_id}", summary="Get detailed lawyer profile")
async def get_lawyer_profile(
    lawyer_id: int,
    db: AsyncSession = Depends(get_db),
):
    lawyer = (await db.execute(
        select(User).where(User.id == lawyer_id, User.role == UserRole.LAWYER, User.is_active == True)
    )).scalar_one_or_none()
    if not lawyer:
        raise HTTPException(status_code=404, detail="Lawyer not found")

    # Rating
    rating_q = select(
        func.avg(MarketplaceReview.rating),
        func.count(MarketplaceReview.id),
    ).where(MarketplaceReview.lawyer_id == lawyer_id)
    rating_result = (await db.execute(rating_q)).first()
    avg_rating = round(float(rating_result[0]), 1) if rating_result[0] else 0.0
    review_count = rating_result[1] or 0

    # Services
    services = (await db.execute(
        select(MarketplaceService).where(
            MarketplaceService.lawyer_id == lawyer_id,
            MarketplaceService.is_active == 1,
        )
    )).scalars().all()

    # Reviews (latest 20)
    reviews_q = select(MarketplaceReview).where(
        MarketplaceReview.lawyer_id == lawyer_id
    ).order_by(MarketplaceReview.created_at.desc()).limit(20)
    reviews = (await db.execute(reviews_q)).scalars().all()

    review_items = []
    for r in reviews:
        client = (await db.execute(select(User).where(User.id == r.client_id))).scalar_one_or_none()
        review_items.append({
            "id": r.id,
            "client_id": r.client_id,
            "client_name": client.full_name if client else "Anonymous",
            "rating": r.rating,
            "review_text": r.review_text,
            "case_type": r.case_type,
            "created_at": str(r.created_at),
        })

    # Cases won
    cases_won = (await db.execute(
        select(func.count(HireRequest.id)).where(
            HireRequest.lawyer_id == lawyer_id,
            HireRequest.status == HireStatus.COMPLETED,
        )
    )).scalar() or 0

    years_exp = max(1, (datetime.utcnow() - (lawyer.created_at or datetime.utcnow())).days // 365) if lawyer.created_at else 1

    return {
        "id": lawyer.id,
        "full_name": lawyer.full_name,
        "email": lawyer.email,
        "city": lawyer.city,
        "specialization": lawyer.specialization,
        "bio": lawyer.bio,
        "bar_number": lawyer.bar_number,
        "profile_picture": lawyer.profile_picture,
        "avg_rating": avg_rating,
        "review_count": review_count,
        "years_experience": years_exp,
        "cases_won": cases_won,
        "services": [
            {
                "id": s.id,
                "title": s.title,
                "description": s.description,
                "category": s.category.value if s.category else "other",
                "hourly_rate": s.hourly_rate,
                "fixed_fee": s.fixed_fee,
                "availability": s.availability,
                "areas_of_expertise": s.areas_of_expertise,
                "created_at": str(s.created_at),
            }
            for s in services
        ],
        "reviews": review_items,
    }


# ---------------------------------------------------------------------------
# 3. POST /marketplace/services - Create/update service listing
# ---------------------------------------------------------------------------

@router.post("/services", summary="Create a service listing (lawyers only)")
async def create_service(
    request: ServiceCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != UserRole.LAWYER:
        raise HTTPException(status_code=403, detail="Only lawyers can create service listings")

    service = MarketplaceService(
        lawyer_id=current_user.id,
        title=request.title,
        description=request.description,
        category=request.category,
        hourly_rate=request.hourly_rate,
        fixed_fee=request.fixed_fee,
        availability=request.availability,
        areas_of_expertise=request.areas_of_expertise,
    )
    db.add(service)
    await db.flush()
    await db.refresh(service)

    return {
        "id": service.id,
        "lawyer_id": service.lawyer_id,
        "title": service.title,
        "description": service.description,
        "category": service.category.value,
        "hourly_rate": service.hourly_rate,
        "fixed_fee": service.fixed_fee,
        "availability": service.availability,
        "areas_of_expertise": service.areas_of_expertise,
        "created_at": str(service.created_at),
    }


# ---------------------------------------------------------------------------
# 4. GET /marketplace/services - Browse all services
# ---------------------------------------------------------------------------

@router.get("/services", summary="Browse all service listings")
async def browse_services(
    category: Optional[ServiceCategory] = Query(None),
    search: Optional[str] = Query(None),
    min_rate: Optional[float] = Query(None, ge=0),
    max_rate: Optional[float] = Query(None, ge=0),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    base = select(MarketplaceService).where(MarketplaceService.is_active == 1)
    count_q = select(func.count(MarketplaceService.id)).where(MarketplaceService.is_active == 1)

    if category:
        base = base.where(MarketplaceService.category == category)
        count_q = count_q.where(MarketplaceService.category == category)
    if search:
        like = f"%{search}%"
        cond = MarketplaceService.title.ilike(like) | MarketplaceService.description.ilike(like)
        base = base.where(cond)
        count_q = count_q.where(cond)
    if min_rate is not None:
        base = base.where(MarketplaceService.hourly_rate >= min_rate)
        count_q = count_q.where(MarketplaceService.hourly_rate >= min_rate)
    if max_rate is not None:
        base = base.where(MarketplaceService.hourly_rate <= max_rate)
        count_q = count_q.where(MarketplaceService.hourly_rate <= max_rate)

    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(
        base.order_by(MarketplaceService.created_at.desc()).offset(skip).limit(limit)
    )).scalars().all()

    items = []
    for s in rows:
        lawyer = (await db.execute(select(User).where(User.id == s.lawyer_id))).scalar_one_or_none()
        items.append({
            "id": s.id,
            "lawyer_id": s.lawyer_id,
            "lawyer_name": lawyer.full_name if lawyer else "Unknown",
            "lawyer_city": lawyer.city if lawyer else None,
            "title": s.title,
            "description": s.description,
            "category": s.category.value if s.category else "other",
            "hourly_rate": s.hourly_rate,
            "fixed_fee": s.fixed_fee,
            "availability": s.availability,
            "areas_of_expertise": s.areas_of_expertise,
            "created_at": str(s.created_at),
        })

    return {"items": items, "total": total}


# ---------------------------------------------------------------------------
# 5. POST /marketplace/reviews - Client reviews a lawyer
# ---------------------------------------------------------------------------

@router.post("/reviews", summary="Submit a review for a lawyer")
async def create_review(
    request: ReviewCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify the lawyer exists
    lawyer = (await db.execute(
        select(User).where(User.id == request.lawyer_id, User.role == UserRole.LAWYER)
    )).scalar_one_or_none()
    if not lawyer:
        raise HTTPException(status_code=404, detail="Lawyer not found")

    # Can't review yourself
    if current_user.id == request.lawyer_id:
        raise HTTPException(status_code=400, detail="You cannot review yourself")

    # Check for existing review (one review per client per lawyer)
    existing = (await db.execute(
        select(MarketplaceReview).where(
            MarketplaceReview.client_id == current_user.id,
            MarketplaceReview.lawyer_id == request.lawyer_id,
        )
    )).scalar_one_or_none()
    if existing:
        # Update existing review
        existing.rating = request.rating
        existing.review_text = request.review_text
        existing.case_type = request.case_type
        await db.flush()
        await db.refresh(existing)
        return {
            "id": existing.id,
            "client_id": existing.client_id,
            "lawyer_id": existing.lawyer_id,
            "rating": existing.rating,
            "review_text": existing.review_text,
            "case_type": existing.case_type,
            "created_at": str(existing.created_at),
            "updated": True,
        }

    review = MarketplaceReview(
        client_id=current_user.id,
        lawyer_id=request.lawyer_id,
        rating=request.rating,
        review_text=request.review_text,
        case_type=request.case_type,
    )
    db.add(review)
    await db.flush()
    await db.refresh(review)

    return {
        "id": review.id,
        "client_id": review.client_id,
        "lawyer_id": review.lawyer_id,
        "rating": review.rating,
        "review_text": review.review_text,
        "case_type": review.case_type,
        "created_at": str(review.created_at),
        "updated": False,
    }


# ---------------------------------------------------------------------------
# 6. GET /marketplace/reviews/{lawyer_id} - Get reviews for a lawyer
# ---------------------------------------------------------------------------

@router.get("/reviews/{lawyer_id}", summary="Get reviews for a lawyer")
async def get_lawyer_reviews(
    lawyer_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
):
    # Verify lawyer exists
    lawyer = (await db.execute(
        select(User).where(User.id == lawyer_id, User.role == UserRole.LAWYER)
    )).scalar_one_or_none()
    if not lawyer:
        raise HTTPException(status_code=404, detail="Lawyer not found")

    # Aggregate stats
    stats_q = select(
        func.avg(MarketplaceReview.rating),
        func.count(MarketplaceReview.id),
    ).where(MarketplaceReview.lawyer_id == lawyer_id)
    stats = (await db.execute(stats_q)).first()

    # Get reviews
    reviews_q = select(MarketplaceReview).where(
        MarketplaceReview.lawyer_id == lawyer_id
    ).order_by(MarketplaceReview.created_at.desc()).offset(skip).limit(limit)
    reviews = (await db.execute(reviews_q)).scalars().all()

    items = []
    for r in reviews:
        client = (await db.execute(select(User).where(User.id == r.client_id))).scalar_one_or_none()
        items.append({
            "id": r.id,
            "client_id": r.client_id,
            "client_name": client.full_name if client else "Anonymous",
            "rating": r.rating,
            "review_text": r.review_text,
            "case_type": r.case_type,
            "created_at": str(r.created_at),
        })

    return {
        "lawyer_name": lawyer.full_name,
        "avg_rating": round(float(stats[0]), 1) if stats[0] else 0.0,
        "total_reviews": stats[1] or 0,
        "reviews": items,
    }


# ---------------------------------------------------------------------------
# 7. POST /marketplace/hire - Client sends hire request
# ---------------------------------------------------------------------------

@router.post("/hire", summary="Send a hire request to a lawyer")
async def hire_lawyer(
    request: HireCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify the lawyer exists
    lawyer = (await db.execute(
        select(User).where(User.id == request.lawyer_id, User.role == UserRole.LAWYER, User.is_active == True)
    )).scalar_one_or_none()
    if not lawyer:
        raise HTTPException(status_code=404, detail="Lawyer not found")

    if current_user.id == request.lawyer_id:
        raise HTTPException(status_code=400, detail="You cannot hire yourself")

    hire = HireRequest(
        client_id=current_user.id,
        lawyer_id=request.lawyer_id,
        case_description=request.case_description,
        budget=request.budget,
        urgency=request.urgency,
    )
    db.add(hire)
    await db.flush()
    await db.refresh(hire)

    return {
        "id": hire.id,
        "client_id": hire.client_id,
        "lawyer_id": hire.lawyer_id,
        "lawyer_name": lawyer.full_name,
        "case_description": hire.case_description,
        "budget": hire.budget,
        "urgency": hire.urgency.value,
        "status": hire.status.value,
        "created_at": str(hire.created_at),
    }


# ---------------------------------------------------------------------------
# Extra: GET /marketplace/hire - List my hire requests
# ---------------------------------------------------------------------------

@router.get("/hire", summary="List my hire requests")
async def list_hire_requests(
    status_filter: Optional[HireStatus] = Query(None, alias="status"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import or_
    query = select(HireRequest).where(
        or_(
            HireRequest.client_id == current_user.id,
            HireRequest.lawyer_id == current_user.id,
        )
    )
    if status_filter:
        query = query.where(HireRequest.status == status_filter)
    query = query.order_by(HireRequest.created_at.desc())

    rows = (await db.execute(query)).scalars().all()
    items = []
    for h in rows:
        client = (await db.execute(select(User).where(User.id == h.client_id))).scalar_one_or_none()
        lawyer = (await db.execute(select(User).where(User.id == h.lawyer_id))).scalar_one_or_none()
        items.append({
            "id": h.id,
            "client_id": h.client_id,
            "client_name": client.full_name if client else "Unknown",
            "lawyer_id": h.lawyer_id,
            "lawyer_name": lawyer.full_name if lawyer else "Unknown",
            "case_description": h.case_description,
            "budget": h.budget,
            "urgency": h.urgency.value,
            "status": h.status.value,
            "created_at": str(h.created_at),
        })
    return items


# ---------------------------------------------------------------------------
# Extra: PUT /marketplace/hire/{hire_id} - Update hire request status
# ---------------------------------------------------------------------------

@router.put("/hire/{hire_id}", summary="Update hire request status")
async def update_hire_request(
    hire_id: int,
    status: HireStatus = Query(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    from sqlalchemy import or_
    hire = (await db.execute(
        select(HireRequest).where(
            HireRequest.id == hire_id,
            or_(
                HireRequest.client_id == current_user.id,
                HireRequest.lawyer_id == current_user.id,
            ),
        )
    )).scalar_one_or_none()
    if not hire:
        raise HTTPException(status_code=404, detail="Hire request not found")

    hire.status = status
    await db.flush()
    await db.refresh(hire)

    return {
        "id": hire.id,
        "status": hire.status.value,
        "updated_at": str(hire.updated_at),
    }
