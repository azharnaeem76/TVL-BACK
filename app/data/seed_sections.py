"""
Async seeder for statute sections - loads real Pakistani sections from JSON.
Called from FastAPI lifespan in main.py.
"""

import json
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def seed_sections(db: AsyncSession):
    """Seed sections from real_sections.json, linking to statutes by name."""
    json_path = os.path.join(os.path.dirname(__file__), "real_sections.json")
    if not os.path.exists(json_path):
        print("real_sections.json not found, skipping section seed.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    sections = data.get("sections", [])
    if not sections:
        print("No sections in real_sections.json, skipping.")
        return

    # Check current count
    result = await db.execute(text("SELECT COUNT(*) FROM sections"))
    count = result.scalar()

    # Only re-seed if we have more data than what's in DB
    if count >= len(sections):
        print(f"sections table has {count} records (>= {len(sections)} in JSON), skipping seed.")
        return

    # Delete existing dummy sections
    if count > 0:
        print(f"Removing {count} existing dummy sections...")
        await db.execute(text("DELETE FROM sections"))

    # Build statute name -> id map
    rows = await db.execute(text("SELECT id, title FROM statutes"))
    statute_map = {row[1]: row[0] for row in rows.fetchall()}

    print(f"Seeding {len(sections)} real sections...")
    inserted = 0
    skipped = 0

    for s in sections:
        statute_name = s.get("statute_name", "")
        statute_id = statute_map.get(statute_name)

        if not statute_id:
            # Try partial match
            for title, sid in statute_map.items():
                if statute_name.lower() in title.lower() or title.lower() in statute_name.lower():
                    statute_id = sid
                    break

        if not statute_id:
            skipped += 1
            continue

        try:
            await db.execute(
                text("""
                    INSERT INTO sections (statute_id, section_number, title, content, content_ur)
                    VALUES (:statute_id, :section_number, :title, :content, :content_ur)
                """),
                {
                    "statute_id": statute_id,
                    "section_number": s.get("section_number", ""),
                    "title": s.get("title", ""),
                    "content": s.get("description", ""),
                    "content_ur": s.get("description_ur", ""),
                }
            )
            inserted += 1
        except Exception as e:
            print(f"Error inserting section {s.get('section_number', '?')}: {e}")
            skipped += 1

    print(f"Successfully seeded {inserted} sections ({skipped} skipped - no matching statute).")
