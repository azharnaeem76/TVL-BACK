"""Admin-managed study content: quiz questions, study notes, past papers."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from pydantic import BaseModel, Field
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.models.study_content import StudyContent, ContentType

router = APIRouter(prefix="/study-content", tags=["Study Content"])

CATEGORIES = [
    "Constitutional", "Criminal", "Civil", "Family", "Property",
    "Contract", "Evidence", "Labour", "Cyber", "Islamic",
    "International", "Administrative", "Jurisprudence", "General",
]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ContentCreate(BaseModel):
    content_type: str = Field(..., description="quiz_question, study_note, or past_paper")
    title: str = Field(..., min_length=3, max_length=500)
    category: str = Field("General", max_length=100)
    exam_type: Optional[str] = None
    difficulty: Optional[str] = None
    content: Optional[str] = None  # For notes/past papers
    question_data: Optional[dict] = None  # For quiz questions


class ContentUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    exam_type: Optional[str] = None
    difficulty: Optional[str] = None
    content: Optional[str] = None
    question_data: Optional[dict] = None
    is_published: Optional[bool] = None


class ContentResponse(BaseModel):
    id: int
    content_type: str
    title: str
    category: str
    exam_type: Optional[str] = None
    difficulty: Optional[str] = None
    content: Optional[str] = None
    question_data: Optional[dict] = None
    is_published: bool
    created_by: int
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin required")
    return current_user


# ---------------------------------------------------------------------------
# Public: Read content (students)
# ---------------------------------------------------------------------------

@router.get("/questions", summary="Get quiz questions (published)")
async def get_questions(
    category: Optional[str] = Query(None),
    exam_type: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base = select(StudyContent).where(
        StudyContent.content_type == ContentType.QUIZ_QUESTION,
        StudyContent.is_published == True,
    )
    if category:
        base = base.where(StudyContent.category == category)
    if exam_type:
        base = base.where(StudyContent.exam_type == exam_type)
    if difficulty:
        base = base.where(StudyContent.difficulty == difficulty)

    rows = (await db.execute(base.order_by(func.random()).limit(limit))).scalars().all()

    return [
        {
            "id": r.id,
            "category": r.category,
            "difficulty": r.difficulty,
            "exam_type": r.exam_type,
            **(r.question_data or {}),
        }
        for r in rows
    ]


@router.get("/notes", summary="Get study notes (published)")
async def get_notes(
    category: Optional[str] = Query(None),
    exam_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base = select(StudyContent).where(
        StudyContent.content_type.in_([ContentType.STUDY_NOTE, ContentType.PAST_PAPER]),
        StudyContent.is_published == True,
    )
    count_q = select(func.count(StudyContent.id)).where(
        StudyContent.content_type.in_([ContentType.STUDY_NOTE, ContentType.PAST_PAPER]),
        StudyContent.is_published == True,
    )
    if category:
        base = base.where(StudyContent.category == category)
        count_q = count_q.where(StudyContent.category == category)
    if exam_type:
        base = base.where(StudyContent.exam_type == exam_type)
        count_q = count_q.where(StudyContent.exam_type == exam_type)
    if search:
        like = f"%{search}%"
        base = base.where(StudyContent.title.ilike(like))
        count_q = count_q.where(StudyContent.title.ilike(like))

    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(
        base.order_by(StudyContent.created_at.desc()).offset(skip).limit(limit)
    )).scalars().all()

    return {
        "items": [
            {
                "id": r.id,
                "content_type": r.content_type.value,
                "title": r.title,
                "category": r.category,
                "exam_type": r.exam_type,
                "content": r.content,
                "created_at": str(r.created_at) if r.created_at else None,
            }
            for r in rows
        ],
        "total": total,
    }


@router.get("/categories", summary="List available categories")
async def list_categories(current_user: User = Depends(get_current_user)):
    return CATEGORIES


# ---------------------------------------------------------------------------
# Admin: CRUD content
# ---------------------------------------------------------------------------

@router.get("/admin/all", summary="List all content (admin)")
async def admin_list_content(
    content_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    base = select(StudyContent)
    count_q = select(func.count(StudyContent.id))
    if content_type:
        base = base.where(StudyContent.content_type == content_type)
        count_q = count_q.where(StudyContent.content_type == content_type)
    if category:
        base = base.where(StudyContent.category == category)
        count_q = count_q.where(StudyContent.category == category)

    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(
        base.order_by(StudyContent.created_at.desc()).offset(skip).limit(limit)
    )).scalars().all()

    return {
        "items": [
            {
                "id": r.id,
                "content_type": r.content_type.value,
                "title": r.title,
                "category": r.category,
                "exam_type": r.exam_type,
                "difficulty": r.difficulty,
                "content": r.content[:200] if r.content else None,
                "question_data": r.question_data,
                "is_published": r.is_published,
                "created_at": str(r.created_at) if r.created_at else None,
            }
            for r in rows
        ],
        "total": total,
    }


@router.post("/admin/create", summary="Create content (admin)")
async def admin_create_content(
    payload: ContentCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if payload.content_type not in ["quiz_question", "study_note", "past_paper"]:
        raise HTTPException(status_code=400, detail="Invalid content type")

    if payload.content_type == "quiz_question" and not payload.question_data:
        raise HTTPException(status_code=400, detail="question_data is required for quiz questions")

    if payload.content_type == "quiz_question" and payload.question_data:
        qd = payload.question_data
        if not qd.get("question") or not qd.get("options") or qd.get("correct") is None:
            raise HTTPException(status_code=400, detail="question_data must include question, options, and correct")

    item = StudyContent(
        content_type=ContentType(payload.content_type),
        title=payload.title,
        category=payload.category,
        exam_type=payload.exam_type,
        difficulty=payload.difficulty,
        content=payload.content,
        question_data=payload.question_data,
        created_by=admin.id,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)

    return {"id": item.id, "title": item.title, "content_type": item.content_type.value}


@router.put("/admin/{item_id}", summary="Update content (admin)")
async def admin_update_content(
    item_id: int,
    payload: ContentUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    item = (await db.execute(select(StudyContent).where(StudyContent.id == item_id))).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")

    for field in ["title", "category", "exam_type", "difficulty", "content", "question_data", "is_published"]:
        val = getattr(payload, field)
        if val is not None:
            setattr(item, field, val)

    await db.flush()
    await db.refresh(item)
    return {"ok": True, "id": item.id}


@router.delete("/admin/{item_id}", summary="Delete content (admin)")
async def admin_delete_content(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    item = (await db.execute(select(StudyContent).where(StudyContent.id == item_id))).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    await db.delete(item)
    return {"ok": True}
