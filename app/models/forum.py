"""Community Forum models."""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, ForeignKey
from app.core.database import Base


class ForumPost(Base):
    __tablename__ = "forum_posts"

    id = Column(Integer, primary_key=True, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(300), nullable=False)
    content = Column(Text, nullable=False)
    category = Column(String(50), default="general")  # general, case_discussion, legal_help, career, news
    is_pinned = Column(Boolean, default=False)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ForumReply(Base):
    __tablename__ = "forum_replies"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("forum_posts.id"), nullable=False, index=True)
    author_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    content = Column(Text, nullable=False)
    is_deleted = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ForumLike(Base):
    __tablename__ = "forum_likes"

    id = Column(Integer, primary_key=True, index=True)
    post_id = Column(Integer, ForeignKey("forum_posts.id"), nullable=True, index=True)
    reply_id = Column(Integer, ForeignKey("forum_replies.id"), nullable=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
