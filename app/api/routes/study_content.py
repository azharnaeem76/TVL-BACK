"""Admin-managed study content: quiz questions, study notes, past papers."""
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from typing import Optional
from pydantic import BaseModel, Field
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, UserRole
from app.models.study_content import StudyContent, ContentType

router = APIRouter(prefix="/study-content", tags=["Study Content"])

CATEGORIES = [
    "Constitutional", "Criminal", "Civil", "Family", "Property",
    "Contract", "Evidence", "Labour", "Cyber", "Islamic",
    "International", "Administrative", "Jurisprudence", "General",
]


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ContentCreate(BaseModel):
    content_type: str = Field(..., description="quiz_question, study_note, or past_paper")
    title: str = Field(..., min_length=3, max_length=500)
    category: str = Field("General", max_length=100)
    exam_type: Optional[str] = None
    difficulty: Optional[str] = None
    content: Optional[str] = None  # For notes/past papers
    question_data: Optional[dict] = None  # For quiz questions


class ContentUpdate(BaseModel):
    title: Optional[str] = None
    category: Optional[str] = None
    exam_type: Optional[str] = None
    difficulty: Optional[str] = None
    content: Optional[str] = None
    question_data: Optional[dict] = None
    is_published: Optional[bool] = None


class ContentResponse(BaseModel):
    id: int
    content_type: str
    title: str
    category: str
    exam_type: Optional[str] = None
    difficulty: Optional[str] = None
    content: Optional[str] = None
    question_data: Optional[dict] = None
    is_published: bool
    created_by: int
    created_at: Optional[str] = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------

async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(status_code=403, detail="Admin required")
    return current_user


# ---------------------------------------------------------------------------
# Public: Read content (students)
# ---------------------------------------------------------------------------

@router.get("/questions", summary="Get quiz questions (published)")
async def get_questions(
    category: Optional[str] = Query(None),
    exam_type: Optional[str] = Query(None),
    difficulty: Optional[str] = Query(None),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base = select(StudyContent).where(
        StudyContent.content_type == ContentType.QUIZ_QUESTION,
        StudyContent.is_published == True,
    )
    if category:
        base = base.where(StudyContent.category == category)
    if exam_type:
        base = base.where(StudyContent.exam_type == exam_type)
    if difficulty:
        base = base.where(StudyContent.difficulty == difficulty)

    rows = (await db.execute(base.order_by(func.random()).limit(limit))).scalars().all()

    return [
        {
            "id": r.id,
            "category": r.category,
            "difficulty": r.difficulty,
            "exam_type": r.exam_type,
            **(r.question_data or {}),
        }
        for r in rows
    ]


@router.get("/notes", summary="Get study notes (published)")
async def get_notes(
    category: Optional[str] = Query(None),
    exam_type: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=50),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base = select(StudyContent).where(
        StudyContent.content_type.in_([ContentType.STUDY_NOTE, ContentType.PAST_PAPER]),
        StudyContent.is_published == True,
    )
    count_q = select(func.count(StudyContent.id)).where(
        StudyContent.content_type.in_([ContentType.STUDY_NOTE, ContentType.PAST_PAPER]),
        StudyContent.is_published == True,
    )
    if category:
        base = base.where(StudyContent.category == category)
        count_q = count_q.where(StudyContent.category == category)
    if exam_type:
        base = base.where(StudyContent.exam_type == exam_type)
        count_q = count_q.where(StudyContent.exam_type == exam_type)
    if search:
        like = f"%{search}%"
        base = base.where(StudyContent.title.ilike(like))
        count_q = count_q.where(StudyContent.title.ilike(like))

    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(
        base.order_by(StudyContent.created_at.desc()).offset(skip).limit(limit)
    )).scalars().all()

    return {
        "items": [
            {
                "id": r.id,
                "content_type": r.content_type.value,
                "title": r.title,
                "category": r.category,
                "exam_type": r.exam_type,
                "content": r.content,
                "created_at": str(r.created_at) if r.created_at else None,
            }
            for r in rows
        ],
        "total": total,
    }


@router.get("/categories", summary="List available categories")
async def list_categories(current_user: User = Depends(get_current_user)):
    return CATEGORIES


# ---------------------------------------------------------------------------
# Admin: CRUD content
# ---------------------------------------------------------------------------

@router.get("/admin/all", summary="List all content (admin)")
async def admin_list_content(
    content_type: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    base = select(StudyContent)
    count_q = select(func.count(StudyContent.id))
    if content_type:
        base = base.where(StudyContent.content_type == content_type)
        count_q = count_q.where(StudyContent.content_type == content_type)
    if category:
        base = base.where(StudyContent.category == category)
        count_q = count_q.where(StudyContent.category == category)

    total = (await db.execute(count_q)).scalar() or 0
    rows = (await db.execute(
        base.order_by(StudyContent.created_at.desc()).offset(skip).limit(limit)
    )).scalars().all()

    return {
        "items": [
            {
                "id": r.id,
                "content_type": r.content_type.value,
                "title": r.title,
                "category": r.category,
                "exam_type": r.exam_type,
                "difficulty": r.difficulty,
                "content": r.content[:200] if r.content else None,
                "question_data": r.question_data,
                "is_published": r.is_published,
                "created_at": str(r.created_at) if r.created_at else None,
            }
            for r in rows
        ],
        "total": total,
    }


@router.post("/admin/create", summary="Create content (admin)")
async def admin_create_content(
    payload: ContentCreate,
    db: AsyncSession = Depends(get_db),
    admin: User = Depends(require_admin),
):
    if payload.content_type not in ["quiz_question", "study_note", "past_paper"]:
        raise HTTPException(status_code=400, detail="Invalid content type")

    if payload.content_type == "quiz_question" and not payload.question_data:
        raise HTTPException(status_code=400, detail="question_data is required for quiz questions")

    if payload.content_type == "quiz_question" and payload.question_data:
        qd = payload.question_data
        if not qd.get("question") or not qd.get("options") or qd.get("correct") is None:
            raise HTTPException(status_code=400, detail="question_data must include question, options, and correct")

    item = StudyContent(
        content_type=ContentType(payload.content_type),
        title=payload.title,
        category=payload.category,
        exam_type=payload.exam_type,
        difficulty=payload.difficulty,
        content=payload.content,
        question_data=payload.question_data,
        created_by=admin.id,
    )
    db.add(item)
    await db.flush()
    await db.refresh(item)

    return {"id": item.id, "title": item.title, "content_type": item.content_type.value}


@router.put("/admin/{item_id}", summary="Update content (admin)")
async def admin_update_content(
    item_id: int,
    payload: ContentUpdate,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    item = (await db.execute(select(StudyContent).where(StudyContent.id == item_id))).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")

    for field in ["title", "category", "exam_type", "difficulty", "content", "question_data", "is_published"]:
        val = getattr(payload, field)
        if val is not None:
            setattr(item, field, val)

    await db.flush()
    await db.refresh(item)
    return {"ok": True, "id": item.id}


@router.delete("/admin/{item_id}", summary="Delete content (admin)")
async def admin_delete_content(
    item_id: int,
    db: AsyncSession = Depends(get_db),
    _admin: User = Depends(require_admin),
):
    item = (await db.execute(select(StudyContent).where(StudyContent.id == item_id))).scalar_one_or_none()
    if not item:
        raise HTTPException(status_code=404, detail="Content not found")
    await db.delete(item)
    return {"ok": True}


# ---------------------------------------------------------------------------
# Seed data
# ---------------------------------------------------------------------------

SEED_QUESTIONS = [
    # Constitutional Law
    {"title": "Fundamental Rights - Article 9", "category": "Constitutional", "exam_type": "llb", "difficulty": "easy",
     "question_data": {"question": "Article 9 of the Constitution of Pakistan 1973 deals with:", "options": ["Right to life and liberty", "Freedom of speech", "Right to education", "Freedom of movement"], "correct": 0, "explanation": "Article 9 states: No person shall be deprived of life or liberty save in accordance with law."}},
    {"title": "Amendment Power", "category": "Constitutional", "exam_type": "llb", "difficulty": "medium",
     "question_data": {"question": "Under the Constitution of Pakistan, the power to amend the Constitution lies with:", "options": ["The President", "The Parliament", "The Supreme Court", "The Prime Minister"], "correct": 1, "explanation": "Article 239 of the Constitution grants the Parliament the power to amend the Constitution by a two-thirds majority."}},
    {"title": "Judicial Review", "category": "Constitutional", "exam_type": "judiciary", "difficulty": "hard",
     "question_data": {"question": "Which article of the Constitution of Pakistan 1973 provides for the writ jurisdiction of the High Court?", "options": ["Article 184", "Article 185", "Article 199", "Article 203"], "correct": 2, "explanation": "Article 199 empowers each High Court to issue writs including habeas corpus, mandamus, prohibition, quo warranto, and certiorari."}},
    {"title": "President's Powers", "category": "Constitutional", "exam_type": "css_law", "difficulty": "medium",
     "question_data": {"question": "The President of Pakistan can dissolve the National Assembly under:", "options": ["Article 48", "Article 58", "Article 90", "Article 112"], "correct": 1, "explanation": "Article 58 deals with the dissolution of the National Assembly, which can be done by the President on the advice of the Prime Minister."}},

    # Criminal Law
    {"title": "PPC Section 302 - Murder", "category": "Criminal", "exam_type": "bar", "difficulty": "easy",
     "question_data": {"question": "Section 302 of the Pakistan Penal Code deals with:", "options": ["Theft", "Qatl-i-amd (intentional murder)", "Hurt", "Robbery"], "correct": 1, "explanation": "Section 302 PPC prescribes punishment for Qatl-i-amd which means intentional causing of death."}},
    {"title": "Right of Private Defence", "category": "Criminal", "exam_type": "llb", "difficulty": "medium",
     "question_data": {"question": "The right of private defence of body under PPC extends to causing death in cases mentioned in:", "options": ["Section 96", "Section 100", "Section 102", "Section 106"], "correct": 1, "explanation": "Section 100 PPC lists the situations where the right of private defence extends to causing death, including assault giving reasonable apprehension of death."}},
    {"title": "Bail Provisions CrPC", "category": "Criminal", "exam_type": "judiciary", "difficulty": "hard",
     "question_data": {"question": "Under Section 497 CrPC, bail in non-bailable offences can be granted when:", "options": ["The offence is punishable with death only", "There are reasonable grounds to believe the accused is not guilty", "The accused is a minor only", "The FIR has been quashed"], "correct": 1, "explanation": "Section 497 CrPC allows bail when there are reasonable grounds for believing that the accused is not guilty of an offence punishable with death or imprisonment for life."}},

    # Civil Law
    {"title": "CPC - Res Judicata", "category": "Civil", "exam_type": "llb", "difficulty": "medium",
     "question_data": {"question": "The principle of Res Judicata is embodied in which section of CPC?", "options": ["Section 9", "Section 10", "Section 11", "Section 12"], "correct": 2, "explanation": "Section 11 CPC embodies the principle of Res Judicata which prevents re-litigation of issues already decided between the same parties."}},
    {"title": "Limitation Period - Suit for Money", "category": "Civil", "exam_type": "bar", "difficulty": "easy",
     "question_data": {"question": "The limitation period for filing a suit for recovery of money under the Limitation Act is:", "options": ["1 year", "2 years", "3 years", "6 years"], "correct": 2, "explanation": "Under Article 46 of the Limitation Act 1908, the period for filing a suit for money is 3 years from the date when the amount becomes due."}},

    # Evidence Law
    {"title": "Burden of Proof", "category": "Evidence", "exam_type": "lat", "difficulty": "easy",
     "question_data": {"question": "Under Article 117 of Qanun-e-Shahadat 1984, the burden of proof lies on:", "options": ["The person who denies a fact", "The person who asserts a fact", "The court", "The prosecution only"], "correct": 1, "explanation": "Article 117 states that the burden of proof lies on the person who would fail if no evidence were given on either side."}},
    {"title": "Dying Declaration", "category": "Evidence", "exam_type": "judiciary", "difficulty": "hard",
     "question_data": {"question": "A dying declaration is admissible under which Article of Qanun-e-Shahadat Order 1984?", "options": ["Article 38", "Article 46", "Article 47", "Article 48"], "correct": 2, "explanation": "Article 47 deals with the relevancy of dying declarations when the statement is made by a person about the cause of death or circumstances of the transaction resulting in death."}},

    # Contract Law
    {"title": "Valid Contract Elements", "category": "Contract", "exam_type": "llb", "difficulty": "easy",
     "question_data": {"question": "Under the Contract Act 1872, which is NOT an essential element of a valid contract?", "options": ["Free consent", "Lawful consideration", "Written document", "Competent parties"], "correct": 2, "explanation": "A written document is not always essential for a valid contract. Section 10 requires: free consent, competent parties, lawful consideration, and lawful object."}},
    {"title": "Void Agreement", "category": "Contract", "exam_type": "bar", "difficulty": "medium",
     "question_data": {"question": "An agreement in restraint of trade under Section 27 of the Contract Act 1872 is:", "options": ["Voidable", "Valid", "Void", "Illegal"], "correct": 2, "explanation": "Section 27 declares every agreement in restraint of trade to be void, except for sale of goodwill with reasonable restrictions."}},

    # Family Law
    {"title": "Khula in Muslim Law", "category": "Family", "exam_type": "llb", "difficulty": "medium",
     "question_data": {"question": "Under Muslim Family Laws Ordinance 1961, Khula is a form of dissolution of marriage at the instance of:", "options": ["The husband", "The wife", "The court only", "The arbitration council"], "correct": 1, "explanation": "Khula is a right of the wife to seek dissolution of marriage by returning the dower (mahr) or other consideration to the husband."}},

    # GAT/LAT General
    {"title": "Pakistan Legal System", "category": "General", "exam_type": "lat", "difficulty": "easy",
     "question_data": {"question": "The highest court of Pakistan is:", "options": ["High Court", "Federal Shariat Court", "Supreme Court", "District Court"], "correct": 2, "explanation": "The Supreme Court of Pakistan, established under Article 176 of the Constitution, is the apex court of the country."}},
    {"title": "Sources of Law", "category": "Jurisprudence", "exam_type": "gat_law", "difficulty": "medium",
     "question_data": {"question": "Which is considered a primary source of law in Pakistan?", "options": ["Textbooks", "Legislation", "Legal journals", "Law commission reports"], "correct": 1, "explanation": "Legislation enacted by Parliament is a primary source of law. Textbooks and journals are secondary sources used for interpretation."}},
    {"title": "International Law - Sovereignty", "category": "International", "exam_type": "css_law", "difficulty": "medium",
     "question_data": {"question": "The concept of state sovereignty in international law was established by:", "options": ["Treaty of Versailles 1919", "Treaty of Westphalia 1648", "UN Charter 1945", "Vienna Convention 1961"], "correct": 1, "explanation": "The Peace of Westphalia (1648) is generally considered as establishing the modern concept of state sovereignty and the principle of non-interference."}},
]

SEED_NOTES = [
    {"title": "Constitutional Law - Fundamental Rights Overview", "category": "Constitutional", "exam_type": "llb",
     "content": "<h2>Fundamental Rights (Articles 8-28)</h2><p>The Constitution of Pakistan 1973 guarantees fundamental rights in Part II, Chapter 1.</p><h3>Key Articles:</h3><ul><li><strong>Article 8:</strong> Laws inconsistent with fundamental rights are void</li><li><strong>Article 9:</strong> Security of person - no deprivation of life or liberty except in accordance with law</li><li><strong>Article 10:</strong> Safeguards as to arrest and detention</li><li><strong>Article 10A:</strong> Right to fair trial (inserted by 18th Amendment)</li><li><strong>Article 14:</strong> Inviolability of dignity of man and privacy of home</li><li><strong>Article 17:</strong> Freedom of association</li><li><strong>Article 19:</strong> Freedom of speech</li><li><strong>Article 25:</strong> Equality of citizens</li></ul><h3>Enforcement:</h3><p>Under Article 199, any citizen can approach the High Court for enforcement of fundamental rights through writ jurisdiction.</p>"},
    {"title": "Criminal Procedure - Bail Essentials", "category": "Criminal", "exam_type": "bar",
     "content": "<h2>Bail Provisions under CrPC</h2><h3>Types of Bail:</h3><ol><li><strong>Pre-arrest bail (Section 498 CrPC):</strong> Anticipatory bail granted before arrest</li><li><strong>Post-arrest bail (Section 497 CrPC):</strong> Granted after arrest in non-bailable offences</li><li><strong>Bail in bailable offences (Section 496):</strong> As of right</li></ol><h3>Key Principles:</h3><ul><li>Bail is the rule, jail is the exception</li><li>Reasonable grounds to believe accused not guilty of offence punishable with death/life imprisonment</li><li>Further inquiry into guilt is required</li><li>Accused is not previously convicted of similar offence</li></ul><h3>Cancellation of Bail:</h3><p>Section 497(5) CrPC allows cancellation when accused misuses bail, tampers with evidence, or absconds.</p>"},
    {"title": "Contract Act 1872 - Key Concepts", "category": "Contract", "exam_type": "llb",
     "content": "<h2>Contract Act 1872 - Essential Concepts</h2><h3>Formation of Contract (Section 10):</h3><p>All agreements are contracts if made by free consent of competent parties, for a lawful consideration and lawful object.</p><h3>Important Definitions:</h3><ul><li><strong>Offer (Section 2a):</strong> Proposal to do or abstain from doing an act</li><li><strong>Acceptance (Section 2b):</strong> When the person to whom the proposal is made signifies assent</li><li><strong>Consideration (Section 2d):</strong> Something in return - quid pro quo</li><li><strong>Void Agreement (Section 2g):</strong> An agreement not enforceable by law</li></ul><h3>Vitiating Factors:</h3><ul><li>Coercion (Section 15)</li><li>Undue Influence (Section 16)</li><li>Fraud (Section 17)</li><li>Misrepresentation (Section 18)</li><li>Mistake (Sections 20-22)</li></ul>"},
    {"title": "Evidence Law - Hearsay Rule", "category": "Evidence", "exam_type": "judiciary",
     "content": "<h2>Hearsay Evidence under Qanun-e-Shahadat 1984</h2><h3>General Rule:</h3><p>Hearsay evidence is generally inadmissible as it lacks the safeguards of oath, cross-examination, and demeanor observation.</p><h3>Exceptions:</h3><ol><li><strong>Dying Declaration (Article 47):</strong> Statement by person about cause of death</li><li><strong>Statement against interest (Article 46):</strong> Statement against pecuniary or proprietary interest</li><li><strong>Entries in books of account (Article 36):</strong> Regularly kept in the course of business</li><li><strong>Public documents (Articles 85-88):</strong> Government records and official documents</li></ol><h3>Modern Developments:</h3><p>Electronic evidence under the Prevention of Electronic Crimes Act 2016 has expanded the scope of admissible evidence.</p>"},
]

SEED_PAST_PAPERS = [
    {"title": "LLB Part I - Constitutional Law 2024", "category": "Constitutional", "exam_type": "llb",
     "content": "<h2>LLB Part I - Constitutional Law</h2><h3>Annual Examination 2024</h3><p><em>Time: 3 Hours | Maximum Marks: 100</em></p><h3>Part A - MCQs (20 Marks)</h3><ol><li>The Preamble of the Constitution of Pakistan 1973 declares Pakistan as:<br/>a) Secular Republic b) Islamic Republic c) Federal Republic d) Democratic Republic</li><li>Fundamental Rights are enshrined in which Part of the Constitution?<br/>a) Part I b) Part II Chapter 1 c) Part III d) Part IV</li></ol><h3>Part B - Short Questions (40 Marks)</h3><ol><li>Define the concept of Parliamentary Sovereignty under the Constitution of Pakistan.</li><li>Explain the procedure of amendment of the Constitution under Article 239.</li><li>Discuss the grounds for disqualification of members under Article 63.</li><li>What is the significance of Article 10A (Right to Fair Trial)?</li></ol><h3>Part C - Essay Questions (40 Marks)</h3><ol><li>Critically analyze the role of the Supreme Court in protecting fundamental rights through Article 184(3).</li><li>Discuss the impact of the 18th Amendment on the federal structure of Pakistan.</li></ol>"},
    {"title": "Bar Council Exam - Criminal Law 2023", "category": "Criminal", "exam_type": "bar",
     "content": "<h2>Bar Council Licensing Examination</h2><h3>Criminal Law & Procedure - 2023</h3><p><em>Time: 3 Hours | Maximum Marks: 100</em></p><h3>Section A (30 Marks)</h3><ol><li>Define Qatl-i-amd under PPC. What are the various punishments prescribed for it?</li><li>Explain the right of private defence of body and property under PPC.</li><li>Discuss the provisions relating to bail in non-bailable offences under CrPC.</li></ol><h3>Section B (40 Marks)</h3><ol><li>Draft an application for pre-arrest bail under Section 498 CrPC with all necessary grounds.</li><li>Explain the procedure for filing an FIR and its evidentiary value.</li></ol><h3>Section C (30 Marks)</h3><ol><li>A is charged with murder of B. The only evidence is a dying declaration made by B to C. Discuss the admissibility and evidentiary value of this dying declaration.</li></ol>"},
    {"title": "LAT Sample Paper - Legal Aptitude 2024", "category": "General", "exam_type": "lat",
     "content": "<h2>HEC Law Admission Test (LAT)</h2><h3>Sample Paper 2024</h3><p><em>Time: 2 Hours | Total MCQs: 100</em></p><h3>Section 1: Legal Aptitude (40 Questions)</h3><ol><li>The rule of law means:<br/>a) Government by laws b) Government by people c) Supremacy of law over arbitrary power d) All of the above</li><li>Which organ of the state interprets the Constitution?<br/>a) Legislature b) Executive c) Judiciary d) Military</li><li>The age of majority under the Majority Act 1875 is:<br/>a) 16 years b) 18 years c) 21 years d) 25 years</li></ol><h3>Section 2: Pakistan Studies (30 Questions)</h3><ol><li>The Lahore Resolution was passed in:<br/>a) 1938 b) 1940 c) 1942 d) 1946</li></ol><h3>Section 3: English Comprehension (30 Questions)</h3><p><em>Read the passage and answer questions...</em></p>"},
]


async def seed_study_content(db):
    """Seed dummy study content if table is empty."""
    from app.models.user import User, UserRole
    count = (await db.execute(select(func.count(StudyContent.id)))).scalar() or 0
    if count > 0:
        return  # already seeded

    # Find an admin user to set as creator
    admin = (await db.execute(
        select(User).where(User.role == UserRole.ADMIN).limit(1)
    )).scalar_one_or_none()
    admin_id = admin.id if admin else 1

    # Seed quiz questions
    for q in SEED_QUESTIONS:
        db.add(StudyContent(
            content_type=ContentType.QUIZ_QUESTION,
            title=q["title"],
            category=q["category"],
            exam_type=q.get("exam_type"),
            difficulty=q.get("difficulty"),
            question_data=q["question_data"],
            created_by=admin_id,
        ))

    # Seed study notes
    for n in SEED_NOTES:
        db.add(StudyContent(
            content_type=ContentType.STUDY_NOTE,
            title=n["title"],
            category=n["category"],
            exam_type=n.get("exam_type"),
            content=n["content"],
            created_by=admin_id,
        ))

    # Seed past papers
    for p in SEED_PAST_PAPERS:
        db.add(StudyContent(
            content_type=ContentType.PAST_PAPER,
            title=p["title"],
            category=p["category"],
            exam_type=p.get("exam_type"),
            content=p["content"],
            created_by=admin_id,
        ))

    await db.flush()
