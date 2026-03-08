"""
Pakistani legal seed data loader.

Loads case laws, statutes, and sections from JSON files.
Real data: 4900+ case laws, 500+ statutes, 1000+ sections covering all legal categories.
"""

import json
import os

DATA_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_json(filename: str) -> dict:
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def load_statutes() -> list[dict]:
    # Load real statutes if available, fallback to old seed file
    real_path = os.path.join(DATA_DIR, "real_statutes.json")
    if os.path.exists(real_path):
        data = _load_json("real_statutes.json")
        return data["statutes"]
    data = _load_json("seed_statutes.json")
    return data["statutes"]


def load_sections() -> list[dict]:
    # Load real sections if available, fallback to old seed file
    real_path = os.path.join(DATA_DIR, "real_sections.json")
    if os.path.exists(real_path):
        data = _load_json("real_sections.json")
        return data["sections"]
    data = _load_json("seed_sections.json")
    return data["sections"]


def load_case_laws() -> list[dict]:
    # Load real case laws from TVL dump (4900+ real Pakistani case laws)
    tvl_dump = os.path.join(DATA_DIR, "tvl_case_laws.json")
    if os.path.exists(tvl_dump):
        with open(tvl_dump, "r", encoding="utf-8") as f:
            return json.load(f)
    # Fallback to old seed files
    case_files = [
        "seed_cases_criminal.json",
        "seed_cases_civil_family_property.json",
        "seed_cases_corporate_tax_labor.json",
        "seed_cases_remaining.json",
    ]
    all_cases = []
    for filename in case_files:
        filepath = os.path.join(DATA_DIR, filename)
        if os.path.exists(filepath):
            data = _load_json(filename)
            all_cases.extend(data["case_laws"])
    return all_cases


# Backwards-compatible exports used by seeder.py
SAMPLE_STATUTES = load_statutes()
SAMPLE_SECTIONS = load_sections()
SAMPLE_CASE_LAWS = load_case_laws()
