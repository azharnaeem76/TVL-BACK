"""Ingest remaining case laws from FAMILY-CIVIL PDF (Chapter 4 Gilgit Baltistan + AJK cases)."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.services.embedding_service import generate_embeddings_batch

settings = get_settings()

CASES = [
    {
        "citation": "2016 CLC 630 Gilgit Baltistan",
        "title": "Mst. Gulzar Begum vs Mst. Bibi Zaitoon and two others",
        "court": "GILGIT_BALTISTAN_COURT",
        "category": "FAMILY",
        "year": 2016,
        "summary_en": "Petitioner/plaintiff sought a decree for 1/4th share in properties of her father Hajat Aman (late) who had only four daughters as legal heirs. Respondents/defendants contested suit on grounds of gift deeds. The donor hadn't transferred possession of suit land in favor of donees. No marginal witnesses of the gift deeds were produced by defendants and they failed to prove the gifts as valid. The impugned judgment was the result of misreading evidence. The Trail Court's evidence was restored and revision was allowed.",
        "headnotes": "Gift deed without delivery of possession, Four daughters as heirs, Marginal witnesses, Misreading of evidence",
        "sections_applied": "Transfer of Property Act, Muslim Personal Law",
        "relevant_statutes": "Transfer of Property Act, 1882",
    },
    {
        "citation": "2016 CLC 1224 Gilgit Baltistan",
        "title": "Hasan and another vs Musa",
        "court": "GILGIT_BALTISTAN_COURT",
        "category": "FAMILY",
        "year": 2016,
        "summary_en": "Plaintiffs declared they owned land measuring 21 kanals and 2 marlas through two gift deeds. The defendant contested and claimed that disputed land measuring 4 kanals and 10 marlas had devolved on him from his mother. The burden of proof shifted to plaintiffs to prove they had obtained the suit land via two gift deeds. The gift deed was not accepted as a correct and genuine document. Trial Court had passed a vague decree. Appellate Court rightly set aside the judgment.",
        "headnotes": "Gift deed proof, Burden of proof, Vague decree, Land inheritance from mother",
        "sections_applied": "Transfer of Property Act",
        "relevant_statutes": "Transfer of Property Act, 1882",
    },
    {
        "citation": "2016 MLD 586 Gilgit Baltistan",
        "title": "Yousuf vs Ghulam Abbas",
        "court": "GILGIT_BALTISTAN_COURT",
        "category": "FAMILY",
        "year": 2016,
        "summary_en": "A suit was decreed by Trial Court against which an appeal was filed. An application was moved for production of documentary evidence by defendant that was dismissed. When the defendant lost the document required to be produced, the court examined the evidentiary requirement of the deed document. The Appellate Court did not point out any irregularity in the impugned order. The revision was dismissed.",
        "headnotes": "Evidentiary requirement, Lost deed document, Production of documentary evidence",
        "sections_applied": "Civil Procedure Code, Evidence Act",
        "relevant_statutes": "Civil Procedure Code, 1908; Qanun-e-Shahadat Order, 1984",
    },
    {
        "citation": "2016 YLR 2557 Gilgit Baltistan",
        "title": "Muhammad and four others vs Rehman and 19 others",
        "court": "GILGIT_BALTISTAN_COURT",
        "category": "FAMILY",
        "year": 2016,
        "summary_en": "Suit land had been given to the parties through their forefathers and was the share of plaintiff's mother. The court examined how inherited land can be transferred in a gift deed. The defendant claimed the property was given through a gift deed but was put under burden to prove this. The Court discarded the defendant's witness statement and held that any gift of Sharai share of any person in any property was illegal until such share was separated and physical possession handed over. The Chief Court set aside the impugned decree of appellate court and declared plaintiffs entitled to suit land through their mother.",
        "headnotes": "Gift of inherited land, Sharai share must be separated, Physical possession requirement, Mother's inheritance",
        "sections_applied": "Muslim Personal Law, Transfer of Property Act",
        "relevant_statutes": "Transfer of Property Act, 1882; Muslim Personal Law (Shariat) Application Act, 1962",
    },
    {
        "citation": "2016 MLD 594 AJK",
        "title": "Muhammad Bashir vs Muhammad Sarwar and two others",
        "court": "AJK_HIGH_COURT",
        "category": "FAMILY",
        "year": 2016,
        "summary_en": "Suit property was mortgaged in favor of plaintiff by defendant. The defendant agreed to return the property by a given date and if he failed, he'd be liable to register a sale deed. The defendant did not return the amount and gifted the suit property to his sons. The gift deed was executed during pendency of suit which wasn't a valid execution. The ingredient of gift with respect to delivery of possession hadn't been fulfilled. The plaintiff was entitled to decree for specific performance. Impugned judgments were set aside.",
        "headnotes": "Gift during pendency of suit, Mortgage property gifted to sons, Specific performance, Delivery of possession not fulfilled",
        "sections_applied": "Transfer of Property Act, Specific Relief Act 1877",
        "relevant_statutes": "Transfer of Property Act, 1882; Specific Relief Act, 1877",
    },
    {
        "citation": "2016 YLR 760 AJK",
        "title": "Mst. Hassan Jan and 8 others vs Akhtar Jan and 19 others",
        "court": "AJK_HIGH_COURT",
        "category": "FAMILY",
        "year": 2016,
        "summary_en": "Both plaintiffs and defendants instituted suits against each other. Plaintiffs contended they were owners of suit property and the gift deed in favor of defendants was fictitious. The plaintiffs were in possession of the suit property and the gift deed in favor of defendants was without delivery of possession. The subsequent transaction could never be preferred over the existing one. The impugned gift deed was liable to be cancelled to the extent of property owned by plaintiffs.",
        "headnotes": "Fictitious gift deed, No delivery of possession, Prior ownership prevails, Cancellation of gift deed",
        "sections_applied": "Transfer of Property Act, Specific Relief Act 1877 S.42",
        "relevant_statutes": "Transfer of Property Act, 1882; Specific Relief Act, 1877",
    },
    {
        "citation": "2016 CLC 15 Islamabad",
        "title": "Shazia Qamar and others vs Bashiran Bibi and others",
        "court": "ISLAMABAD_HIGH_COURT",
        "category": "FAMILY",
        "year": 2016,
        "summary_en": "A suit for recovery was filed by plaintiff against defendant (her daughter in law), claiming she had loaned a suit amount to help get a study visa under an oral agreement, but the defendant refused to return this after being divorced by her son. The court found the amount was transferred as a gift based on love and affection, not a loan. The burden was on plaintiff to prove existence of oral agreement which she failed to discharge. The High Court dismissed the suit and set aside judgments of lower courts.",
        "headnotes": "Gift vs loan, Oral agreement burden of proof, Mother-in-law vs daughter-in-law, Study visa amount",
        "sections_applied": "Civil Procedure Code, Evidence Act",
        "relevant_statutes": "Civil Procedure Code, 1908; Qanun-e-Shahadat Order, 1984",
    },
    {
        "citation": "2017 YLR 925 AJK",
        "title": "Mst. Zohra Bibi and 3 others vs Ashiq Hussain and 2 others",
        "court": "AJK_SUPREME_COURT",
        "category": "FAMILY",
        "year": 2017,
        "summary_en": "Specific Relief Act (I of 1877) Sections 42, 12 and 39 of CPC. The plaintiff contended he was the owner of suit land and the gift deed was liable to be cancelled. The suit was dismissed to the extent of declaration but decreed to extent of cancellation of gift deed and specific performance of agreement to sell. The plaintiff proved his case by leading oral and documentary evidence. The defendant was bound to prove the agreement to sell was forged. The agreement to sell didn't create any title.",
        "headnotes": "Cancellation of gift deed, Specific performance, Agreement to sell creates no title, Forged document",
        "sections_applied": "Specific Relief Act 1877 S.42, S.12, S.39, CPC",
        "relevant_statutes": "Specific Relief Act, 1877; Civil Procedure Code, 1908",
    },
    {
        "citation": "2017 MLD 2051 AJK",
        "title": "Mst. Chanaan Bi and 2 others vs Muhammad Shahpal and 2 others",
        "court": "AJK_SUPREME_COURT",
        "category": "FAMILY",
        "year": 2017,
        "summary_en": "Plaintiffs contended that the gift deed had been fraudulently obtained and they were deprived of their right of inheritance. The gift deed was executed on a particular date but was entered on the revenue record after the death of the donor. The defendant failed to appear in the witness box. The gift obtained was held by a practicing fraud. The impugned gift deed couldn't be approved. The decree was granted in favor of plaintiff with the impugned gift deed being inoperative against the rights of plaintiffs.",
        "headnotes": "Fraudulent gift deed, Revenue record after death, Defendant failed to appear, Inheritance deprivation",
        "sections_applied": "Transfer of Property Act, Muslim Personal Law",
        "relevant_statutes": "Transfer of Property Act, 1882",
    },
    {
        "citation": "2017 CLC 704 AJK",
        "title": "Zahoor Ahmed vs Mohammad Siddiqui",
        "court": "AJK_SUPREME_COURT",
        "category": "FAMILY",
        "year": 2017,
        "summary_en": "A suit was filed in which a gift deed was challenged. The Trial Court decreed the suit and the respondent filed an appeal. The appeal was dismissed as compromise was effected between the parties and the gift deed was restored. Another suit was filed by plaintiff claiming the compromise was obtained fraudulently, but the suit was dismissed by the courts. The plaintiff was bound to prove fraud and deception in his evidence but failed to do so.",
        "headnotes": "Gift deed challenge, Compromise, Fraud allegation, Burden of proof on plaintiff",
        "sections_applied": "Civil Procedure Code, Transfer of Property Act",
        "relevant_statutes": "Civil Procedure Code, 1908; Transfer of Property Act, 1882",
    },
    {
        "citation": "2017 YLR Note 129 AJK",
        "title": "Muhammad Razzaq and 3 others vs Tassadaq Hussain Shah and another",
        "court": "AJK_SUPREME_COURT",
        "category": "FAMILY",
        "year": 2017,
        "summary_en": "The suit was filed by the pre-emptor three years before the disputed gift deed in favor of the defendants was registered. The suit property was transferred in favor of the defendants during the pendency of the suit. The improvements were made after the transaction of the gift deed. The Trail Court decreed the suit along with the cost of improvements but the Appellate Court disallowed such cost. The impugned judgment did not suffer from any illegality or infirmity.",
        "headnotes": "Pre-emption, Gift deed during suit pendency, Cost of improvements, Disputed gift deed registration",
        "sections_applied": "Transfer of Property Act, Pre-emption laws",
        "relevant_statutes": "Transfer of Property Act, 1882",
    },
    {
        "citation": "2019 MLD 576 AJK",
        "title": "Syed Iqbal Shah and another vs Syeda Tahira Bibi and 2 others",
        "court": "AJK_SUPREME_COURT",
        "category": "FAMILY",
        "year": 2019,
        "summary_en": "Case related to Suit for declaration regarding land given as dower to the plaintiff (wife) and also challenged the gift deed relating to the said land executed in favor of a third party. The court held that the land given as dower hadn't been abandoned by the wife, and the Civil Court was an appropriate channel to determine the matter of controversy regarding payment of dower. No mis-reading or non-reading of evidence was pointed out by the impugned judgments.",
        "headnotes": "Dower land, Gift deed of dower property to third party, Civil Court jurisdiction, Wife's dower rights",
        "sections_applied": "Specific Relief Act 1877 S.42, AJK Family Courts Act 1993 S.5",
        "relevant_statutes": "Specific Relief Act, 1877; AJK Family Courts Act, 1993",
    },
]


def main():
    engine = create_engine(settings.SYNC_DATABASE_URL, echo=False)
    with Session(engine) as db:
        existing = {row[0] for row in db.execute(text("SELECT citation FROM case_laws")).fetchall()}
        new_cases = [c for c in CASES if c["citation"] not in existing]

        if not new_cases:
            print("No new cases to ingest.")
            return

        print(f"{len(new_cases)} new cases to ingest. Generating embeddings...")
        texts = [f"{c['title']}. {c.get('summary_en', '')} {c.get('headnotes', '')} {c.get('sections_applied', '')} {c.get('relevant_statutes', '')}" for c in new_cases]
        embeddings = generate_embeddings_batch(texts)
        print(f"Generated {len(embeddings)} embeddings.")

        for i, case in enumerate(new_cases):
            db.execute(
                text("""
                    INSERT INTO case_laws (citation, title, court, category, year, summary_en, headnotes, sections_applied, relevant_statutes, embedding)
                    VALUES (:citation, :title, :court, :category, :year, :summary_en, :headnotes, :sections_applied, :relevant_statutes, :embedding)
                """),
                {**case, "embedding": json.dumps(embeddings[i])},
            )
            print(f"  [{i+1}/{len(new_cases)}] Inserted: {case['citation']}")

        db.commit()
        total = db.execute(text("SELECT COUNT(*) FROM case_laws")).scalar()
        print(f"\nDone! Inserted {len(new_cases)} cases. Total in DB: {total}")


if __name__ == "__main__":
    main()
