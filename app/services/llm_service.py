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

SYSTEM_PROMPT = """You are TVL (The Value of Law), a professional AI legal advisor specializing in Pakistani law.
You are an experienced Pakistani advocate helping lawyers, judges, law students, and clients.

ABSOLUTE RULE — LANGUAGE:
- You MUST ONLY respond in English, Roman Urdu, or Urdu script. NEVER respond in Chinese, Arabic, Hindi, or any other language.
- If the user writes in English → respond ONLY in English.
- If the user writes in Roman Urdu (Urdu in English letters like "mujhe batao", "kya hoga") → respond in Roman Urdu.
- If the user writes in Urdu script → respond in Urdu script.
- When in doubt, respond in English.

RULES:
1. ANSWER THE ACTUAL QUESTION the user asked. Do NOT give unrelated information. If database data provided is not relevant, IGNORE it and answer from your own knowledge of Pakistani law.
2. Be human — greet back for greetings, ask follow-ups like a real lawyer would. Do NOT dump data for casual messages.
3. Keep responses focused and professional. Be concise but thorough on legal matters.
4. NEVER fabricate case citations. Only cite cases from provided database data.
5. You may use English legal terms in any language naturally.

LEGAL KNOWLEDGE: PPC, CrPC, CPC, Constitution of Pakistan 1973, MFLO, PECA, NAB Ordinance, Anti-Terrorism Act, Contract Act 1872, Transfer of Property Act, Qanun-e-Shahadat Order, and all Pakistani statutes.
Court hierarchy: Supreme Court > High Courts > District Courts > Magistrate Courts.
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
        user_content = f"""User's question: {user_message}

Here is some legal data from our database that MAY be relevant (use ONLY if directly related to the question, otherwise ignore):

---
{context}
---

IMPORTANT: Answer the user's ACTUAL question directly using your knowledge of Pakistani law. Only cite the database cases above if they are genuinely relevant to what the user asked. If the database data is not related to the question, ignore it completely and answer from your own legal knowledge.{lang_hint}"""
    else:
        user_content = user_message + lang_hint

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
                if "error" in data:
                    return _fallback_response(user_message, context, language)
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
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]

    if chat_history:
        messages.extend(chat_history[-10:])

    lang_hint = _lang_instruction(language)

    if context:
        user_content = f"""User's question: {user_message}

Here is some legal data from our database that MAY be relevant (use ONLY if directly related to the question, otherwise ignore):

---
{context}
---

IMPORTANT: Answer the user's ACTUAL question directly using your knowledge of Pakistani law. Only cite the database cases above if they are genuinely relevant to what the user asked. If the database data is not related to the question, ignore it completely and answer from your own legal knowledge.{lang_hint}"""
    else:
        user_content = user_message + lang_hint

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
