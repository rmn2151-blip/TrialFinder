"""
Conversational intake agent.

Instead of a giant static form, this service runs an adaptive Q&A loop powered
by Claude. The model chooses the next single question based on prior answers,
asks until it has enough to build a complete PatientProfile, then returns the
structured payload.

Session state is kept in memory keyed by session_id. For hackathon scope this
is fine; for production we'd use Redis or push state into the DB.
"""

import json
import logging
import os
import re
import uuid
from datetime import datetime, timedelta
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)

_ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_SESSION_TTL = timedelta(hours=1)
_MAX_TURNS = 10

# { session_id: {"turns": [...], "created_at": datetime} }
_sessions: dict[str, dict] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def start_session() -> tuple[str, str]:
    """Create a new session and return (session_id, first_question)."""
    _gc()
    session_id = uuid.uuid4().hex
    first_question = (
        "To help me find the right trials for you, I'll ask a few short "
        "questions. To start: what condition or diagnosis are you looking "
        "for trials for?"
    )
    _sessions[session_id] = {
        "turns": [{"role": "assistant", "content": first_question}],
        "created_at": datetime.utcnow(),
    }
    return session_id, first_question


def answer(session_id: str, user_answer: str) -> dict:
    """
    Record the user's answer, then either return the next question or, if the
    agent has gathered enough info, return the structured profile.
    """
    session = _sessions.get(session_id)
    if session is None:
        raise ValueError("Session not found or expired. Please start a new intake.")

    session["turns"].append({"role": "user", "content": user_answer})
    turns_so_far = sum(1 for t in session["turns"] if t["role"] == "user")

    if not _ANTHROPIC_API_KEY:
        # No LLM available — fall back to a deterministic fixed script.
        return _fallback_next(session, turns_so_far)

    decision = _ask_llm_next(session["turns"], turns_so_far)

    if decision.get("complete") and decision.get("profile"):
        session["turns"].append({
            "role": "assistant",
            "content": "Thanks — I have enough to find your trials.",
        })
        return {
            "complete": True,
            "question": None,
            "profile": _validate_profile(decision["profile"]),
            "turns_so_far": turns_so_far,
        }

    next_q = decision.get("next_question") or "Could you tell me a little more about your situation?"
    session["turns"].append({"role": "assistant", "content": next_q})
    return {
        "complete": False,
        "question": next_q,
        "profile": None,
        "turns_so_far": turns_so_far,
    }


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------


def _ask_llm_next(turns: list[dict], turns_so_far: int) -> dict:
    transcript = "\n".join(
        f"{t['role'].upper()}: {t['content']}" for t in turns
    )
    prompt = _PROMPT.format(
        transcript=transcript,
        turns_so_far=turns_so_far,
        max_turns=_MAX_TURNS,
    )

    client = anthropic.Anthropic(api_key=_ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=900,
        system=(
            "You are a friendly intake assistant for a clinical trial matching "
            "service. Respond ONLY with the JSON object specified — no prose."
        ),
        messages=[{"role": "user", "content": prompt}],
    )
    return _parse_json(msg.content[0].text)


def _parse_json(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {}


_PROMPT = """\
You are running a short adaptive intake for a clinical trial matching service.
Below is the conversation transcript so far. Decide whether you have enough
information to build a useful PatientProfile, OR ask ONE next question.

Transcript:
{transcript}

Constraints:
- You have asked the user {turns_so_far} of a maximum of {max_turns} questions.
- ALWAYS ask ONE question at a time. Keep it short and plain-language.
- Tailor what you ask next to what's already been said. For a cancer patient,
  cover staging, treatment history, biomarkers (KRAS, EGFR, HER2, BRCA, MSI, PD-L1),
  location, age, medications. For other conditions, adapt accordingly (e.g. for
  diabetes: type, A1c, current meds, prior trials of newer drugs).
- Required fields before completing: condition, location. Highly recommended:
  treatment_history (if any prior treatment), biomarkers (if oncology), age,
  medications, last_treatment_date (YYYY-MM-DD if relevant).
- If a field is unknown, that's fine — leave it out of the profile.
- When you have enough to be genuinely useful (at minimum condition + location),
  set complete=true and produce the profile.

Output ONLY this JSON shape — no prose, no markdown fences:
{{
  "complete": false,
  "next_question": "Your next single question to the user.",
  "profile": null
}}
OR, when you have enough:
{{
  "complete": true,
  "next_question": null,
  "profile": {{
    "condition": "stage 3 non-small cell lung cancer KRAS G12C",
    "treatment_history": "carboplatin + paclitaxel 6 cycles",
    "location": "New York, NY",
    "age": 58,
    "medications": ["metformin"],
    "biomarkers": ["KRAS G12C+"],
    "last_treatment_date": "2025-04-10",
    "additional_context": "ECOG 1"
  }}
}}
"""


# ---------------------------------------------------------------------------
# Fallback (no Anthropic key) — deterministic question script
# ---------------------------------------------------------------------------


_FALLBACK_SCRIPT = [
    ("condition", "What condition or diagnosis are you looking for trials for?"),
    ("location", "Where are you located (city, state, or ZIP)?"),
    ("treatment_history", "What treatments have you already tried, if any?"),
    ("biomarkers", "Any biomarker or genomic test results (e.g. KRAS G12C+, HER2+)? Type 'none' if not applicable."),
    ("age", "How old are you? Type any number, or 'skip' to skip."),
    ("medications", "Any current medications? List them separated by commas, or type 'none'."),
]


def _fallback_next(session: dict, turns_so_far: int) -> dict:
    user_answers = [t["content"] for t in session["turns"] if t["role"] == "user"]
    profile: dict = {}
    for i, (key, _) in enumerate(_FALLBACK_SCRIPT):
        if i >= len(user_answers):
            break
        val = user_answers[i].strip()
        if val.lower() in ("none", "n/a", "skip", ""):
            continue
        if key == "age":
            try:
                profile["age"] = int(val)
            except ValueError:
                pass
        elif key in ("medications", "biomarkers"):
            profile[key] = [v.strip() for v in val.split(",") if v.strip()]
        else:
            profile[key] = val

    if len(user_answers) >= len(_FALLBACK_SCRIPT):
        if "condition" in profile and "location" in profile:
            return {
                "complete": True,
                "question": None,
                "profile": _validate_profile(profile),
                "turns_so_far": turns_so_far,
            }

    next_q = _FALLBACK_SCRIPT[min(len(user_answers), len(_FALLBACK_SCRIPT) - 1)][1]
    session["turns"].append({"role": "assistant", "content": next_q})
    return {
        "complete": False,
        "question": next_q,
        "profile": None,
        "turns_so_far": turns_so_far,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _validate_profile(profile: dict) -> dict:
    """Strip empty fields + clamp medication/biomarker lists."""
    out = {}
    for k, v in profile.items():
        if v in (None, "", [], {}):
            continue
        if k in ("medications", "biomarkers") and not isinstance(v, list):
            v = [str(v)]
        out[k] = v
    return out


def _gc() -> None:
    cutoff = datetime.utcnow() - _SESSION_TTL
    for sid, sess in list(_sessions.items()):
        if sess["created_at"] < cutoff:
            _sessions.pop(sid, None)
