"""
Interactive Chat API.

Users can have ongoing conversations about legal scenarios.
The system maintains context and provides follow-up citations.
"""

import json
import re
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.models.legal import ChatSession, ChatMessage, CaseLaw
from app.schemas.legal import ChatRequest, ChatResponse, ChatMessageResponse, CaseLawResponse
from app.services.language_service import detect_language, normalize_to_english
from app.services.embedding_service import generate_embedding
from app.services.llm_service import generate_response, generate_response_stream
from app.services.search_service import _vector_search_cases, _vector_search_statutes, _text_search_statutes
from app.core.config import get_settings


def _clean_summary(en: str | None, ur: str | None, max_len: int = 800) -> str:
    """Return the best available summary, treating placeholder values like '.' as empty."""
    placeholders = {'.', '()', '', '-', 'N/A', 'n/a'}
    if en and en.strip() not in placeholders:
        return en[:max_len]
    if ur and ur.strip() not in placeholders:
        return ur[:max_len]
    return 'N/A'


def _is_casual_message(message: str) -> bool:
    """Detect if a message is a greeting or casual chat that doesn't need legal DB context."""
    msg = message.strip().lower()
    # Remove punctuation for matching
    msg_clean = re.sub(r'[^\w\s]', '', msg)
    casual_patterns = [
        'hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening',
        'assalam', 'salam', 'walaikum', 'aoa', 'slm', 'how are you',
        'thank', 'thanks', 'shukriya', 'meherbani', 'okay', 'ok', 'bye',
        'goodbye', 'khuda hafiz', 'allah hafiz', 'take care',
        'who are you', 'what is your name', 'what can you do', 'help me',
        'kya kar sakte', 'tum kaun', 'aap kaun', 'kya hai ye',
        'theek hai', 'acha', 'ji', 'haan', 'nahi',
    ]
    # Check if the message is short and matches a casual pattern
    if len(msg_clean.split()) <= 6:
        for pattern in casual_patterns:
            if pattern in msg_clean:
                return True
    return False

settings = get_settings()
router = APIRouter(prefix="/chat", tags=["Interactive Chat"])


@router.post(
    "/message",
    response_model=ChatResponse,
    summary="Send a chat message",
    response_description="AI response with cited case laws",
)
async def send_message(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Send a message in a chat session. Creates a new session if session_id is not provided.

    The chat supports:
    - Follow-up questions about previous results
    - Multilingual conversations (English, Urdu, Roman Urdu)
    - Automatic citation of relevant case laws
    """
    # Get or create session
    if request.session_id:
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.id == request.session_id,
                ChatSession.user_id == current_user.id,
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
    else:
        session = ChatSession(
            user_id=current_user.id,
            title=request.message[:100],
        )
        db.add(session)
        await db.flush()

    # Detect language
    language = detect_language(request.message)

    # Save user message
    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=request.message,
        language=language,
    )
    db.add(user_msg)

    # Get chat history
    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at)
    )
    history_rows = history_result.scalars().all()
    chat_history = [{"role": msg.role, "content": msg.content} for msg in history_rows[-10:]]

    # Search for relevant case laws AND statutes (skip for greetings/casual messages)
    relevant_cases = []
    context = ""
    cited_ids = []
    if not _is_casual_message(request.message):
        normalized = normalize_to_english(request.message, language)
        query_embedding = generate_embedding(normalized)
        all_cases = await _vector_search_cases(db=db, embedding=query_embedding, limit=8)
        # Keep cases above the configured similarity threshold
        relevant_cases = [cl for cl in all_cases if getattr(cl, '_similarity', 0) >= settings.SIMILARITY_THRESHOLD]

        context_parts = []
        for cl in relevant_cases:
            cited_ids.append(cl.id)
            score = getattr(cl, '_similarity', 0)
            summary = _clean_summary(cl.summary_en, cl.summary_ur)
            headnotes = (cl.headnotes or 'N/A')[:800]
            sections = cl.sections_applied or 'N/A'
            statutes = cl.relevant_statutes or 'N/A'
            judge = cl.judge_name or 'N/A'
            context_parts.append(
                f"- [Relevance: {score:.0%}] {cl.citation} | {cl.title[:150]} | Court: {cl.court.value if cl.court else 'N/A'} | "
                f"Year: {cl.year} | Judge: {judge}\n"
                f"  Summary (Outcome/Facts/Relief): {summary}\n"
                f"  Headnotes (Disposition/Observations/Principles): {headnotes}\n"
                f"  Sections/Articles/Orders/Rules: {sections}\n"
                f"  Acts/Ordinances/Statutes: {statutes}"
            )

        # Also search statutes
        statutes_found = await _vector_search_statutes(db=db, embedding=query_embedding, limit=5)
        if not statutes_found:
            statutes_found = await _text_search_statutes(db=db, query=normalized, limit=5)
        for st in statutes_found:
            st_summary = _clean_summary(st.summary_en, getattr(st, 'summary_ur', None))
            context_parts.append(
                f"- [STATUTE] {st.title} | Act No: {st.act_number or 'N/A'} | Year: {st.year or 'N/A'}\n  Summary: {st_summary}"
            )

        context = "\n".join(context_parts) if context_parts else ""

    # Generate AI response
    ai_response = await generate_response(
        user_message=request.message,
        context=context,
        language=language,
        chat_history=chat_history,
    )

    # Save assistant message
    assistant_msg = ChatMessage(
        session_id=session.id,
        role="assistant",
        content=ai_response,
        language=language,
        cited_case_ids=json.dumps(cited_ids) if cited_ids else None,
    )
    db.add(assistant_msg)
    await db.flush()

    # Build response BEFORE commit (commit can expire ORM objects)
    cited_cases = [
        CaseLawResponse(
            id=cl.id,
            citation=cl.citation,
            title=cl.title,
            court=cl.court,
            category=cl.category,
            year=cl.year,
            judge_name=cl.judge_name,
            summary_en=cl.summary_en,
            summary_ur=cl.summary_ur,
            headnotes=cl.headnotes,
            relevant_statutes=cl.relevant_statutes,
            sections_applied=cl.sections_applied,
        )
        for cl in relevant_cases
    ]

    response = ChatResponse(
        session_id=session.id,
        message=ChatMessageResponse.model_validate(assistant_msg),
        cited_cases=cited_cases,
    )

    # Commit after building response so ORM objects aren't expired
    await db.commit()

    return response


@router.post(
    "/message/stream",
    summary="Send a chat message (streaming)",
    response_description="Server-Sent Events stream of AI response chunks followed by cited cases",
)
async def send_message_stream(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Streaming version of chat. Returns Server-Sent Events for real-time token delivery.

    Event types:
    - `token`: a chunk of the AI response text
    - `citations`: JSON array of cited case laws (sent once at end)
    - `done`: signals completion, includes session_id and message_id
    """
    # Get or create session
    if request.session_id:
        result = await db.execute(
            select(ChatSession).where(
                ChatSession.id == request.session_id,
                ChatSession.user_id == current_user.id,
            )
        )
        session = result.scalar_one_or_none()
        if not session:
            raise HTTPException(status_code=404, detail="Chat session not found")
    else:
        session = ChatSession(
            user_id=current_user.id,
            title=request.message[:100],
        )
        db.add(session)
        await db.flush()

    # Detect language
    language = detect_language(request.message)

    # Save user message
    user_msg = ChatMessage(
        session_id=session.id,
        role="user",
        content=request.message,
        language=language,
    )
    db.add(user_msg)
    await db.flush()
    await db.commit()

    # Get chat history
    history_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session.id)
        .order_by(ChatMessage.created_at)
    )
    history_rows = history_result.scalars().all()
    chat_history = [{"role": msg.role, "content": msg.content} for msg in history_rows[-10:]]

    # Search for relevant case laws AND statutes (skip for greetings/casual messages)
    context_parts = []
    cited_ids = []
    cited_cases_data = []
    if not _is_casual_message(request.message):
        normalized = normalize_to_english(request.message, language)
        query_embedding = generate_embedding(normalized)
        all_cases = await _vector_search_cases(db=db, embedding=query_embedding, limit=8)
        # Keep cases above the configured similarity threshold
        relevant_cases = [cl for cl in all_cases if getattr(cl, '_similarity', 0) >= settings.SIMILARITY_THRESHOLD]

        for cl in relevant_cases:
            cited_ids.append(cl.id)
            score = getattr(cl, '_similarity', 0)
            summary = _clean_summary(cl.summary_en, cl.summary_ur)
            headnotes = (cl.headnotes or 'N/A')[:800]
            sections = cl.sections_applied or 'N/A'
            statutes = cl.relevant_statutes or 'N/A'
            judge = cl.judge_name or 'N/A'
            context_parts.append(
                f"- [Relevance: {score:.0%}] {cl.citation} | {cl.title[:150]} | Court: {cl.court.value if cl.court else 'N/A'} | "
                f"Year: {cl.year} | Judge: {judge}\n"
                f"  Summary (Outcome/Facts/Relief): {summary}\n"
                f"  Headnotes (Disposition/Observations/Principles): {headnotes}\n"
                f"  Sections/Articles/Orders/Rules: {sections}\n"
                f"  Acts/Ordinances/Statutes: {statutes}"
            )
            cited_cases_data.append({
                "id": cl.id,
                "citation": cl.citation,
                "title": cl.title,
                "court": cl.court.value if cl.court else None,
                "category": cl.category.value if cl.category else None,
                "year": cl.year,
                "judge_name": cl.judge_name,
                "summary_en": cl.summary_en,
                "summary_ur": cl.summary_ur,
                "headnotes": cl.headnotes,
                "relevant_statutes": cl.relevant_statutes,
                "sections_applied": cl.sections_applied,
            })

        # Also search statutes
        statutes_found = await _vector_search_statutes(db=db, embedding=query_embedding, limit=5)
        if not statutes_found:
            statutes_found = await _text_search_statutes(db=db, query=normalized, limit=5)
        for st in statutes_found:
            st_summary = _clean_summary(st.summary_en, getattr(st, 'summary_ur', None))
            context_parts.append(
                f"- [STATUTE] {st.title} | Act No: {st.act_number or 'N/A'} | Year: {st.year or 'N/A'}\n  Summary: {st_summary}"
            )

    context = "\n".join(context_parts) if context_parts else ""

    # Capture variables needed for the generator closure
    session_id = session.id

    async def event_generator():
        full_response = []
        async for chunk in generate_response_stream(
            user_message=request.message,
            context=context,
            language=language,
            chat_history=chat_history,
        ):
            full_response.append(chunk)
            yield f"data: {json.dumps({'type': 'token', 'content': chunk})}\n\n"

        # Send cited cases
        yield f"data: {json.dumps({'type': 'citations', 'cases': cited_cases_data})}\n\n"

        # Save assistant message to DB
        full_text = "".join(full_response)
        assistant_msg = ChatMessage(
            session_id=session_id,
            role="assistant",
            content=full_text,
            language=language,
            cited_case_ids=json.dumps(cited_ids) if cited_ids else None,
        )
        db.add(assistant_msg)
        await db.flush()
        await db.commit()

        yield f"data: {json.dumps({'type': 'done', 'session_id': session_id, 'message_id': assistant_msg.id})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/sessions",
    summary="List chat sessions",
    description="Get all chat sessions for the current user, ordered by most recent.",
)
async def get_sessions(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ChatSession)
        .where(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
    )
    sessions = result.scalars().all()
    return [
        {"id": s.id, "title": s.title, "created_at": str(s.created_at), "updated_at": str(s.updated_at)}
        for s in sessions
    ]


@router.get(
    "/sessions/{session_id}/messages",
    summary="Get session messages",
    description="Retrieve full message history of a specific chat session.",
)
async def get_session_messages(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Verify session belongs to user
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Session not found")

    messages_result = await db.execute(
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at)
    )
    messages = messages_result.scalars().all()
    return [ChatMessageResponse.model_validate(msg) for msg in messages]


@router.delete(
    "/sessions/{session_id}",
    summary="Delete a chat session",
    description="Delete a chat session and all its messages.",
)
async def delete_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(ChatSession).where(
            ChatSession.id == session_id,
            ChatSession.user_id == current_user.id,
        )
    )
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Delete all messages first
    from sqlalchemy import delete as sql_delete
    await db.execute(
        sql_delete(ChatMessage).where(ChatMessage.session_id == session_id)
    )
    await db.delete(session)
    await db.commit()
    return {"detail": "Session deleted"}
