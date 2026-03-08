"""Seed statutes from PakistanLaw parsed PDFs."""
import json
import os
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text

logger = logging.getLogger(__name__)

# __file__ = .../tvl-ai/backend/app/data/seed_pakistan_laws.py
# We need: .../tvl/tvlDump/pakistan_law_statutes.json
_this_dir = os.path.dirname(os.path.abspath(__file__))  # app/data/
_backend_dir = os.path.dirname(os.path.dirname(_this_dir))  # tvl-ai/backend/
_tvl_ai_dir = os.path.dirname(_backend_dir)  # tvl-ai/
_tvl_root = os.path.dirname(_tvl_ai_dir)  # tvl/
DATA_FILE = os.path.join(_tvl_root, "tvlDump", "pakistan_law_statutes.json")


async def seed_pakistan_law_statutes(db: AsyncSession):
    """Load parsed Pakistan law statutes into the database (skip duplicates)."""
    if not os.path.exists(DATA_FILE):
        print(f"Pakistan law data file not found at {DATA_FILE}, skipping.")
        return

    with open(DATA_FILE, "r", encoding="utf-8") as f:
        statutes = json.load(f)

    if not statutes:
        return

    # Get existing statute titles to skip duplicates
    result = await db.execute(text("SELECT title FROM statutes"))
    existing = {row[0].lower().strip() for row in result.fetchall()}
    logger.info(f"Found {len(existing)} existing statutes in DB.")

    inserted = 0
    skipped = 0
    for s in statutes:
        title = s.get("title", "").strip()
        if not title or title.lower() in existing:
            skipped += 1
            continue

        try:
            await db.execute(
                text("""
                    INSERT INTO statutes (title, category, year, act_number, summary_en, summary_ur, full_text, created_at)
                    VALUES (:title, :category, :year, :act_number, :summary_en, :summary_ur, :full_text, NOW())
                """),
                {
                    "title": title,
                    "category": s.get("category", "civil").upper(),
                    "year": s.get("year", 2000),
                    "act_number": s.get("act_number", ""),
                    "summary_en": s.get("summary_en", ""),
                    "summary_ur": s.get("summary_ur", ""),
                    "full_text": s.get("full_text", "")[:10000],
                },
            )
            existing.add(title.lower())
            inserted += 1
        except Exception as e:
            logger.warning(f"Failed to insert statute '{title}': {e}")
            continue

    if inserted > 0:
        await db.commit()
    print(f"Pakistan law statutes: {inserted} inserted, {skipped} skipped (duplicates).")
