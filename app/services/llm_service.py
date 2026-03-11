"""
LLM Service using Ollama (free, local).

Ollama runs models like Qwen 2.5, Llama 3, Mistral, etc. locally.
Install: https://ollama.ai
Then run: ollama pull qwen2.5:7b
"""

import httpx
import json
import asyncio
from typing import AsyncGenerator
from app.core.config import get_settings
settings = get_settings()

SYSTEM_PROMPT = """You are TVL (The Value of Law), a senior Pakistani advocate with 25+ years of experience. You speak like a real lawyer giving a consultation — authoritative, practical, and direct. You have extensive knowledge of Pakistani case law and statutes built from years of practice.

YOUR PERSONALITY:
- Talk like a senior advocate in a consultation, NOT like a textbook or search engine.
- Give your LEGAL OPINION — don't just list information. Take a position on the matter.
- Be practical — tell the client what to DO, what their chances are, what risks they face.
- When analyzing facts, apply the law to the SPECIFIC situation, don't give generic summaries.
- Use legal terminology naturally but explain it when needed for non-lawyers.

CRITICAL RULES:
- The RELEVANT CASE LAWS provided below are REAL cases that you have reviewed for this query.
- NEVER say "I don't have access", "as of my last update", "database", "search results", or "retrieved from database". Speak as if this knowledge is YOUR OWN from your legal practice.
- Say "mere pas ye case laws hain" or "I have reviewed these cases" — NEVER say "database mein ye case hain" or "found in database".
- NEVER fabricate case citations. Only cite cases from the RELEVANT CASE LAWS provided.
- If the provided cases have low relevance to the question, briefly mention them but focus on explaining the applicable law from your knowledge.
- ONLY cite sections and statutes that are DIRECTLY relevant to the specific legal question asked. Do NOT mention unrelated laws. For example, if the question is about property fraud, do NOT cite rape or murder sections. Stay focused on the exact legal issue.

LANGUAGE RULE:
- English question → English answer. Roman Urdu question → Roman Urdu answer. Urdu script → Urdu script.
- NEVER respond in Chinese, Arabic, or Hindi.

HOW TO ANSWER:
1. First, UNDERSTAND the specific legal question being asked. Identify the exact legal issue.
2. Give your LEGAL OPINION upfront — what does the law say about this specific situation?
3. Cite the most relevant applicable SECTIONS, ARTICLES, ORDERS, RULES, and STATUTES (e.g., "Section 10 MFLO 1961", "Order VII Rule 11 CPC", "Article 199 Constitution"). Include ALL applicable provisions — sections, articles, orders, rules, chapters, acts, and ordinances.
4. Reference the MOST RELEVANT case laws from the DATABASE RESULTS — for each one:
   - State the OUTCOME/DISPOSITION (appeal allowed/dismissed, bail granted/refused, conviction upheld/set aside)
   - Quote the COURT'S OBSERVATIONS and REMARKS — what the judge specifically observed or held
   - Explain the RELIEF GRANTED — what order did the court actually pass?
   - Identify the LEGAL PRINCIPLES established — what ratio decidendi was laid down?
   - Explain HOW it applies to this situation — connect to the specific facts
5. Give PRACTICAL ADVICE — what should the person do? What are their options? What evidence do they need? What court to approach?
6. If the question is about a dispute, analyze BOTH sides — strengths and weaknesses.
7. When citing from enriched data, mention: the scenario of the cited case, what the court observed, what relief was granted, and what can be LEARNED from it for the current question.

KEY PAKISTANI LAW:
- Criminal: PPC (S.302 murder, S.304 culpable homicide, S.324 attempt to murder, S.337 hurt, S.375 rape, S.420 fraud, S.489-F dishonour of cheque), CrPC (S.154 FIR, S.497/498 bail, S.161 statements)
  - S.324 PPC (attempt to murder) requires: (a) attack on vital body part, (b) intent to kill, (c) weapon capable of causing death. If attack is on non-vital part, no repeated blows, or no clear motive → may fall under S.337 (hurt) not S.324. Defense grounds: delay in FIR, no specific role in FIR, no motive, medical evidence contradicts attempt to kill, single blow vs repeated attack.
  - Bail considerations: S.497 CrPC for bailable offenses, S.498 for non-bailable. Key factors: severity of injury, weapon used, prior enmity, FIR delay, medical evidence, prosecution case strength.
- Civil: CPC (O.VII R.11 rejection, O.XXXIX injunction), Contract Act 1872, Transfer of Property Act, Specific Relief Act
- Constitutional: Art.4 right of individuals, Art.9 liberty, Art.10-A fair trial, Art.25 equality, Art.184(3) fundamental rights, Art.199 writ jurisdiction
- Family: MFLO 1961 (S.7 polygamy, S.8 dissolution), West Pakistan Family Courts Act 1964, Guardians & Wards Act 1890, Nikahnama columns (Col.13=specified dower/property, Col.14=deferred dower, Col.15=dower received, Col.16=special conditions/stipulations, Col.17=rights delegated to wife)
- Special: PECA 2016, NAB Ordinance 1999, Anti-Terrorism Act 1997, Qanun-e-Shahadat Order 1984
- Court hierarchy: Supreme Court > Federal Shariat Court > High Courts > District Courts > Magistrate Courts

NIKAHNAMA KNOWLEDGE:
- Column 13: Haq Mehr Muajjal (prompt dower) — property/amount given or promised at the time of nikah
- Column 14: Haq Mehr Muwajjal (deferred dower) — to be paid later
- Column 15: Total dower received by bride
- Column 16: Special conditions/stipulations agreed by both parties (e.g., right to divorce, education, work, property conditions)
- Column 17: Whether the right of divorce (talaq) has been delegated to the wife
- Columns 13 and 16 are LEGALLY DISTINCT — Column 13 is about dower (mehr), Column 16 is about special conditions. Entries in both columns are separately enforceable.
"""

SCENARIO_PROMPT = """You are TVL (The Value of Law), a senior Pakistani advocate with 25+ years experience analyzing a legal scenario. You speak like a real lawyer in a consultation — authoritative, direct, and practical.

LANGUAGE RULE:
- English question → English answer. Roman Urdu → Roman Urdu. Urdu script → Urdu script.
- NEVER respond in Chinese, Arabic, or Hindi.

HOW TO ANALYZE:
You are given a legal scenario along with REAL case laws + statutes that you have reviewed. The case laws include enriched data: disposition (who won), relief granted, court observations, legal principles, all applicable sections/articles/orders/rules, acts and ordinances referenced, and cited precedents. NEVER mention "database" — speak as if these cases are from your own legal knowledge and practice.

1. **Mera Mashwara (My Legal Opinion):** Start with your clear legal opinion on the scenario. What is the legal position? Who has the stronger case and why?
2. **Applicable Law:** Identify ALL applicable legal provisions — sections, articles, orders, rules, chapters of acts and ordinances (e.g., "Section 10 MFLO 1961", "Order VII Rule 11 CPC", "Article 199 Constitution", "Chapter XIV CrPC"). Explain what each provision says and how it applies to THESE specific facts.
3. **Key Precedents:** Cite the MOST RELEVANT case laws from the database. For each one:
   (a) State the OUTCOME/DISPOSITION — what did the court decide? Who won and why?
   (b) Quote the COURT'S OBSERVATIONS — what did the judge specifically observe or hold?
   (c) Explain the RELIEF GRANTED — what order was passed?
   (d) Identify the LEGAL PRINCIPLES — what ratio decidendi was established that the user can learn from?
   (e) Explain HOW that ruling applies to THIS scenario — connect to the specific facts.
4. **Strengths & Weaknesses:** Analyze both sides. What are the strong points? What are the risks?
5. **Practical Advice:** Tell the client exactly what to do — what evidence to gather, which court to approach, what arguments to make, what to avoid.

CRITICAL: Do NOT invent citations. Only cite cases from the RELEVANT CASES provided. Talk like a lawyer, not a textbook. NEVER say "database" — say "mere pas" or "I have reviewed".
"""


def _lang_instruction(language: str) -> str:
    """Get a short language instruction for the LLM."""
    if language == "roman_urdu":
        return "\n\nIMPORTANT: Respond in Roman Urdu (Urdu written in English letters). Do NOT use Urdu script or Chinese."
    if language == "urdu":
        return "\n\nIMPORTANT: Respond in Urdu script."
    return "\n\nIMPORTANT: Respond in English only. Do NOT use Urdu script or Chinese."


async def generate_response(
    user_message: str,
    context: str = "",
    language: str = "english",
    chat_history: list[dict] = None,
) -> str:
    """Generate a response using Ollama (local LLM)."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if chat_history:
        messages.extend(chat_history[-10:])  # Keep last 10 messages for context

    lang_hint = _lang_instruction(language)

    if context:
        user_content = f"""{user_message}

--- RELEVANT CASE LAWS & STATUTES (from your legal practice and research) ---
{context}
--- END RELEVANT CASES ---

INSTRUCTIONS:
1. First give your LEGAL OPINION on the question — what does the law say? Apply the law to the specific facts.
2. Cite the most relevant case laws from the RELEVANT CASES above — explain HOW each one specifically applies. Only cite the ones that truly matter, not all of them.
3. NEVER invent or fabricate case citations. ONLY use citations from the RELEVANT CASES provided.
4. ONLY mention sections and statutes that are DIRECTLY relevant to this specific question. Do NOT cite unrelated laws — if the question is about property, do not mention rape or murder sections. Stay focused.
5. Give practical advice — what should the person do next?
6. Talk like a senior advocate giving a consultation, not a search engine listing results.{lang_hint}"""
    else:
        user_content = f"""{user_message}

Note: No specific case laws are available for this query. Answer using your knowledge of Pakistani law as a senior advocate would. Explain ONLY the directly applicable law, sections, and practical advice. Do NOT cite unrelated sections. Do NOT fabricate case law citations.{lang_hint}"""

    messages.append({"role": "user", "content": user_content})

    try:
        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.4,
                        "num_predict": 2048,
                        "num_ctx": 8192,
                        "repeat_penalty": 1.3,
                        "repeat_last_n": 256,
                    },
                },
            )

            if response.status_code == 200:
                data = response.json()
                if "error" in data:
                    return _fallback_response(user_message, context, language)
                return data.get("message", {}).get("content", "I apologize, I could not generate a response.")
            else:
                return _fallback_response(user_message, context, language)

    except (httpx.ConnectError, httpx.ReadTimeout, httpx.TimeoutException, Exception):
        return _fallback_response(user_message, context, language)
    except Exception as e:
        return f"Error generating response: {str(e)}"


async def generate_response_stream(
    user_message: str,
    context: str = "",
    language: str = "english",
    chat_history: list[dict] = None,
) -> AsyncGenerator[str, None]:
    """Generate a streaming response using Ollama (local LLM). Yields chunks of text."""
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if chat_history:
        messages.extend(chat_history[-10:])

    lang_hint = _lang_instruction(language)

    if context:
        user_content = f"""{user_message}

--- RELEVANT CASE LAWS & STATUTES (from your legal practice and research) ---
{context}
--- END RELEVANT CASES ---

INSTRUCTIONS:
1. First give your LEGAL OPINION on the question — what does the law say? Apply the law to the specific facts.
2. Cite the most relevant case laws from the RELEVANT CASES above — explain HOW each one specifically applies. Only cite the ones that truly matter, not all of them.
3. NEVER invent or fabricate case citations. ONLY use citations from the RELEVANT CASES provided.
4. ONLY mention sections and statutes that are DIRECTLY relevant to this specific question. Do NOT cite unrelated laws — if the question is about property, do not mention rape or murder sections. Stay focused.
5. Give practical advice — what should the person do next?
6. Talk like a senior advocate giving a consultation, not a search engine listing results.{lang_hint}"""
    else:
        user_content = f"""{user_message}

Note: No specific case laws are available for this query. Answer using your knowledge of Pakistani law as a senior advocate would. Explain ONLY the directly applicable law, sections, and practical advice. Do NOT cite unrelated sections. Do NOT fabricate case law citations.{lang_hint}"""

    messages.append({"role": "user", "content": user_content})

    try:
        async with httpx.AsyncClient(timeout=None) as client:
            async with client.stream(
                "POST",
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": 0.4,
                        "num_predict": 2048,
                        "num_ctx": 8192,
                        "repeat_penalty": 1.3,
                        "repeat_last_n": 256,
                    },
                },
            ) as response:
                async for line in response.aiter_lines():
                    if line.strip():
                        try:
                            data = json.loads(line)
                            content = data.get("message", {}).get("content", "")
                            if content:
                                yield content
                            if data.get("done", False):
                                break
                        except json.JSONDecodeError:
                            continue

    except httpx.ConnectError:
        yield _fallback_response(user_message, context, language)
    except Exception as e:
        yield f"Error generating response: {str(e)}"


def _fallback_response(user_message: str, context: str, language: str) -> str:
    """Fallback when Ollama is not available - return structured results from database."""
    if not context:
        if language == "roman_urdu":
            return ("Ollama LLM server chal nahi raha. Apna scenario search karne ke liye, "
                    "pehle Ollama install karein (ollama.ai) aur 'ollama pull qwen2.5:7b' chalayein. "
                    "Lekin aapke scenario ke mutabiq jo case laws mile hain wo neeche hain.")
        elif language == "urdu":
            return ("اولاما سرور نہیں چل رہا۔ براہ کرم اولاما انسٹال کریں۔ "
                    "تاہم، آپ کے سوال سے متعلق قانونی حوالے نیچے دیے گئے ہیں۔")
        return ("Ollama LLM server is not running. Please install Ollama from ollama.ai "
                "and run 'ollama pull qwen2.5:7b'. However, here are the relevant legal references "
                "for your query.")

    return (
        f"**Note:** AI analysis is unavailable (Ollama not running). "
        f"Below are the matching legal references:\n\n{context}"
    )


async def generate_scenario_analysis(
    scenario: str,
    case_laws: list[dict],
    statutes: list[dict],
    language: str = "english",
) -> str:
    """Generate a detailed analysis for a legal scenario with citations."""
    context_parts = []

    if case_laws:
        context_parts.append("RELEVANT CASE LAWS:")
        for i, cl in enumerate(case_laws[:7], 1):  # Top 7 cases
            summary_en = (cl.get('summary') or cl.get('summary_en') or '')
            summary_ur = cl.get('summary_ur') or ''
            # Use whichever summary is available (prefer English, include Urdu if no English)
            summary = summary_en if summary_en and summary_en.strip() not in {'.', '', 'N/A'} else summary_ur
            summary = summary[:1200]  # Allow more context for better analysis
            headnotes = (cl.get('headnotes') or 'N/A')[:800]
            sections = cl.get('sections_applied') or 'N/A'
            rel_statutes = cl.get('relevant_statutes') or 'N/A'
            context_parts.append(
                f"{i}. {cl.get('citation', 'N/A')} | {cl.get('title', 'N/A')[:150]} | "
                f"Court: {cl.get('court', 'N/A')} | Year: {cl.get('year', 'N/A')} | "
                f"Judge: {cl.get('judge_name', 'N/A')}\n"
                f"   Summary (Outcome/Facts/Relief): {summary}\n"
                f"   Headnotes (Disposition/Observations/Principles): {headnotes}\n"
                f"   Sections/Articles/Orders/Rules: {sections}\n"
                f"   Acts/Ordinances/Statutes: {rel_statutes}"
            )

    if statutes:
        context_parts.append("\nRELEVANT STATUTES:")
        for i, st in enumerate(statutes, 1):
            context_parts.append(
                f"{i}. {st.get('title', 'N/A')} (Act {st.get('act_number', 'N/A')}, Year {st.get('year', 'N/A')})\n"
                f"   Summary: {st.get('summary_en', 'N/A')}"
            )

    context = "\n".join(context_parts)
    lang_hint = _lang_instruction(language)

    messages = [{"role": "system", "content": SCENARIO_PROMPT}]
    messages.append({"role": "user", "content": f"""Analyze this legal scenario:

{scenario}

{context}

INSTRUCTIONS:
1. Start with your LEGAL OPINION — what is the legal position on this scenario?
2. Apply the law to these SPECIFIC facts — don't give generic legal principles.
3. Cite the most relevant case laws from above by citation, court, year — explain how each ruling applies HERE. You don't need to cite all — only the truly relevant ones.
4. NEVER invent citations — only use what's shown above.
5. Give practical advice — what should the person DO next? What evidence to collect? Which court to approach?
6. Talk like a senior advocate, not a textbook.{lang_hint}"""})

    try:
        async with httpx.AsyncClient(timeout=None) as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.4,
                        "num_predict": 2048,
                        "num_ctx": 8192,
                        "repeat_penalty": 1.3,
                        "repeat_last_n": 256,
                    },
                },
            )
            if response.status_code == 200:
                data = response.json()
                if "error" in data:
                    return _fallback_response(scenario, context, language)
                return data.get("message", {}).get("content", "Analysis could not be generated.")
            return _fallback_response(scenario, context, language)
    except (httpx.ConnectError, httpx.ReadTimeout, httpx.TimeoutException, Exception):
        return _fallback_response(scenario, context, language)
    except Exception as e:
        return f"Error: {str(e)}"
