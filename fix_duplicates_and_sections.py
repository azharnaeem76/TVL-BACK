"""
Fix duplicate statutes and section ordering issues.
1. Merge duplicate statutes (keep the one with full_text, move sections, delete empty one)
2. Remove duplicate sections within same statute
3. Fix section_number format for proper sorting
"""

import os
import sys
import re

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.core.config import get_settings

settings = get_settings()


def normalize_title(title: str) -> str:
    """Normalize statute title for comparison."""
    t = title.lower().strip()
    # Remove year suffix variations
    t = re.sub(r',?\s*\d{4}\s*$', '', t)
    # Remove special chars
    t = re.sub(r'[^\w\s]', '', t)
    t = re.sub(r'\s+', ' ', t).strip()
    return t


def main():
    engine = create_engine(settings.SYNC_DATABASE_URL, echo=False)

    with Session(engine) as db:
        # Step 1: Find and merge duplicate statutes
        print("=" * 60)
        print("STEP 1: Finding and merging duplicate statutes...")
        print("=" * 60)

        rows = db.execute(text("""
            SELECT id, title, year, category,
                   LENGTH(COALESCE(full_text, '')) as ft_len,
                   (SELECT COUNT(*) FROM sections WHERE statute_id = statutes.id) as sec_count
            FROM statutes
            ORDER BY id
        """)).fetchall()

        # Group by normalized title
        groups = {}
        for row in rows:
            norm = normalize_title(row[1])
            if norm not in groups:
                groups[norm] = []
            groups[norm].append({
                'id': row[0], 'title': row[1], 'year': row[2],
                'category': row[3], 'ft_len': row[4], 'sec_count': row[5],
            })

        merged = 0
        deleted_ids = set()

        for norm_title, entries in groups.items():
            if len(entries) < 2:
                continue

            # Sort: prefer the one with more full_text, then more sections
            entries.sort(key=lambda x: (x['ft_len'], x['sec_count']), reverse=True)
            keep = entries[0]

            for dup in entries[1:]:
                if dup['id'] in deleted_ids:
                    continue

                print(f"\n  MERGE: Keep ID={keep['id']} '{keep['title']}' ({keep['ft_len']} chars, {keep['sec_count']} sections)")
                print(f"         Delete ID={dup['id']} '{dup['title']}' ({dup['ft_len']} chars, {dup['sec_count']} sections)")

                # Move sections from duplicate to keeper (if keeper has none)
                if dup['sec_count'] > 0 and keep['sec_count'] == 0:
                    db.execute(
                        text("UPDATE sections SET statute_id = :keep_id WHERE statute_id = :dup_id"),
                        {"keep_id": keep['id'], "dup_id": dup['id']},
                    )
                    print(f"         Moved {dup['sec_count']} sections to ID={keep['id']}")
                else:
                    # Delete sections from the duplicate
                    db.execute(text("DELETE FROM sections WHERE statute_id = :id"), {"id": dup['id']})

                # If keeper has no full_text but dup does, copy it
                if keep['ft_len'] == 0 and dup['ft_len'] > 0:
                    db.execute(
                        text("UPDATE statutes SET full_text = (SELECT full_text FROM statutes WHERE id = :dup_id), summary_en = (SELECT summary_en FROM statutes WHERE id = :dup_id) WHERE id = :keep_id"),
                        {"keep_id": keep['id'], "dup_id": dup['id']},
                    )
                    print(f"         Copied full_text from dup to keeper")

                # Delete the duplicate statute
                db.execute(text("DELETE FROM statutes WHERE id = :id"), {"id": dup['id']})
                deleted_ids.add(dup['id'])
                merged += 1

        db.commit()
        print(f"\n  Merged {merged} duplicate statutes.\n")

        # Step 2: Remove duplicate sections within same statute
        print("=" * 60)
        print("STEP 2: Removing duplicate sections...")
        print("=" * 60)

        dup_sections = db.execute(text("""
            SELECT statute_id, section_number, COUNT(*) as cnt
            FROM sections
            GROUP BY statute_id, section_number
            HAVING COUNT(*) > 1
        """)).fetchall()

        total_removed = 0
        for row in dup_sections:
            sid, sec_num, cnt = row[0], row[1], row[2]
            # Keep the one with the longest content
            dups = db.execute(text("""
                SELECT id, LENGTH(COALESCE(content, '')) as clen
                FROM sections
                WHERE statute_id = :sid AND section_number = :sec_num
                ORDER BY LENGTH(COALESCE(content, '')) DESC
            """), {"sid": sid, "sec_num": sec_num}).fetchall()

            keep_id = dups[0][0]
            for dup in dups[1:]:
                db.execute(text("DELETE FROM sections WHERE id = :id"), {"id": dup[0]})
                total_removed += 1

        db.commit()
        print(f"  Removed {total_removed} duplicate sections.\n")

        # Step 3: Pad section numbers for proper sorting (e.g., "1" -> "1", but DB sorts numerically via CAST)
        # Actually, let's just make sure section_number is clean
        print("=" * 60)
        print("STEP 3: Cleaning section numbers...")
        print("=" * 60)

        # Remove sections that are clearly TOC entries or junk
        junk_removed = db.execute(text("""
            DELETE FROM sections
            WHERE LENGTH(content) < 15
            OR content ~ '^\s*\d+\s*$'
        """)).rowcount
        db.commit()
        print(f"  Removed {junk_removed} junk/TOC sections.\n")

        # Final stats
        final_statutes = db.execute(text("SELECT COUNT(*) FROM statutes")).scalar()
        final_sections = db.execute(text("SELECT COUNT(*) FROM sections")).scalar()
        with_text = db.execute(text("SELECT COUNT(*) FROM statutes WHERE full_text IS NOT NULL AND LENGTH(full_text) > 100")).scalar()

        print("=" * 60)
        print(f"DONE!")
        print(f"  Total statutes: {final_statutes}")
        print(f"  Statutes with full text: {with_text}")
        print(f"  Total sections: {final_sections}")
        print("=" * 60)


if __name__ == "__main__":
    main()
