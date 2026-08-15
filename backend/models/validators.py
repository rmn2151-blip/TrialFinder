"""
Shared input validation and sanitization.

Threat model for this application:

  SQL injection      Not reachable through the ORM: every query goes through
                     SQLAlchemy with bound parameters. There is no string
                     concatenation into SQL anywhere in the codebase. The
                     validators here are defence in depth, not the primary
                     control.

  Command injection  No user input ever reaches a shell. There are no
                     subprocess/os.system calls in request paths.

  Script injection   The API returns JSON, and React escapes by default, so
                     stored XSS needs an explicit dangerouslySetInnerHTML,
                     which this codebase does not use. We still strip control
                     characters and cap lengths so hostile input cannot be
                     stored and later rendered somewhere unsafe (for example
                     the PDF generator or an HTML email).

  Prompt injection   Real and specific to this app: patient free-text is fed
                     to an LLM. We neutralise the common override patterns
                     and cap length so a user cannot hijack the ranking
                     instructions.

  Unsafe uploads     There are no file upload endpoints. If one is added, it
                     must validate content type, magic bytes, and size, and
                     must never write into a web-served directory.
"""

import re
import unicodedata
from typing import Optional

# Characters that have no legitimate place in patient free text and that can
# break out of log lines, CSV exports, or terminal output.
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

# Zero-width and bidirectional-override characters. These are invisible and
# have been used to smuggle hidden instructions past human review. Written as
# explicit escapes (not literal invisible bytes) so the pattern itself stays
# reviewable in a diff and doesn't trip source-level bidi-character scanners.
_INVISIBLE = re.compile(
    "[\u200b-\u200f\u202a-\u202e\u2060-\u2064\ufeff]"
)

# Patterns that attempt to override the system prompt.
# Optional filler words ("the", "all", "any") so trivial rewording does not
# slip past. Kept deliberately narrow to avoid redacting real clinical text.
_FILLER = r"(?:\s+(?:all|any|the|your|these|those|previous|prior|above|earlier))*"

_PROMPT_INJECTION = [
    re.compile(rf"ignore{_FILLER}\s+(?:instructions?|prompts?|rules?|context)", re.I),
    re.compile(rf"disregard{_FILLER}\b", re.I),
    re.compile(rf"forget{_FILLER}\s+(?:instructions?|everything|context)", re.I),
    re.compile(r"you\s+are\s+now\s+(?:a|an|the)\s+", re.I),
    re.compile(r"act\s+as\s+(?:a|an|the)\s+\w+\s+(?:instead|now)", re.I),
    re.compile(r"new\s+(?:system\s+)?(?:prompt|instructions?)\s*[:=]", re.I),
    re.compile(r"(?:reveal|show|print|repeat|output)\s+(?:your|the)\s+"
               r"(?:system\s+)?(?:prompt|instructions?)", re.I),
    re.compile(r"^\s*(?:system|assistant|developer|user)\s*[:>]", re.I | re.M),
    re.compile(r"</?(?:system|instructions?|prompt)\s*>", re.I),
    re.compile(r"\[/?INST\]|<\|im_(?:start|end)\|>|<\|endoftext\|>", re.I),
]

_REDACTION = "[removed]"


def clean_text(
    value: Optional[str],
    *,
    max_length: int = 2000,
    field: str = "input",
) -> Optional[str]:
    """
    Normalize and sanitize a free-text field.

    Returns None for empty input so optional fields stay optional.
    Raises ValueError when the input is not a string, which enforces strict
    typing at the boundary rather than silently coercing.
    """
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"{field} must be text.")

    # NFKC folds look-alike Unicode into canonical form, so filters cannot be
    # bypassed with homoglyphs.
    text = unicodedata.normalize("NFKC", value)
    text = _CONTROL_CHARS.sub("", text)
    text = _INVISIBLE.sub("", text)
    text = re.sub(r"[ \t]{3,}", "  ", text)
    text = re.sub(r"\n{4,}", "\n\n\n", text)
    text = text.strip()

    if not text:
        return None
    if len(text) > max_length:
        raise ValueError(f"{field} is too long. Limit is {max_length} characters.")
    return text


def strip_prompt_injection(value: Optional[str]) -> Optional[str]:
    """
    Neutralize attempts to hijack the LLM's instructions.

    We redact rather than reject: a real patient could plausibly write
    something that trips a pattern, and silently dropping their search would
    be worse than redacting a phrase.
    """
    if not value:
        return value
    cleaned = value
    for pattern in _PROMPT_INJECTION:
        cleaned = pattern.sub(_REDACTION, cleaned)
    return cleaned


def clean_freetext_for_llm(
    value: Optional[str], *, max_length: int = 2000, field: str = "input"
) -> Optional[str]:
    """Sanitize, then neutralize prompt injection. Use for anything sent to an LLM."""
    return strip_prompt_injection(clean_text(value, max_length=max_length, field=field))


def clean_str_list(
    values,
    *,
    max_items: int = 25,
    max_item_length: int = 120,
    field: str = "list",
) -> list[str]:
    """Validate a list of short strings (medications, biomarkers)."""
    if values is None:
        return []
    if not isinstance(values, list):
        raise ValueError(f"{field} must be a list.")
    if len(values) > max_items:
        raise ValueError(f"{field} has too many entries. Limit is {max_items}.")

    out: list[str] = []
    seen: set[str] = set()
    for item in values:
        if not isinstance(item, str):
            raise ValueError(f"Each entry in {field} must be text.")
        cleaned = clean_text(item, max_length=max_item_length, field=field)
        if not cleaned:
            continue
        cleaned = strip_prompt_injection(cleaned)
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        out.append(cleaned)
    return out


# ---------------------------------------------------------------------------
# Format validators
# ---------------------------------------------------------------------------

_NCT_RE = re.compile(r"^NCT\d{8}$")
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]{2,}$")
_SAFE_URL_RE = re.compile(r"^https://[A-Za-z0-9.\-]+(/[^\s]*)?$")


def validate_nct_id(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = str(value).strip().upper()
    if not _NCT_RE.match(value):
        raise ValueError("NCT ID must look like NCT12345678.")
    return value


def validate_email(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("Email must be text.")
    email = value.strip().lower()
    if len(email) > 320 or not _EMAIL_RE.match(email):
        raise ValueError("Please enter a valid email address.")
    return email


def safe_external_url(value: Optional[str]) -> Optional[str]:
    """
    Only allow plain https URLs.

    Blocks javascript:, data:, and file: schemes, which are the payloads used
    when a stored URL is later rendered as a clickable link.
    """
    if not value:
        return None
    url = str(value).strip()
    if not _SAFE_URL_RE.match(url) or len(url) > 2000:
        return None
    return url
