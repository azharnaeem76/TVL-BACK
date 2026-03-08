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
from app.services.language_service import get_response_language_instruction

settings = get_settings()

SYSTEM_PROMPT = """You are TVL (The Virtual Lawyer), an AI legal assistant specializing exclusively in Pakistani law.
You help lawyers, judges, law students, and clients understand Pakistani legal matters.

CRITICAL: You are a Pakistani law specialist. ALL your responses MUST be grounded in Pakistani law - Pakistan Penal Code (PPC), Code of Criminal Procedure (CrPC), Civil Procedure Code (CPC), Constitution of Pakistan 1973, Muslim Family Laws Ordinance, PECA, NAB Ordinance, Anti-Terrorism Act, Contract Act 1872, Transfer of Property Act, Qanun-e-Shahadat Order, and other Pakistani statutes.

Your capabilities:
- Explain Pakistani laws, statutes, and legal procedures
- Analyze legal scenarios citing relevant Pakistani case law and statutes
- Explain court judgments in simple language
- Guide users on legal rights and procedures under Pakistani law
- Support queries in English, Urdu, and Roman Urdu

Response rules:
- ALWAYS cite specific Pakistani case laws (with citation, court, year), statutes, and sections
- Reference actual sections of Pakistani law (e.g., "Section 302 PPC", "Section 497 CrPC", "Article 199 Constitution")
- Clearly state when something is legal advice vs general information
- Be accurate about Pakistani court hierarchy: Supreme Court > High Courts > District/Session Courts > Magistrate Courts
- If database references are provided, use them as PRIMARY source - cite the exact case law citations, courts, and years from the data
- Format responses with clear headings, bullet points, and section references
- When provided with legal data from our database, BASE YOUR RESPONSE PRIMARILY ON THAT DATA and cite the specific case laws and statutes provided
- If the provided data is insufficient, supplement with your knowledge of Pakistani law but clearly indicate: "Based on our database: [X]. Additionally from general Pakistani legal knowledge: [Y]"
- NEVER make up case citations. If you don't have a specific citation, say "relevant case law exists on this point" rather than fabricating one
"""


async def generate_response(
    user_message: str,
    context: str = "",
    language: str = "english",
    chat_history: list[dict] = None,
) -> str:
    """Generate a response using Ollama (local LLM)."""
    lang_instruction = get_response_language_instruction(language)

    messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n\n" + lang_instruction}]

    if chat_history:
        messages.extend(chat_history[-10:])  # Keep last 10 messages for context

    if context:
        user_content = f"""Based on the following relevant legal data from our database:

---
{context}
---

User's question: {user_message}

Please provide a comprehensive answer citing the relevant case laws and statutes from the data above.
If the data doesn't fully answer the question, supplement with your knowledge of Pakistani law but clearly indicate which parts come from the database and which from general knowledge."""
    else:
        user_content = user_message

    messages.append({"role": "user", "content": user_content})

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "messages": messages,
                    "stream": False,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 2048,
                    },
                },
            )

            if response.status_code == 200:
                data = response.json()
                return data.get("message", {}).get("content", "I apologize, I could not generate a response.")
            else:
                return _fallback_response(user_message, context, language)

    except httpx.ConnectError:
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
    lang_instruction = get_response_language_instruction(language)

    messages = [{"role": "system", "content": SYSTEM_PROMPT + "\n\n" + lang_instruction}]

    if chat_history:
        messages.extend(chat_history[-10:])

    if context:
        user_content = f"""Based on the following relevant legal data from our database:

---
{context}
---

User's question: {user_message}

Please provide a comprehensive answer citing the relevant case laws and statutes from the data above.
If the data doesn't fully answer the question, supplement with your knowledge of Pakistani law but clearly indicate which parts come from the database and which from general knowledge."""
    else:
        user_content = user_message

    messages.append({"role": "user", "content": user_content})

    try:
        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream(
                "POST",
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "messages": messages,
                    "stream": True,
                    "options": {
                        "temperature": 0.3,
                        "num_predict": 2048,
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
                "from our database for your query.")

    return (
        f"**Note:** AI analysis is unavailable (Ollama not running). "
        f"Below are the matching legal references from the database:\n\n{context}"
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
        context_parts.append("**Relevant Case Laws:**")
        for cl in case_laws:
            context_parts.append(
                f"- {cl.get('citation', 'N/A')} | {cl.get('title', 'N/A')} | "
                f"Court: {cl.get('court', 'N/A')} | Year: {cl.get('year', 'N/A')}\n"
                f"  Summary: {cl.get('summary_en', 'N/A')}\n"
                f"  Headnotes: {cl.get('headnotes', 'N/A')}"
            )

    if statutes:
        context_parts.append("\n**Relevant Statutes:**")
        for st in statutes:
            context_parts.append(
                f"- {st.get('title', 'N/A')} ({st.get('act_number', 'N/A')}, {st.get('year', 'N/A')})\n"
                f"  Summary: {st.get('summary_en', 'N/A')}"
            )

    context = "\n".join(context_parts)

    return await generate_response(
        user_message=scenario,
        context=context,
        language=language,
    )
