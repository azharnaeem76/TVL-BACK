import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, Boolean, Text
from app.core.database import Base


class UserRole(str, enum.Enum):
    LAWYER = "lawyer"
    JUDGE = "judge"
    PARALEGAL = "paralegal"
    LAW_STUDENT = "law_student"
    CLIENT = "client"
    ADMIN = "admin"
    SUPPORT = "support"


class SubscriptionPlan(str, enum.Enum):
    FREE = "free"
    PRO = "pro"
    FIRM = "firm"


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, index=True, nullable=False)
    full_name = Column(String(255), nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(Enum(UserRole), default=UserRole.CLIENT, nullable=False)
    plan = Column(Enum(SubscriptionPlan), default=SubscriptionPlan.FREE, nullable=False)
    plan_expires_at = Column(DateTime, nullable=True)
    phone = Column(String(20), nullable=True)
    city = Column(String(100), nullable=True)
    bar_number = Column(String(50), nullable=True)  # For lawyers
    specialization = Column(String(255), nullable=True)
    bio = Column(Text, nullable=True)
    profile_picture = Column(String(500), nullable=True)  # URL to profile picture
    is_active = Column(Boolean, default=True)
    is_suspended = Column(Boolean, default=False)
    suspension_reason = Column(Text, nullable=True)
    preferred_language = Column(String(10), default="en")  # en, ur, roman_ur
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
