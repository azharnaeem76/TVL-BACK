import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Enum, Boolean, Text
from app.core.database import Base


class UserRole(str, enum.Enum):
    LAWYER = "lawyer"
    JUDGE = "judge"
    PARALEGAL = "paralegal"
    LAW_STUDENT = "law_student"
    CLIENT = "client"
    ADMIN = "admin"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.CLIENT, nullable=False)
    phone = Column(String(20), nullable=True)
    city = Column(String(100), nullable=True)
    bar_number = Column(String(50), nullable=True)  # For lawyers
    specialization = Column(String(255), nullable=True)
    bio = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    preferred_language = Column(String(10), default="en")  # en, ur, roman_ur
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
