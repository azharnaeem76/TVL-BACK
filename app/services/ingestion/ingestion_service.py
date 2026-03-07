"""
Data Ingestion Pipeline Service.

Complete pipeline:
1. Admin uploads PDF (50-60 page court judgment)
2. Extract text from PDF
3. Extract metadata (citation, court, judge) from text patterns
4. Summarize using LLM (or fallback to extractive)
5. Generate vector embedding
6. Store in database as a new CaseLaw entry

Also supports bulk ingestion and re-processing.
"""

import json
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models.legal import CaseLaw, LawCategory, Court
from app.services.ingestion.pdf_processor import (
    extract_text_from_pdf,
    extract_text_chunked,
    extract_metadata_from_text,
    get_page_count,
)
from app.services.ingestion.summarizer import summarize_document
from app.services.embedding_service import generate_embedding


class IngestionResult:
    """Result of a document ingestion."""

    def __init__(self):
        self.success = False
        self.case_law_id: int | None = None
        self.citation: str = ""
        self.title: str = ""
        self.message: str = ""
        self.page_count: int = 0
        self.warnings: list[str] = []

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "case_law_id": self.case_law_id,
            "citation": self.citation,
            "title": self.title,
            "message": self.message,
            "page_count": self.page_count,
            "warnings": self.warnings,
        }


async def ingest_pdf(
    file_bytes: bytes,
    filename: str,
    db: AsyncSession,
    # Optional overrides (admin can provide these if auto-detection fails)
    citation_override: str | None = None,
    title_override: str | None = None,
    court_override: str | None = None,
    category_override: str | None = None,
    year_override: int | None = None,
    judge_override: str | None = None,
) -> IngestionResult:
    """
    Full ingestion pipeline for a single PDF document.
    """
    result = IngestionResult()

    # Step 1: Basic validation
    result.page_count = get_page_count(file_bytes)
    if result.page_count == 0:
        result.message = "PDF has no pages or could not be read."
        return result

    # Step 2: Extract text
    full_text = extract_text_from_pdf(file_bytes)
    if not full_text or len(full_text) < 100:
        result.message = "Could not extract meaningful text from PDF. It may be a scanned document without OCR."
        result.warnings.append("Consider using an OCR tool to process scanned documents first.")
        return result

    # Step 3: Extract metadata from text patterns
    pdf_metadata = extract_metadata_from_text(full_text)

    # Apply overrides
    if citation_override:
        pdf_metadata["citation"] = citation_override
    if title_override:
        pdf_metadata["title"] = title_override
    if court_override:
        pdf_metadata["court"] = court_override
    if year_override:
        pdf_metadata["year"] = year_override
    if judge_override:
        pdf_metadata["judge_name"] = judge_override

    # Step 4: Check for duplicate citation
    if pdf_metadata.get("citation"):
        existing = await db.execute(
            select(CaseLaw).where(CaseLaw.citation == pdf_metadata["citation"])
        )
        if existing.scalar_one_or_none():
            result.message = f"Case law with citation '{pdf_metadata['citation']}' already exists."
            result.citation = pdf_metadata["citation"]
            return result

    # Step 5: Chunk text for summarization
    text_chunks = extract_text_chunked(file_bytes, chunk_size=4000)

    # Step 6: Summarize using LLM (or fallback)
    summary_data = await summarize_document(text_chunks, pdf_metadata)

    # Step 7: Validate required fields
    citation = summary_data.get("citation") or f"PENDING-{filename}"
    title = summary_data.get("title") or filename.replace(".pdf", "")

    if not summary_data.get("citation"):
        result.warnings.append("Citation could not be auto-detected. Please update it manually.")
    if not summary_data.get("court"):
        result.warnings.append("Court could not be auto-detected. Defaulting to 'district_court'.")

    # Validate category enum
    category_str = category_override or summary_data.get("category", "civil")
    try:
        category = LawCategory(category_str)
    except ValueError:
        category = LawCategory.CIVIL
        result.warnings.append(f"Invalid category '{category_str}', defaulted to 'civil'.")

    # Validate court enum
    court_str = summary_data.get("court", "district_court")
    try:
        court = Court(court_str)
    except ValueError:
        court = Court.DISTRICT_COURT
        result.warnings.append(f"Invalid court '{court_str}', defaulted to 'district_court'.")

    # Step 8: Generate embedding from summary + headnotes
    embedding_text = f"{title} {summary_data.get('summary_en', '')} {summary_data.get('headnotes', '')}"
    embedding = generate_embedding(embedding_text)

    # Step 9: Create CaseLaw entry
    case_law = CaseLaw(
        citation=citation,
        title=title,
        court=court,
        category=category,
        year=summary_data.get("year"),
        judge_name=summary_data.get("judge_name"),
        summary_en=summary_data.get("summary_en"),
        summary_ur=summary_data.get("summary_ur"),
        full_text=full_text,  # Store the complete text
        headnotes=summary_data.get("headnotes"),
        relevant_statutes=summary_data.get("relevant_statutes"),
        sections_applied=summary_data.get("sections_applied"),
        embedding=embedding,
    )
    db.add(case_law)
    await db.flush()

    # Step 10: Return result
    result.success = True
    result.case_law_id = case_law.id
    result.citation = citation
    result.title = title
    result.message = f"Successfully ingested '{title}' ({result.page_count} pages)."

    return result


async def reprocess_case_law(case_law_id: int, db: AsyncSession) -> IngestionResult:
    """
    Re-generate summary and embedding for an existing case law entry.
    Useful when the LLM model is updated or wasn't available during initial ingestion.
    """
    result = IngestionResult()

    case_law_result = await db.execute(select(CaseLaw).where(CaseLaw.id == case_law_id))
    case_law = case_law_result.scalar_one_or_none()

    if not case_law:
        result.message = "Case law not found."
        return result

    if not case_law.full_text:
        result.message = "No full text available for re-processing."
        return result

    # Re-chunk and re-summarize
    # Split full_text into chunks manually since we don't have the PDF
    text = case_law.full_text
    chunk_size = 4000
    chunks = [text[i:i + chunk_size] for i in range(0, len(text), chunk_size)]

    pdf_metadata = {
        "citation": case_law.citation,
        "title": case_law.title,
        "court": case_law.court.value if case_law.court else None,
        "year": case_law.year,
        "judge_name": case_law.judge_name,
    }

    summary_data = await summarize_document(chunks, pdf_metadata)

    # Update fields
    case_law.summary_en = summary_data.get("summary_en") or case_law.summary_en
    case_law.summary_ur = summary_data.get("summary_ur") or case_law.summary_ur
    case_law.headnotes = summary_data.get("headnotes") or case_law.headnotes
    case_law.relevant_statutes = summary_data.get("relevant_statutes") or case_law.relevant_statutes
    case_law.sections_applied = summary_data.get("sections_applied") or case_law.sections_applied

    # Re-generate embedding
    embedding_text = f"{case_law.title} {case_law.summary_en} {case_law.headnotes}"
    case_law.embedding = generate_embedding(embedding_text)

    result.success = True
    result.case_law_id = case_law.id
    result.citation = case_law.citation
    result.title = case_law.title
    result.message = f"Successfully re-processed '{case_law.title}'."

    return result
