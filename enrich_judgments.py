"""
Post-processing script to enrich LHC judgment records with deeper legal extraction.

Extracts from full_text already stored in case_laws table:
- Ordinances referenced
- Chapter references
- Relief/order granted by the court
- Court observations and remarks
- Disposition (who won and why)
- Legal principles / ratio decidendi
- Additional acts/laws not caught by initial scrape

Stores enriched data in headnotes and summary_en fields.

Usage: python enrich_judgments.py [--limit 100] [--force]
"""

import os
import re
import sys
import json
import argparse
import logging
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.services.embedding_service import generate_embeddings_batch

settings = get_settings()
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)


# ============================================================================
# ENHANCED EXTRACTION FUNCTIONS
# ============================================================================

# --- Ordinance extraction ---
ORDINANCE_PATTERN = re.compile(
    r'(?:'
    r'(?:the\s+)?(\w[\w\s\-,()]+?)\s+Ordinance(?:,?\s*(\d{4}))?'
    r')',
    re.IGNORECASE
)

def extract_ordinances(text: str) -> list:
    """Extract all ordinance references from judgment text."""
    ordinances = set()
    for m in ORDINANCE_PATTERN.finditer(text):
        name = m.group(1).strip()
        year = m.group(2) or ""
        # Clean up — remove leading articles and very short names
        name = re.sub(r'^(?:the|said|above|ibid|this|that|any|such)\s+', '', name, flags=re.IGNORECASE).strip()
        if len(name) < 3 or len(name) > 80:
            continue
        # Skip generic references like "the Ordinance"
        if name.lower() in ('', 'said', 'above', 'ibid', 'this', 'that', 'same', 'aforementioned'):
            continue
        entry = f"{name} Ordinance"
        if year:
            entry += f", {year}"
        ordinances.add(entry)
    return sorted(ordinances)


# --- Chapter extraction ---
CHAPTER_PATTERN = re.compile(
    r'Chapter\s+([IVXLCDM]+|\d+[A-Z]?)'
    r'(?:\s*(?:of|,)\s*(?:the\s+)?([\w\s]+?)(?=\s*(?:deals?|relates?|provides?|reads?|states?|,|\.|;|\n)))?',
    re.IGNORECASE
)

def extract_chapters(text: str) -> list:
    """Extract chapter references from judgment text."""
    chapters = set()
    for m in CHAPTER_PATTERN.finditer(text):
        ch_num = m.group(1)
        statute = (m.group(2) or "").strip()[:60]
        if statute:
            chapters.add(f"Chapter {ch_num} of {statute}")
        else:
            chapters.add(f"Chapter {ch_num}")
    return sorted(chapters)


# --- Relief/Order extraction ---
def extract_relief(text: str) -> str:
    """Extract the relief/order granted by the court."""
    if not text or len(text) < 200:
        return ""

    # Normalize newlines for matching
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text)

    relief_parts = []

    # Pattern 1: Explicit relief/order paragraphs
    relief_patterns = [
        # "In view of above/foregoing... appeal/petition is hereby allowed/dismissed"
        r'(?:In view of|For the (?:fore)?going reasons?|Consequently|Resultantly|'
        r'In the result|For what has been discussed|In these circumstances|'
        r'Upshot of the above|The upshot|As a consequence|In light of)'
        r'[,\s]+(.{50,1500}?)(?:\n\n|\Z)',

        # "This appeal/petition/revision is hereby allowed/dismissed"
        r'(?:This|The\s+instant|The\s+present|The\s+above)\s+'
        r'(?:appeal|petition|writ petition|revision|application|suit|complaint|reference|case)'
        r'\s+(?:is|stands?)\s+(?:hereby\s+)?'
        r'((?:allowed|dismissed|disposed|accepted|rejected|partly allowed|converted|'
        r'decreed|set aside|quashed|maintained|upheld|vacated).{0,500}?)(?:\n\n|\Z)',

        # "Ordered/Directed that..."
        r'(?:It is (?:hereby )?ordered|It is (?:hereby )?directed|The court (?:hereby )?orders?|'
        r'We (?:hereby )?order|We (?:hereby )?direct)\s+(?:that\s+)?(.{50,1000}?)(?:\n\n|\Z)',
    ]

    for pattern in relief_patterns:
        matches = list(re.finditer(pattern, text, re.IGNORECASE | re.DOTALL))
        if matches:
            # Take the last match (usually the final order)
            last = matches[-1]
            snippet = last.group(0).strip()
            snippet = re.sub(r'\s+', ' ', snippet)[:800]
            relief_parts.append(snippet)
            break

    # Pattern 2: Bail granted/refused
    bail_patterns = [
        r'(?:bail|pre-arrest bail|post-arrest bail|protective bail|interim bail|ad-interim bail)'
        r'\s+(?:is|stands?)\s+(?:hereby\s+)?'
        r'((?:granted|allowed|confirmed|refused|dismissed|rejected|recalled|cancelled).{0,300}?)(?:\.|$)',
    ]
    for pattern in bail_patterns:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            snippet = m.group(0).strip()
            snippet = re.sub(r'\s+', ' ', snippet)[:300]
            if snippet not in ' '.join(relief_parts):
                relief_parts.append(snippet)
            break

    # Pattern 3: Sentence/conviction
    sentence_patterns = [
        r'(?:sentenced?|convicted?|acquitted?)\s+(?:to|of|from)\s+(.{20,400}?)(?:\.|$)',
        r'(?:death sentence|life imprisonment|rigorous imprisonment|simple imprisonment)'
        r'(?:\s+(?:for|of)\s+(.{10,200}?))?(?:\.|$)',
    ]
    for pattern in sentence_patterns:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            snippet = m.group(0).strip()
            snippet = re.sub(r'\s+', ' ', snippet)[:300]
            if snippet not in ' '.join(relief_parts):
                relief_parts.append(snippet)
            break

    return "\n".join(relief_parts[:3]) if relief_parts else ""


# --- Court observations/remarks ---
def extract_observations(text: str) -> list:
    """Extract court observations, remarks, and judicial reasoning."""
    if not text or len(text) < 200:
        return []

    # Normalize special chars and newlines for better matching
    text = text.replace('\u0092', "'").replace('\u0093', '"').replace('\u0094', '"')
    text = text.replace('�', "'").replace('�', '"').replace('�', '"')
    # Collapse newlines (judgments have line breaks mid-sentence from PDF extraction)
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text)

    observations = []

    obs_patterns = [
        # "It is observed/noted/opined that..."
        r'(?:It is|We|This Court|The Court)\s+(?:observed?|noted?|opined?|remarked?|found?)\s+that\s+(.{50,600}?)(?:\.\s|\n)',
        # "The learned counsel... submitted that..." (key arguments considered)
        r'(?:The learned (?:counsel|advocate|APG|DAG|AAG))\s+(?:for the (?:petitioner|appellant|respondent|complainant|accused|State|prosecution))\s+(?:submitted|argued|contended|stated)\s+that\s+(.{50,400}?)(?:\.\s|\n)',
        # Observations starting with "In our considered view/opinion"
        r'(?:In (?:our|my) (?:considered )?(?:view|opinion|judgment))[,\s]+(.{50,600}?)(?:\.\s|\n)',
        # "The moot point/question for determination is..."
        r'(?:The (?:moot|pivotal|key|main|important|crucial) (?:point|question|issue)(?:\s+for (?:determination|consideration|adjudication))?\s+is\s+)(.{50,400}?)(?:\.\s|\n)',
        # "it may be stated/noted that..." (common in LHC judgments)
        r'(?:it may be (?:stated|noted|observed|mentioned))\s+that\s+(.{50,600}?)(?:\.\s|\n)',
        # "the Supreme Court/High Court held that..."
        r'(?:the (?:august |Hon.?ble |learned )?(?:Supreme Court|High Court|apex Court|this Court))\s+.*?(?:held|observed|ruled|decided)\s+that[:\s-]+(.{50,600}?)(?:\.\s|\n)',
        # "has not been able to point out any..." (negative findings)
        r'(?:has not been able to (?:point out|show|demonstrate|establish))\s+(.{30,400}?)(?:\.\s|\n)',
        # Numbered paragraph observations (common pattern: "8. In this case...")
        r'\d+\.\s+(In this case.{50,500}?)(?:\.\s|\n)',
        # "The pivotal/moot question before this Court..."
        r'(The (?:pivotal|moot|key|main|crucial|important) question (?:before|for).{50,500}?)(?:\.\s)',
        # "Admittedly..." (accepted facts by court)
        r'(Admittedly\s+.{50,400}?)(?:\.\s|\n)',
        # "The above provision of law..."
        r'(The above (?:provision|section|article|law|principle).{50,400}?)(?:\.\s|\n)',
        # "The concurrent findings..."
        r'(The concurrent findings.{30,400}?)(?:\.\s|\n)',
    ]

    for pattern in obs_patterns:
        for m in re.finditer(pattern, text, re.IGNORECASE):
            snippet = m.group(0).strip() if m.lastindex == 0 else m.group(0).strip()
            snippet = re.sub(r'\s+', ' ', snippet)[:500]
            if len(snippet) > 40 and snippet not in observations:
                observations.append(snippet)
            if len(observations) >= 5:
                break
        if len(observations) >= 5:
            break

    return observations[:5]


# --- Disposition (who won and why) ---
def extract_disposition(text: str) -> str:
    """Extract who won and the key reason."""
    if not text or len(text) < 200:
        return ""

    # Normalize and check the last 3000 chars for disposition
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    tail = text[-3000:]

    disposition_parts = []

    # Who won?
    win_patterns = [
        (r'(?:civil revision|appeal|petition|revision|application|writ petition|suit|criminal appeal|criminal revision)'
         r'\s+(?:is|stands|being\s+\w+\s+(?:of\s+)?(?:any\s+)?(?:merit\s+)?is)\s+(?:hereby\s+)?'
         r'(allowed|dismissed|disposed\s+of|accepted|rejected|decreed|partly\s+allowed|converted'
         r'|dismissed\s+in\s+limine|dismissed\s+being)', 'result'),
        (r'(?:bail|pre-arrest bail|post-arrest bail)\s+(?:is|stands)\s+(?:hereby\s+)?'
         r'(granted|confirmed|refused|dismissed|rejected|cancelled|recalled)', 'bail'),
        (r'(?:conviction|sentence)\s+(?:is|stands)\s+(?:hereby\s+)?'
         r'(maintained|upheld|set\s+aside|modified|commuted|affirmed)', 'conviction'),
        (r'(?:accused|appellant|petitioner|respondent)\s+(?:is|stands)\s+(?:hereby\s+)?'
         r'(acquitted|convicted|discharged|released)', 'accused'),
        # "being devoid of any merit is dismissed" pattern
        (r'being\s+devoid\s+of\s+(?:any\s+)?merit\s+is\s+(dismissed\w*)', 'result'),
    ]

    for pattern, label in win_patterns:
        m = re.search(pattern, tail, re.IGNORECASE)
        if m:
            outcome = m.group(1).strip()
            # Determine who benefited
            if label == 'result':
                if 'allowed' in outcome.lower() or 'accepted' in outcome.lower() or 'decreed' in outcome.lower():
                    disposition_parts.append(f"Outcome: {outcome.title()} (in favor of petitioner/appellant)")
                elif 'dismissed' in outcome.lower() or 'rejected' in outcome.lower():
                    disposition_parts.append(f"Outcome: {outcome.title()} (in favor of respondent)")
                else:
                    disposition_parts.append(f"Outcome: {outcome.title()}")
            elif label == 'bail':
                if 'granted' in outcome.lower() or 'confirmed' in outcome.lower():
                    disposition_parts.append(f"Bail: {outcome.title()} (in favor of accused)")
                else:
                    disposition_parts.append(f"Bail: {outcome.title()} (against accused)")
            elif label == 'conviction':
                disposition_parts.append(f"Conviction: {outcome.title()}")
            elif label == 'accused':
                disposition_parts.append(f"Accused: {outcome.title()}")
            break

    # Why? — Look for the key reason near the disposition
    reason_patterns = [
        r'(?:The (?:main|key|primary|sole) reason|The reason (?:being|is)|'
        r'inasmuch as|since the prosecution|since no|as the prosecution|'
        r'as there (?:is|was) no|in absence of|for want of)\s+(.{30,400}?)(?:\.\s|\n)',
    ]
    for pattern in reason_patterns:
        m = re.search(pattern, tail, re.IGNORECASE)
        if m:
            reason = re.sub(r'\s+', ' ', m.group(0).strip())[:400]
            disposition_parts.append(f"Reason: {reason}")
            break

    return "\n".join(disposition_parts) if disposition_parts else ""


# --- Legal principles / What can be learned ---
def extract_legal_principles(text: str) -> list:
    """Extract key legal principles and ratio decidendi from the judgment."""
    if not text or len(text) < 300:
        return []

    # Normalize special chars and newlines
    text = text.replace('\u0092', "'").replace('\u0093', '"').replace('\u0094', '"')
    text = text.replace('�', "'").replace('�', '"').replace('�', '"')
    text = re.sub(r'\n+', ' ', text)
    text = re.sub(r'\s+', ' ', text)

    principles = []

    principle_patterns = [
        # "The law is well settled that..."
        r'(?:The law is (?:well )?settled|It is (?:a )?well.?settled (?:law|principle|proposition)|'
        r'It is (?:a )?settled (?:law|principle|proposition))\s+that\s+(.{50,500}?)(?:\.\s|\n)',
        # "The principle laid down in..."
        r'(?:The (?:principle|ratio|proposition|dictum) (?:laid down|enunciated|propounded|established) in)\s+(.{30,500}?)(?:\.\s|\n)',
        # "It is the duty of..."
        r'(?:It is the (?:duty|obligation|responsibility) of\s+(?:the )?(?:prosecution|complainant|accused|plaintiff|defendant|court|judge))\s+(.{30,400}?)(?:\.\s|\n)',
        # "The onus/burden of proof..."
        r'(?:The (?:onus|burden) of (?:proof|proving))\s+(.{30,400}?)(?:\.\s|\n)',
        # "Held" paragraphs (ratio decidendi)
        r'(?:^|\n)\s*(?:Held|HELD)[:\s—-]+(.{50,500}?)(?:\.\s|\n)',
        # Supreme Court held that... (quoted principles)
        r'(?:Supreme Court|High Court|apex Court).*?held\s+that[:\s—-]+["\']?(.{50,500}?)["\']?(?:\.\s|\n)',
        # "This brings us to the conclusion that..."
        r'(?:This brings us to the conclusion|We are of the (?:considered )?(?:view|opinion)|It is well established)\s+that\s+(.{50,500}?)(?:\.\s|\n)',
        # "A true owner can..." / "there is no period of limitation..." (definitive legal statements)
        r'(?:there is no (?:period of )?(?:limitation|bar|embargo)|A true owner can|the concurrent findings)\s+(.{30,400}?)(?:\.\s|\n)',
        # "the question of limitation finds no place..."
        r'(?:The question of (?:limitation|jurisdiction|maintainability))\s+(.{30,400}?)(?:\.\s|\n)',
    ]

    for pattern in principle_patterns:
        for m in re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE):
            snippet = m.group(0).strip()
            snippet = re.sub(r'\s+', ' ', snippet)[:500]
            if len(snippet) > 40 and snippet not in principles:
                principles.append(snippet)
            if len(principles) >= 5:
                break
        if len(principles) >= 5:
            break

    return principles[:5]


# --- Additional Acts/Laws extraction ---
ACT_PATTERN = re.compile(
    r'(?:the\s+)?((?:[A-Z][\w]+\s+){1,5})Act(?:,?\s*(\d{4}))?',
    re.IGNORECASE
)

def extract_acts(text: str) -> list:
    """Extract all Act references from judgment text."""
    acts = set()
    for m in ACT_PATTERN.finditer(text):
        name = m.group(1).strip()
        year = m.group(2) or ""
        # Clean up — remove leading articles
        name = re.sub(r'^(?:the|said|above|ibid|this|that|any|such|an|a)\s+', '', name, flags=re.IGNORECASE).strip()
        # Must start with capital letter and be a proper name
        if not name or not name[0].isupper():
            continue
        if len(name) < 4 or len(name) > 80:
            continue
        # Skip generic/garbage words
        skip_words = {'Section', 'Article', 'Order', 'Rule', 'Chapter', 'Para', 'Paragraph',
                      'Court', 'Judge', 'Learned', 'Hon', 'This', 'That', 'Same', 'Above',
                      'Said', 'Present', 'Instant', 'Impugned', 'Filing', 'Respective'}
        if name.split()[0] in skip_words:
            continue
        entry = f"{name}Act"
        if year:
            entry += f", {year}"
        acts.add(entry)
    return sorted(acts)


# --- Section pattern (enhanced) ---
SECTION_PATTERN = re.compile(
    r'(?:Section|S\.|Sec\.)\s*(\d{1,3}[A-Z]?(?:-[A-Z])?)'
    r'(?:\s*(?:of|,)\s*(?:the\s+)?'
    r'((?:Pakistan\s+)?Penal\s+Code|PPC|Cr\.?\s*P\.?\s*C\.?|Code\s+of\s+Criminal\s+Procedure|'
    r'CPC|Code\s+of\s+Civil\s+Procedure|Constitution|MFLO|'
    r'Anti[- ]?Terrorism\s+Act(?:,?\s*\d{4})?|PECA(?:,?\s*\d{4})?|'
    r'NAB\s+Ordinance(?:,?\s*\d{4})?|Qanun[- ]?e[- ]?Shahadat(?:\s+Order)?(?:,?\s*\d{4})?|'
    r'Control\s+of\s+Narcotic\s+Substances\s+Act(?:,?\s*\d{4})?|CNSA|'
    r'Transfer\s+of\s+Property\s+Act(?:,?\s*\d{4})?|Specific\s+Relief\s+Act(?:,?\s*\d{4})?|'
    r'Contract\s+Act(?:,?\s*\d{4})?|Limitation\s+Act(?:,?\s*\d{4})?|Registration\s+Act(?:,?\s*\d{4})?|'
    r'West\s+Pakistan\s+Family\s+Courts?\s+Act(?:,?\s*\d{4})?|'
    r'Muslim\s+Family\s+Laws?\s+Ordinance(?:,?\s*\d{4})?|'
    r'Punjab\s+(?:Rented\s+Premises\s+Act|Pre[- ]?emption\s+Act)(?:,?\s*\d{4})?|'
    r'(?:[\w]+\s+){1,4}(?:Act|Ordinance|Order|Rules|Code|Regulations?)(?:,?\s*\d{4})?))?',
    re.IGNORECASE
)

ARTICLE_PATTERN = re.compile(
    r'(?:Article|Art\.)\s*(\d+[\-A-Z]*(?:\(\d+\)(?:\([a-z]\))?)?)'
    r'(?:\s*(?:of|,)\s*(?:the\s+)?(Constitution[\w\s,]*?)(?=\.|,|\s+and|\s+of|\s+read))?',
    re.IGNORECASE
)

ORDER_RULE_PATTERN = re.compile(
    r'Order\s+([IVXLCDM]+(?:\s*[-,]\s*[IVXLCDM]+)?)\s*,?\s*Rule\s*(\d+[\-A-Z]*)'
    r'(?:\s*(?:of|,)\s*(?:the\s+)?(CPC|Code\s+of\s+Civil\s+Procedure|[\w\s]+))?',
    re.IGNORECASE
)

RULE_PATTERN = re.compile(
    r'Rule\s+(\d+[A-Z]?(?:\(\d+\))?)'
    r'(?:\s*(?:of|,)\s*(?:the\s+)?([\w\s]+?(?:Rules|Regulations)(?:,?\s*\d{4})?))?',
    re.IGNORECASE
)

# Case law citation patterns
CITED_CASE_PATTERN = re.compile(
    r'(?:'
    r'(?:PLD|SCMR|CLC|YLR|PCrLJ|PLJ|PTD|MLD|PLC|NLR|GBLR|KLR|PSC|ALD)\s*\d{4}\s+\w+\s+\d+'
    r'|\d{4}\s+(?:SCMR|CLC|YLR|PCrLJ|PLJ|PTD|MLD|PLC|NLR|PLD|GBLR|KLR|PSC|ALD)\s+\d+'
    r'|\d{4}\s+LHC\s+\d+'
    r')',
    re.IGNORECASE
)


def extract_all_sections(text: str) -> list:
    """Extract ALL sections/articles/orders/rules mentioned in the judgment."""
    sections = set()

    for m in SECTION_PATTERN.finditer(text):
        sec_num = m.group(1)
        statute = (m.group(2) or "").strip()
        statute = re.sub(r'\s+', ' ', statute)[:80]
        if statute:
            sections.add(f"S.{sec_num} {statute}")
        else:
            sections.add(f"S.{sec_num}")

    for m in ARTICLE_PATTERN.finditer(text):
        art_num = m.group(1)
        statute = (m.group(2) or "Constitution").strip()
        statute = re.sub(r'\s+', ' ', statute)[:80]
        sections.add(f"Art.{art_num} {statute}")

    for m in ORDER_RULE_PATTERN.finditer(text):
        order = m.group(1)
        rule = m.group(2)
        statute = (m.group(3) or "CPC").strip()[:40]
        sections.add(f"O.{order} R.{rule} {statute}")

    for m in RULE_PATTERN.finditer(text):
        rule_num = m.group(1)
        rules_name = (m.group(2) or "").strip()[:60]
        if rules_name:
            sections.add(f"Rule {rule_num} {rules_name}")

    # Filter out unreasonable section numbers
    filtered = set()
    for s in sections:
        m = re.match(r'[SA]\w*\.(\d+)', s)
        if m and int(m.group(1)) > 700:
            continue
        filtered.add(s)

    return sorted(filtered)


def extract_cited_cases(text: str) -> list:
    """Extract all case law citations referenced within the judgment."""
    clean_text = re.sub(r'\n', ' ', text)
    cases = set()
    for m in CITED_CASE_PATTERN.finditer(clean_text):
        cite = re.sub(r'\s+', ' ', m.group(0).strip())
        cases.add(cite)
    return sorted(cases)


# ============================================================================
# BUILD ENRICHED DATA
# ============================================================================

def build_enriched_headnotes(
    full_text: str,
    existing_headnotes: str,
    sections: list,
    cited_cases: list,
    ordinances: list,
    chapters: list,
    acts: list,
    relief: str,
    observations: list,
    disposition: str,
    principles: list,
    tag_line: str = "",
    decision_date: str = "",
    other_citations: str = "",
) -> str:
    """Build comprehensive enriched headnotes from all extracted data."""
    parts = []

    # Preserve existing tag line and decision date if present
    if decision_date:
        parts.append(f"Decision Date: {decision_date}")
    if tag_line:
        parts.append(f"Tag Line: {tag_line}")
    if other_citations:
        parts.append(f"Digest Citations: {other_citations}")

    # Disposition (who won)
    if disposition:
        parts.append(f"DISPOSITION:\n{disposition}")

    # Relief granted
    if relief:
        parts.append(f"RELIEF/ORDER:\n{relief}")

    # Legal provisions
    if sections:
        parts.append(f"SECTIONS & ARTICLES: {', '.join(sections[:20])}")

    # Acts & Ordinances
    all_laws = []
    if acts:
        all_laws.extend(acts[:10])
    if ordinances:
        all_laws.extend(ordinances[:5])
    if all_laws:
        parts.append(f"ACTS & ORDINANCES: {', '.join(all_laws)}")

    # Chapters
    if chapters:
        parts.append(f"CHAPTERS: {', '.join(chapters[:5])}")

    # Court observations
    if observations:
        obs_text = "\n".join(f"- {o}" for o in observations[:3])
        parts.append(f"COURT OBSERVATIONS:\n{obs_text}")

    # Legal principles
    if principles:
        prin_text = "\n".join(f"- {p}" for p in principles[:3])
        parts.append(f"LEGAL PRINCIPLES:\n{prin_text}")

    # Cited cases
    if cited_cases:
        parts.append(f"CITED CASES: {', '.join(cited_cases[:15])}")

    result = "\n\n".join(parts)
    return result[:8000]  # Allow generous space


def build_enriched_summary(
    full_text: str,
    title: str,
    relief: str,
    disposition: str,
    observations: list,
    principles: list,
    existing_summary: str = "",
) -> str:
    """Build comprehensive summary including outcome, reasoning, and takeaways."""
    parts = []

    # Opening facts (first meaningful paragraph)
    if full_text and len(full_text) > 500:
        opening = full_text[200:800]
        opening = re.sub(r'\s+', ' ', opening).strip()
        if opening:
            parts.append(f"FACTS: {opening[:400]}")

    # Disposition
    if disposition:
        parts.append(f"OUTCOME: {disposition}")

    # Relief
    if relief:
        parts.append(f"ORDER: {relief[:600]}")

    # Key observations
    if observations:
        parts.append(f"KEY OBSERVATIONS: {observations[0][:400]}")

    # Legal principles (what can be learned)
    if principles:
        takeaways = "; ".join(p[:200] for p in principles[:2])
        parts.append(f"LEGAL TAKEAWAYS: {takeaways}")

    return "\n\n".join(parts)[:5000] if parts else existing_summary


# ============================================================================
# MAIN PROCESSING
# ============================================================================

def enrich_records(limit: int = 0, force: bool = False):
    """Re-process full_text in DB to extract enriched legal data."""
    engine = create_engine(settings.SYNC_DATABASE_URL, echo=False)

    with Session(engine) as db:
        # Get records that have full_text
        if force:
            query = """
                SELECT id, citation, title, full_text, headnotes, summary_en
                FROM case_laws
                WHERE full_text IS NOT NULL AND LENGTH(full_text) > 200
                ORDER BY id
            """
        else:
            # Only process records that don't have enriched headnotes yet
            query = """
                SELECT id, citation, title, full_text, headnotes, summary_en
                FROM case_laws
                WHERE full_text IS NOT NULL AND LENGTH(full_text) > 200
                AND (headnotes NOT LIKE '%DISPOSITION:%' OR headnotes IS NULL)
                ORDER BY id
            """

        if limit > 0:
            query += f" LIMIT {limit}"

        rows = db.execute(text(query)).fetchall()
        logger.info(f"Found {len(rows)} records to enrich")

        for idx, row in enumerate(rows, 1):
            rec_id, citation, title, full_text, existing_headnotes, existing_summary = row

            try:
                logger.info(f"[{idx}/{len(rows)}] Enriching {citation}")
            except UnicodeEncodeError:
                logger.info(f"[{idx}/{len(rows)}] Enriching record {rec_id}")

            # Extract all data
            sections = extract_all_sections(full_text)
            cited_cases = extract_cited_cases(full_text)
            ordinances = extract_ordinances(full_text)
            chapters = extract_chapters(full_text)
            acts = extract_acts(full_text)
            relief = extract_relief(full_text)
            observations = extract_observations(full_text)
            disposition = extract_disposition(full_text)
            principles = extract_legal_principles(full_text)

            # Extract preserved fields from existing headnotes
            tag_line = ""
            decision_date = ""
            other_citations = ""
            if existing_headnotes:
                tl_match = re.search(r'Tag Line:\s*(.+?)(?:\n|$)', existing_headnotes)
                if tl_match:
                    tag_line = tl_match.group(1).strip()
                dd_match = re.search(r'Decision Date:\s*(.+?)(?:\n|$)', existing_headnotes)
                if dd_match:
                    decision_date = dd_match.group(1).strip()
                dc_match = re.search(r'Digest Citations:\s*(.+?)(?:\n|$)', existing_headnotes)
                if dc_match:
                    other_citations = dc_match.group(1).strip()

            # Build enriched data
            new_headnotes = build_enriched_headnotes(
                full_text=full_text,
                existing_headnotes=existing_headnotes or "",
                sections=sections,
                cited_cases=cited_cases,
                ordinances=ordinances,
                chapters=chapters,
                acts=acts,
                relief=relief,
                observations=observations,
                disposition=disposition,
                principles=principles,
                tag_line=tag_line,
                decision_date=decision_date,
                other_citations=other_citations,
            )

            new_summary = build_enriched_summary(
                full_text=full_text,
                title=title,
                relief=relief,
                disposition=disposition,
                observations=observations,
                principles=principles,
                existing_summary=existing_summary or "",
            )

            # Also update sections_applied and relevant_statutes with enriched data
            all_statutes = set()
            for act in acts:
                all_statutes.add(act)
            for ordi in ordinances:
                all_statutes.add(ordi)
            # Also add from section mappings
            statute_map = {
                "ppc": "Pakistan Penal Code, 1860",
                "penal code": "Pakistan Penal Code, 1860",
                "cr.p.c": "Code of Criminal Procedure, 1898",
                "crpc": "Code of Criminal Procedure, 1898",
                "cpc": "Code of Civil Procedure, 1908",
                "constitution": "Constitution of Pakistan, 1973",
                "mflo": "Muslim Family Laws Ordinance, 1961",
                "peca": "Prevention of Electronic Crimes Act, 2016",
                "anti-terrorism": "Anti-Terrorism Act, 1997",
                "nab ordinance": "National Accountability Ordinance, 1999",
                "qanun-e-shahadat": "Qanun-e-Shahadat Order, 1984",
                "cnsa": "Control of Narcotic Substances Act, 1997",
                "transfer of property": "Transfer of Property Act, 1882",
                "specific relief": "Specific Relief Act, 1877",
                "contract act": "Contract Act, 1872",
                "limitation act": "Limitation Act, 1908",
                "registration act": "Registration Act, 1908",
                "family courts act": "West Pakistan Family Courts Act, 1964",
            }
            for sec in sections:
                sec_lower = sec.lower()
                for key, statute_name in statute_map.items():
                    if key in sec_lower:
                        all_statutes.add(statute_name)
                        break

            sections_json = json.dumps(sections) if sections else None
            statutes_json = json.dumps(sorted(all_statutes)) if all_statutes else None

            try:
                db.execute(
                    text("""
                        UPDATE case_laws SET
                            headnotes = :headnotes,
                            summary_en = :summary_en,
                            sections_applied = :sections_applied,
                            relevant_statutes = :relevant_statutes
                        WHERE id = :id
                    """),
                    {
                        "id": rec_id,
                        "headnotes": new_headnotes[:8000] if new_headnotes else existing_headnotes,
                        "summary_en": new_summary[:5000] if new_summary else existing_summary,
                        "sections_applied": sections_json,
                        "relevant_statutes": statutes_json,
                    },
                )

                if idx % 50 == 0:
                    db.commit()
                    logger.info(f"  --- Committed batch (progress: {idx}/{len(rows)}) ---")

            except Exception as e:
                logger.error(f"  DB error for {citation}: {e}")
                db.rollback()

        db.commit()
        logger.info(f"DONE! Enriched {len(rows)} records.")

        # Regenerate embeddings for enriched records (the enriched headnotes/summary give better search)
        logger.info("Regenerating embeddings for enriched records...")
        emb_rows = db.execute(
            text("""
                SELECT id, citation, title, summary_en, headnotes, sections_applied
                FROM case_laws
                WHERE full_text IS NOT NULL AND LENGTH(full_text) > 200
                ORDER BY id
            """)
        ).fetchall()

        batch_size = 50
        for i in range(0, len(emb_rows), batch_size):
            batch = emb_rows[i:i + batch_size]
            texts = []
            ids = []
            for row in batch:
                # Include enriched data in embedding for better semantic search
                embed_text = f"{row[1]} {row[2]}. {(row[3] or '')[:600]} {(row[4] or '')[:400]} {row[5] or ''}"
                texts.append(embed_text[:1200])
                ids.append(row[0])

            embeddings = generate_embeddings_batch(texts)
            for j, emb in enumerate(embeddings):
                db.execute(
                    text("UPDATE case_laws SET embedding = :emb WHERE id = :id"),
                    {"emb": json.dumps(emb), "id": ids[j]},
                )
            db.commit()
            logger.info(f"  Embeddings batch {i // batch_size + 1}/{(len(emb_rows) + batch_size - 1) // batch_size}")

        logger.info("All embeddings regenerated.")


def normalize_citation(cite: str) -> str:
    """Normalize a citation to a canonical form for deduplication.
    e.g. 'PLD  2020  SC  1' -> 'PLD 2020 SC 1'
         '2019  scmr  500' -> '2019 SCMR 500'
    """
    cite = re.sub(r'\s+', ' ', cite.strip())
    # Uppercase the journal/report abbreviation
    parts = cite.split()
    normalized = []
    for p in parts:
        if p.upper() in ('PLD', 'SCMR', 'CLC', 'YLR', 'PCRLJ', 'PLJ', 'PTD', 'MLD',
                         'PLC', 'NLR', 'GBLR', 'KLR', 'PSC', 'ALD', 'LHC', 'PCTLR',
                         'CLD', 'SC', 'LAHORE', 'SINDH', 'PESHAWAR', 'BALOCHISTAN',
                         'ISLAMABAD', 'KARACHI', 'QUETTA', 'SUPREME', 'COURT', 'FC',
                         'AJK', 'NOTE'):
            normalized.append(p.upper())
        else:
            normalized.append(p)
    return ' '.join(normalized)


def extract_year_from_citation(cite: str) -> int:
    """Extract year from a citation string."""
    m = re.search(r'(\d{4})', cite)
    return int(m.group(1)) if m else 2025


def guess_court_from_citation(cite: str) -> str:
    """Guess the court from a citation string."""
    cite_upper = cite.upper()
    court_map = {
        'SCMR': 'SUPREME_COURT',
        'SC ': 'SUPREME_COURT',
        'SUPREME': 'SUPREME_COURT',
        'LHC': 'LAHORE_HIGH_COURT',
        'LAHORE': 'LAHORE_HIGH_COURT',
        'SINDH': 'SINDH_HIGH_COURT',
        'KARACHI': 'SINDH_HIGH_COURT',
        'PESHAWAR': 'PESHAWAR_HIGH_COURT',
        'BALOCHISTAN': 'BALOCHISTAN_HIGH_COURT',
        'QUETTA': 'BALOCHISTAN_HIGH_COURT',
        'ISB': 'ISLAMABAD_HIGH_COURT',
        'ISLAMABAD': 'ISLAMABAD_HIGH_COURT',
        'FC ': 'FAMILY_COURT',
        'GBLR': 'GILGIT_BALTISTAN_COURT',
        'AJK': 'AJK_HIGH_COURT',
        'HC AK': 'AJK_HIGH_COURT',
        'SC AJK': 'AJK_SUPREME_COURT',
        'SC AK': 'AJK_SUPREME_COURT',
    }
    # PLD citations include court name: PLD 2020 SC 1, PLD 2020 Lahore 465
    for key, court in court_map.items():
        if key in cite_upper:
            return court
    # Generic journals: CLC, YLR, PCrLJ, MLD, PLC, PLJ, PTD, NLR, ALD, PLD
    # These can be from any court — default based on journal
    if 'PCRLJ' in cite_upper:
        return 'SUPREME_COURT'  # Criminal law journal — could be any court
    if 'PLD' in cite_upper:
        return 'SUPREME_COURT'
    return 'SUPREME_COURT'  # Default — most cited cases are SC


def store_cited_case_laws(db, existing_citations: set):
    """
    Extract all cited case citations from existing case_laws and create stub records
    for those that don't already exist in the database.
    """
    logger.info("=== STORING CITED CASE LAWS AS NEW RECORDS ===")

    # Collect ALL cited case references from:
    # 1. CITED CASES section in enriched headnotes
    # 2. Old-format 'Cited Cases:' in headnotes
    # 3. 'Digest Citations:' (other publication references for same case)
    # 4. Full text of judgments (re-extract)

    all_cited = set()  # (citation, source_citation) tuples for tracking

    rows = db.execute(text("""
        SELECT id, citation, headnotes, full_text
        FROM case_laws
        ORDER BY id
    """)).fetchall()

    logger.info(f"Scanning {len(rows)} records for cited case references...")

    for row in rows:
        rec_id, source_citation, headnotes, full_text = row
        found_cites = set()

        # Extract from headnotes
        if headnotes:
            # Enriched format: CITED CASES: cite1, cite2
            m = re.search(r'CITED CASES:\s*(.+?)(?:\n|$)', headnotes)
            if m:
                for cite in re.split(r',\s*', m.group(1)):
                    cite = cite.strip()
                    if cite:
                        found_cites.add(cite)

            # Old format: Cited Cases: cite1, cite2
            m = re.search(r'(?<!ED )Cited Cases:\s*(.+?)(?:\n|$)', headnotes)
            if m:
                for cite in re.split(r',\s*', m.group(1)):
                    cite = cite.strip()
                    if cite:
                        found_cites.add(cite)

            # Digest Citations (other publication references)
            m = re.search(r'Digest Citations:\s*(.+?)(?:\n|$)', headnotes)
            if m:
                for cite in re.split(r'[,;]\s*', m.group(1)):
                    cite = cite.strip()
                    # Remove trailing court info in brackets like "[Lahore (Rawalpindi Bench)]"
                    cite = re.sub(r'\s*\[.*?\]\s*$', '', cite)
                    if cite:
                        found_cites.add(cite)

        # Also extract from full_text using citation pattern
        if full_text and len(full_text) > 200:
            for fc in extract_cited_cases(full_text):
                found_cites.add(fc)

        for cite in found_cites:
            all_cited.add(normalize_citation(cite))

    logger.info(f"Found {len(all_cited)} unique cited case references across all records")

    # Normalize existing citations for comparison
    existing_normalized = {}
    for ec in existing_citations:
        existing_normalized[normalize_citation(ec)] = ec

    # Filter out ones that already exist
    new_citations = []
    for cite in sorted(all_cited):
        if cite not in existing_normalized:
            # Also check without normalization edge cases
            if cite not in existing_citations:
                new_citations.append(cite)

    logger.info(f"Of those, {len(new_citations)} are NEW (not already in DB)")

    if not new_citations:
        logger.info("No new citations to store.")
        return 0

    # Insert stub records for new citations
    inserted = 0
    skipped = 0
    for idx, cite in enumerate(new_citations, 1):
        year = extract_year_from_citation(cite)
        court = guess_court_from_citation(cite)

        try:
            # Double-check not already inserted (race condition safety)
            exists = db.execute(
                text("SELECT 1 FROM case_laws WHERE citation = :c"),
                {"c": cite}
            ).fetchone()
            if exists:
                skipped += 1
                continue

            db.execute(
                text("""
                    INSERT INTO case_laws (citation, title, court, category, year, created_at)
                    VALUES (:citation, :title, :court, :category, :year, NOW())
                """),
                {
                    "citation": cite,
                    "title": f"Cited Reference — {cite}",
                    "court": court,
                    "category": "CIVIL",  # Default; will be updated if full text is added later
                    "year": year,
                }
            )
            inserted += 1

            if idx % 100 == 0:
                db.commit()
                logger.info(f"  Inserted {inserted} citation records (progress: {idx}/{len(new_citations)})")

        except Exception as e:
            logger.error(f"  Error inserting citation {cite}: {e}")
            db.rollback()

    db.commit()
    logger.info(f"DONE! Inserted {inserted} new citation records, skipped {skipped} duplicates.")
    return inserted


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich LHC judgment records with deeper legal extraction")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of records to process (0=all)")
    parser.add_argument("--force", action="store_true", help="Re-process even already enriched records")
    parser.add_argument("--skip-citations", action="store_true", help="Skip storing cited case law records")
    args = parser.parse_args()

    os.makedirs(r"E:\tvl\tvl\LHC data", exist_ok=True)
    enrich_records(limit=args.limit, force=args.force)

    # After enrichment, store cited cases as new records
    if not args.skip_citations:
        engine = create_engine(settings.SYNC_DATABASE_URL, echo=False)
        with Session(engine) as db:
            existing = {r[0] for r in db.execute(text("SELECT citation FROM case_laws")).fetchall()}
            store_cited_case_laws(db, existing)
