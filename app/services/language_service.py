"""
Language Detection and Normalization Service.

Handles:
- English
- Urdu (اردو)
- Roman Urdu (e.g., "mujhe talaq ka qanoon batao")
- Mixed language input common in Pakistani text messaging
"""

import re
from langdetect import detect, DetectorFactory

# Make language detection deterministic
DetectorFactory.seed = 0

# Common Roman Urdu legal terms mapped to English equivalents
ROMAN_URDU_LEGAL_TERMS = {
    # Legal concepts
    "qanoon": "law",
    "adalat": "court",
    "muqadma": "case",
    "wukeel": "lawyer",
    "vakeel": "lawyer",
    "judge": "judge",
    "faisla": "judgment",
    "saza": "punishment",
    "jurm": "crime",
    "mulzim": "accused",
    "mudai": "plaintiff",
    "gawah": "witness",
    "saboot": "evidence",
    "zamaanat": "bail",
    "bail": "bail",
    "appeal": "appeal",
    "petition": "petition",
    "darkhwast": "application",
    "haq": "right",
    "huqooq": "rights",

    # Family law
    "talaq": "divorce",
    "nikah": "marriage",
    "shadi": "marriage",
    "mehar": "dower",
    "haq mehar": "dower",
    "iddat": "iddat waiting period",
    "khula": "khula dissolution of marriage",
    "jahez": "dowry",
    "bachon ki hifazat": "child custody",
    "custody": "custody",
    "nafqa": "maintenance",
    "wirasat": "inheritance",
    "jaidad": "property",

    # Criminal law
    "qatl": "murder",
    "chori": "theft",
    "daku": "robbery",
    "daketi": "dacoity",
    "zina": "adultery",
    "qazaf": "false accusation",
    "diyat": "blood money compensation",
    "qisas": "retaliation",
    "hudood": "hudood offenses",
    "fasad": "mischief",

    # Property
    "zameen": "land",
    "makan": "house",
    "kiraya": "rent",
    "kirayedar": "tenant",
    "malik makan": "landlord",
    "intiqal": "transfer of property",
    "registry": "registration",
    "bainama": "sale deed",
    "qabza": "possession",

    # Constitutional
    "buniyadi huqooq": "fundamental rights",
    "azadi": "freedom",
    "ain": "constitution",
    "dastoor": "constitution",
    "parliament": "parliament",
    "qomi assembly": "national assembly",

    # General
    "kya": "what",
    "kaise": "how",
    "kyun": "why",
    "kab": "when",
    "kahan": "where",
    "mujhe": "I/me",
    "batao": "tell",
    "bataiye": "please tell",
    "madad": "help",
    "chahiye": "need/want",
    "kar sakta": "can do",
    "hoga": "will happen",
    "hai": "is",
    "karna": "to do",
    "ho sakta": "possible",
    "nahi": "no/not",
}

# Urdu script legal terms
URDU_LEGAL_TERMS = {
    "قانون": "law",
    "عدالت": "court",
    "مقدمہ": "case",
    "وکیل": "lawyer",
    "فیصلہ": "judgment",
    "سزا": "punishment",
    "جرم": "crime",
    "ملزم": "accused",
    "طلاق": "divorce",
    "نکاح": "marriage",
    "مہر": "dower",
    "خلع": "khula",
    "وراثت": "inheritance",
    "جائیداد": "property",
    "ضمانت": "bail",
    "گواہ": "witness",
    "ثبوت": "evidence",
    "حقوق": "rights",
    "آئین": "constitution",
    "قتل": "murder",
    "چوری": "theft",
    "زمین": "land",
    "کرایہ": "rent",
    "دعویٰ": "claim",
    "اپیل": "appeal",
    "درخواست": "application",
    "حفاظت": "custody",
    "نفقہ": "maintenance",
}


def detect_language(text: str) -> str:
    """Detect whether input is English, Urdu script, or Roman Urdu."""
    # Check for Urdu script characters
    urdu_pattern = re.compile(r"[\u0600-\u06FF\u0750-\u077F\uFB50-\uFDFF\uFE70-\uFEFF]")
    if urdu_pattern.search(text):
        return "urdu"

    # Check for Roman Urdu by looking for common Roman Urdu words
    text_lower = text.lower()
    words = text_lower.split()
    roman_urdu_count = sum(1 for word in words if word in ROMAN_URDU_LEGAL_TERMS)

    if roman_urdu_count >= 2 or (roman_urdu_count >= 1 and len(words) <= 5):
        return "roman_urdu"

    # Fall back to langdetect
    try:
        lang = detect(text)
        if lang == "ur":
            return "urdu"
        return "english"
    except Exception:
        return "english"


def normalize_to_english(text: str, language: str) -> str:
    """
    Normalize input text to English for embedding search.
    Keeps original context while adding English translations.
    """
    if language == "english":
        return text.strip()

    if language == "roman_urdu":
        return _normalize_roman_urdu(text)

    if language == "urdu":
        return _normalize_urdu(text)

    return text.strip()


def _normalize_roman_urdu(text: str) -> str:
    """Convert Roman Urdu to English using term mapping."""
    words = text.lower().split()
    translated_parts = []
    english_terms = []

    for word in words:
        clean_word = re.sub(r"[^\w]", "", word)
        if clean_word in ROMAN_URDU_LEGAL_TERMS:
            english_terms.append(ROMAN_URDU_LEGAL_TERMS[clean_word])
        else:
            translated_parts.append(word)

    # Combine: keep original + add English translations
    result = text + " | " + " ".join(english_terms) if english_terms else text
    return result.strip()


def _normalize_urdu(text: str) -> str:
    """Convert Urdu script terms to English using term mapping."""
    english_terms = []

    for urdu_term, english_term in URDU_LEGAL_TERMS.items():
        if urdu_term in text:
            english_terms.append(english_term)

    result = text + " | " + " ".join(english_terms) if english_terms else text
    return result.strip()


def get_response_language_instruction(language: str) -> str:
    """Get instruction for LLM to respond in the appropriate language."""
    if language == "urdu":
        return "Respond in Urdu script (اردو). Use legal terminology in Urdu."
    elif language == "roman_urdu":
        return "Respond in Roman Urdu (the way Pakistanis text in Urdu using English letters). Use legal terms in both Roman Urdu and English."
    return "Respond in English."
