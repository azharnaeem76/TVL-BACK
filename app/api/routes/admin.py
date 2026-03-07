from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from typing import Optional

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.models.legal import CaseLaw, Statute, Section, LawCategory, Court
from app.schemas.admin import (
    DashboardStats,
    CategoryCount,
    CourtCount,
    DailyCount,
    CaseLawCreate,
    CaseLawUpdate,
    CaseLawAdminResponse,
    StatuteCreate,
    StatuteUpdate,
    StatuteAdminResponse,
    SectionCreate,
    SectionUpdate,
    SectionAdminResponse,
    UserAdminUpdate,
    UserAdminResponse,
    BulkCaseLawImport,
    BulkDeleteRequest,
    BulkOperationResult,
)

router = APIRouter(prefix="/admin", tags=["Admin"])


# ---------------------------------------------------------------------------
# Admin dependency
# ---------------------------------------------------------------------------

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    """Dependency that ensures the authenticated user has the admin role."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin privileges required",
        )
    return current_user


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@router.get(
    "/stats",
    response_model=DashboardStats,
    summary="Admin dashboard statistics",
)
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)

    # Totals
    total_case_laws = (await db.execute(select(func.count(CaseLaw.id)))).scalar() or 0
    total_statutes = (await db.execute(select(func.count(Statute.id)))).scalar() or 0
    total_sections = (await db.execute(select(func.count(Section.id)))).scalar() or 0
    total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0

    # Cases per category
    cat_rows = (
        await db.execute(
            select(CaseLaw.category, func.count(CaseLaw.id))
            .group_by(CaseLaw.category)
        )
    ).all()
    cases_per_category = [
        CategoryCount(category=row[0], count=row[1]) for row in cat_rows
    ]

    # Cases per court
    court_rows = (
        await db.execute(
            select(CaseLaw.court, func.count(CaseLaw.id))
            .group_by(CaseLaw.court)
        )
    ).all()
    cases_per_court = [
        CourtCount(court=row[0], count=row[1]) for row in court_rows
    ]

    # Recent additions (last 7 days)
    recent_case_laws = (
        await db.execute(
            select(func.count(CaseLaw.id)).where(CaseLaw.created_at >= seven_days_ago)
        )
    ).scalar() or 0

    recent_statutes = (
        await db.execute(
            select(func.count(Statute.id)).where(Statute.created_at >= seven_days_ago)
        )
    ).scalar() or 0

    # User registrations per day (last 30 days)
    thirty_days_ago = now - timedelta(days=30)
    reg_rows = (
        await db.execute(
            select(
                func.date(User.created_at).label("day"),
                func.count(User.id),
            )
            .where(User.created_at >= thirty_days_ago)
            .group_by(func.date(User.created_at))
            .order_by(func.date(User.created_at))
        )
    ).all()
    user_registrations_per_day = [
        DailyCount(date=str(row[0]), count=row[1]) for row in reg_rows
    ]

    return DashboardStats(
        total_case_laws=total_case_laws,
        total_statutes=total_statutes,
        total_sections=total_sections,
        total_users=total_users,
        cases_per_category=cases_per_category,
        cases_per_court=cases_per_court,
        recent_case_laws=recent_case_laws,
        recent_statutes=recent_statutes,
        user_registrations_per_day=user_registrations_per_day,
    )


# ---------------------------------------------------------------------------
# Case Laws CRUD
# ---------------------------------------------------------------------------

@router.get(
    "/case-laws",
    response_model=dict,
    summary="List case laws (admin, paginated)",
)
async def admin_list_case_laws(
    category: Optional[LawCategory] = Query(None),
    court: Optional[Court] = Query(None),
    year: Optional[int] = Query(None),
    search: Optional[str] = Query(None, description="Search title / citation"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    base = select(CaseLaw)
    count_q = select(func.count(CaseLaw.id))

    if category:
        base = base.where(CaseLaw.category == category)
        count_q = count_q.where(CaseLaw.category == category)
    if court:
        base = base.where(CaseLaw.court == court)
        count_q = count_q.where(CaseLaw.court == court)
    if year:
        base = base.where(CaseLaw.year == year)
        count_q = count_q.where(CaseLaw.year == year)
    if search:
        like = f"%{search}%"
        condition = CaseLaw.title.ilike(like) | CaseLaw.citation.ilike(like)
        base = base.where(condition)
        count_q = count_q.where(condition)

    total = (await db.execute(count_q)).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(CaseLaw.created_at.desc()).offset(skip).limit(limit)
        )
    ).scalars().all()

    return {
        "items": [CaseLawAdminResponse.model_validate(r) for r in rows],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.post(
    "/case-laws",
    response_model=CaseLawAdminResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a case law",
)
async def admin_create_case_law(
    payload: CaseLawCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    # Check unique citation
    existing = (
        await db.execute(select(CaseLaw).where(CaseLaw.citation == payload.citation))
    ).scalar_one_or_none()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Case law with citation '{payload.citation}' already exists",
        )

    case = CaseLaw(**payload.model_dump())
    db.add(case)
    await db.flush()
    await db.refresh(case)
    return CaseLawAdminResponse.model_validate(case)


@router.put(
    "/case-laws/{case_id}",
    response_model=CaseLawAdminResponse,
    summary="Update a case law",
)
async def admin_update_case_law(
    case_id: int,
    payload: CaseLawUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(CaseLaw).where(CaseLaw.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case law not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(case, field, value)

    await db.flush()
    await db.refresh(case)
    return CaseLawAdminResponse.model_validate(case)


@router.delete(
    "/case-laws/{case_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a case law",
)
async def admin_delete_case_law(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(CaseLaw).where(CaseLaw.id == case_id))
    case = result.scalar_one_or_none()
    if not case:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Case law not found")

    await db.delete(case)
    await db.flush()


# ---------------------------------------------------------------------------
# Statutes CRUD
# ---------------------------------------------------------------------------

@router.get(
    "/statutes",
    response_model=dict,
    summary="List statutes (admin, paginated)",
)
async def admin_list_statutes(
    category: Optional[LawCategory] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    base = select(Statute)
    count_q = select(func.count(Statute.id))

    if category:
        base = base.where(Statute.category == category)
        count_q = count_q.where(Statute.category == category)
    if search:
        like = f"%{search}%"
        base = base.where(Statute.title.ilike(like))
        count_q = count_q.where(Statute.title.ilike(like))

    total = (await db.execute(count_q)).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(Statute.created_at.desc()).offset(skip).limit(limit)
        )
    ).scalars().all()

    return {
        "items": [StatuteAdminResponse.model_validate(r) for r in rows],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.post(
    "/statutes",
    response_model=StatuteAdminResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a statute",
)
async def admin_create_statute(
    payload: StatuteCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    statute = Statute(**payload.model_dump())
    db.add(statute)
    await db.flush()
    await db.refresh(statute)
    return StatuteAdminResponse.model_validate(statute)


@router.put(
    "/statutes/{statute_id}",
    response_model=StatuteAdminResponse,
    summary="Update a statute",
)
async def admin_update_statute(
    statute_id: int,
    payload: StatuteUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(Statute).where(Statute.id == statute_id))
    statute = result.scalar_one_or_none()
    if not statute:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statute not found")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(statute, field, value)

    await db.flush()
    await db.refresh(statute)
    return StatuteAdminResponse.model_validate(statute)


@router.delete(
    "/statutes/{statute_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a statute",
)
async def admin_delete_statute(
    statute_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(Statute).where(Statute.id == statute_id))
    statute = result.scalar_one_or_none()
    if not statute:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Statute not found")

    await db.delete(statute)
    await db.flush()


# ---------------------------------------------------------------------------
# Sections CRUD
# ---------------------------------------------------------------------------

@router.post(
    "/sections",
    response_model=SectionAdminResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a section",
)
async def admin_create_section(
    payload: SectionCreate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    # Verify parent statute exists
    statute = (
        await db.execute(select(Statute).where(Statute.id == payload.statute_id))
    ).scalar_one_or_none()
    if not statute:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Statute with id {payload.statute_id} not found",
        )

    section = Section(**payload.model_dump())
    db.add(section)
    await db.flush()
    await db.refresh(section)
    return SectionAdminResponse.model_validate(section)


@router.put(
    "/sections/{section_id}",
    response_model=SectionAdminResponse,
    summary="Update a section",
)
async def admin_update_section(
    section_id: int,
    payload: SectionUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(Section).where(Section.id == section_id))
    section = result.scalar_one_or_none()
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")

    update_data = payload.model_dump(exclude_unset=True)

    # If statute_id is being changed, verify the target exists
    if "statute_id" in update_data:
        statute = (
            await db.execute(select(Statute).where(Statute.id == update_data["statute_id"]))
        ).scalar_one_or_none()
        if not statute:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Statute with id {update_data['statute_id']} not found",
            )

    for field, value in update_data.items():
        setattr(section, field, value)

    await db.flush()
    await db.refresh(section)
    return SectionAdminResponse.model_validate(section)


@router.delete(
    "/sections/{section_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a section",
)
async def admin_delete_section(
    section_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    result = await db.execute(select(Section).where(Section.id == section_id))
    section = result.scalar_one_or_none()
    if not section:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Section not found")

    await db.delete(section)
    await db.flush()


# ---------------------------------------------------------------------------
# Users Management
# ---------------------------------------------------------------------------

@router.get(
    "/users",
    response_model=dict,
    summary="List users (admin, paginated)",
)
async def admin_list_users(
    role: Optional[UserRole] = Query(None),
    is_active: Optional[bool] = Query(None),
    search: Optional[str] = Query(None, description="Search by name or email"),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    base = select(User)
    count_q = select(func.count(User.id))

    if role:
        base = base.where(User.role == role)
        count_q = count_q.where(User.role == role)
    if is_active is not None:
        base = base.where(User.is_active == is_active)
        count_q = count_q.where(User.is_active == is_active)
    if search:
        like = f"%{search}%"
        condition = User.full_name.ilike(like) | User.email.ilike(like)
        base = base.where(condition)
        count_q = count_q.where(condition)

    total = (await db.execute(count_q)).scalar() or 0
    rows = (
        await db.execute(
            base.order_by(User.created_at.desc()).offset(skip).limit(limit)
        )
    ).scalars().all()

    return {
        "items": [UserAdminResponse.model_validate(r) for r in rows],
        "total": total,
        "skip": skip,
        "limit": limit,
    }


@router.put(
    "/users/{user_id}",
    response_model=UserAdminResponse,
    summary="Update user role / status",
)
async def admin_update_user(
    user_id: int,
    payload: UserAdminUpdate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    # Prevent admin from deactivating themselves
    if user.id == admin.id and payload.is_active is False:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot deactivate your own account",
        )

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)

    await db.flush()
    await db.refresh(user)
    return UserAdminResponse.model_validate(user)


@router.delete(
    "/users/{user_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a user",
)
async def admin_delete_user(
    user_id: int,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if user_id == admin.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot delete your own account",
        )

    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await db.delete(user)
    await db.flush()


# ---------------------------------------------------------------------------
# Bulk Operations
# ---------------------------------------------------------------------------

@router.post(
    "/case-laws/bulk",
    response_model=BulkOperationResult,
    status_code=status.HTTP_201_CREATED,
    summary="Bulk import case laws from JSON",
)
async def admin_bulk_import_case_laws(
    payload: BulkCaseLawImport,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    success_count = 0
    error_count = 0
    errors: list[str] = []

    for idx, item in enumerate(payload.case_laws):
        try:
            # Check for duplicate citation
            existing = (
                await db.execute(
                    select(CaseLaw.id).where(CaseLaw.citation == item.citation)
                )
            ).scalar_one_or_none()
            if existing:
                error_count += 1
                errors.append(f"Row {idx}: duplicate citation '{item.citation}'")
                continue

            case = CaseLaw(**item.model_dump())
            db.add(case)
            await db.flush()
            success_count += 1
        except Exception as exc:
            error_count += 1
            errors.append(f"Row {idx}: {str(exc)}")

    return BulkOperationResult(
        success_count=success_count,
        error_count=error_count,
        errors=errors,
    )


@router.delete(
    "/case-laws/bulk",
    response_model=BulkOperationResult,
    summary="Bulk delete case laws by IDs",
)
async def admin_bulk_delete_case_laws(
    payload: BulkDeleteRequest,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    if not payload.ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No IDs provided",
        )

    # Find which IDs actually exist
    existing_result = await db.execute(
        select(CaseLaw.id).where(CaseLaw.id.in_(payload.ids))
    )
    existing_ids = {row[0] for row in existing_result.all()}

    missing_ids = set(payload.ids) - existing_ids
    errors = [f"Case law with id {mid} not found" for mid in missing_ids]

    if existing_ids:
        await db.execute(
            delete(CaseLaw).where(CaseLaw.id.in_(existing_ids))
        )
        await db.flush()

    return BulkOperationResult(
        success_count=len(existing_ids),
        error_count=len(missing_ids),
        errors=errors,
    )
