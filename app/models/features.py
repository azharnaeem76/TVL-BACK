"""Feature flags and modular service models."""
import enum
from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Enum, ForeignKey, Float, JSON
from app.core.database import Base


# ---------------------------------------------------------------------------
# Feature Flags
# ---------------------------------------------------------------------------

class FeatureCategory(str, enum.Enum):
    CORE = "core"
    AI = "ai"
    COLLABORATION = "collaboration"
    BUSINESS = "business"
    STUDENT = "student"
    NOTIFICATIONS = "notifications"


class FeatureFlag(Base):
    __tablename__ = "feature_flags"

    id = Column(Integer, primary_key=True, index=True)
    key = Column(String(100), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    category = Column(Enum(FeatureCategory), nullable=False)
    enabled = Column(Boolean, default=False)
    config = Column(JSON, nullable=True)  # Optional JSON config per feature
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Case Tracker
# ---------------------------------------------------------------------------

class CaseStatus(str, enum.Enum):
    ACTIVE = "active"
    PENDING = "pending"
    ADJOURNED = "adjourned"
    DISPOSED = "disposed"
    APPEALED = "appealed"
    CLOSED = "closed"


class TrackedCase(Base):
    __tablename__ = "tracked_cases"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String(500), nullable=False)
    case_number = Column(String(100), nullable=True)
    court = Column(String(100), nullable=True)
    judge_name = Column(String(255), nullable=True)
    opposing_counsel = Column(String(255), nullable=True)
    client_name = Column(String(255), nullable=True)
    status = Column(Enum(CaseStatus), default=CaseStatus.ACTIVE)
    category = Column(String(100), nullable=True)
    next_hearing = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Client Management (CRM)
# ---------------------------------------------------------------------------

class Client(Base):
    __tablename__ = "clients"

    id = Column(Integer, primary_key=True, index=True)
    lawyer_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    email = Column(String(255), nullable=True)
    phone = Column(String(20), nullable=True)
    cnic = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Notifications
# ---------------------------------------------------------------------------

class NotificationType(str, enum.Enum):
    HEARING_REMINDER = "hearing_reminder"
    CASE_UPDATE = "case_update"
    NEW_JUDGMENT = "new_judgment"
    SYSTEM = "system"
    WELCOME = "welcome"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    type = Column(Enum(NotificationType), nullable=False)
    title = Column(String(500), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, default=False)
    link = Column(String(500), nullable=True)  # Optional link to navigate to
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Consultation Booking
# ---------------------------------------------------------------------------

class ConsultationStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Consultation(Base):
    __tablename__ = "consultations"

    id = Column(Integer, primary_key=True, index=True)
    client_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    lawyer_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    scheduled_at = Column(DateTime, nullable=False)
    duration_minutes = Column(Integer, default=30)
    topic = Column(String(500), nullable=True)
    notes = Column(Text, nullable=True)
    status = Column(Enum(ConsultationStatus), default=ConsultationStatus.PENDING)
    fee = Column(Float, nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Audit Log
# ---------------------------------------------------------------------------

class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    action = Column(String(100), nullable=False)  # e.g., "create_case_law", "delete_user"
    resource_type = Column(String(100), nullable=True)  # e.g., "case_law", "statute"
    resource_id = Column(Integer, nullable=True)
    details = Column(JSON, nullable=True)
    ip_address = Column(String(50), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
