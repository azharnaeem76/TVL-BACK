import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Enum, Text, ForeignKey, Float, Index
from app.core.database import Base


class LawCategory(str, enum.Enum):
    CRIMINAL = "criminal"
    CIVIL = "civil"
    CONSTITUTIONAL = "constitutional"
    FAMILY = "family"
    CORPORATE = "corporate"
    TAXATION = "taxation"
    LABOR = "labor"
    PROPERTY = "property"
    CYBER = "cyber"
    BANKING = "banking"
    INTELLECTUAL_PROPERTY = "intellectual_property"
    HUMAN_RIGHTS = "human_rights"
    ENVIRONMENTAL = "environmental"
    ISLAMIC = "islamic"


class Court(str, enum.Enum):
    SUPREME_COURT = "supreme_court"
    FEDERAL_SHARIAT_COURT = "federal_shariat_court"
    LAHORE_HIGH_COURT = "lahore_high_court"
    SINDH_HIGH_COURT = "sindh_high_court"
    PESHAWAR_HIGH_COURT = "peshawar_high_court"
    BALOCHISTAN_HIGH_COURT = "balochistan_high_court"
    ISLAMABAD_HIGH_COURT = "islamabad_high_court"
    DISTRICT_COURT = "district_court"
    SESSION_COURT = "session_court"
    FAMILY_COURT = "family_court"
    BANKING_COURT = "banking_court"
    ANTI_TERRORISM_COURT = "anti_terrorism_court"


class CaseLaw(Base):
    __tablename__ = "case_laws"

    id = Column(Integer, primary_key=True, index=True)
    citation = Column(String(255), unique=True, index=True, nullable=False)
    title = Column(String(500), nullable=False)
    court = Column(Enum(Court), nullable=False)
    category = Column(Enum(LawCategory), nullable=False)
    year = Column(Integer, index=True)
    judge_name = Column(String(255), nullable=True)

    # Content in multiple languages
    summary_en = Column(Text, nullable=True)
    summary_ur = Column(Text, nullable=True)
    full_text = Column(Text, nullable=True)
    headnotes = Column(Text, nullable=True)

    # Relevant statutes and sections
    relevant_statutes = Column(Text, nullable=True)  # JSON string of statutes
    sections_applied = Column(Text, nullable=True)  # JSON string of sections

    # Vector embedding for semantic search (stored as JSON text without pgvector)
    embedding = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Statute(Base):
    __tablename__ = "statutes"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(500), nullable=False)
    short_title = Column(String(255), nullable=True)
    act_number = Column(String(50), nullable=True)
    year = Column(Integer, nullable=True)
    category = Column(Enum(LawCategory), nullable=False)

    full_text = Column(Text, nullable=True)
    summary_en = Column(Text, nullable=True)
    summary_ur = Column(Text, nullable=True)

    embedding = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Section(Base):
    __tablename__ = "sections"

    id = Column(Integer, primary_key=True, index=True)
    statute_id = Column(Integer, ForeignKey("statutes.id"), nullable=False)
    section_number = Column(String(20), nullable=False)
    title = Column(String(500), nullable=True)
    content = Column(Text, nullable=False)
    content_ur = Column(Text, nullable=True)

    embedding = Column(Text, nullable=True)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class SearchHistory(Base):
    __tablename__ = "search_history"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    query_text = Column(Text, nullable=False)
    detected_language = Column(String(20), nullable=True)
    normalized_query = Column(Text, nullable=True)
    results_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ChatSession(Base):
    __tablename__ = "chat_sessions"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    title = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("chat_sessions.id"), nullable=False)
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    language = Column(String(20), nullable=True)
    cited_case_ids = Column(Text, nullable=True)  # JSON list of case law IDs
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
