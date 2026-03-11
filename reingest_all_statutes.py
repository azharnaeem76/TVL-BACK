"""
Re-ingest ALL statutes from PakistanLaw PDFs with COMPLETE text extraction.
- Reads ALL pages from each PDF (not just first 2-3)
- Extracts sections by parsing section/article patterns
- Updates existing statutes or inserts new ones
- Generates embeddings for search
"""

import os
import re
import sys
import json
import time

# Fix Windows console encoding
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import pdfplumber
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.services.embedding_service import generate_embeddings_batch

settings = get_settings()
LAWS_DIR = r"E:\tvl\tvl\PakisanLaw\laws_of_pakistan"

CATEGORY_MAP = {
    "Anti Money Laundering and Foreign Exchange Laws": "BANKING",
    "Anti Trust Laws": "CORPORATE",
    "Balochistan Provincial Statutes": "CONSTITUTIONAL",
    "Banking Laws": "BANKING",
    "Commercial Laws": "CORPORATE",
    "Company Laws": "CORPORATE",
    "Constitutional and Administrative Laws": "CONSTITUTIONAL",
    "Criminal Laws": "CRIMINAL",
    "Cyber Crimes": "CYBER",
    "Drug Laws": "CRIMINAL",
    "Electricity Petroleum and Gas Laws": "PROPERTY",
    "Environment and Wildlife Laws": "ENVIRONMENTAL",
    "Family Laws": "FAMILY",
    "Foreigners Laws": "CONSTITUTIONAL",
    "Insurance Laws": "CORPORATE",
    "Intellectual Property Laws": "INTELLECTUAL_PROPERTY",
    "KPK Provincial Statutes": "CONSTITUTIONAL",
    "Labour Laws": "LABOR",
    "Law Enforcement Agency Laws": "CRIMINAL",
    "Military and Arms Laws": "CRIMINAL",
    "Miscellaneous Laws": "CIVIL",
    "Non Profit Organization": "CORPORATE",
    "Procedural Laws": "CIVIL",
    "Property Laws": "PROPERTY",
    "Punjab Provincial Statutes": "CONSTITUTIONAL",
    "Sindh Provincial Statutes": "CONSTITUTIONAL",
    "Stock Exchange and Listing": "CORPORATE",
    "Tax and Fiscal Laws": "TAXATION",
    "Telecommunication Laws": "CYBER",
}


def extract_title_and_year(filename: str) -> tuple:
    """Extract clean title and year from PDF filename."""
    name = filename.replace(".pdf", "").replace(".PDF", "")
    name = re.sub(r"\s*-\s*Khalid Zafar.*$", "", name, flags=re.IGNORECASE)
    name = name.strip()
    year_match = re.search(r"(\d{4})", name)
    year = int(year_match.group(1)) if year_match else None
    if year and (year < 1800 or year > 2030):
        year = None
    return name, year


def extract_full_text(pdf_path: str) -> str:
    """Extract ALL text from ALL pages of a PDF."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            all_text = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    all_text.append(page_text)
            return "\n\n".join(all_text)
    except Exception as e:
        print(f"    ERROR reading PDF: {e}")
        return ""


def generate_summary(full_text: str, title: str) -> str:
    """Generate a summary from the full text (first meaningful paragraph)."""
    if not full_text or len(full_text) < 50:
        return f"{title} - Pakistani legislation."

    # Skip table of contents - find actual content
    # Look for preamble/whereas clauses or first section
    patterns = [
        r"(?:WHEREAS|An Act to|An Ordinance to|An Order to|Be it enacted)",
        r"(?:^|\n)\s*1\.\s+(?:Short title|Title|Extent)",
        r"(?:CHAPTER\s+I\b)",
    ]
    start_pos = 0
    for pattern in patterns:
        match = re.search(pattern, full_text, re.IGNORECASE | re.MULTILINE)
        if match:
            start_pos = max(0, match.start() - 50)
            break

    # Take a chunk from the start of actual content
    chunk = full_text[start_pos:start_pos + 1000]
    # Clean up
    chunk = re.sub(r"\s+", " ", chunk).strip()
    # Take first 500 chars
    if len(chunk) > 500:
        # Try to break at a sentence boundary
        cut = chunk[:500].rfind(".")
        if cut > 200:
            chunk = chunk[:cut + 1]
        else:
            chunk = chunk[:500] + "..."
    return chunk


def extract_sections(full_text: str) -> list:
    """Extract sections/articles from statute text."""
    sections = []
    if not full_text or len(full_text) < 100:
        return sections

    # Pattern to match section headers like:
    # "1. Short title, extent and commencement"
    # "Section 1. Short title"
    # "Article 1. Short title"
    # "2. Definitions.—"
    # Also handles: "S. 1", "Sec. 1", etc.
    section_pattern = re.compile(
        r'(?:^|\n)\s*'
        r'(?:(?:Section|Article|S\.|Sec\.)\s*)?'
        r'(\d+[A-Z]?(?:-[A-Z])?)\.\s*'
        r'([^\n.—:]+(?:[.—:])?)',
        re.MULTILINE
    )

    matches = list(section_pattern.finditer(full_text))
    if not matches:
        return sections

    for i, match in enumerate(matches):
        sec_num = match.group(1).strip()
        sec_title = match.group(2).strip().rstrip(".—:-")

        # Skip if section number is unreasonably large (probably page numbers)
        try:
            if int(re.sub(r'[A-Z-]', '', sec_num)) > 999:
                continue
        except ValueError:
            pass

        # Skip TOC entries (very short, just page references)
        if len(sec_title) < 3:
            continue

        # Get content: text between this section and the next
        start = match.end()
        if i + 1 < len(matches):
            end = matches[i + 1].start()
        else:
            end = min(start + 5000, len(full_text))

        content = full_text[start:end].strip()

        # Clean up content
        content = re.sub(r"\n\s*\n\s*\n+", "\n\n", content)

        # Skip if content is too short (likely TOC entry)
        if len(content) < 20:
            continue

        # Skip if content looks like a TOC (mostly page numbers)
        if re.match(r"^\s*\d+\s*$", content):
            continue

        # Limit content to reasonable size per section
        if len(content) > 10000:
            content = content[:10000]

        sections.append({
            "section_number": sec_num,
            "title": sec_title[:500],
            "content": content,
        })

    return sections


def main():
    engine = create_engine(settings.SYNC_DATABASE_URL, echo=False)
    total_statutes_updated = 0
    total_statutes_new = 0
    total_sections_created = 0
    errors = []

    with Session(engine) as db:
        # Get existing statutes by title for matching
        existing = {}
        rows = db.execute(text("SELECT id, title FROM statutes")).fetchall()
        for row in rows:
            existing[row[1].lower().strip()] = row[0]
        print(f"Found {len(existing)} existing statutes in DB.\n")

        all_pdfs = []
        for folder in sorted(os.listdir(LAWS_DIR)):
            folder_path = os.path.join(LAWS_DIR, folder)
            if not os.path.isdir(folder_path):
                continue
            category = CATEGORY_MAP.get(folder, "CIVIL")
            for pdf_file in sorted(os.listdir(folder_path)):
                if not pdf_file.lower().endswith(".pdf"):
                    continue
                all_pdfs.append((folder, folder_path, pdf_file, category))

        print(f"Total PDFs to process: {len(all_pdfs)}\n")

        for idx, (folder, folder_path, pdf_file, category) in enumerate(all_pdfs, 1):
            title, year = extract_title_and_year(pdf_file)
            if not title:
                continue

            pdf_path = os.path.join(folder_path, pdf_file)
            try:
                print(f"[{idx}/{len(all_pdfs)}] {title}")
            except UnicodeEncodeError:
                print(f"[{idx}/{len(all_pdfs)}] (title with special chars)")

            # Extract FULL text from ALL pages
            try:
                full_text = extract_full_text(pdf_path)
            except Exception as e:
                print(f"  ERROR: {e}")
                errors.append(f"{title}: {e}")
                continue

            if not full_text:
                print(f"  WARNING: No text extracted")
                errors.append(f"{title}: No text extracted")
                continue

            text_len = len(full_text)
            print(f"  Extracted {text_len:,} chars from PDF")

            # Generate summary from full text
            summary = generate_summary(full_text, title)

            # Extract sections
            sections = extract_sections(full_text)
            print(f"  Found {len(sections)} sections")

            # Determine act_number
            act_match = re.search(r"(Act|Ordinance|Rules|Code|Order|Regulations?),?\s*(\d{4})", title)
            act_number = f"{act_match.group(1)} of {act_match.group(2)}" if act_match else ""

            # Check if statute already exists
            title_lower = title.lower().strip()
            statute_id = existing.get(title_lower)

            if statute_id:
                # UPDATE existing statute with complete data
                db.execute(
                    text("""
                        UPDATE statutes
                        SET full_text = :full_text,
                            summary_en = :summary_en,
                            category = :category,
                            year = COALESCE(:year, year),
                            act_number = COALESCE(NULLIF(:act_number, ''), act_number)
                        WHERE id = :id
                    """),
                    {
                        "full_text": full_text,
                        "summary_en": summary,
                        "category": category,
                        "year": year,
                        "act_number": act_number,
                        "id": statute_id,
                    },
                )
                print(f"  UPDATED statute ID={statute_id}")
                total_statutes_updated += 1
            else:
                # INSERT new statute
                result = db.execute(
                    text("""
                        INSERT INTO statutes (title, short_title, act_number, year, category, full_text, summary_en)
                        VALUES (:title, :short_title, :act_number, :year, :category, :full_text, :summary_en)
                        RETURNING id
                    """),
                    {
                        "title": title,
                        "short_title": title[:255] if len(title) > 255 else title,
                        "act_number": act_number,
                        "year": year or 2000,
                        "category": category,
                        "full_text": full_text,
                        "summary_en": summary,
                    },
                )
                statute_id = result.fetchone()[0]
                existing[title_lower] = statute_id
                print(f"  INSERTED new statute ID={statute_id}")
                total_statutes_new += 1

            # Delete old sections for this statute and insert new ones
            if sections:
                db.execute(text("DELETE FROM sections WHERE statute_id = :sid"), {"sid": statute_id})
                for sec in sections:
                    db.execute(
                        text("""
                            INSERT INTO sections (statute_id, section_number, title, content)
                            VALUES (:statute_id, :section_number, :title, :content)
                        """),
                        {
                            "statute_id": statute_id,
                            "section_number": sec["section_number"],
                            "title": sec["title"],
                            "content": sec["content"],
                        },
                    )
                total_sections_created += len(sections)
                print(f"  Inserted {len(sections)} sections")

            # Commit every 10 statutes to avoid losing progress
            if idx % 10 == 0:
                db.commit()
                print(f"  --- Committed batch (progress: {idx}/{len(all_pdfs)}) ---")

        # Final commit
        db.commit()

        # Now generate embeddings for updated statutes
        print(f"\n{'='*60}")
        print(f"Generating embeddings for statutes...")

        # Get all statutes that need embeddings
        rows = db.execute(
            text("SELECT id, title, summary_en, full_text FROM statutes WHERE embedding IS NULL OR full_text IS NOT NULL")
        ).fetchall()

        batch_size = 50
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            texts = []
            ids = []
            for row in batch:
                # Use title + summary for embedding (full_text too large for embedding)
                embed_text = f"{row[1]}. {row[2] or ''}"
                texts.append(embed_text[:1000])
                ids.append(row[0])

            embeddings = generate_embeddings_batch(texts)
            for j, emb in enumerate(embeddings):
                db.execute(
                    text("UPDATE statutes SET embedding = :emb WHERE id = :id"),
                    {"emb": json.dumps(emb), "id": ids[j]},
                )

            db.commit()
            print(f"  Embeddings batch {i // batch_size + 1}/{(len(rows) + batch_size - 1) // batch_size}")

        # Generate embeddings for sections
        print(f"Generating embeddings for sections...")
        sec_rows = db.execute(
            text("SELECT s.id, s.section_number, s.title, s.content, st.title as statute_title FROM sections s JOIN statutes st ON s.statute_id = st.id")
        ).fetchall()

        for i in range(0, len(sec_rows), batch_size):
            batch = sec_rows[i:i + batch_size]
            texts = []
            ids = []
            for row in batch:
                embed_text = f"Section {row[1]} {row[2] or ''} of {row[4]}. {(row[3] or '')[:500]}"
                texts.append(embed_text[:1000])
                ids.append(row[0])

            embeddings = generate_embeddings_batch(texts)
            for j, emb in enumerate(embeddings):
                db.execute(
                    text("UPDATE sections SET embedding = :emb WHERE id = :id"),
                    {"emb": json.dumps(emb), "id": ids[j]},
                )

            db.commit()
            print(f"  Sections embeddings batch {i // batch_size + 1}/{(len(sec_rows) + batch_size - 1) // batch_size}")

        # Final stats
        final_statutes = db.execute(text("SELECT COUNT(*) FROM statutes")).scalar()
        final_sections = db.execute(text("SELECT COUNT(*) FROM sections")).scalar()

        print(f"\n{'='*60}")
        print(f"DONE!")
        print(f"  Statutes updated: {total_statutes_updated}")
        print(f"  Statutes new: {total_statutes_new}")
        print(f"  Sections created: {total_sections_created}")
        print(f"  Total statutes in DB: {final_statutes}")
        print(f"  Total sections in DB: {final_sections}")
        if errors:
            print(f"\n  Errors ({len(errors)}):")
            for e in errors:
                print(f"    - {e}")


if __name__ == "__main__":
    main()
