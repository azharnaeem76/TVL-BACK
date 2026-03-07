"""
PDF Processing Service.

Extracts text from uploaded legal PDF documents (50-60+ pages).
Handles scanned PDFs, multi-column layouts, and Urdu text.
"""

import io
import re
import pdfplumber


def extract_text_from_pdf(file_bytes: bytes) -> str:
    """Extract all text from a PDF file."""
    text_parts = []

    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            page_text = page.extract_text()
            if page_text:
                text_parts.append(page_text)

    full_text = "\n\n".join(text_parts)
    # Clean up common PDF artifacts
    full_text = re.sub(r"\n{3,}", "\n\n", full_text)
    full_text = re.sub(r" {2,}", " ", full_text)
    return full_text.strip()


def extract_text_chunked(file_bytes: bytes, chunk_size: int = 4000) -> list[str]:
    """
    Extract text from PDF and split into chunks for LLM processing.
    Each chunk stays within token limits while preserving paragraph boundaries.
    """
    full_text = extract_text_from_pdf(file_bytes)
    if not full_text:
        return []

    paragraphs = full_text.split("\n\n")
    chunks = []
    current_chunk = ""

    for para in paragraphs:
        if len(current_chunk) + len(para) + 2 > chunk_size:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = para
        else:
            current_chunk += "\n\n" + para if current_chunk else para

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def extract_metadata_from_text(text: str) -> dict:
    """
    Attempt to extract basic metadata from the first few pages of a legal document.
    Looks for patterns common in Pakistani court judgments.
    """
    first_section = text[:3000]  # First ~3000 chars usually have metadata

    metadata = {
        "citation": None,
        "title": None,
        "court": None,
        "year": None,
        "judge_name": None,
    }

    # Try to find citation patterns: PLD 2024 Supreme Court 123, 2024 SCMR 456, etc.
    citation_patterns = [
        r"(PLD\s+\d{4}\s+\w[\w\s]+\d+)",
        r"(\d{4}\s+SCMR\s+\d+)",
        r"(\d{4}\s+CLC\s+\d+)",
        r"(\d{4}\s+PCrLJ\s+\d+)",
        r"(\d{4}\s+PTD\s+\d+)",
        r"(\d{4}\s+CLD\s+\d+)",
        r"(\d{4}\s+MLD\s+\d+)",
        r"(\d{4}\s+YLR\s+\d+)",
        r"(\d{4}\s+PLC\s+\d+)",
    ]
    for pattern in citation_patterns:
        match = re.search(pattern, first_section, re.IGNORECASE)
        if match:
            metadata["citation"] = match.group(1).strip()
            break

    # Extract year
    year_match = re.search(r"\b(19|20)\d{2}\b", first_section)
    if year_match:
        metadata["year"] = int(year_match.group())

    # Try to find court name
    court_keywords = {
        "supreme court": "supreme_court",
        "federal shariat court": "federal_shariat_court",
        "lahore high court": "lahore_high_court",
        "sindh high court": "sindh_high_court",
        "peshawar high court": "peshawar_high_court",
        "balochistan high court": "balochistan_high_court",
        "islamabad high court": "islamabad_high_court",
        "district court": "district_court",
        "sessions court": "session_court",
        "session court": "session_court",
        "family court": "family_court",
        "banking court": "banking_court",
        "anti-terrorism court": "anti_terrorism_court",
        "anti terrorism court": "anti_terrorism_court",
    }
    first_lower = first_section.lower()
    for keyword, court_val in court_keywords.items():
        if keyword in first_lower:
            metadata["court"] = court_val
            break

    # Try to find judge name: "Before: Justice XYZ" or "Hon'ble Mr. Justice XYZ"
    judge_patterns = [
        r"(?:Before|Hon'ble|Honourable)[:\s]+(?:Mr\.\s+|Mrs\.\s+)?Justice\s+([A-Z][a-zA-Z\s\.]+?)(?:\n|,|$)",
        r"Justice\s+([A-Z][a-zA-Z\s\.]+?)(?:\n|,|\s*-)",
    ]
    for pattern in judge_patterns:
        match = re.search(pattern, first_section)
        if match:
            metadata["judge_name"] = match.group(1).strip()
            break

    # Try to find title: "X v. Y" or "X vs Y" or "X versus Y"
    title_patterns = [
        r"([A-Z][A-Za-z\s\.]+?)\s+(?:v\.|vs\.?|versus)\s+([A-Z][A-Za-z\s\.]+?)(?:\n|$)",
    ]
    for pattern in title_patterns:
        match = re.search(pattern, first_section)
        if match:
            metadata["title"] = f"{match.group(1).strip()} v. {match.group(2).strip()}"
            break

    return metadata


def get_page_count(file_bytes: bytes) -> int:
    """Get the total number of pages in a PDF."""
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        return len(pdf.pages)
