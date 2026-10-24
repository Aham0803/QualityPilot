"""
Data Standardization Utilities for MDM Entity Matching.
Performs deterministic field normalization: trimming, lowercasing, punctuation stripping,
phone digit normalization, and blocking key creation.
"""

import re
from typing import Optional

def clean_text(text: Optional[str]) -> str:
    """Trim, lowercase, and collapse multiple whitespaces."""
    if text is None or not isinstance(text, str):
        return ""
    # Strip non-alphanumeric except whitespace
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    return " ".join(cleaned.split())

DUMMY_EMAILS = {"abc@@invalid.domain..com", "missing_at_symbol.com", "null", "none", "nan"}

def normalize_email(email: Optional[str]) -> str:
    """Lowercase, strip whitespace, and ignore known corrupted defect placeholders."""
    if email is None:
        return ""
    em = str(email).strip().lower()
    if em in DUMMY_EMAILS or "@" not in em or "@@" in em or ".." in em:
        return ""
    return em

def normalize_phone(phone: Optional[str]) -> str:
    """Extract only trailing 10 digits and ignore dummy repeated digits."""
    if phone is None:
        return ""
    digits = re.sub(r"\D", "", str(phone))
    normalized = digits[-10:] if len(digits) >= 10 else digits
    # Filter dummy strings like 9999999999 or 0000000000
    if len(set(normalized)) <= 1 or len(normalized) < 10:
        return ""
    return normalized

def normalize_postal(postal: Optional[str]) -> str:
    """Extract standard 5-6 digit postal code."""
    if postal is None:
        return ""
    digits = re.sub(r"\D", "", str(postal))
    return digits[:6]

def generate_blocking_key(name: str, postal: str) -> str:
    """
    Generate efficient blocking key (e.g., first 3 letters of name + first 3 digits of postal).
    Drastically reduces pair comparisons from O(N^2) to within-block subsets.
    """
    clean_n = clean_text(name).replace(" ", "")
    n_prefix = clean_n[:3].ljust(3, "x")
    p_prefix = normalize_postal(postal)[:3].ljust(3, "0")
    return f"{n_prefix}_{p_prefix}"
