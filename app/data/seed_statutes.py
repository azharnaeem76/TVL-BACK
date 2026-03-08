"""
Async seeder for statutes - loads real Pakistani statutes from JSON.
Called from FastAPI lifespan in main.py.
"""

import json
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def seed_statutes(db: AsyncSession):
    """Seed statutes from real_statutes.json, replacing any dummy data."""
    json_path = os.path.join(os.path.dirname(__file__), "real_statutes.json")
    if not os.path.exists(json_path):
        print("real_statutes.json not found, skipping statute seed.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    statutes = data.get("statutes", [])
    if not statutes:
        print("No statutes in real_statutes.json, skipping.")
        return

    # Check current count
    result = await db.execute(text("SELECT COUNT(*) FROM statutes"))
    count = result.scalar()

    # Only re-seed if we have more data than what's in DB (replace dummy with real)
    if count >= len(statutes):
        print(f"statutes table has {count} records (>= {len(statutes)} in JSON), skipping seed.")
        return

    # Delete existing dummy statutes (and their sections via CASCADE or manual delete)
    if count > 0:
        print(f"Removing {count} existing dummy statutes...")
        await db.execute(text("DELETE FROM sections"))
        await db.execute(text("DELETE FROM statutes"))

    print(f"Seeding {len(statutes)} real statutes...")
    inserted = 0

    for s in statutes:
        try:
            category = s.get("category", "CIVIL").upper()
            await db.execute(
                text("""
                    INSERT INTO statutes (title, short_title, act_number, year, category,
                        summary_en, summary_ur, full_text)
                    VALUES (:title, :short_title, :act_number, :year, :category,
                        :summary_en, :summary_ur, :full_text)
                """),
                {
                    "title": s.get("title", ""),
                    "short_title": s.get("short_title"),
                    "act_number": s.get("act_number"),
                    "year": s.get("year"),
                    "category": category,
                    "summary_en": s.get("summary_en", s.get("summary", "")),
                    "summary_ur": s.get("summary_ur", ""),
                    "full_text": s.get("full_text", ""),
                }
            )
            inserted += 1
        except Exception as e:
            print(f"Error inserting statute '{s.get('title', 'unknown')}': {e}")

    print(f"Successfully seeded {inserted} statutes.")
