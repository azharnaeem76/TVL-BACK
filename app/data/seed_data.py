"""
Pakistani legal seed data loader.

Loads case laws, statutes, and sections from JSON files.
Total: 120+ case laws, 54 statutes, 90+ sections covering all legal categories.
"""

import json
import os

DATA_DIR = os.path.dirname(os.path.abspath(__file__))


def _load_json(filename: str) -> dict:
    filepath = os.path.join(DATA_DIR, filename)
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def load_statutes() -> list[dict]:
    data = _load_json("seed_statutes.json")
    return data["statutes"]


def load_sections() -> list[dict]:
    data = _load_json("seed_sections.json")
    return data["sections"]


def load_case_laws() -> list[dict]:
    case_files = [
        "seed_cases_criminal.json",
        "seed_cases_civil_family_property.json",
        "seed_cases_corporate_tax_labor.json",
        "seed_cases_remaining.json",
    ]
    all_cases = []
    for filename in case_files:
        data = _load_json(filename)
        all_cases.extend(data["case_laws"])
    return all_cases


# Backwards-compatible exports used by seeder.py
SAMPLE_STATUTES = load_statutes()
SAMPLE_SECTIONS = load_sections()
SAMPLE_CASE_LAWS = load_case_laws()
