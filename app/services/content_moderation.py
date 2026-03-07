"""Simple content moderation to block abusive/offensive messages."""
import re

# Common abusive words and slurs (basic list - extend as needed)
BLOCKED_PATTERNS = [
    # English profanity
    r'\bf+u+c+k+\b', r'\bs+h+i+t+\b', r'\bb+i+t+c+h+\b', r'\ba+s+s+h+o+l+e+\b',
    r'\bd+a+m+n+\b', r'\bb+a+s+t+a+r+d+\b', r'\bw+h+o+r+e+\b', r'\bs+l+u+t+\b',
    r'\bd+i+c+k+\b', r'\bp+u+s+s+y+\b', r'\bc+u+n+t+\b', r'\bn+i+g+g+\w*\b',
    r'\bf+a+g+\w*\b', r'\br+e+t+a+r+d+\b',
    # Threats
    r'\bkill\s+you\b', r'\bi\s+will\s+kill\b', r'\bdeath\s+threat\b',
    r'\bI\'ll\s+murder\b', r'\bgoing\s+to\s+die\b',
    # Harassment
    r'\bkys\b', r'\bstfu\b',
    # Urdu/Roman Urdu common abusive words
    r'\bharamzada\b', r'\bharamzadi\b', r'\bkutta\b', r'\bkutiya\b',
    r'\bbhenchod\b', r'\bmadarchod\b', r'\bgandu\b', r'\bchutiya\b',
    r'\bsala\b', r'\bkamina\b', r'\bkameeni\b', r'\bharami\b',
    r'\bkanjar\b', r'\bbesharam\b',
]

COMPILED_PATTERNS = [re.compile(p, re.IGNORECASE) for p in BLOCKED_PATTERNS]


def check_content(text: str) -> tuple[bool, str | None]:
    """
    Check if text contains abusive content.
    Returns (is_clean, matched_word_or_None).
    """
    if not text:
        return True, None

    for pattern in COMPILED_PATTERNS:
        match = pattern.search(text)
        if match:
            return False, match.group()

    return True, None
