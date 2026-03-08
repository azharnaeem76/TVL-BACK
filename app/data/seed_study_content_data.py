"""
Async seeder for study content - loads real quiz questions, study notes, and past papers from JSON.
Called from FastAPI lifespan in main.py.
"""

import json
import os
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def seed_study_content_from_json(db: AsyncSession):
    """Seed study content from real_study_content.json, replacing dummy data."""
    json_path = os.path.join(os.path.dirname(__file__), "real_study_content.json")
    if not os.path.exists(json_path):
        print("real_study_content.json not found, skipping study content seed.")
        return

    with open(json_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    items = data.get("study_content", [])
    if not items:
        print("No study content in real_study_content.json, skipping.")
        return

    # Check current count
    result = await db.execute(text("SELECT COUNT(*) FROM study_content"))
    count = result.scalar()

    # Only re-seed if we have more data than what's in DB
    if count >= len(items):
        print(f"study_content table has {count} records (>= {len(items)} in JSON), skipping seed.")
        return

    # Find admin user ID for created_by
    admin_result = await db.execute(text("SELECT id FROM users WHERE role = 'admin' LIMIT 1"))
    admin_row = admin_result.fetchone()
    admin_id = admin_row[0] if admin_row else 1

    # Delete existing dummy content
    if count > 0:
        print(f"Removing {count} existing dummy study content...")
        await db.execute(text("DELETE FROM study_content"))

    print(f"Seeding {len(items)} real study content items...")
    inserted = 0

    for item in items:
        try:
            question_data = item.get("question_data")
            qd_json = json.dumps(question_data) if question_data else None

            await db.execute(
                text("""
                    INSERT INTO study_content (content_type, title, category, exam_type,
                        difficulty, content, question_data, is_published, created_by)
                    VALUES (:content_type, :title, :category, :exam_type,
                        :difficulty, :content, :question_data, :is_published, :created_by)
                """),
                {
                    "content_type": item.get("content_type", "study_note"),
                    "title": item.get("title", ""),
                    "category": item.get("category", "General"),
                    "exam_type": item.get("exam_type"),
                    "difficulty": item.get("difficulty"),
                    "content": item.get("content"),
                    "question_data": qd_json,
                    "is_published": item.get("is_published", True),
                    "created_by": admin_id,
                }
            )
            inserted += 1
        except Exception as e:
            print(f"Error inserting study content '{item.get('title', 'unknown')}': {e}")

    print(f"Successfully seeded {inserted} study content items.")
