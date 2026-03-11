"""
Scrape Lahore High Court (LHC) approved judgments from data.lhc.gov.pk
1. Scrape metadata (citation, case#, title, judge, date, other citations)
2. Download all PDFs to E:\tvl\tvl\LHC data\
3. Extract full text from PDFs
4. Parse: sections applied, case laws cited, category, headnotes
5. Ingest into TVL database (case_laws table)
6. Generate embeddings for search

Usage: python scrape_lhc_judgments.py [--year 2025] [--skip-download] [--skip-existing]
"""

import os
import re
import sys
import json
import time
import argparse
import logging
from datetime import datetime

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
sys.stderr.reconfigure(encoding='utf-8', errors='replace')
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
import pdfplumber
from bs4 import BeautifulSoup
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.services.embedding_service import generate_embeddings_batch

settings = get_settings()
LHC_DATA_DIR = r"E:\tvl\tvl\LHC data"
LHC_BASE_URL = "https://data.lhc.gov.pk/dynamic/approved_judgments_result_new.php"
PDF_BASE_URL = "https://sys.lhc.gov.pk/appjudgments"

logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
logger = logging.getLogger(__name__)

# --- Category detection from case type and content ---
CATEGORY_KEYWORDS = {
    "criminal": [
        r"criminal", r"crl\.", r"jail appeal", r"murder", r"bail", r"fir\b",
        r"\bppc\b", r"anti.?terrorism", r"narcotics", r"drug", r"blasphemy",
        r"capital sentence", r"death sentence", r"qisas", r"diyat", r"zina",
        r"dacoity", r"robbery", r"theft", r"kidnapping", r"abduction",
    ],
    "constitutional": [
        r"writ petition", r"constitutional", r"fundamental right", r"article 199",
        r"article 184", r"article 25", r"habeas corpus", r"intra court",
    ],
    "family": [
        r"family", r"guardian", r"custody", r"maintenance", r"khula", r"divorce",
        r"dower", r"mehr", r"nikahnama", r"haq mehr", r"dissolution of muslim",
        r"jactitation", r"mflo",
    ],
    "civil": [
        r"civil revision", r"civil appeal", r"first appeal", r"specific performance",
        r"injunction", r"declaratory", r"suit", r"decree", r"partition",
        r"pre.?emption", r"ejectment",
    ],
    "property": [
        r"property", r"land", r"revenue", r"mutation", r"rent", r"tenancy",
        r"transfer of property", r"registration",
    ],
    "taxation": [
        r"tax", r"fiscal", r"customs", r"income tax", r"sales tax", r"excise",
        r"revenue", r"ptd\b", r"ftr\b",
    ],
    "corporate": [
        r"company", r"corporate", r"partnership", r"banking", r"insurance",
        r"cheque", r"negotiable instrument", r"arbitration",
    ],
    "labor": [
        r"labour", r"labor", r"industrial", r"employment", r"worker",
        r"wages", r"eobi", r"social security",
    ],
    "cyber": [
        r"cyber", r"peca", r"electronic", r"online", r"digital",
    ],
}


def detect_category(case_type: str, title: str, full_text: str = "") -> str:
    """Detect law category from case type, title, and content."""
    combined = f"{case_type} {title} {full_text[:2000]}".lower()
    scores = {}
    for cat, patterns in CATEGORY_KEYWORDS.items():
        score = sum(1 for p in patterns if re.search(p, combined, re.IGNORECASE))
        if score > 0:
            scores[cat] = score
    if scores:
        return max(scores, key=scores.get)
    return "civil"  # default


# --- Section/statute extraction from judgment text ---
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
    r'LDA\s+Act|Punjab\s+(?:Rented\s+Premises\s+Act|Pre[- ]?emption\s+Act)(?:,?\s*\d{4})?|'
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

# Case law citation patterns found within judgments
CITED_CASE_PATTERN = re.compile(
    r'(?:'
    r'(?:PLD|SCMR|CLC|YLR|PCrLJ|PLJ|PTD|MLD|PLC|NLR|GBLR|KLR|PSC|ALD)\s*\d{4}\s+\w+\s+\d+'
    r'|\d{4}\s+(?:SCMR|CLC|YLR|PCrLJ|PLJ|PTD|MLD|PLC|NLR|PLD|GBLR|KLR|PSC|ALD)\s+\d+'
    r'|\d{4}\s+LHC\s+\d+'
    r')',
    re.IGNORECASE
)


def extract_sections_applied(text: str) -> list:
    """Extract all sections/articles/orders mentioned in the judgment."""
    sections = set()

    for m in SECTION_PATTERN.finditer(text):
        sec_num = m.group(1)
        statute = (m.group(2) or "").strip()
        # Clean up: remove newlines, limit statute name length
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
        statute = (m.group(3) or "CPC").strip()
        statute = re.sub(r'\s+', ' ', statute)[:40]
        sections.add(f"O.{order} R.{rule} {statute}")

    # Filter out obviously wrong entries (section numbers that are too big)
    filtered = set()
    for s in sections:
        m = re.match(r'[SA]\w*\.(\d+)', s)
        if m and int(m.group(1)) > 700:
            continue  # Skip unreasonable section numbers
        filtered.add(s)

    return sorted(filtered)


def extract_cited_cases(text: str) -> list:
    """Extract all case law citations referenced within the judgment."""
    # Normalize newlines first for better matching
    clean_text = re.sub(r'\n', ' ', text)
    cases = set()
    for m in CITED_CASE_PATTERN.finditer(clean_text):
        cite = re.sub(r'\s+', ' ', m.group(0).strip())
        cases.add(cite)
    return sorted(cases)


def extract_relevant_statutes(sections: list) -> list:
    """Derive statute names from extracted sections."""
    statutes = set()
    statute_map = {
        "ppc": "Pakistan Penal Code, 1860",
        "penal code": "Pakistan Penal Code, 1860",
        "cr.p.c": "Code of Criminal Procedure, 1898",
        "crpc": "Code of Criminal Procedure, 1898",
        "code of criminal procedure": "Code of Criminal Procedure, 1898",
        "cpc": "Code of Civil Procedure, 1908",
        "code of civil procedure": "Code of Civil Procedure, 1908",
        "constitution": "Constitution of Pakistan, 1973",
        "mflo": "Muslim Family Laws Ordinance, 1961",
        "muslim family law": "Muslim Family Laws Ordinance, 1961",
        "peca": "Prevention of Electronic Crimes Act, 2016",
        "anti-terrorism": "Anti-Terrorism Act, 1997",
        "anti terrorism": "Anti-Terrorism Act, 1997",
        "nab ordinance": "National Accountability Ordinance, 1999",
        "qanun-e-shahadat": "Qanun-e-Shahadat Order, 1984",
        "qanun e shahadat": "Qanun-e-Shahadat Order, 1984",
        "cnsa": "Control of Narcotic Substances Act, 1997",
        "narcotic": "Control of Narcotic Substances Act, 1997",
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
                statutes.add(statute_name)
                break
    return sorted(statutes)


def generate_headnotes(full_text: str, title: str, sections: list) -> str:
    """Generate headnotes from the judgment text — extract key legal principles."""
    headnotes_parts = []

    # Look for "held" paragraphs — these contain the ratio decidendi
    held_patterns = [
        r'(?:^|\n)\s*(?:Held|HELD)[:\s—-]+(.{50,500})',
        r'(?:It is|We)\s+(?:held|observed|noted)\s+that\s+(.{50,500})',
        r'(?:The|This)\s+(?:Court|Bench|Hon.?ble)\s+(?:held|observed|noted)\s+that\s+(.{50,500})',
    ]
    for pattern in held_patterns:
        for m in re.finditer(pattern, full_text, re.IGNORECASE | re.MULTILINE):
            snippet = m.group(1).strip()
            snippet = re.sub(r'\s+', ' ', snippet)
            if len(snippet) > 50:
                headnotes_parts.append(snippet[:500])
            if len(headnotes_parts) >= 5:
                break
        if len(headnotes_parts) >= 5:
            break

    # If no "held" found, look for conclusion paragraphs
    if not headnotes_parts:
        conclusion_patterns = [
            r'(?:In view of|For the (?:fore)?going reasons?|Consequently|Resultantly|In the result)[,\s]+(.{50,500})',
            r'(?:appeal|petition|revision|application)\s+is\s+(?:hereby\s+)?(?:allowed|dismissed|disposed|accepted|rejected)(.{0,300})',
        ]
        for pattern in conclusion_patterns:
            for m in re.finditer(pattern, full_text, re.IGNORECASE):
                snippet = m.group(0).strip()
                snippet = re.sub(r'\s+', ' ', snippet)
                if len(snippet) > 30:
                    headnotes_parts.append(snippet[:500])
                if len(headnotes_parts) >= 3:
                    break
            if headnotes_parts:
                break

    if sections:
        headnotes_parts.insert(0, f"Sections/Articles: {', '.join(sections[:15])}")

    return "\n".join(headnotes_parts[:6]) if headnotes_parts else ""


def generate_summary(full_text: str, title: str, case_type: str) -> str:
    """Generate a summary from the judgment text focusing on the outcome."""
    if not full_text or len(full_text) < 100:
        return f"{title} — Lahore High Court judgment."

    summary_parts = []

    # Get the conclusion/disposition (usually last few paragraphs)
    # Look for result/conclusion
    result_patterns = [
        r'(?:In view of|For the (?:fore)?going reasons?|Consequently|Resultantly|In the result|'
        r'For what has been discussed|In these circumstances|Upshot)[,\s]+(.{50,1000})',
    ]
    for pattern in result_patterns:
        matches = list(re.finditer(pattern, full_text, re.IGNORECASE))
        if matches:
            last_match = matches[-1]
            conclusion = last_match.group(0).strip()
            conclusion = re.sub(r'\s+', ' ', conclusion)
            summary_parts.append(conclusion[:800])
            break

    # If no conclusion found, take the last meaningful paragraph
    if not summary_parts:
        paragraphs = [p.strip() for p in full_text.split('\n') if len(p.strip()) > 100]
        if paragraphs:
            last_para = paragraphs[-1]
            summary_parts.append(re.sub(r'\s+', ' ', last_para)[:800])

    # Also get the opening/facts briefly
    if len(full_text) > 500:
        # Skip first ~200 chars (usually header/caption)
        opening = full_text[200:800]
        opening = re.sub(r'\s+', ' ', opening).strip()
        if opening:
            summary_parts.insert(0, opening[:400])

    return "\n\n".join(summary_parts) if summary_parts else f"{title} — Lahore High Court judgment."


# --- Scraping ---

def scrape_lhc_page(year: int) -> list:
    """Scrape all judgment metadata from the LHC website for a given year."""
    url = f"{LHC_BASE_URL}?year={year}"
    logger.info(f"Fetching {url}")

    resp = requests.get(url, timeout=60)
    resp.raise_for_status()
    resp.encoding = 'utf-8'

    soup = BeautifulSoup(resp.text, 'html.parser')
    judgments = []
    current_judge = ""

    # The page structure: judge headers in <h2> tags, then tables with rows
    all_tables = soup.find_all('table')

    for table in all_tables:
        # Check if this is a judge header table
        h2 = table.find('h2')
        if h2:
            current_judge = h2.get_text(strip=True)
            # Remove "Mr. Justice " or "Mrs. Justice " prefix
            current_judge = re.sub(r'^(?:Mr\.|Mrs\.|Ms\.)\s*Justice\s*', '', current_judge).strip()
            continue

        # Check if this is a data table (has td elements with case data)
        rows = table.find_all('tr')
        for row in rows:
            cells = row.find_all('td')
            if not cells:
                continue

            # Check if this is a tag line row (colspan td with "Tag Line:")
            first_cell = cells[0]
            first_cell_text = first_cell.get_text(strip=True)
            if 'Tag Line' in first_cell_text:
                tag_text = re.sub(r'^.*?Tag\s*Line\s*:?\s*', '', first_cell_text, flags=re.IGNORECASE).strip()
                if judgments and tag_text:
                    judgments[-1]['tag_line'] = tag_text
                continue

            if len(cells) < 6:
                continue

            # Try to parse as a judgment row
            try:
                sr_no = cells[0].get_text(strip=True)
                if not sr_no or not sr_no.replace(' ', '').isdigit():
                    continue

                # Case # - contains case type and number
                case_cell = cells[1]
                case_parts = [t.strip() for t in case_cell.stripped_strings]
                case_type = case_parts[0] if case_parts else ""
                case_number = case_parts[1] if len(case_parts) > 1 else ""

                # Title — get_text with separator to avoid concatenation
                title = cells[2].get_text(separator=' ', strip=True)
                title = re.sub(r'\s+', ' ', title)
                # Ensure VS has spaces
                title = re.sub(r'(\w)(VS)(\w)', r'\1 VS \3', title, flags=re.IGNORECASE)

                # Decision Date
                decision_date = cells[3].get_text(strip=True)

                # LHC Citation
                lhc_citation = cells[4].get_text(strip=True)

                # Other Citations
                other_citations = cells[5].get_text(strip=True)

                # PDF link
                pdf_link = ""
                link_tag = row.find('a', href=True)
                if link_tag:
                    pdf_link = link_tag['href']

                if not lhc_citation:
                    continue

                judgment = {
                    'sr_no': int(sr_no.strip()),
                    'case_type': case_type,
                    'case_number': case_number,
                    'title': title,
                    'decision_date': decision_date,
                    'lhc_citation': lhc_citation,
                    'other_citations': other_citations,
                    'pdf_url': pdf_link,
                    'judge_name': current_judge,
                    'tag_line': '',
                    'year': year,
                }
                judgments.append(judgment)

            except (IndexError, ValueError) as e:
                continue

    logger.info(f"Scraped {len(judgments)} judgments for year {year}")
    return judgments


def download_pdf(pdf_url: str, save_dir: str) -> str:
    """Download a PDF from URL. Returns local path."""
    filename = pdf_url.split('/')[-1]
    local_path = os.path.join(save_dir, filename)

    if os.path.exists(local_path) and os.path.getsize(local_path) > 1000:
        return local_path  # Already downloaded

    try:
        # LHC sys server has SSL issues — use HTTP directly
        http_url = pdf_url.replace('https://', 'http://')
        resp = requests.get(http_url, timeout=120, stream=True)
        resp.raise_for_status()

        with open(local_path, 'wb') as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
        return local_path
    except Exception as e:
        # Try alternate URL pattern
        try:
            # Some PDFs are at data.lhc.gov.pk instead
            alt_filename = filename
            alt_url = f"https://data.lhc.gov.pk/reported_judgments/download_file/{alt_filename}"
            resp = requests.get(alt_url, timeout=120, stream=True, verify=False)
            if resp.status_code == 200 and len(resp.content) > 1000:
                with open(local_path, 'wb') as f:
                    f.write(resp.content)
                return local_path
        except Exception:
            pass
        logger.warning(f"Failed to download {pdf_url}: {e}")
        return ""


def extract_pdf_text(pdf_path: str) -> str:
    """Extract ALL text from ALL pages of a PDF."""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            all_text = []
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    all_text.append(page_text)
            return "\n\n".join(all_text)
    except Exception as e:
        logger.warning(f"Failed to extract text from {pdf_path}: {e}")
        return ""


def parse_other_citations(citation_str: str) -> list:
    """Parse the 'Other Citations' field into a list of individual citations."""
    if not citation_str:
        return []
    # Split by common separators
    citations = re.split(r'[;\n]', citation_str)
    return [c.strip() for c in citations if c.strip()]


def extract_year_from_citation(citation: str) -> int:
    """Extract year from citation like '2025 LHC 5745'."""
    m = re.search(r'(\d{4})\s+LHC', citation)
    if m:
        return int(m.group(1))
    m = re.search(r'(\d{4})', citation)
    if m:
        return int(m.group(1))
    return datetime.now().year


# --- Database ingestion ---

def ingest_judgments(judgments: list, pdf_dir: str, skip_existing: bool = True, skip_download: bool = False):
    """Download PDFs, extract text, parse legal data, and ingest into database."""
    engine = create_engine(settings.SYNC_DATABASE_URL, echo=False)
    total_new = 0
    total_updated = 0
    total_skipped = 0
    errors = []

    with Session(engine) as db:
        # Always load existing citations to know whether to INSERT or UPDATE
        rows = db.execute(text("SELECT citation FROM case_laws")).fetchall()
        existing = {r[0] for r in rows}
        logger.info(f"Found {len(existing)} existing case laws in DB")

        for idx, jdg in enumerate(judgments, 1):
            citation = jdg['lhc_citation']
            try:
                logger.info(f"[{idx}/{len(judgments)}] {citation} - {jdg['title'][:80]}")
            except UnicodeEncodeError:
                logger.info(f"[{idx}/{len(judgments)}] {citation}")

            if citation in existing and skip_existing:
                total_skipped += 1
                continue

            # Download PDF
            full_text = ""
            if not skip_download and jdg['pdf_url']:
                pdf_path = download_pdf(jdg['pdf_url'], pdf_dir)
                if pdf_path:
                    full_text = extract_pdf_text(pdf_path)
                    if full_text:
                        logger.info(f"  Extracted {len(full_text):,} chars from PDF")
                    else:
                        logger.warning(f"  No text extracted from PDF")
                        errors.append(f"{citation}: No text extracted")

            # Parse legal data from full text
            sections = extract_sections_applied(full_text) if full_text else []
            cited_cases = extract_cited_cases(full_text) if full_text else []
            relevant_statutes = extract_relevant_statutes(sections) if sections else []

            # Detect category (DB uses uppercase enum values)
            category = detect_category(jdg['case_type'], jdg['title'], full_text).upper()

            # Generate headnotes and summary
            headnotes = generate_headnotes(full_text, jdg['title'], sections) if full_text else ''
            summary = generate_summary(full_text, jdg['title'], jdg['case_type']) if full_text else ''

            # Tag line from website is important — always include it
            tag_line = jdg.get('tag_line', '').strip()
            if tag_line:
                headnotes = f"Tag Line: {tag_line}\n{headnotes}" if headnotes else f"Tag Line: {tag_line}"
                if not summary:
                    summary = tag_line

            # Decision date
            decision_date = jdg.get('decision_date', '')
            if decision_date:
                headnotes = f"Decision Date: {decision_date}\n{headnotes}" if headnotes else f"Decision Date: {decision_date}"

            # Build other citations string
            other_cites = jdg['other_citations']
            if cited_cases:
                # Add internally cited cases to metadata
                other_cites_list = parse_other_citations(other_cites)
                other_cites = "; ".join(other_cites_list) if other_cites_list else ""

            year = extract_year_from_citation(citation)

            # Sections and statutes as JSON strings
            sections_json = json.dumps(sections) if sections else None
            statutes_json = json.dumps(relevant_statutes) if relevant_statutes else None

            # Also store cited cases and other citations in the full text metadata
            if other_cites:
                if headnotes:
                    headnotes = f"Digest Citations: {other_cites}\n{headnotes}"
                else:
                    headnotes = f"Digest Citations: {other_cites}"

            if cited_cases:
                cited_str = ", ".join(cited_cases[:20])
                if headnotes:
                    headnotes += f"\nCited Cases: {cited_str}"
                else:
                    headnotes = f"Cited Cases: {cited_str}"

            # Store case type and case number in the title for search
            full_title = jdg['title']
            if jdg['case_type'] and jdg['case_number']:
                full_title = f"{jdg['case_type']} {jdg['case_number']} — {jdg['title']}"

            try:
                if citation in existing:
                    # Update existing
                    db.execute(
                        text("""
                            UPDATE case_laws SET
                                title = :title,
                                judge_name = :judge_name,
                                full_text = :full_text,
                                summary_en = :summary_en,
                                headnotes = :headnotes,
                                sections_applied = :sections_applied,
                                relevant_statutes = :relevant_statutes,
                                category = :category,
                                year = :year
                            WHERE citation = :citation
                        """),
                        {
                            "citation": citation,
                            "title": full_title[:500],
                            "judge_name": jdg['judge_name'][:255] if jdg['judge_name'] else None,
                            "full_text": full_text or None,
                            "summary_en": summary[:5000] if summary else None,
                            "headnotes": headnotes[:5000] if headnotes else None,
                            "sections_applied": sections_json,
                            "relevant_statutes": statutes_json,
                            "category": category,
                            "year": year,
                        },
                    )
                    total_updated += 1
                else:
                    # Insert new
                    db.execute(
                        text("""
                            INSERT INTO case_laws
                                (citation, title, court, category, year, judge_name,
                                 summary_en, full_text, headnotes,
                                 relevant_statutes, sections_applied)
                            VALUES
                                (:citation, :title, :court, :category, :year, :judge_name,
                                 :summary_en, :full_text, :headnotes,
                                 :relevant_statutes, :sections_applied)
                        """),
                        {
                            "citation": citation,
                            "title": full_title[:500],
                            "court": "LAHORE_HIGH_COURT",
                            "category": category,
                            "year": year,
                            "judge_name": jdg['judge_name'][:255] if jdg['judge_name'] else None,
                            "summary_en": summary[:5000] if summary else None,
                            "full_text": full_text or None,
                            "headnotes": headnotes[:5000] if headnotes else None,
                            "relevant_statutes": statutes_json,
                            "sections_applied": sections_json,
                        },
                    )
                    existing.add(citation)
                    total_new += 1

                if idx % 10 == 0:
                    db.commit()
                    logger.info(f"  --- Committed batch (progress: {idx}/{len(judgments)}) ---")

            except Exception as e:
                logger.error(f"  DB error for {citation}: {e}")
                errors.append(f"{citation}: {e}")
                db.rollback()

        db.commit()

        # Generate embeddings
        logger.info("=" * 60)
        logger.info("Generating embeddings for new/updated case laws...")

        rows = db.execute(
            text("""
                SELECT id, citation, title, summary_en, headnotes, sections_applied
                FROM case_laws
                WHERE court = 'LAHORE_HIGH_COURT'
                AND (embedding IS NULL OR embedding = '')
            """)
        ).fetchall()

        batch_size = 50
        for i in range(0, len(rows), batch_size):
            batch = rows[i:i + batch_size]
            texts = []
            ids = []
            for row in batch:
                embed_text = f"{row[1]} {row[2]}. {(row[3] or '')[:500]} {(row[4] or '')[:300]} {row[5] or ''}"
                texts.append(embed_text[:1000])
                ids.append(row[0])

            embeddings = generate_embeddings_batch(texts)
            for j, emb in enumerate(embeddings):
                db.execute(
                    text("UPDATE case_laws SET embedding = :emb WHERE id = :id"),
                    {"emb": json.dumps(emb), "id": ids[j]},
                )
            db.commit()
            logger.info(f"  Embeddings batch {i // batch_size + 1}/{(len(rows) + batch_size - 1) // batch_size}")

        # Final stats
        total_lhc = db.execute(
            text("SELECT COUNT(*) FROM case_laws WHERE court = 'LAHORE_HIGH_COURT'")
        ).scalar()
        total_all = db.execute(text("SELECT COUNT(*) FROM case_laws")).scalar()

        logger.info("=" * 60)
        logger.info(f"DONE!")
        logger.info(f"  New: {total_new}")
        logger.info(f"  Updated: {total_updated}")
        logger.info(f"  Skipped (existing): {total_skipped}")
        logger.info(f"  LHC case laws in DB: {total_lhc}")
        logger.info(f"  Total case laws in DB: {total_all}")
        if errors:
            logger.info(f"  Errors ({len(errors)}):")
            for e in errors[:20]:
                logger.info(f"    - {e}")


def main():
    parser = argparse.ArgumentParser(description="Scrape LHC judgments and ingest into TVL database")
    parser.add_argument("--year", type=int, default=2025, help="Year to scrape (default: 2025)")
    parser.add_argument("--all-years", action="store_true", help="Scrape all available years")
    parser.add_argument("--skip-download", action="store_true", help="Skip PDF downloads")
    parser.add_argument("--skip-existing", action="store_true", default=True, help="Skip existing citations")
    parser.add_argument("--force", action="store_true", help="Re-download and update all")
    args = parser.parse_args()

    os.makedirs(LHC_DATA_DIR, exist_ok=True)

    if args.force:
        args.skip_existing = False

    if args.all_years:
        # Scrape ALL years available on LHC website (2011-2026)
        years = list(range(2011, datetime.now().year + 1))
    else:
        years = [args.year]

    all_judgments = []
    for year in years:
        try:
            judgments = scrape_lhc_page(year)
            all_judgments.extend(judgments)

            # Save metadata to JSON
            meta_file = os.path.join(LHC_DATA_DIR, f"lhc_metadata_{year}.json")
            with open(meta_file, 'w', encoding='utf-8') as f:
                json.dump(judgments, f, ensure_ascii=False, indent=2)
            logger.info(f"Saved metadata to {meta_file}")

        except Exception as e:
            logger.error(f"Failed to scrape year {year}: {e}")

    if all_judgments:
        logger.info(f"\nTotal judgments to process: {len(all_judgments)}")
        ingest_judgments(
            all_judgments,
            pdf_dir=LHC_DATA_DIR,
            skip_existing=args.skip_existing,
            skip_download=args.skip_download,
        )


if __name__ == "__main__":
    main()
