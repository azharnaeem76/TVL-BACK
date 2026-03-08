"""Models for admin-managed study content: quiz questions and study notes."""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Enum, JSON, ForeignKey
from app.core.database import Base


class ContentType(str, enum.Enum):
    QUIZ_QUESTION = "quiz_question"
    STUDY_NOTE = "study_note"
    PAST_PAPER = "past_paper"


class StudyContent(Base):
    __tablename__ = "study_content"

    id = Column(Integer, primary_key=True, index=True)
    content_type = Column(Enum(ContentType), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    category = Column(String(100), nullable=False, index=True)  # e.g., Constitutional, Criminal
    exam_type = Column(String(50), nullable=True, index=True)  # llb, bar, lat, gat_general, etc.
    difficulty = Column(String(20), nullable=True)  # easy, medium, hard
    content = Column(Text, nullable=True)  # For notes: the full text content

    # Quiz question fields (stored in JSON for flexibility)
    question_data = Column(JSON, nullable=True)
    # Expected shape for quiz: {"question": str, "options": [str], "correct": int, "explanation": str}

    is_published = Column(Boolean, default=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
