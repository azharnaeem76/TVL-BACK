"""Community Forum API."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, or_
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.forum import ForumPost, ForumReply, ForumLike
from app.services.content_moderation import check_content

router = APIRouter(prefix="/forum", tags=["Community Forum"])

CATEGORIES = ["general", "case_discussion", "legal_help", "career", "news"]


class CreatePost(BaseModel):
    title: str = Field(..., min_length=3, max_length=300)
    content: str = Field(..., min_length=5, max_length=10000)
    category: str = "general"


class CreateReply(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)


# ---------------------------------------------------------------------------
# Posts
# ---------------------------------------------------------------------------

@router.get("/posts", summary="List forum posts")
async def list_posts(
    category: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base = select(ForumPost).where(ForumPost.is_deleted == False)
    count_q = select(func.count(ForumPost.id)).where(ForumPost.is_deleted == False)

    if category and category in CATEGORIES:
        base = base.where(ForumPost.category == category)
        count_q = count_q.where(ForumPost.category == category)
    if search:
        like = f"%{search}%"
        cond = or_(ForumPost.title.ilike(like), ForumPost.content.ilike(like))
        base = base.where(cond)
        count_q = count_q.where(cond)

    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(
        base.order_by(ForumPost.is_pinned.desc(), ForumPost.created_at.desc()).offset(skip).limit(limit)
    )).scalars().all()

    items = []
    for p in rows:
        author = (await db.execute(select(User).where(User.id == p.author_id))).scalar_one_or_none()
        reply_count = (await db.execute(
            select(func.count(ForumReply.id)).where(ForumReply.post_id == p.id, ForumReply.is_deleted == False)
        )).scalar() or 0
        like_count = (await db.execute(
            select(func.count(ForumLike.id)).where(ForumLike.post_id == p.id)
        )).scalar() or 0
        user_liked = (await db.execute(
            select(ForumLike.id).where(ForumLike.post_id == p.id, ForumLike.user_id == current_user.id)
        )).scalar_one_or_none()

        items.append({
            "id": p.id,
            "title": p.title,
            "content": p.content,
            "category": p.category,
            "is_pinned": p.is_pinned,
            "author": {
                "id": author.id if author else 0,
                "name": author.full_name if author else "Unknown",
                "role": author.role.value if author else "",
                "profile_picture": getattr(author, 'profile_picture', None) if author else None,
            },
            "reply_count": reply_count,
            "like_count": like_count,
            "user_liked": user_liked is not None,
            "created_at": str(p.created_at),
        })

    return {"items": items, "total": total}


@router.post("/posts", summary="Create a forum post")
async def create_post(
    payload: CreatePost,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Content moderation
    is_clean, matched = check_content(payload.title + " " + payload.content)
    if not is_clean:
        raise HTTPException(
            status_code=400,
            detail=f"Your message contains inappropriate language and cannot be posted. Please revise your content."
        )

    if payload.category not in CATEGORIES:
        payload.category = "general"

    post = ForumPost(
        author_id=current_user.id,
        title=payload.title,
        content=payload.content,
        category=payload.category,
    )
    db.add(post)
    await db.commit()
    await db.refresh(post)

    return {
        "id": post.id,
        "title": post.title,
        "content": post.content,
        "category": post.category,
        "author": {"id": current_user.id, "name": current_user.full_name, "role": current_user.role.value},
        "reply_count": 0,
        "like_count": 0,
        "user_liked": False,
        "created_at": str(post.created_at),
    }


@router.delete("/posts/{post_id}", summary="Delete a forum post")
async def delete_post(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = (await db.execute(select(ForumPost).where(ForumPost.id == post_id))).scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    if post.author_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    post.is_deleted = True
    await db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Replies
# ---------------------------------------------------------------------------

@router.get("/posts/{post_id}/replies", summary="Get replies for a post")
async def get_replies(
    post_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = (await db.execute(select(ForumPost).where(ForumPost.id == post_id, ForumPost.is_deleted == False))).scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    rows = (await db.execute(
        select(ForumReply).where(ForumReply.post_id == post_id, ForumReply.is_deleted == False)
        .order_by(ForumReply.created_at.asc()).offset(skip).limit(limit)
    )).scalars().all()

    items = []
    for r in rows:
        author = (await db.execute(select(User).where(User.id == r.author_id))).scalar_one_or_none()
        like_count = (await db.execute(
            select(func.count(ForumLike.id)).where(ForumLike.reply_id == r.id)
        )).scalar() or 0
        user_liked = (await db.execute(
            select(ForumLike.id).where(ForumLike.reply_id == r.id, ForumLike.user_id == current_user.id)
        )).scalar_one_or_none()

        items.append({
            "id": r.id,
            "post_id": r.post_id,
            "content": r.content,
            "author": {
                "id": author.id if author else 0,
                "name": author.full_name if author else "Unknown",
                "role": author.role.value if author else "",
                "profile_picture": getattr(author, 'profile_picture', None) if author else None,
            },
            "like_count": like_count,
            "user_liked": user_liked is not None,
            "created_at": str(r.created_at),
        })

    return items


@router.post("/posts/{post_id}/replies", summary="Reply to a forum post")
async def create_reply(
    post_id: int,
    payload: CreateReply,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = (await db.execute(select(ForumPost).where(ForumPost.id == post_id, ForumPost.is_deleted == False))).scalar_one_or_none()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")

    is_clean, matched = check_content(payload.content)
    if not is_clean:
        raise HTTPException(
            status_code=400,
            detail=f"Your reply contains inappropriate language and cannot be posted. Please revise your content."
        )

    reply = ForumReply(post_id=post_id, author_id=current_user.id, content=payload.content)
    db.add(reply)
    await db.commit()
    await db.refresh(reply)

    return {
        "id": reply.id,
        "post_id": reply.post_id,
        "content": reply.content,
        "author": {"id": current_user.id, "name": current_user.full_name, "role": current_user.role.value},
        "like_count": 0,
        "user_liked": False,
        "created_at": str(reply.created_at),
    }


@router.delete("/replies/{reply_id}", summary="Delete a reply")
async def delete_reply(
    reply_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    reply = (await db.execute(select(ForumReply).where(ForumReply.id == reply_id))).scalar_one_or_none()
    if not reply:
        raise HTTPException(status_code=404, detail="Reply not found")
    if reply.author_id != current_user.id and current_user.role.value != "admin":
        raise HTTPException(status_code=403, detail="Not authorized")
    reply.is_deleted = True
    await db.commit()
    return {"ok": True}


# ---------------------------------------------------------------------------
# Likes
# ---------------------------------------------------------------------------

@router.post("/posts/{post_id}/like", summary="Like/unlike a post")
async def toggle_post_like(
    post_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = (await db.execute(
        select(ForumLike).where(ForumLike.post_id == post_id, ForumLike.user_id == current_user.id)
    )).scalar_one_or_none()

    if existing:
        await db.delete(existing)
        await db.commit()
        return {"liked": False}
    else:
        like = ForumLike(post_id=post_id, user_id=current_user.id)
        db.add(like)
        await db.commit()
        return {"liked": True}


@router.post("/replies/{reply_id}/like", summary="Like/unlike a reply")
async def toggle_reply_like(
    reply_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    existing = (await db.execute(
        select(ForumLike).where(ForumLike.reply_id == reply_id, ForumLike.user_id == current_user.id)
    )).scalar_one_or_none()

    if existing:
        await db.delete(existing)
        await db.commit()
        return {"liked": False}
    else:
        like = ForumLike(reply_id=reply_id, user_id=current_user.id)
        db.add(like)
        await db.commit()
        return {"liked": True}
