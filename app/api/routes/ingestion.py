"""
Data Ingestion API - Admin Module.

Allows administrators to upload court judgment PDFs.
The system automatically:
1. Extracts text from the PDF
2. Detects citation, court, judge, and year from the text
3. Generates an AI-powered summary using local LLM
4. Creates vector embeddings for semantic search
5. Stores everything in the database

Supports 50-60+ page documents.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.models.legal import CaseLaw, LawCategory, Court
from app.services.ingestion.ingestion_service import ingest_pdf, reprocess_case_law
from app.schemas.legal import CaseLawResponse

router = APIRouter(prefix="/ingestion", tags=["Data Ingestion (Admin)"])


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Dependency that ensures the user is an admin or lawyer (for ingestion)."""
    if user.role not in (UserRole.ADMIN, UserRole.LAWYER, UserRole.JUDGE):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only admins, lawyers, and judges can ingest documents.",
        )
    return user


@router.post(
    "/upload-pdf",
    summary="Upload a court judgment PDF for ingestion",
    description="""
Upload a PDF document (court judgment, case law, etc.) and the system will:

1. **Extract text** from all pages of the PDF
2. **Auto-detect metadata**: citation (e.g., PLD 2024 SC 123), court name, judge name, year
3. **Generate AI summary** using local LLM (Ollama) - both English and Urdu
4. **Extract headnotes**, relevant statutes, and sections applied
5. **Categorize** the case by area of law (criminal, family, property, etc.)
6. **Generate vector embedding** for semantic search
7. **Store** everything in the database

Supports documents up to 60+ pages. If metadata auto-detection fails, you can provide
overrides via the optional fields.

**Note:** If Ollama is not running, the system falls back to extractive summarization
(basic text extraction without AI analysis). You can re-process later using the
`/reprocess/{case_id}` endpoint once Ollama is set up.
    """,
    response_description="Ingestion result with case law ID, detected metadata, and any warnings",
)
async def upload_pdf(
    file: UploadFile = File(..., description="PDF file of the court judgment (supports 50-60+ page documents)"),
    citation: Optional[str] = Form(None, description="Override: case citation (e.g., 'PLD 2024 Supreme Court 123')"),
    title: Optional[str] = Form(None, description="Override: case title (e.g., 'Ali v. The State')"),
    court: Optional[str] = Form(None, description="Override: court name (e.g., 'supreme_court', 'lahore_high_court')"),
    category: Optional[str] = Form(None, description="Override: law category (e.g., 'criminal', 'family', 'property')"),
    year: Optional[int] = Form(None, description="Override: year of judgment"),
    judge_name: Optional[str] = Form(None, description="Override: presiding judge name"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    # Read file
    file_bytes = await file.read()
    if len(file_bytes) == 0:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    # Size limit: 50MB
    if len(file_bytes) > 50 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File size exceeds 50MB limit.")

    # Run ingestion pipeline
    result = await ingest_pdf(
        file_bytes=file_bytes,
        filename=file.filename,
        db=db,
        citation_override=citation,
        title_override=title,
        court_override=court,
        category_override=category,
        year_override=year,
        judge_override=judge_name,
    )

    if not result.success:
        raise HTTPException(status_code=422, detail=result.to_dict())

    return result.to_dict()


@router.post(
    "/upload-batch",
    summary="Upload multiple PDFs for batch ingestion",
    description="Upload multiple court judgment PDFs at once. Each file is processed independently.",
    response_description="List of ingestion results for each file",
)
async def upload_batch(
    files: list[UploadFile] = File(..., description="Multiple PDF files to ingest"),
    category: Optional[str] = Form(None, description="Apply this category to all uploaded files"),
    court: Optional[str] = Form(None, description="Apply this court to all uploaded files"),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    if len(files) > 20:
        raise HTTPException(status_code=400, detail="Maximum 20 files per batch.")

    results = []
    for file in files:
        if not file.filename or not file.filename.lower().endswith(".pdf"):
            results.append({
                "filename": file.filename,
                "success": False,
                "message": "Skipped: not a PDF file.",
            })
            continue

        file_bytes = await file.read()
        result = await ingest_pdf(
            file_bytes=file_bytes,
            filename=file.filename,
            db=db,
            court_override=court,
            category_override=category,
        )
        result_dict = result.to_dict()
        result_dict["filename"] = file.filename
        results.append(result_dict)

    return {
        "total": len(files),
        "successful": sum(1 for r in results if r.get("success")),
        "failed": sum(1 for r in results if not r.get("success")),
        "results": results,
    }


@router.post(
    "/reprocess/{case_id}",
    summary="Re-process an existing case law with AI",
    description="""
Re-generate the summary, headnotes, and embedding for an existing case law entry.

Useful when:
- Ollama was not running during initial ingestion (fallback summary was used)
- You've upgraded to a better LLM model
- You want to refresh the embeddings after model updates
    """,
    response_description="Re-processing result",
)
async def reprocess(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await reprocess_case_law(case_id, db)
    if not result.success:
        raise HTTPException(status_code=422, detail=result.to_dict())
    return result.to_dict()


@router.put(
    "/case-laws/{case_id}",
    summary="Update case law metadata manually",
    description="Manually update fields that were incorrectly auto-detected during ingestion.",
    response_model=CaseLawResponse,
)
async def update_case_law(
    case_id: int,
    citation: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    court: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    year: Optional[int] = Form(None),
    judge_name: Optional[str] = Form(None),
    summary_en: Optional[str] = Form(None),
    summary_ur: Optional[str] = Form(None),
    headnotes: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(select(CaseLaw).where(CaseLaw.id == case_id))
    case_law = result.scalar_one_or_none()
    if not case_law:
        raise HTTPException(status_code=404, detail="Case law not found.")

    if citation is not None:
        case_law.citation = citation
    if title is not None:
        case_law.title = title
    if court is not None:
        try:
            case_law.court = Court(court)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid court: {court}")
    if category is not None:
        try:
            case_law.category = LawCategory(category)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid category: {category}")
    if year is not None:
        case_law.year = year
    if judge_name is not None:
        case_law.judge_name = judge_name
    if summary_en is not None:
        case_law.summary_en = summary_en
    if summary_ur is not None:
        case_law.summary_ur = summary_ur
    if headnotes is not None:
        case_law.headnotes = headnotes

    # Re-generate embedding if summary or title changed
    if any(x is not None for x in [title, summary_en, headnotes]):
        from app.services.embedding_service import generate_embedding
        embedding_text = f"{case_law.title} {case_law.summary_en} {case_law.headnotes}"
        case_law.embedding = generate_embedding(embedding_text)

    return CaseLawResponse.model_validate(case_law)


@router.delete(
    "/case-laws/{case_id}",
    summary="Delete a case law entry",
    description="Permanently delete a case law from the database. This action cannot be undone.",
    status_code=status.HTTP_200_OK,
)
async def delete_case_law(
    case_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    result = await db.execute(select(CaseLaw).where(CaseLaw.id == case_id))
    case_law = result.scalar_one_or_none()
    if not case_law:
        raise HTTPException(status_code=404, detail="Case law not found.")

    await db.delete(case_law)
    return {"message": f"Case law '{case_law.citation}' deleted successfully."}


@router.get(
    "/stats",
    summary="Get ingestion statistics",
    description="Get counts of case laws by category, court, and year for admin dashboard.",
)
async def get_ingestion_stats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    # Total count
    total_result = await db.execute(select(func.count(CaseLaw.id)))
    total = total_result.scalar()

    # By category
    cat_result = await db.execute(
        select(CaseLaw.category, func.count(CaseLaw.id))
        .group_by(CaseLaw.category)
    )
    by_category = {row[0].value if row[0] else "unknown": row[1] for row in cat_result}

    # By court
    court_result = await db.execute(
        select(CaseLaw.court, func.count(CaseLaw.id))
        .group_by(CaseLaw.court)
    )
    by_court = {row[0].value if row[0] else "unknown": row[1] for row in court_result}

    # Cases without AI summary (need reprocessing)
    pending_result = await db.execute(
        select(func.count(CaseLaw.id)).where(
            CaseLaw.summary_en.is_(None) | (CaseLaw.summary_en == "")
        )
    )
    pending_summary = pending_result.scalar()

    return {
        "total_case_laws": total,
        "by_category": by_category,
        "by_court": by_court,
        "pending_ai_summary": pending_summary,
    }
