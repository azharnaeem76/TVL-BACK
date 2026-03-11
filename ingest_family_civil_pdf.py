"""
Ingest case laws from FAMILY-CIVIL/Case-Law-Book.pdf into the database.

Women's Right to Property: Selected Case Law (Legal Aid Society, 2021)
Chapters: Khula & Divorce, Inheritance (Sunni/Shia/Hindu/Christian),
          Exclusion of Heirs, Gifts Resulting in Exclusion

Run from backend directory:
    python ingest_family_civil_pdf.py
"""

import sys
import os
import json

# Add the backend dir to path so we can import app modules
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from app.core.config import get_settings
from app.services.embedding_service import generate_embedding, generate_embeddings_batch

settings = get_settings()

# Use sync DB URL
SYNC_URL = settings.SYNC_DATABASE_URL


# ── All case laws extracted from the PDF ──────────────────────────────
CASES = [
    # ═══ CHAPTER 1: KHULA & DIVORCE ═══
    {
        "citation": "PLD 1959 Lahore 566",
        "title": "Mst. Balqis Fatima vs Najm-ul-Ikram Qureshi",
        "court": "lahore_high_court",
        "category": "family",
        "year": 1959,
        "summary_en": "Landmark case on Khula rights. The court held that a wife has the right to seek dissolution of marriage through Khula even without the husband's consent, if she is willing to return the dower/bridal gifts. Established the principle that Khula is a wife's unilateral right in Islam.",
        "headnotes": "Khula, Dissolution of marriage, Wife's right, Return of dower",
        "sections_applied": "Muslim Family Laws",
        "relevant_statutes": "Dissolution of Muslim Marriages Act, 1939",
    },
    {
        "citation": "2018 PLD 34 Peshawar",
        "title": "Khula Case - Peshawar High Court",
        "court": "peshawar_high_court",
        "category": "family",
        "year": 2018,
        "summary_en": "Case regarding Khula rights and dissolution of marriage. The court reaffirmed the wife's right to seek Khula and discussed the conditions and terms under which Khula may be granted by the Family Court.",
        "headnotes": "Khula, Dissolution of marriage, Family Court jurisdiction",
        "sections_applied": "Muslim Family Laws",
        "relevant_statutes": "Dissolution of Muslim Marriages Act, 1939; West Pakistan Family Courts Act, 1964",
    },
    {
        "citation": "2019 YLR 2298",
        "title": "Khula and Maintenance Rights",
        "court": "lahore_high_court",
        "category": "family",
        "year": 2019,
        "summary_en": "Case on Khula and related maintenance rights. The court examined the interplay between a wife's right to Khula and her entitlement to maintenance during the iddat period following dissolution.",
        "headnotes": "Khula, Maintenance, Iddat period, Dissolution of marriage",
        "sections_applied": "Muslim Family Laws",
        "relevant_statutes": "Dissolution of Muslim Marriages Act, 1939",
    },
    {
        "citation": "2019 MLD 720",
        "title": "Khula - Family Court",
        "court": "family_court",
        "category": "family",
        "year": 2019,
        "summary_en": "Family court case on Khula proceedings and the procedure for dissolution of marriage at the wife's instance. The court discussed the requirement for the wife to return benefits received from the husband.",
        "headnotes": "Khula, Family Court, Dissolution procedure, Return of benefits",
        "sections_applied": "Muslim Family Laws",
        "relevant_statutes": "West Pakistan Family Courts Act, 1964",
    },

    # ═══ BRIDAL GIFTS & DOWER ═══
    {
        "citation": "2020 PLD 269 Supreme Court",
        "title": "Bridal Gifts and Dower - Supreme Court",
        "court": "supreme_court",
        "category": "family",
        "year": 2020,
        "summary_en": "Supreme Court case on bridal gifts and dower rights. The court examined the distinction between dower (mahr) and bridal gifts, and the wife's entitlement to both. Established that dower is a wife's absolute right and cannot be waived without her genuine consent.",
        "headnotes": "Dower, Mahr, Bridal gifts, Wife's property rights",
        "sections_applied": "Muslim Personal Law, Muslim Family Laws Ordinance 1961",
        "relevant_statutes": "Muslim Family Laws Ordinance, 1961",
    },
    {
        "citation": "2019 MLD 112",
        "title": "Bridal Gifts Recovery",
        "court": "family_court",
        "category": "family",
        "year": 2019,
        "summary_en": "Case regarding recovery of bridal gifts and dower. The court discussed the wife's entitlement to recover her dower and bridal gifts upon dissolution of marriage.",
        "headnotes": "Dower recovery, Bridal gifts, Dissolution of marriage",
        "sections_applied": "Muslim Family Laws",
        "relevant_statutes": "West Pakistan Family Courts Act, 1964",
    },
    {
        "citation": "2009 YLR 1823",
        "title": "Dower Rights",
        "court": "lahore_high_court",
        "category": "family",
        "year": 2009,
        "summary_en": "High Court case on dower rights and the wife's entitlement. The court held that dower is a debt on the husband and must be paid to the wife. It remains a charge on the husband's property until fully paid.",
        "headnotes": "Dower, Mahr, Husband's debt, Wife's right",
        "sections_applied": "Muslim Personal Law",
        "relevant_statutes": "Muslim Family Laws Ordinance, 1961",
    },
    {
        "citation": "2018 CLC 1337",
        "title": "Dower and Bridal Gifts",
        "court": "lahore_high_court",
        "category": "family",
        "year": 2018,
        "summary_en": "Case regarding dower and bridal gifts. The court examined the enforceability of dower agreements and the wife's right to claim both prompt and deferred dower.",
        "headnotes": "Dower, Prompt dower, Deferred dower, Bridal gifts",
        "sections_applied": "Muslim Personal Law",
        "relevant_statutes": "Muslim Family Laws Ordinance, 1961",
    },
    {
        "citation": "2018 MLD 1811",
        "title": "Recovery of Dower",
        "court": "lahore_high_court",
        "category": "family",
        "year": 2018,
        "summary_en": "Case on recovery of dower and the procedure for claiming unpaid dower through the Family Court. The court discussed the calculation of dower and its enforceability.",
        "headnotes": "Dower recovery, Family Court jurisdiction, Mahr calculation",
        "sections_applied": "Muslim Family Laws",
        "relevant_statutes": "West Pakistan Family Courts Act, 1964",
    },

    # ═══ RETURN OF DOWRY ARTICLES ═══
    {
        "citation": "2017 SCMR 393",
        "title": "Return of Dowry Articles - Supreme Court",
        "court": "supreme_court",
        "category": "family",
        "year": 2017,
        "summary_en": "Supreme Court case on return of dowry articles. The court held that dowry articles belong to the wife and must be returned upon dissolution of marriage. The husband's family cannot retain the wife's dowry articles.",
        "headnotes": "Dowry articles, Wife's property, Return of dowry, Dissolution of marriage",
        "sections_applied": "Muslim Personal Law, Dowry and Bridal Gifts (Restriction) Act 1976",
        "relevant_statutes": "Dowry and Bridal Gifts (Restriction) Act, 1976",
    },
    {
        "citation": "2017 SCMR 321",
        "title": "Dowry Articles Recovery",
        "court": "supreme_court",
        "category": "family",
        "year": 2017,
        "summary_en": "Supreme Court ruling on recovery of dowry articles. Confirmed that dowry articles are the exclusive property of the wife and she has the right to recover them at any time.",
        "headnotes": "Dowry recovery, Wife's exclusive property, Right to recover",
        "sections_applied": "Muslim Personal Law",
        "relevant_statutes": "Dowry and Bridal Gifts (Restriction) Act, 1976",
    },
    {
        "citation": "2006 SCMR 1136",
        "title": "Dowry Articles - Supreme Court",
        "court": "supreme_court",
        "category": "family",
        "year": 2006,
        "summary_en": "Supreme Court case establishing that dowry articles are the wife's property. The court emphasized that these articles cannot be withheld by the husband or his family members.",
        "headnotes": "Dowry articles, Wife's property rights, Recovery",
        "sections_applied": "Muslim Personal Law",
        "relevant_statutes": "Dowry and Bridal Gifts (Restriction) Act, 1976",
    },
    {
        "citation": "2011 SCMR 1412",
        "title": "Dowry Recovery Case",
        "court": "supreme_court",
        "category": "family",
        "year": 2011,
        "summary_en": "Supreme Court case on dowry recovery. The court held that dowry articles listed in the dowry list (jahez list) are presumed to be the wife's property unless proven otherwise.",
        "headnotes": "Dowry list, Jahez, Presumption of ownership, Wife's property",
        "sections_applied": "Muslim Personal Law",
        "relevant_statutes": "Dowry and Bridal Gifts (Restriction) Act, 1976",
    },
    {
        "citation": "1995 SCMR 885",
        "title": "Dowry Articles Ownership",
        "court": "supreme_court",
        "category": "family",
        "year": 1995,
        "summary_en": "Supreme Court established the principle that dowry articles belong exclusively to the wife and the husband has no right over them. The burden of proof lies on the person denying the wife's ownership.",
        "headnotes": "Dowry ownership, Burden of proof, Wife's exclusive right",
        "sections_applied": "Muslim Personal Law",
        "relevant_statutes": "Dowry and Bridal Gifts (Restriction) Act, 1976",
    },
    {
        "citation": "2011 SCMR 1361",
        "title": "Recovery of Dowry - Supreme Court",
        "court": "supreme_court",
        "category": "family",
        "year": 2011,
        "summary_en": "Supreme Court case on recovery of dowry articles. The court reaffirmed that the wife's dowry articles are her stridhan (personal property) and must be returned.",
        "headnotes": "Dowry recovery, Stridhan, Personal property",
        "sections_applied": "Muslim Personal Law",
        "relevant_statutes": "Dowry and Bridal Gifts (Restriction) Act, 1976",
    },
    {
        "citation": "2012 SCMR 976",
        "title": "Dowry Articles Case",
        "court": "supreme_court",
        "category": "family",
        "year": 2012,
        "summary_en": "Supreme Court ruling on dowry articles. Held that dowry articles given to the bride at the time of marriage are her exclusive property regardless of who purchased them.",
        "headnotes": "Dowry articles, Bride's property, Marriage gifts",
        "sections_applied": "Muslim Personal Law",
        "relevant_statutes": "Dowry and Bridal Gifts (Restriction) Act, 1976",
    },
    {
        "citation": "2012 SCMR 641",
        "title": "Dowry Property Rights",
        "court": "supreme_court",
        "category": "family",
        "year": 2012,
        "summary_en": "Supreme Court case on dowry property rights. The court held that dowry articles are the wife's absolute property and she retains full ownership even after divorce.",
        "headnotes": "Dowry, Property rights, Post-divorce ownership",
        "sections_applied": "Muslim Personal Law",
        "relevant_statutes": "Dowry and Bridal Gifts (Restriction) Act, 1976",
    },
    {
        "citation": "2012 SCMR 671",
        "title": "Return of Dowry Supreme Court",
        "court": "supreme_court",
        "category": "family",
        "year": 2012,
        "summary_en": "Supreme Court case on return of dowry. Confirmed that the wife has an absolute right to her dowry articles and they must be returned in the same condition.",
        "headnotes": "Dowry return, Condition of articles, Wife's right",
        "sections_applied": "Muslim Personal Law",
        "relevant_statutes": "Dowry and Bridal Gifts (Restriction) Act, 1976",
    },
    {
        "citation": "2013 SCMR 1049",
        "title": "Dowry Articles Supreme Court",
        "court": "supreme_court",
        "category": "family",
        "year": 2013,
        "summary_en": "Supreme Court ruling reinforcing that dowry articles are the bride's exclusive property. The court examined the evidentiary requirements for proving the list and value of dowry articles.",
        "headnotes": "Dowry articles, Evidence, Proof of dowry list, Valuation",
        "sections_applied": "Muslim Personal Law",
        "relevant_statutes": "Dowry and Bridal Gifts (Restriction) Act, 1976",
    },
    {
        "citation": "2014 PLD 335 Supreme Court",
        "title": "Dowry and Gift Articles",
        "court": "supreme_court",
        "category": "family",
        "year": 2014,
        "summary_en": "Supreme Court case on dowry and gift articles. The court discussed the distinction between dowry articles and other gifts given at the time of marriage.",
        "headnotes": "Dowry vs gifts, Marriage gifts, Property distinction",
        "sections_applied": "Muslim Personal Law",
        "relevant_statutes": "Dowry and Bridal Gifts (Restriction) Act, 1976",
    },
    {
        "citation": "2016 PLD 613 Supreme Court",
        "title": "Recovery of Dowry and Gifts",
        "court": "supreme_court",
        "category": "family",
        "year": 2016,
        "summary_en": "Supreme Court case on recovery of dowry and gifts. The court examined the process for claiming and valuing dowry articles through the Family Court.",
        "headnotes": "Dowry recovery, Gift articles, Family Court procedure",
        "sections_applied": "Muslim Personal Law",
        "relevant_statutes": "Dowry and Bridal Gifts (Restriction) Act, 1976; West Pakistan Family Courts Act, 1964",
    },
    {
        "citation": "2020 CLC 380 Quetta",
        "title": "Recovery of Dowry Articles - Quetta",
        "court": "balochistan_high_court",
        "category": "family",
        "year": 2020,
        "summary_en": "Balochistan High Court case on recovery of dowry articles. The court upheld the wife's right to recover her dowry articles and discussed the procedure for enforcement of such decrees.",
        "headnotes": "Dowry recovery, Enforcement of decree, Balochistan",
        "sections_applied": "Muslim Personal Law",
        "relevant_statutes": "West Pakistan Family Courts Act, 1964",
    },

    # ═══ MAINTENANCE ═══
    {
        "citation": "2018 YLR 2586",
        "title": "Wife's Maintenance Rights",
        "court": "lahore_high_court",
        "category": "family",
        "year": 2018,
        "summary_en": "Case on wife's maintenance rights. The court held that a husband is obligated to provide maintenance to his wife and the amount should be determined based on the husband's financial capacity and the wife's reasonable needs.",
        "headnotes": "Maintenance, Wife's rights, Husband's obligation, Financial capacity",
        "sections_applied": "Muslim Personal Law, S.9 West Pakistan Family Courts Act 1964",
        "relevant_statutes": "West Pakistan Family Courts Act, 1964; Muslim Family Laws Ordinance, 1961",
    },
    {
        "citation": "2019 MLD 1936",
        "title": "Maintenance Case",
        "court": "lahore_high_court",
        "category": "family",
        "year": 2019,
        "summary_en": "Case on maintenance for wife and children. The court discussed the factors to be considered in determining the quantum of maintenance including husband's income, standard of living, and cost of living.",
        "headnotes": "Maintenance, Wife and children, Quantum determination, Standard of living",
        "sections_applied": "Muslim Personal Law",
        "relevant_statutes": "West Pakistan Family Courts Act, 1964",
    },

    # ═══ INTERIM MAINTENANCE ═══
    {
        "citation": "2009 MLD 790",
        "title": "Interim Maintenance Order",
        "court": "family_court",
        "category": "family",
        "year": 2009,
        "summary_en": "Case on interim maintenance. The court held that interim maintenance can be granted to the wife during the pendency of the suit to ensure she is not left without financial support.",
        "headnotes": "Interim maintenance, Pendente lite, Wife's support",
        "sections_applied": "S.17A West Pakistan Family Courts Act 1964",
        "relevant_statutes": "West Pakistan Family Courts Act, 1964",
    },
    {
        "citation": "2009 CLC 980",
        "title": "Interim Maintenance Rights",
        "court": "lahore_high_court",
        "category": "family",
        "year": 2009,
        "summary_en": "High Court case on interim maintenance. The court discussed the criteria for granting interim maintenance and held that it should be sufficient to meet the wife's basic needs.",
        "headnotes": "Interim maintenance, Basic needs, Criteria for grant",
        "sections_applied": "S.17A West Pakistan Family Courts Act 1964",
        "relevant_statutes": "West Pakistan Family Courts Act, 1964",
    },
    {
        "citation": "2010 YLR 3275",
        "title": "Interim Maintenance Quantum",
        "court": "lahore_high_court",
        "category": "family",
        "year": 2010,
        "summary_en": "Case on determination of quantum of interim maintenance. The court held that the Family Court has discretion to fix interim maintenance at a reasonable amount considering the circumstances.",
        "headnotes": "Interim maintenance, Quantum, Family Court discretion",
        "sections_applied": "S.17A West Pakistan Family Courts Act 1964",
        "relevant_statutes": "West Pakistan Family Courts Act, 1964",
    },
    {
        "citation": "2010 YLR 1702",
        "title": "Interim Maintenance Case",
        "court": "lahore_high_court",
        "category": "family",
        "year": 2010,
        "summary_en": "Case regarding interim maintenance for wife. The court examined the procedure for applying for interim maintenance and the time frame within which it should be decided.",
        "headnotes": "Interim maintenance, Application procedure, Time frame",
        "sections_applied": "S.17A West Pakistan Family Courts Act 1964",
        "relevant_statutes": "West Pakistan Family Courts Act, 1964",
    },
    {
        "citation": "2015 YLR 2364",
        "title": "Interim Maintenance Appeal",
        "court": "lahore_high_court",
        "category": "family",
        "year": 2015,
        "summary_en": "Case on appeal against interim maintenance order. The court held that interim maintenance orders can be challenged but should not be stayed lightly as the wife needs immediate financial support.",
        "headnotes": "Interim maintenance, Appeal, Stay order, Wife's support",
        "sections_applied": "S.17A West Pakistan Family Courts Act 1964",
        "relevant_statutes": "West Pakistan Family Courts Act, 1964",
    },

    # ═══ IDDAT MAINTENANCE ═══
    {
        "citation": "1989 SCMR 119",
        "title": "Iddat Maintenance - Supreme Court",
        "court": "supreme_court",
        "category": "family",
        "year": 1989,
        "summary_en": "Supreme Court case on iddat maintenance. The court held that maintenance during iddat is the wife's absolute right and must be paid by the husband following divorce.",
        "headnotes": "Iddat maintenance, Divorce, Husband's obligation, Wife's right",
        "sections_applied": "Muslim Personal Law",
        "relevant_statutes": "Muslim Family Laws Ordinance, 1961",
    },
    {
        "citation": "1989 SCMR 1416",
        "title": "Iddat Maintenance Rights",
        "court": "supreme_court",
        "category": "family",
        "year": 1989,
        "summary_en": "Supreme Court case on iddat maintenance rights. The court confirmed that a divorced wife is entitled to maintenance during the iddat period and the amount should reflect her standard of living during the marriage.",
        "headnotes": "Iddat maintenance, Standard of living, Divorced wife's rights",
        "sections_applied": "Muslim Personal Law",
        "relevant_statutes": "Muslim Family Laws Ordinance, 1961",
    },
    {
        "citation": "2007 SCMR 49",
        "title": "Iddat Maintenance Obligation",
        "court": "supreme_court",
        "category": "family",
        "year": 2007,
        "summary_en": "Supreme Court case on the husband's obligation to pay iddat maintenance. The court reiterated that iddat maintenance is a mandatory obligation and cannot be avoided.",
        "headnotes": "Iddat maintenance, Mandatory obligation, Cannot be waived",
        "sections_applied": "Muslim Personal Law",
        "relevant_statutes": "Muslim Family Laws Ordinance, 1961",
    },
    {
        "citation": "2016 SCMR 2069",
        "title": "Iddat Maintenance Quantum",
        "court": "supreme_court",
        "category": "family",
        "year": 2016,
        "summary_en": "Supreme Court case on quantum of iddat maintenance. The court discussed the factors for determining the amount of maintenance during iddat period.",
        "headnotes": "Iddat maintenance, Quantum determination, Period of iddat",
        "sections_applied": "Muslim Personal Law",
        "relevant_statutes": "Muslim Family Laws Ordinance, 1961",
    },

    # ═══ CHAPTER 2: SUNNI INHERITANCE ═══
    {
        "citation": "2018 MLD 1982",
        "title": "Sunni Inheritance Distribution",
        "court": "lahore_high_court",
        "category": "family",
        "year": 2018,
        "summary_en": "Case on Sunni inheritance distribution. The court examined the rules of inheritance under Sunni (Hanafi) law and the shares allocated to various heirs including daughters, wives, and mothers.",
        "headnotes": "Sunni inheritance, Hanafi law, Shares of heirs, Daughters' rights",
        "sections_applied": "Muslim Personal Law (Shariat) Application Act 1962, S.2-A",
        "relevant_statutes": "Muslim Personal Law (Shariat) Application Act, 1962",
    },
    {
        "citation": "PLD 2018 379 Lahore",
        "title": "Inheritance Shares Under Sunni Law",
        "court": "lahore_high_court",
        "category": "family",
        "year": 2018,
        "summary_en": "Lahore High Court case on inheritance shares under Sunni law. The court discussed the fixed shares (fard) allocated to various heirs and the residuary (asaba) distribution system.",
        "headnotes": "Sunni inheritance, Fixed shares, Fard, Asaba, Residuary heirs",
        "sections_applied": "Muslim Personal Law",
        "relevant_statutes": "Muslim Personal Law (Shariat) Application Act, 1962",
    },
    {
        "citation": "2018 PLD 803 Lahore",
        "title": "Tahira Bibi Petitioner vs Muhammad Khan & Others",
        "court": "lahore_high_court",
        "category": "family",
        "year": 2018,
        "summary_en": "Case involving inheritance dispute and gift deeds used to exclude legal heirs. The plaintiff challenged gift mutations as fraudulent, made to deprive her of inheritance from her deceased father. The court examined whether the deceased followed Shia or Sunni school and the burden of proof for validity of gift deeds. Impugned gift mutations were declared illegal and plaintiff was entitled to her legal share as per Sunni school of inheritance.",
        "headnotes": "Inheritance dispute, Gift deed fraud, Shia vs Sunni inheritance, Burden of proof, Exclusion of female heirs",
        "sections_applied": "Muslim Personal Law, Transfer of Property Act 1882 S.129",
        "relevant_statutes": "Muslim Personal Law (Shariat) Application Act, 1962; Transfer of Property Act, 1882",
    },
    {
        "citation": "2016 MLD 185",
        "title": "Sunni Inheritance Case",
        "court": "lahore_high_court",
        "category": "family",
        "year": 2016,
        "summary_en": "Case on Sunni inheritance distribution and the rights of female heirs. The court discussed the mandatory nature of Islamic inheritance law and that no heir can be deprived of their share.",
        "headnotes": "Sunni inheritance, Female heirs' rights, Mandatory shares",
        "sections_applied": "Muslim Personal Law (Shariat) Application Act 1962",
        "relevant_statutes": "Muslim Personal Law (Shariat) Application Act, 1962",
    },

    # ═══ SHIA INHERITANCE ═══
    {
        "citation": "2016 SCMR 1195",
        "title": "Shia Inheritance - Supreme Court",
        "court": "supreme_court",
        "category": "family",
        "year": 2016,
        "summary_en": "Supreme Court case on Shia inheritance rules. The court examined the differences between Sunni and Shia inheritance systems, particularly regarding the shares of daughters and widows under Shia (Jafari) jurisprudence.",
        "headnotes": "Shia inheritance, Jafari law, Daughters' shares, Differences from Sunni law",
        "sections_applied": "Muslim Personal Law",
        "relevant_statutes": "Muslim Personal Law (Shariat) Application Act, 1962",
    },
    {
        "citation": "PLD 2016 865 Lahore",
        "title": "Shia Inheritance Distribution",
        "court": "lahore_high_court",
        "category": "family",
        "year": 2016,
        "summary_en": "Lahore High Court case on Shia inheritance distribution. The court discussed the Shia rules of inheritance and how they differ from Sunni rules, particularly that under Shia law daughters can inherit the entire estate in the absence of sons.",
        "headnotes": "Shia inheritance, Daughter inheriting entire estate, Jafari jurisprudence",
        "sections_applied": "Muslim Personal Law",
        "relevant_statutes": "Muslim Personal Law (Shariat) Application Act, 1962",
    },

    # ═══ HINDU INHERITANCE ═══
    {
        "citation": "2019 CLC 1159 Karachi",
        "title": "Hindu Inheritance - Sindh High Court",
        "court": "sindh_high_court",
        "category": "family",
        "year": 2019,
        "summary_en": "Sindh High Court case on Hindu inheritance rights in Pakistan. The court examined the Hindu law of succession and the rights of Hindu women to inherit property.",
        "headnotes": "Hindu inheritance, Hindu women's rights, Succession in Pakistan",
        "sections_applied": "Hindu Law, Succession Act 1925",
        "relevant_statutes": "Succession Act, 1925",
    },
    {
        "citation": "PLD 2016 Sindh 197",
        "title": "Mrs. Ratna Devi W/O Justice (Retd.) Rana Bhagwandas",
        "court": "sindh_high_court",
        "category": "family",
        "year": 2016,
        "summary_en": "Succession Act 1925, Section 372. Hindu law of succession. The deceased's property was to devolve upon legal heirs. Under Hindu law, daughters couldn't inherit father's property during mother's lifetime. The widow took limited interest (widow's estate), and after her demise, estate would be inherited by next heirs. The widow filed an affidavit giving her estate to sons and other legal heirs. Application for grant of succession certificate and letters of administration was allowed.",
        "headnotes": "Hindu succession, Widow's estate, Limited interest, Succession certificate, Daughters' inheritance",
        "sections_applied": "Succession Act 1925 S.372",
        "relevant_statutes": "Succession Act, 1925",
    },

    # ═══ CHRISTIAN INHERITANCE ═══
    {
        "citation": "1992 PLD 385 Supreme Court",
        "title": "Innayat Bibi vs Issac Nazir Ullah",
        "court": "supreme_court",
        "category": "family",
        "year": 1992,
        "summary_en": "Christian women brought an inheritance claim seeking the fundamental right to inheritance. The court held that Christian females were allowed to inherit in presence of male heirs. The Succession Act 1925, by statutory dispensation, determined the mode of succession when a Christian male died, and neither the custom nor any other law would be applicable. This also abolished customary law in Punjab for Christians.",
        "headnotes": "Christian inheritance, Female inheritance rights, Succession Act 1925, Customary law abolished",
        "sections_applied": "Succession Act 1925 S.29",
        "relevant_statutes": "Succession Act, 1925",
    },
    {
        "citation": "2016 YLR 2721 Board of Revenue Punjab",
        "title": "Bashir Alam and Others vs Marthan and Others",
        "court": "district_court",
        "category": "family",
        "year": 2016,
        "summary_en": "Case regarding exclusion of female heirs in favour of male heirs in a Christian family. Land measuring 100-kanals was allotted to Nawab Masih. After his death, sons got sanctioned inheritance mutation, depriving daughters. The court held that both male and female offspring are entitled to succession of the deceased, relying on PLD 1992 SC 385. Customary law excluding female Christian heirs was struck down.",
        "headnotes": "Christian inheritance, Female exclusion, Customary law, Equal inheritance rights, Colonization of Government Lands Act 1912 S.20",
        "sections_applied": "Colonization of Government Lands Act 1912 S.20, Succession Act 1925 S.29",
        "relevant_statutes": "Succession Act, 1925; Colonization of Government Lands Act, 1912",
    },
    {
        "citation": "2006 CLC 1099 Karachi",
        "title": "Zubair Hussain Siddqui vs Mst. Shakeela Khanum and Others",
        "court": "sindh_high_court",
        "category": "family",
        "year": 2006,
        "summary_en": "Case on whether a Muslim woman who married a non-Muslim man can be denied inheritance from her deceased Muslim father. The court held that a Muslim female marrying a Christian shall not become non-Muslim merely by fact of such marriage though it would be a sinful act, and shall not be deprived of right of inheritance from her Muslim parents. The mere assertion of embracing Islam is sufficient proof of conversion.",
        "headnotes": "Interfaith marriage, Muslim inheritance, Conversion to Islam, Inheritance rights not lost by marriage to non-Muslim",
        "sections_applied": "Islamic Law, Succession Act 1925",
        "relevant_statutes": "Succession Act, 1925",
    },

    # ═══ CHAPTER 3: EXCLUSION OF HEIRS - WOMEN ═══
    {
        "citation": "1976 PLD 119 Lahore",
        "title": "Hidayat Shah vs Murad Khatun",
        "court": "lahore_high_court",
        "category": "family",
        "year": 1976,
        "summary_en": "The husband wished to divorce his wife before he passed away. The issue was whether she would be entitled to inheritance if the husband died during her Iddat. The court held that Marazul Maut is a question of facts and the woman was not to be deprived of inheritance if the husband dies within the period of iddat.",
        "headnotes": "Inheritance during Iddat, Marazul Maut, Divorce before death, Wife's inheritance rights",
        "sections_applied": "Muslim Personal Law",
        "relevant_statutes": "Muslim Family Laws Ordinance, 1961",
    },
    {
        "citation": "1990 PLD 1 Supreme Court",
        "title": "Ghulam Ali vs Ghulam Sarwar Naqvi",
        "court": "supreme_court",
        "category": "family",
        "year": 1990,
        "summary_en": "Landmark case on women's right to inheritance. The brother tried to claim adverse possession against his sister, claiming they had spent money on her weddings and in a murder case for five years, hence she had relinquished her right. The court held that a woman cannot relinquish her right to inheritance as it is against public policy in Islam. This is a pivotal case on brother's right to claim adverse possession against sister, duty to maintain a divorced or widowed sister, and moral basis of brother ousting sister from property.",
        "headnotes": "Women's inheritance, Adverse possession, Right cannot be relinquished, Public policy in Islam, Brother vs sister property dispute",
        "sections_applied": "Muslim Personal Law, Limitation Act",
        "relevant_statutes": "Muslim Personal Law (Shariat) Application Act, 1962",
    },
    {
        "citation": "1992 PLD 811 Supreme Court",
        "title": "Fazal Jan vs Roshan Din",
        "court": "supreme_court",
        "category": "family",
        "year": 1992,
        "summary_en": "The claimant in the inheritance case was a woman who did not possess the mental capacity to possess and manage property. The Supreme Court granted leave to appeal and ordered that the petitioner be provided with legal assistance through engagement of a competent counsel at State expenses, as there was possibility that others might have taken undue advantage of her incapacity.",
        "headnotes": "Mental incapacity, Inheritance rights, Legal aid, State-funded counsel, Protection of vulnerable heirs",
        "sections_applied": "Constitutional Law, Muslim Personal Law",
        "relevant_statutes": "Constitution of Pakistan 1973",
    },
    {
        "citation": "1999 MLD 2934 Karachi",
        "title": "Halima vs Muhammad Kassam",
        "court": "sindh_high_court",
        "category": "family",
        "year": 1999,
        "summary_en": "Five daughters of the deceased brought a claim against the widow, sons and son's children for property bought in the name of defendants, claiming it was a Benami Transaction and should be included in the estate. The court held that in Benami transactions, the real owner must prove it were his funds used to purchase the property. The burden to prove a property is benami is on the real owner. Justice Shaiq Usamani spoke of a male dominated society taking advantage of Islamic inheritance laws.",
        "headnotes": "Benami transaction, Inheritance, Daughters' claim, Burden of proof, Male dominated society",
        "sections_applied": "Transfer of Property Act, Benami Transactions",
        "relevant_statutes": "Transfer of Property Act, 1882; Benami Transactions (Prohibition) Act",
    },
    {
        "citation": "2010 PLD 569 Supreme Court",
        "title": "Ghulam Murtaza vs Asia Bibi",
        "court": "supreme_court",
        "category": "family",
        "year": 2010,
        "summary_en": "Husband and wife after separating contended ownership of property. The property was bought in the name of the wife and the husband wished to retrieve it. The court held that a transaction will only be held Benami if the motive of buyer who made it on behalf of another was to retrieve the property. The High Court declared the case in favour of the wife. The Supreme Court upheld the decision of the High Court and dismissed the appeal.",
        "headnotes": "Benami transaction, Property in wife's name, Husband's claim, Motive for Benami",
        "sections_applied": "Transfer of Property Act",
        "relevant_statutes": "Transfer of Property Act, 1882",
    },
    {
        "citation": "2003 SCMR 1535",
        "title": "Muhammad Yousuf vs Mst. Karam Khatoon",
        "court": "supreme_court",
        "category": "family",
        "year": 2003,
        "summary_en": "Property dispute where a daughter claimed inheritance from her father who died in 1923-24. The Male heir who had acquired agricultural land under custom from a Muslim prior to 15th March 1948 would be deemed to have inherited the same under Muslim Law. Under S.2-A of West Pakistan Muslim Personal Law (Shariat) Application Act 1962, female heirs derived limited interest from male heirs. Karam Khatoon was entitled to inherit directly from her father Ali and subsequently from her mother.",
        "headnotes": "Customary law vs Islamic law, Female inheritance, S.2-A Shariat Application Act, Agricultural land, Limited interest",
        "sections_applied": "West Pakistan Muslim Personal Law (Shariat) Application Act 1962 S.2-A, S.4, S.5",
        "relevant_statutes": "Muslim Personal Law (Shariat) Application Act, 1962",
    },
    {
        "citation": "2003 SCMR 362",
        "title": "Mst. Ghulam Janat vs Ghulam Janat",
        "court": "supreme_court",
        "category": "family",
        "year": 2003,
        "summary_en": "In 1930, sons were to be given the inheritance share, excluding the daughter who filed suit for her share. The court held that Section 2-A of West Pakistan Personal Law (Shariat) Application Act 1962 was retrospective in its operation, and inheritance would be deemed to have devolved on date of death of last male owner on all his heirs under Islamic Law, who would be deemed to have become joint owners.",
        "headnotes": "Retrospective application, Shariat Act 1962, Joint ownership, Daughters' inheritance, Pre-partition customary law",
        "sections_applied": "West Pakistan Muslim Personal Law (Shariat) Application Act 1962 S.2-A",
        "relevant_statutes": "Muslim Personal Law (Shariat) Application Act, 1962",
    },
    {
        "citation": "2014 SCMR 801",
        "title": "Mst. Gohar Khanum vs Mst. Jamila Jan",
        "court": "supreme_court",
        "category": "family",
        "year": 2014,
        "summary_en": "The property was mutated only to the brother's name with exclusion of sister. The brother alleged that his sister was fully aware and did not challenge it for fifty years. The court held that in order to relinquish or transfer interest in property, there had to be a positive and affirmative act. No document or deed of relinquishment was brought on record. The sister came to own 1/3rd of the property by operation of law and not by any mutation. Erroneous mutation in favour of the brother only would not create title in his favour.",
        "headnotes": "Relinquishment of inheritance, Positive affirmative act required, Mutation not equal to title, Sister's inheritance, Time bar not applicable",
        "sections_applied": "Muslim Personal Law, Sharia Law of Inheritance",
        "relevant_statutes": "Muslim Personal Law (Shariat) Application Act, 1962",
    },
    {
        "citation": "2017 MLD 1567 Lahore",
        "title": "Muhammad Siddique vs Mst. Kaniz Fatima",
        "court": "lahore_high_court",
        "category": "family",
        "year": 2017,
        "summary_en": "The plaintiff filed suit for her share out of the legacy left by her father. The brothers contended that no custom existed to give anything from inheritance to daughters at the time of death. The court held that the heir of any deceased would become owner to the extent of his/her share by operation of law the moment the predecessor died and that no limitation would run against claim of inheritance. Sale transactions/alienations made by defendants were declared illegal and unlawful.",
        "headnotes": "No limitation on inheritance claims, Heir becomes owner at death, Custom cannot override Shariat, Sham transactions declared illegal",
        "sections_applied": "Muslim Personal Law, Limitation Act",
        "relevant_statutes": "Muslim Personal Law (Shariat) Application Act, 1962; Limitation Act, 1908",
    },
    {
        "citation": "2018 PLD 819 Lahore",
        "title": "Khalida Idrees vs Anas Farooq Chaudhry",
        "court": "lahore_high_court",
        "category": "family",
        "year": 2018,
        "summary_en": "After death of the father (Ahmadi by faith), two sisters were excluded by their only brother who claimed the property was transferred via gift deed. The court held that deprivation of women folk from their due share in property through Will deed, gift/Tamleek deed or under the garb of custom, family honour, regional culture as well as under coercion were common, and courts were saddled with unalienable obligation to show extraordinary circumspection. The appellants were entitled to receive half the property.",
        "headnotes": "Ahmadi inheritance, Gift deed to exclude sisters, Women's share, Custom cannot override law, Extraordinary circumspection by courts",
        "sections_applied": "Muslim Personal Law, Transfer of Property Act",
        "relevant_statutes": "Muslim Personal Law (Shariat) Application Act, 1962; Transfer of Property Act, 1882",
    },
    {
        "citation": "2020 SCMR 1618",
        "title": "Mst. Brikhna vs Faiz Ullah Khan",
        "court": "supreme_court",
        "category": "family",
        "year": 2020,
        "summary_en": "The sister/petitioner was one of the legal heirs of the deceased father and became entitled to inherit the legacy from the day her father died, becoming co-sharer/co-owner. The brother contended she was not a real daughter. The Respondent failed to establish this. The Petitioner was entitled to her due Sharai share which came to 1/7. The court observed that people belonging from certain regions normally avoid giving their daughters/sisters their due shares in inheritance.",
        "headnotes": "Daughters' inheritance, Co-ownership by operation of law, 1/7 Sharai share, Regional customs excluding women",
        "sections_applied": "Muslim Personal Law, Sharia Law",
        "relevant_statutes": "Muslim Personal Law (Shariat) Application Act, 1962",
    },
    {
        "citation": "2020 SCMR 72",
        "title": "Basheer Ahmed vs Mst. Fatima Bibi (Deceased)",
        "court": "supreme_court",
        "category": "family",
        "year": 2020,
        "summary_en": "Upon death of original tenant, his two sons succeeded to the tenancy rights to the exclusion of three daughters under S.20 of the Colonization of Government Lands (Punjab) Act 1912. When both sons died in 1940, under S.21(b) the succession was determined as though the original tenant had died, and all heirs (including three daughters) became entitled to a share under Islamic law of inheritance. The court held that the Plaintiff was entitled, as a daughter, to an appropriate share in the tenancy devolving from her father.",
        "headnotes": "Government land tenancy, Daughters' exclusion reversed, S.20 vs S.21, Islamic law of inheritance, Colonization Act",
        "sections_applied": "Colonization of Government Lands (Punjab) Act 1912 S.20, S.21",
        "relevant_statutes": "Colonization of Government Lands (Punjab) Act, 1912",
    },

    # ═══ TRANSGENDER PERSONS ═══
    {
        "citation": "2018 PLD 54 Lahore",
        "title": "Mian Asia vs Federation of Pakistan through Secretary Finance and 2 others",
        "court": "lahore_high_court",
        "category": "human_rights",
        "year": 2018,
        "summary_en": "A transgender person wished to renew their CNIC which did not contain the father's name. The court held that gender identity is one of the most essential aspects of life and everyone is entitled to enjoy all human rights without discrimination. Being citizens of Pakistan, transgender/eunuchs were worthy of respect and safeguarding of their fundamental rights. The High Court directed that copies of the judgment be forwarded to Federal and Provincial Secretary Law to ensure maximum benefit to transgender community.",
        "headnotes": "Transgender rights, CNIC, Gender identity, Fundamental rights, Non-discrimination, Constitutional protection",
        "sections_applied": "Constitution of Pakistan 1973, Articles 4, 9, 14, 25",
        "relevant_statutes": "Constitution of Pakistan, 1973; Transgender Persons (Protection of Rights) Act, 2018",
    },
    {
        "citation": "2013 SCMR 187",
        "title": "Dr. Muhammad Aslam Khaki and another vs Senior Superintendent of Police (Operation) Rawalpindi and Others",
        "court": "supreme_court",
        "category": "human_rights",
        "year": 2013,
        "summary_en": "Petition filed to protect Eunuchs from unfair treatment in Pakistan and grant them all rights provided under the constitution. The Supreme Court held that as eunuchs were citizens of Pakistan, they were fully deserving of all the rights that the Constitution granted including right to life, dignity, respect and protection, without any discrimination whatsoever. Federal and Provincial governments were directed to ensure all rights of eunuchs were granted and safeguarded.",
        "headnotes": "Eunuch rights, Constitutional protection, Right to life and dignity, Non-discrimination, Transgender persons",
        "sections_applied": "Constitution of Pakistan 1973, Articles 4, 9, 14, 25",
        "relevant_statutes": "Constitution of Pakistan, 1973",
    },

    # ═══ CHAPTER 4: GIFTS RESULTING IN EXCLUSION ═══
    {
        "citation": "2017 CLC 1601 Lahore",
        "title": "Mst. Kausar Bibi vs Mst. Ayesha Bibi",
        "court": "lahore_high_court",
        "category": "family",
        "year": 2017,
        "summary_en": "Mukhtar Ahmed died in 1990 leaving behind six daughters and a son. After death, the son claimed the land had been orally gifted to him in his father's life time and inheritance mutations were attested. The court held that no female heirs may be excluded. The brother along with his wife were attempting to get away with fraud. Quran verse 4:11 on inheritance was cited. The court held that fraud vitiates all solemn act and any instrument obtained through fraud is a nullity.",
        "headnotes": "Oral gift fraud, Exclusion of female heirs, Quranic verse 4:11, Fraud vitiates all, Inheritance mutations",
        "sections_applied": "Muslim Personal Law, Quran Surah Al-Nisaa 4:11-12",
        "relevant_statutes": "Muslim Personal Law (Shariat) Application Act, 1962",
    },
    {
        "citation": "2005 SCMR 1859",
        "title": "Arshad Khan vs Mst. Resham Jan and others",
        "court": "supreme_court",
        "category": "family",
        "year": 2005,
        "summary_en": "Sisters of defendant disputed mutation of gift attested in favour of defendant on grounds of fraud, forgery and misrepresentation. The court held that express or oral relinquishment of right of a female heir in inherited property in favour of male heir, through gift or any other legal device, takes effect only if such transaction was not denied and/or disputed by the female heir. The onus would be on the person claiming its genuineness. The defendant was under legal obligation to protect his sisters' right in the property.",
        "headnotes": "Gift deed to exclude sisters, Onus on claimant, Female heir's relinquishment, Fraud and forgery, Brother's moral duty",
        "sections_applied": "Muslim Personal Law, Transfer of Property Act",
        "relevant_statutes": "Transfer of Property Act, 1882; Muslim Personal Law (Shariat) Application Act, 1962",
    },
    {
        "citation": "2005 SCMR 135",
        "title": "Mst. Kulsoom Bibi and another vs Muhammad Arif",
        "court": "supreme_court",
        "category": "family",
        "year": 2005,
        "summary_en": "Mst. Kulsoom Bibi widow of Muhammad Fazil and her son filed a suit challenging a registered gift-deed through which property was transferred to the brothers by way of gift. The alleged donor was diabetic, heart patient and on his deathbed. The court held that three ingredients of gift must be proved: proposal, acceptance and delivery of possession. The gift was held fraudulent and the very gift becomes non-existent and nullified, regardless of whether it was made during Marz-ul-Maut or otherwise.",
        "headnotes": "Gift deed challenge, Three ingredients of gift, Proposal acceptance delivery, Marz-ul-Maut, Deathbed gift, Fraud",
        "sections_applied": "Transfer of Property Act 1882 S.129, S.123",
        "relevant_statutes": "Transfer of Property Act, 1882",
    },
    {
        "citation": "2008 PLD 73 Supreme Court",
        "title": "Allah Diwaya vs Ghulam Fatima",
        "court": "supreme_court",
        "category": "family",
        "year": 2008,
        "summary_en": "A gift deed was challenged as unenforceable as it was not registered and possession had not been handed over. The court noted that under section 129 of the Transfer of Property Act 1882, it was permissible under Muslim Law to make an oral gift or even through an unregistered document where essential ingredients of gift were otherwise satisfied. However, the appellant failed to prove the factum of gift and execution. The gift deed was compulsorily registerable under section 17 of the Registration Act.",
        "headnotes": "Unregistered gift deed, Section 129 Transfer of Property Act, Oral gift in Muslim Law, Registration requirement, Factum of gift",
        "sections_applied": "Transfer of Property Act 1882 S.129, S.123, Registration Act S.17",
        "relevant_statutes": "Transfer of Property Act, 1882; Registration Act, 1908",
    },
    {
        "citation": "2010 SCMR 342",
        "title": "Muhammad Ejaz vs Mst. Khalida Awan",
        "court": "supreme_court",
        "category": "family",
        "year": 2010,
        "summary_en": "Respondent Mst. Khalida Awan claimed ownership of suit house on basis of unregistered gift deed executed by her deceased father, to exclusion of her brother and three sisters. The court held that gifts under Muslim Law were excluded from Transfer of Property Act 1882 by virtue of section 129. However, plaintiff failed to prove she had accepted gift or possession was given. Three elements of gift must be present: declaration by donor, acceptance by donee, and delivery of possession. No valid gift of property could be made in absence of these three essential ingredients.",
        "headnotes": "Gift deed excluding siblings, Three elements of gift, Declaration acceptance delivery, Unregistered gift deed, Muslim Law gift",
        "sections_applied": "Transfer of Property Act 1882 S.129",
        "relevant_statutes": "Transfer of Property Act, 1882",
    },
    {
        "citation": "2016 SCMR 662",
        "title": "Mst. Saadia vs Mst. Gul Bibi",
        "court": "supreme_court",
        "category": "family",
        "year": 2016,
        "summary_en": "The prerequisites for a valid gift i.e. offer, acceptance and delivery of possession was not proved. There was non-examination of attesting witnesses of the gift deeds. Interested witnesses were called to prove the execution of purported gift deeds. Non-production of original gift deeds along with the plaint. Gift deeds couldn't be termed as valid in such circumstances.",
        "headnotes": "Invalid gift deed, Prerequisites of gift, Non-examination of witnesses, Non-production of originals",
        "sections_applied": "Transfer of Property Act 1882, Muslim Personal Law",
        "relevant_statutes": "Transfer of Property Act, 1882",
    },
    {
        "citation": "2017 MLD 689 Lahore",
        "title": "Mst. Sardaran Bibi vs Mst. Allah Rakhi",
        "court": "lahore_high_court",
        "category": "family",
        "year": 2017,
        "summary_en": "Plaintiffs filed suit on the ground that suit property was owned by the father (deceased) and defendants-real sisters orally gifted the suit property in favour of plaintiff. The court held that plaintiff had failed to fulfill the mandatory requirements of an oral gift as no specific date, time and place was mentioned. Women who were weaker segment of society were not to be deprived of their right of inheritance in the name of custom or by emotionally exploiting them.",
        "headnotes": "Oral gift requirements, Date time place, Women's inheritance protection, Custom exploitation",
        "sections_applied": "Muslim Personal Law, Transfer of Property Act",
        "relevant_statutes": "Transfer of Property Act, 1882; Muslim Personal Law (Shariat) Application Act, 1962",
    },
    {
        "citation": "2018 SCMR 139",
        "title": "Fareed and others vs Muhammad Tufail and another",
        "court": "supreme_court",
        "category": "family",
        "year": 2018,
        "summary_en": "Case related to the exclusion of a legal heir through a gift deed. The court held that the donee claiming under a gift that excluded an heir was required by law to establish an original transaction of gift irrespective of whether such a transaction was evidenced by a registered deed. A gift deed must justify the disinheritance of an heir from the gift.",
        "headnotes": "Gift deed excluding heir, Donee must prove original transaction, Disinheritance through gift",
        "sections_applied": "Transfer of Property Act, Muslim Personal Law",
        "relevant_statutes": "Transfer of Property Act, 1882",
    },
    {
        "citation": "2018 SCMR 30",
        "title": "Mrs. Khalida Azhar vs Viqar Rustam Bakhshi",
        "court": "supreme_court",
        "category": "family",
        "year": 2018,
        "summary_en": "The appellant (sister) contended that their deceased father left behind a house, which her brother (respondent) managed to get transferred in his name via a forged gift deed and power of attorney. The court found that among the executants, only the appellant had denied execution of the document after 26 years. Multiple witnesses stated the brother did not forcefully get the house. The appellants' challenge to the authenticity of the gift deed wasn't sustainable after 26 years.",
        "headnotes": "Forged gift deed allegation, Power of attorney, Challenge after 26 years, Limitation on challenging gift",
        "sections_applied": "Transfer of Property Act, Limitation Act",
        "relevant_statutes": "Transfer of Property Act, 1882; Limitation Act, 1908",
    },
    {
        "citation": "2018 PLD 698 Supreme Court",
        "title": "Bilal Hussain Shah and another vs Dilawar Shah",
        "court": "supreme_court",
        "category": "family",
        "year": 2018,
        "summary_en": "Case related to a gift deed whereby proof of execution of document required by law is to be attested. The court held that the provision of calling two attesting witnesses to prove execution of document can be waived if it was duly registered according to the provisions of Registration Act 1908 and its execution wasn't specifically denied.",
        "headnotes": "Gift deed attestation, Two witnesses requirement, Waiver if registered, Registration Act 1908",
        "sections_applied": "Registration Act 1908, Transfer of Property Act",
        "relevant_statutes": "Registration Act, 1908; Transfer of Property Act, 1882",
    },
    {
        "citation": "2018 MLD 1090 Lahore",
        "title": "Muhammad Mushtaq Bhutta through legal heirs vs Ch. Muhammad Jameel and 6 others",
        "court": "lahore_high_court",
        "category": "family",
        "year": 2018,
        "summary_en": "Plaintiff brought a case against the donee for a gift received through misrepresentation and fraud, claiming that the mental condition of the deceased was unstable at the time the deed was formed. The suit was dismissed concurrently. The plaintiff failed to prove via any cogent evidence that the deceased was under any mental disability at the time of execution of the gift deed, nor produced any doctor or medical record.",
        "headnotes": "Mental capacity at time of gift, Burden of proof, Medical evidence required, Gift deed challenge",
        "sections_applied": "Transfer of Property Act, Evidence Act",
        "relevant_statutes": "Transfer of Property Act, 1882; Qanun-e-Shahadat Order, 1984",
    },
    {
        "citation": "2019 CLC 1710 Peshawar",
        "title": "Shafi Ur Rehman vs Aziz ur Rehman and Others",
        "court": "peshawar_high_court",
        "category": "family",
        "year": 2019,
        "summary_en": "The plaintiff contended that the gift deed was based on fraud and misrepresentation. The gift deed wasn't affected in presence of the defendant and didn't have his signature or thumb impression. The defendant didn't plead that the gifted property was given out of love and affection, and failed to prove the factum of gift. The High Court observed that the impugned gift deed was fraudulent and was never executed. The revision was dismissed.",
        "headnotes": "Fraudulent gift deed, No signature of donee, Factum of gift not proved, Love and affection not pleaded",
        "sections_applied": "Transfer of Property Act, Specific Relief Act 1877 S.42",
        "relevant_statutes": "Transfer of Property Act, 1882; Specific Relief Act, 1877",
    },
    {
        "citation": "2017 YLR Note 198 Supreme Court AJK",
        "title": "Muhammad Maqbool and 3 others vs Muhammad Younas and another",
        "court": "supreme_court",
        "category": "family",
        "year": 2017,
        "summary_en": "The plaintiffs contended that the donor/mother of the defendant was the only predeceased son's daughter to whom no property was supposed to be devolved through inheritance. According to Islamic law, not more than 1/3rd of the property can be gifted by deed during the life of the donee. The Trial Court correctly reached the conclusion that the donor wasn't competent to execute the gift deed of the whole property in favor of her sons.",
        "headnotes": "Gift limited to 1/3rd of property, Islamic law limitation on gift, Competence of donor",
        "sections_applied": "Muslim Personal Law, Transfer of Property Act",
        "relevant_statutes": "Transfer of Property Act, 1882",
    },
]


def parse_court(court_str: str) -> str:
    """Map court string to Court enum value."""
    mapping = {
        "supreme_court": "supreme_court",
        "lahore_high_court": "lahore_high_court",
        "sindh_high_court": "sindh_high_court",
        "peshawar_high_court": "peshawar_high_court",
        "balochistan_high_court": "balochistan_high_court",
        "islamabad_high_court": "islamabad_high_court",
        "district_court": "district_court",
        "family_court": "family_court",
        "session_court": "session_court",
        "federal_shariat_court": "federal_shariat_court",
    }
    return mapping.get(court_str, "district_court")


def main():
    engine = create_engine(SYNC_URL, echo=False)

    with Session(engine) as db:
        # Check existing citations to avoid duplicates
        result = db.execute(text("SELECT citation FROM case_laws"))
        existing = {row[0] for row in result.fetchall()}
        print(f"Found {len(existing)} existing case laws in DB.")

        new_cases = []
        for case in CASES:
            if case["citation"] in existing:
                print(f"  SKIP (exists): {case['citation']}")
                continue
            new_cases.append(case)

        if not new_cases:
            print("No new cases to ingest. All already exist in DB.")
            return

        print(f"\n{len(new_cases)} new cases to ingest. Generating embeddings...")

        # Build embedding texts (combine citation + title + summary + headnotes for rich embedding)
        texts = []
        for c in new_cases:
            embed_text = f"{c['title']}. {c.get('summary_en', '')} {c.get('headnotes', '')} {c.get('sections_applied', '')} {c.get('relevant_statutes', '')}"
            texts.append(embed_text)

        embeddings = generate_embeddings_batch(texts)
        print(f"Generated {len(embeddings)} embeddings.")

        # Insert into DB
        inserted = 0
        for i, case in enumerate(new_cases):
            emb_json = json.dumps(embeddings[i])
            db.execute(
                text("""
                    INSERT INTO case_laws
                        (citation, title, court, category, year, summary_en, headnotes,
                         sections_applied, relevant_statutes, embedding)
                    VALUES
                        (:citation, :title, :court, :category, :year, :summary_en, :headnotes,
                         :sections_applied, :relevant_statutes, :embedding)
                """),
                {
                    "citation": case["citation"],
                    "title": case["title"],
                    "court": case["court"].upper(),
                    "category": case["category"].upper(),
                    "year": case["year"],
                    "summary_en": case.get("summary_en"),
                    "headnotes": case.get("headnotes"),
                    "sections_applied": case.get("sections_applied"),
                    "relevant_statutes": case.get("relevant_statutes"),
                    "embedding": emb_json,
                },
            )
            inserted += 1
            print(f"  [{inserted}/{len(new_cases)}] Inserted: {case['citation']}")

        db.commit()
        print(f"\nDone! Inserted {inserted} new case laws with embeddings.")

        # Verify count
        result = db.execute(text("SELECT COUNT(*) FROM case_laws"))
        total = result.scalar()
        print(f"Total case laws in DB: {total}")


if __name__ == "__main__":
    main()
