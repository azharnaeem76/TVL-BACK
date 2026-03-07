"""
Legal Document Summarization Service.

Uses Ollama (local LLM) to:
1. Summarize a 50-60 page judgment into a concise summary
2. Extract headnotes, relevant statutes, and sections applied
3. Categorize the case law by area of law
4. Generate Urdu summary

Falls back to extractive summarization if Ollama is unavailable.
"""

import json
import re
import httpx
from app.core.config import get_settings

settings = get_settings()

SUMMARIZE_SYSTEM_PROMPT = """You are an expert Pakistani legal analyst. Your job is to analyze court judgments and extract structured information.

You MUST respond in valid JSON format only. No other text before or after the JSON."""

SUMMARIZE_USER_PROMPT = """Analyze this Pakistani court judgment and extract the following information in JSON format:

{{
  "summary_en": "A comprehensive summary of the judgment in 3-5 paragraphs. Include the key facts, legal issues, arguments, court's reasoning, and final decision/order.",
  "summary_ur": "A brief summary in Urdu (2-3 sentences)",
  "headnotes": "Key legal principles established, comma-separated (e.g., 'Bail - Right to bail - Section 497 CrPC - Principles for grant of bail')",
  "category": "One of: criminal, civil, constitutional, family, corporate, taxation, labor, property, cyber, banking, intellectual_property, human_rights, environmental, islamic",
  "relevant_statutes": ["List of statutes referenced, e.g., 'Pakistan Penal Code 1860', 'Code of Criminal Procedure 1898'"],
  "sections_applied": ["List of specific sections, e.g., '302 PPC', '497 CrPC', 'Article 9'],
  "citation": "The case citation if found (e.g., 'PLD 2024 Supreme Court 123')",
  "title": "Case title (e.g., 'Muhammad Ali v. The State')",
  "court": "One of: supreme_court, federal_shariat_court, lahore_high_court, sindh_high_court, peshawar_high_court, balochistan_high_court, islamabad_high_court, district_court, session_court, family_court, banking_court, anti_terrorism_court",
  "year": 2024,
  "judge_name": "Name of the presiding judge"
}}

Here is the judgment text:

{text}"""


async def summarize_document(text_chunks: list[str], pdf_metadata: dict) -> dict:
    """
    Summarize a legal document using Ollama LLM.

    For long documents, sends the first and last chunks (which typically contain
    the most important parts: facts at the beginning, decision at the end).
    """
    # Build a representative text from the document
    # First ~8000 chars (facts, issues) + last ~4000 chars (decision, order)
    if len(text_chunks) <= 3:
        representative_text = "\n\n".join(text_chunks)
    else:
        # First 2 chunks + last chunk for comprehensive coverage
        representative_text = (
            "\n\n".join(text_chunks[:2])
            + "\n\n[...middle of document omitted for brevity...]\n\n"
            + text_chunks[-1]
        )

    # Truncate if still too long (Ollama context limit)
    if len(representative_text) > 12000:
        representative_text = representative_text[:8000] + "\n\n[...]\n\n" + representative_text[-4000:]

    prompt = SUMMARIZE_USER_PROMPT.replace("{text}", representative_text)

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "messages": [
                        {"role": "system", "content": SUMMARIZE_SYSTEM_PROMPT},
                        {"role": "user", "content": prompt},
                    ],
                    "stream": False,
                    "options": {
                        "temperature": 0.1,  # Low temp for factual extraction
                        "num_predict": 2048,
                    },
                },
            )

            if response.status_code == 200:
                content = response.json().get("message", {}).get("content", "")
                return _parse_llm_response(content, pdf_metadata)

    except httpx.ConnectError:
        pass
    except Exception:
        pass

    # Fallback: extractive summarization without LLM
    return _fallback_summarize(text_chunks, pdf_metadata)


def _parse_llm_response(content: str, pdf_metadata: dict) -> dict:
    """Parse the LLM JSON response, with fallback for malformed JSON."""
    # Try to extract JSON from response
    json_match = re.search(r"\{[\s\S]*\}", content)
    if json_match:
        try:
            data = json.loads(json_match.group())
            # Merge with PDF metadata (PDF metadata takes precedence for citation/court if found)
            result = {
                "summary_en": data.get("summary_en", ""),
                "summary_ur": data.get("summary_ur", ""),
                "headnotes": data.get("headnotes", ""),
                "category": data.get("category", "civil"),
                "relevant_statutes": json.dumps(data.get("relevant_statutes", [])),
                "sections_applied": json.dumps(data.get("sections_applied", [])),
                "citation": pdf_metadata.get("citation") or data.get("citation", ""),
                "title": pdf_metadata.get("title") or data.get("title", ""),
                "court": pdf_metadata.get("court") or data.get("court", ""),
                "year": pdf_metadata.get("year") or data.get("year"),
                "judge_name": pdf_metadata.get("judge_name") or data.get("judge_name", ""),
            }
            return result
        except json.JSONDecodeError:
            pass

    return _fallback_summarize([], pdf_metadata)


def _fallback_summarize(text_chunks: list[str], pdf_metadata: dict) -> dict:
    """
    Extractive fallback when Ollama is not available.
    Creates a basic summary from the first few paragraphs.
    """
    full_text = "\n\n".join(text_chunks) if text_chunks else ""

    # Extract first 500 chars as summary
    summary = full_text[:500].strip()
    if len(full_text) > 500:
        summary += "..."

    # Try to detect category from keywords
    category = _detect_category(full_text)

    # Find statute references
    statutes = _extract_statutes(full_text)
    sections = _extract_sections(full_text)

    return {
        "summary_en": summary or "Summary could not be generated. Please install Ollama for AI summarization.",
        "summary_ur": "",
        "headnotes": "",
        "category": category,
        "relevant_statutes": json.dumps(statutes),
        "sections_applied": json.dumps(sections),
        "citation": pdf_metadata.get("citation", ""),
        "title": pdf_metadata.get("title", ""),
        "court": pdf_metadata.get("court", ""),
        "year": pdf_metadata.get("year"),
        "judge_name": pdf_metadata.get("judge_name", ""),
    }


def _detect_category(text: str) -> str:
    """Detect law category from keywords in the text."""
    text_lower = text.lower()
    keyword_map = {
        "criminal": ["murder", "qatl", "theft", "robbery", "bail", "fir", "accused", "prosecution", "302 ppc", "penal code"],
        "family": ["divorce", "talaq", "khula", "custody", "maintenance", "nafqa", "nikah", "dower", "mehar", "family court"],
        "constitutional": ["fundamental right", "constitution", "article 9", "article 14", "article 184", "constitutional petition"],
        "property": ["property", "land", "tenant", "rent", "eviction", "pre-emption", "transfer of property"],
        "cyber": ["electronic", "cyber", "peca", "online", "digital"],
        "banking": ["bank", "finance", "loan", "recovery", "cheque"],
        "taxation": ["tax", "income tax", "fir", "fbr", "customs"],
        "labor": ["worker", "employee", "labour", "labor", "industrial", "trade union"],
        "islamic": ["shariat", "islamic", "hudood", "qisas", "diyat"],
        "human_rights": ["human rights", "discrimination", "dignity"],
    }
    scores = {cat: sum(1 for kw in keywords if kw in text_lower) for cat, keywords in keyword_map.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "civil"


def _extract_statutes(text: str) -> list[str]:
    """Extract referenced statutes from text."""
    statutes = set()
    statute_patterns = [
        r"Pakistan Penal Code",
        r"Code of Criminal Procedure",
        r"Constitution of Pakistan",
        r"Muslim Family Laws Ordinance",
        r"Transfer of Property Act",
        r"Qanun-e-Shahadat",
        r"Prevention of Electronic Crimes Act",
        r"Guardian and Wards Act",
        r"Specific Relief Act",
        r"Contract Act",
        r"Income Tax Ordinance",
        r"Limitation Act",
    ]
    for pattern in statute_patterns:
        if re.search(pattern, text, re.IGNORECASE):
            statutes.add(pattern)
    return list(statutes)


def _extract_sections(text: str) -> list[str]:
    """Extract specific section references from text."""
    sections = set()
    # Match patterns like "Section 302 PPC", "S. 497 CrPC", "Article 9"
    patterns = [
        r"(?:Section|S\.)\s*(\d+[-A-Z]*)\s*(PPC|CrPC|CPC|QSO|TPA|MFLO|PECA|GWA|ITO)",
        r"(Article\s+\d+(?:\([0-9a-z]+\))?)",
    ]
    for pattern in patterns:
        for match in re.finditer(pattern, text, re.IGNORECASE):
            sections.add(match.group().strip())
    return list(sections)[:20]  # Limit to 20
