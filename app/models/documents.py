"""Document upload and analysis models."""
import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Enum, Text, ForeignKey


from app.core.database import Base


class DocumentStatus(str, enum.Enum):
    UPLOADED = "uploaded"
    ANALYZING = "analyzing"
    COMPLETED = "completed"
    FAILED = "failed"


class Document(Base):
    __tablename__ = "documents"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    filename = Column(String(500), nullable=False)  # stored filename (uuid)
    original_name = Column(String(500), nullable=False)  # original upload name
    file_type = Column(String(10), nullable=False)  # pdf, doc, docx, txt
    file_size = Column(Integer, nullable=False)  # bytes
    status = Column(Enum(DocumentStatus), default=DocumentStatus.UPLOADED)

    # AI-extracted fields
    title = Column(String(500), nullable=True)
    summary = Column(Text, nullable=True)
    extracted_parties = Column(Text, nullable=True)
    extracted_sections = Column(Text, nullable=True)
    extracted_court = Column(String(255), nullable=True)
    extracted_judge = Column(String(255), nullable=True)
    extracted_date = Column(String(100), nullable=True)
    key_points = Column(Text, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
