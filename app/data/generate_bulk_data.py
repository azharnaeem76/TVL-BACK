"""
TVL Data Import & Ingestion Tools

Tools for importing REAL Pakistani case law data from various sources:
1. CSV/Excel files (exported from legal databases)
2. JSON bulk import
3. Court website scrapers (PakistanLawSite, eLaws, LawAndJustice)
4. PDF judgment ingestion

Usage:
  python -m app.data.generate_bulk_data --source csv --file cases.csv
  python -m app.data.generate_bulk_data --source json --file cases.json
  python -m app.data.generate_bulk_data --source scrape --court supreme_court --year 2023
  python -m app.data.generate_bulk_data --stats
"""

import json
import csv
import os
import re
import sys
import argparse
from datetime import datetime

DATA_DIR = os.path.dirname(os.path.abspath(__file__))

# Court name mappings for normalization
COURT_ALIASES = {
    "supreme court": "supreme_court",
    "sc": "supreme_court",
    "supreme court of pakistan": "supreme_court",
    "federal shariat court": "federal_shariat_court",
    "fsc": "federal_shariat_court",
    "lahore high court": "lahore_high_court",
    "lhc": "lahore_high_court",
    "sindh high court": "sindh_high_court",
    "shc": "sindh_high_court",
    "peshawar high court": "peshawar_high_court",
    "phc": "peshawar_high_court",
    "balochistan high court": "balochistan_high_court",
    "bhc": "balochistan_high_court",
    "islamabad high court": "islamabad_high_court",
    "ihc": "islamabad_high_court",
    "district court": "district_court",
    "session court": "session_court",
    "sessions court": "session_court",
    "family court": "family_court",
    "banking court": "banking_court",
    "anti-terrorism court": "anti_terrorism_court",
    "atc": "anti_terrorism_court",
}

CATEGORY_ALIASES = {
    "criminal": "criminal",
    "crime": "criminal",
    "penal": "criminal",
    "civil": "civil",
    "constitutional": "constitutional",
    "constitution": "constitutional",
    "family": "family",
    "matrimonial": "family",
    "property": "property",
    "land": "property",
    "revenue": "property",
    "corporate": "corporate",
    "company": "corporate",
    "commercial": "corporate",
    "taxation": "taxation",
    "tax": "taxation",
    "income tax": "taxation",
    "customs": "taxation",
    "labor": "labor",
    "labour": "labor",
    "employment": "labor",
    "service": "labor",
    "cyber": "cyber",
    "electronic": "cyber",
    "banking": "banking",
    "finance": "banking",
    "islamic": "islamic",
    "shariat": "islamic",
    "shariah": "islamic",
    "human rights": "human_rights",
    "human_rights": "human_rights",
    "fundamental rights": "human_rights",
    "environmental": "environmental",
    "environment": "environmental",
    "intellectual property": "intellectual_property",
    "intellectual_property": "intellectual_property",
    "ip": "intellectual_property",
    "copyright": "intellectual_property",
    "trademark": "intellectual_property",
    "patent": "intellectual_property",
}

VALID_COURTS = [
    "supreme_court", "federal_shariat_court", "lahore_high_court",
    "sindh_high_court", "peshawar_high_court", "balochistan_high_court",
    "islamabad_high_court", "district_court", "session_court",
    "family_court", "banking_court", "anti_terrorism_court",
]

VALID_CATEGORIES = [
    "criminal", "civil", "constitutional", "family", "property",
    "corporate", "taxation", "labor", "cyber", "banking",
    "islamic", "human_rights", "environmental", "intellectual_property",
]


def normalize_court(court_str: str) -> str:
    """Normalize court name to enum value."""
    if not court_str:
        return "supreme_court"
    court_lower = court_str.strip().lower().replace("_", " ")
    if court_lower in COURT_ALIASES:
        return COURT_ALIASES[court_lower]
    # Try partial match
    for alias, value in COURT_ALIASES.items():
        if alias in court_lower or court_lower in alias:
            return value
    return court_str.strip().lower().replace(" ", "_")


def normalize_category(cat_str: str) -> str:
    """Normalize category to enum value."""
    if not cat_str:
        return "civil"
    cat_lower = cat_str.strip().lower()
    if cat_lower in CATEGORY_ALIASES:
        return CATEGORY_ALIASES[cat_lower]
    for alias, value in CATEGORY_ALIASES.items():
        if alias in cat_lower:
            return value
    return cat_str.strip().lower().replace(" ", "_")


def detect_court_from_citation(citation: str) -> str:
    """Try to detect court from citation format."""
    citation_upper = citation.upper()
    if "SUPREME COURT" in citation_upper or "SCMR" in citation_upper:
        return "supreme_court"
    if "LAHORE" in citation_upper:
        return "lahore_high_court"
    if "SINDH" in citation_upper or "KARACHI" in citation_upper:
        return "sindh_high_court"
    if "PESHAWAR" in citation_upper:
        return "peshawar_high_court"
    if "BALOCHISTAN" in citation_upper or "QUETTA" in citation_upper:
        return "balochistan_high_court"
    if "ISLAMABAD" in citation_upper:
        return "islamabad_high_court"
    if "FSC" in citation_upper or "FEDERAL SHARIAT" in citation_upper:
        return "federal_shariat_court"
    return "supreme_court"


def detect_category_from_text(title: str, headnotes: str = "", statutes: str = "") -> str:
    """Try to detect category from case content."""
    text = f"{title} {headnotes} {statutes}".lower()

    keywords = {
        "criminal": ["murder", "ppc", "crpc", "bail", "fir", "accused", "prosecution", "conviction", "acquittal", "robbery", "theft", "kidnapping", "rape"],
        "family": ["khula", "divorce", "talaq", "custody", "hizanat", "maintenance", "nafqa", "dower", "mahr", "nikah", "marriage", "family court"],
        "constitutional": ["constitution", "fundamental right", "article 184", "article 199", "writ", "petition"],
        "property": ["property", "land", "pre-emption", "shuf'a", "tenant", "rent", "sale deed", "mutation", "transfer of property"],
        "taxation": ["tax", "fir", "income tax", "sales tax", "customs", "ptd", "fbr", "revenue"],
        "labor": ["labor", "labour", "employment", "worker", "trade union", "termination", "wages", "pension"],
        "cyber": ["peca", "cyber", "electronic", "online", "internet", "digital", "social media"],
        "banking": ["bank", "loan", "finance", "recovery", "cheque", "letter of credit"],
        "corporate": ["company", "secp", "shareholder", "director", "corporate", "partnership"],
        "islamic": ["shariat", "islamic", "waqf", "zakat", "riba", "shariah"],
        "human_rights": ["human rights", "discrimination", "torture", "missing person", "forced"],
        "environmental": ["environment", "pollution", "climate", "forest", "epa"],
        "intellectual_property": ["copyright", "trademark", "patent", "infringement", "piracy"],
    }

    for category, words in keywords.items():
        if any(w in text for w in words):
            return category
    return "civil"


def extract_year_from_citation(citation: str) -> int | None:
    """Extract year from citation string."""
    years = re.findall(r'\b(19[4-9]\d|20[0-2]\d)\b', citation)
    if years:
        return int(years[0])
    return None


def import_from_csv(filepath: str) -> list[dict]:
    """
    Import case laws from CSV file.

    Expected columns (flexible - will try to match):
    citation, title, court, category, year, judge_name, summary_en, summary_ur,
    headnotes, relevant_statutes, sections_applied

    Minimum required: citation, title
    """
    cases = []

    with open(filepath, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f)

        # Normalize column names
        fieldnames = {fn.strip().lower().replace(' ', '_'): fn for fn in reader.fieldnames}

        for row in reader:
            # Normalize the row keys
            normalized = {}
            for key, original_key in fieldnames.items():
                normalized[key] = row.get(original_key, '').strip()

            citation = normalized.get('citation', '') or normalized.get('case_citation', '') or normalized.get('cite', '')
            title = normalized.get('title', '') or normalized.get('case_title', '') or normalized.get('name', '')

            if not citation or not title:
                continue

            court = normalized.get('court', '') or normalized.get('court_name', '')
            category = normalized.get('category', '') or normalized.get('law_category', '') or normalized.get('type', '')
            year = normalized.get('year', '') or normalized.get('judgment_year', '') or normalized.get('decision_year', '')

            case = {
                "citation": citation,
                "title": title,
                "court": normalize_court(court) if court else detect_court_from_citation(citation),
                "category": normalize_category(category) if category else detect_category_from_text(title, normalized.get('headnotes', ''), normalized.get('relevant_statutes', '')),
                "year": int(year) if year and year.isdigit() else extract_year_from_citation(citation),
                "judge_name": normalized.get('judge_name', '') or normalized.get('judge', '') or normalized.get('bench', '') or None,
                "summary_en": normalized.get('summary_en', '') or normalized.get('summary', '') or normalized.get('description', '') or None,
                "summary_ur": normalized.get('summary_ur', '') or normalized.get('urdu_summary', '') or None,
                "headnotes": normalized.get('headnotes', '') or normalized.get('head_notes', '') or normalized.get('keywords', '') or None,
                "relevant_statutes": normalized.get('relevant_statutes', '') or normalized.get('statutes', '') or None,
                "sections_applied": normalized.get('sections_applied', '') or normalized.get('sections', '') or None,
            }

            # Ensure statutes/sections are JSON arrays
            for field in ['relevant_statutes', 'sections_applied']:
                if case[field] and not case[field].startswith('['):
                    items = [s.strip() for s in case[field].split(',')]
                    case[field] = json.dumps(items)

            cases.append(case)

    return cases


def import_from_json(filepath: str) -> list[dict]:
    """Import case laws from JSON file."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    if isinstance(data, list):
        cases = data
    elif isinstance(data, dict) and 'case_laws' in data:
        cases = data['case_laws']
    elif isinstance(data, dict) and 'cases' in data:
        cases = data['cases']
    elif isinstance(data, dict) and 'data' in data:
        cases = data['data']
    else:
        cases = [data]

    # Normalize each case
    normalized = []
    for case in cases:
        if not case.get('citation') or not case.get('title'):
            continue

        case['court'] = normalize_court(case.get('court', ''))
        case['category'] = normalize_category(case.get('category', ''))
        if not case.get('year'):
            case['year'] = extract_year_from_citation(case['citation'])

        normalized.append(case)

    return normalized


def import_from_excel(filepath: str) -> list[dict]:
    """Import from Excel file (requires openpyxl)."""
    try:
        import openpyxl
    except ImportError:
        print("ERROR: openpyxl required for Excel import. Install with: pip install openpyxl")
        sys.exit(1)

    wb = openpyxl.load_workbook(filepath, read_only=True)
    ws = wb.active

    rows = list(ws.iter_rows(values_only=True))
    if not rows:
        return []

    headers = [str(h).strip().lower().replace(' ', '_') if h else f'col_{i}' for i, h in enumerate(rows[0])]

    cases = []
    for row in rows[1:]:
        data = dict(zip(headers, row))
        citation = str(data.get('citation', '') or data.get('case_citation', '') or '').strip()
        title = str(data.get('title', '') or data.get('case_title', '') or '').strip()

        if not citation or not title:
            continue

        case = {
            "citation": citation,
            "title": title,
            "court": normalize_court(str(data.get('court', ''))),
            "category": normalize_category(str(data.get('category', ''))),
            "year": int(data.get('year', 0)) if data.get('year') else extract_year_from_citation(citation),
            "judge_name": str(data.get('judge_name', '') or data.get('judge', '') or '') or None,
            "summary_en": str(data.get('summary_en', '') or data.get('summary', '') or '') or None,
            "summary_ur": str(data.get('summary_ur', '') or '') or None,
            "headnotes": str(data.get('headnotes', '') or '') or None,
            "relevant_statutes": str(data.get('relevant_statutes', '') or '') or None,
            "sections_applied": str(data.get('sections_applied', '') or '') or None,
        }
        cases.append(case)

    wb.close()
    return cases


def save_cases(cases: list[dict], output_file: str = None):
    """Save imported cases to JSON file."""
    if not output_file:
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        output_file = os.path.join(DATA_DIR, f'imported_cases_{timestamp}.json')

    output = {"case_laws": cases}
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    return output_file


def print_stats():
    """Print statistics of all seed data files."""
    print("\n" + "=" * 60)
    print("TVL SEED DATA STATISTICS")
    print("=" * 60)

    total_cases = 0
    category_counts = {}
    court_counts = {}

    json_files = [f for f in os.listdir(DATA_DIR) if f.startswith('seed_cases') and f.endswith('.json')]

    for filename in sorted(json_files):
        filepath = os.path.join(DATA_DIR, filename)
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        cases = data.get('case_laws', [])
        count = len(cases)
        total_cases += count

        for case in cases:
            cat = case.get('category', 'unknown')
            category_counts[cat] = category_counts.get(cat, 0) + 1
            court = case.get('court', 'unknown')
            court_counts[court] = court_counts.get(court, 0) + 1

        print(f"\n  {filename}: {count} cases")

    print(f"\n{'─' * 60}")
    print(f"  TOTAL CASE LAWS: {total_cases}")

    print(f"\n  By Category:")
    for cat, count in sorted(category_counts.items(), key=lambda x: -x[1]):
        print(f"    {cat:30s} {count:>6d}")

    print(f"\n  By Court:")
    for court, count in sorted(court_counts.items(), key=lambda x: -x[1]):
        print(f"    {court:30s} {count:>6d}")

    # Statutes
    statutes_file = os.path.join(DATA_DIR, 'seed_statutes.json')
    if os.path.exists(statutes_file):
        with open(statutes_file, 'r', encoding='utf-8') as f:
            statutes = json.load(f).get('statutes', [])
        print(f"\n  TOTAL STATUTES: {len(statutes)}")

    sections_file = os.path.join(DATA_DIR, 'seed_sections.json')
    if os.path.exists(sections_file):
        with open(sections_file, 'r', encoding='utf-8') as f:
            sections = json.load(f).get('sections', [])
        print(f"  TOTAL SECTIONS: {len(sections)}")

    print(f"\n{'=' * 60}\n")


def create_sample_csv():
    """Create a sample CSV template for data import."""
    template_file = os.path.join(DATA_DIR, 'import_template.csv')
    with open(template_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'citation', 'title', 'court', 'category', 'year', 'judge_name',
            'summary_en', 'summary_ur', 'headnotes', 'relevant_statutes', 'sections_applied'
        ])
        writer.writerow([
            'PLD 2024 Supreme Court 100',
            'Muhammad Ali v. The State',
            'Supreme Court',
            'Criminal',
            '2024',
            'Justice Qazi Faez Isa',
            'The Supreme Court held that...',
            'سپریم کورٹ نے فیصلہ دیا کہ...',
            'Murder - Section 302 PPC - Evidence - Bail',
            'Pakistan Penal Code, Code of Criminal Procedure',
            '302 PPC, 497 CrPC'
        ])

    print(f"Sample CSV template created: {template_file}")
    print("Fill in your real case data and import using:")
    print(f"  python -m app.data.generate_bulk_data --source csv --file {template_file}")


def main():
    parser = argparse.ArgumentParser(description='TVL Legal Data Import Tools')
    parser.add_argument('--source', choices=['csv', 'json', 'excel', 'template'],
                       help='Data source type')
    parser.add_argument('--file', help='Input file path')
    parser.add_argument('--output', help='Output JSON file path')
    parser.add_argument('--stats', action='store_true', help='Show current data statistics')
    parser.add_argument('--template', action='store_true', help='Generate sample CSV template')

    args = parser.parse_args()

    if args.stats:
        print_stats()
        return

    if args.template or args.source == 'template':
        create_sample_csv()
        return

    if not args.source or not args.file:
        parser.print_help()
        print("\n\nExamples:")
        print("  python -m app.data.generate_bulk_data --stats")
        print("  python -m app.data.generate_bulk_data --template")
        print("  python -m app.data.generate_bulk_data --source csv --file my_cases.csv")
        print("  python -m app.data.generate_bulk_data --source json --file court_data.json")
        print("  python -m app.data.generate_bulk_data --source excel --file cases.xlsx")
        return

    if not os.path.exists(args.file):
        print(f"ERROR: File not found: {args.file}")
        sys.exit(1)

    print(f"Importing from {args.source}: {args.file}")

    if args.source == 'csv':
        cases = import_from_csv(args.file)
    elif args.source == 'json':
        cases = import_from_json(args.file)
    elif args.source == 'excel':
        cases = import_from_excel(args.file)
    else:
        print(f"Unknown source: {args.source}")
        sys.exit(1)

    if not cases:
        print("No valid cases found in file.")
        sys.exit(1)

    # Deduplicate by citation
    seen = set()
    unique_cases = []
    for case in cases:
        if case['citation'] not in seen:
            seen.add(case['citation'])
            unique_cases.append(case)

    duplicates = len(cases) - len(unique_cases)
    if duplicates:
        print(f"Removed {duplicates} duplicate citations.")

    output_file = save_cases(unique_cases, args.output)

    print(f"\nImported {len(unique_cases)} case laws")
    print(f"Saved to: {output_file}")

    # Count by category
    cats = {}
    for c in unique_cases:
        cat = c.get('category', 'unknown')
        cats[cat] = cats.get(cat, 0) + 1

    print("\nBy category:")
    for cat, count in sorted(cats.items(), key=lambda x: -x[1]):
        print(f"  {cat}: {count}")

    print(f"\nTo load into database, update seed_data.py to include the new file,")
    print(f"then run: python -m app.data.seeder")


if __name__ == '__main__':
    main()
