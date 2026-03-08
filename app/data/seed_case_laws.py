"""
Async seeder for case laws - loads 4900+ real Pakistani case laws from JSON.
Called from FastAPI lifespan in main.py.
"""

import json
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def seed_case_laws(db: AsyncSession):
    """Seed case laws from JSON file if table is empty."""
    result = await db.execute(text("SELECT COUNT(*) FROM case_laws"))
    count = result.scalar()
    if count > 0:
        print(f"case_laws table already has {count} records, skipping seed.")
        return

    json_path = os.path.join(os.path.dirname(__file__), "tvl_case_laws.json")
    if not os.path.exists(json_path):
        print("tvl_case_laws.json not found, skipping case law seed.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        case_laws = json.load(f)

    print(f"Seeding {len(case_laws)} case laws...")
    inserted = 0
    batch_size = 100

    for cl in case_laws:
        try:
            await db.execute(
                text("""
                    INSERT INTO case_laws (citation, title, court, category, year, judge_name,
                        summary_en, summary_ur, full_text, headnotes,
                        relevant_statutes, sections_applied)
                    VALUES (:citation, :title, :court, :category, :year, :judge_name,
                        :summary_en, :summary_ur, :full_text, :headnotes,
                        :relevant_statutes, :sections_applied)
                    ON CONFLICT (citation) DO NOTHING
                """),
                cl
            )
            inserted += 1
            if inserted % batch_size == 0:
                print(f"  ... {inserted}/{len(case_laws)} case laws seeded")
        except Exception as e:
            print(f"Error inserting {cl.get('citation', 'unknown')}: {e}")

    print(f"Successfully seeded {inserted} case laws.")
