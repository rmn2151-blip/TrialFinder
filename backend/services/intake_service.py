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

from services import llm_provider

logger = logging.getLogger(__name__)

_SESSION_TTL = timedelta(hours=1)

# Hard ceiling on questions. This is enforced in code, not just requested in
# the prompt: a model that keeps finding "one more thing" to ask will happily
# loop forever otherwise.
_MAX_TURNS = int(os.getenv("INTAKE_MAX_TURNS", "7"))

# Answers that mean "I don't want to answer this".
#
# This must match the WHOLE message, not a prefix. "no prior chemo but I had
# surgery" begins with "no" yet carries real clinical information, and
# treating it as a refusal would silently discard the patient's answer.
_DECLINE_PATTERNS = re.compile(
    r"^\s*(?:"
    r"no|nope|nah|none|n/?a|skip|pass|idk|i don'?t know|i dont know|"
    r"not sure|unsure|prefer not(?: to say| to answer)?|rather not|"
    r"no thanks?|nothing|don'?t have (?:any|one)?|unknown|next|"
    r"move on|continue|that'?s (?:it|all)|stop asking|no idea|"
    r"decline|skip this|skip it"
    r")"
    r"[\s.!,]*$",  # only trailing punctuation/whitespace may follow
    re.I,
)

# { session_id: {"turns": [...], "asked": [...], "declines": int, "created_at": ...} }
_sessions: dict[str, dict] = {}


def _is_decline(text: str) -> bool:
    return bool(_DECLINE_PATTERNS.match((text or "").strip()))


def _normalize_question(q: str) -> str:
    """Loose key for detecting a repeated question."""
    return re.sub(r"[^a-z0-9 ]", "", (q or "").lower()).strip()[:60]


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
        "asked": [_normalize_question(first_question)],
        "declines": 0,
        "created_at": datetime.utcnow(),
    }
    return session_id, first_question


def answer(session_id: str, user_answer: str) -> dict:
    """
    Record the user's answer and return either the next question or the
    finished profile.

    Three guards keep this from becoming an interrogation:
      1. A hard turn cap enforced here, not merely suggested to the model.
      2. Declines ("no", "skip", "I don't know") count toward finishing, and
         two in a row ends the interview immediately.
      3. A repeated question is rejected and forces completion instead.
    """
    session = _sessions.get(session_id)
    if session is None:
        raise ValueError("Session not found or expired. Please start a new intake.")

    session["turns"].append({"role": "user", "content": user_answer})
    turns_so_far = sum(1 for t in session["turns"] if t["role"] == "user")

    if _is_decline(user_answer):
        session["declines"] = session.get("declines", 0) + 1
    else:
        session["declines"] = 0

    # Guard 1: the user has said no twice running. Stop asking.
    if session["declines"] >= 2:
        logger.info("intake.finishing reason=consecutive_declines session=%s", session_id[:8])
        return _finish(session, turns_so_far)

    # Guard 2: hard ceiling reached.
    if turns_so_far >= _MAX_TURNS:
        logger.info("intake.finishing reason=max_turns session=%s", session_id[:8])
        return _finish(session, turns_so_far)

    if not llm_provider.is_configured():
        return _fallback_next(session, turns_so_far)

    try:
        decision = _ask_llm_next(session["turns"], turns_so_far, session["asked"])
    except Exception as exc:
        # Never strand the user mid-interview because of a provider hiccup.
        logger.warning("intake.llm_failed session=%s: %s", session_id[:8], exc)
        return _finish(session, turns_so_far)

    if decision.get("complete") and decision.get("profile"):
        return _finish(session, turns_so_far, profile=decision["profile"])

    next_q = (decision.get("next_question") or "").strip()

    # Guard 3: the model is repeating itself, or produced nothing usable.
    if not next_q or _normalize_question(next_q) in session["asked"]:
        logger.info("intake.finishing reason=repeat_question session=%s", session_id[:8])
        return _finish(session, turns_so_far)

    session["asked"].append(_normalize_question(next_q))
    session["turns"].append({"role": "assistant", "content": next_q})
    return {
        "complete": False,
        "question": next_q,
        "profile": None,
        "turns_so_far": turns_so_far,
    }


def _finish(session: dict, turns_so_far: int, profile: Optional[dict] = None) -> dict:
    """
    End the interview and hand back the best profile we can assemble.

    When the model did not supply one (because we stopped it early), we build
    a profile from the transcript instead of failing. Getting the user to
    results with partial information beats trapping them in questions.
    """
    if profile is None:
        profile = _profile_from_transcript(session)

    session["turns"].append(
        {"role": "assistant", "content": "Thanks, that is enough to search."}
    )
    return {
        "complete": True,
        "question": None,
        "profile": _validate_profile(profile),
        "turns_so_far": turns_so_far,
    }


def _profile_from_transcript(session: dict) -> dict:
    """
    Best-effort extraction when we cut the interview short.

    The first user answer is always the condition (the opening question asks
    for it). After that we ask the model once for a structured summary, and
    fall back to a minimal profile if that fails.
    """
    user_answers = [t["content"] for t in session["turns"] if t["role"] == "user"]
    fallback = {
        "condition": user_answers[0] if user_answers else "",
        "location": "United States",
        "treatment_history": "none",
        "medications": ["none"],
    }

    if not llm_provider.is_configured() or not user_answers:
        return fallback

    transcript = "\n".join(
        f"{t['role'].upper()}: {t['content']}" for t in session["turns"]
    )
    try:
        raw = llm_provider.complete_sync(
            _EXTRACT_PROMPT.format(transcript=transcript),
            system="Respond with JSON only.",
            max_tokens=800,
            json_only=True,
        )
        parsed = llm_provider.parse_json(raw)
        if parsed.get("condition"):
            # Fill required fields the user never got asked about.
            parsed.setdefault("location", "United States")
            parsed.setdefault("treatment_history", "none")
            if not parsed.get("medications"):
                parsed["medications"] = ["none"]
            return parsed
    except Exception as exc:
        logger.warning("intake.extract_failed: %s", exc)

    return fallback


_EXTRACT_PROMPT = """\
Extract a patient profile from this intake conversation. The user may have
declined some questions; do not invent answers for those.

{transcript}

Return JSON only:
{{
  "condition": "the condition or diagnosis they named",
  "location": "city/state if given, otherwise 'United States'",
  "treatment_history": "what they have tried, or 'none'",
  "medications": ["current medications, or 'none'"],
  "biomarkers": ["only if explicitly mentioned"],
  "age": 0
}}
Omit age and biomarkers entirely if they were not provided.
"""


# ---------------------------------------------------------------------------
# LLM call
# ---------------------------------------------------------------------------


def _ask_llm_next(
    turns: list[dict], turns_so_far: int, asked: list[str] | None = None
) -> dict:
    transcript = "\n".join(
        f"{t['role'].upper()}: {t['content']}" for t in turns
    )
    prompt = _PROMPT.format(
        transcript=transcript,
        turns_so_far=turns_so_far,
        max_turns=_MAX_TURNS,
        remaining=max(0, _MAX_TURNS - turns_so_far),
        already_asked="\n".join(f"- {q}" for q in (asked or [])) or "(none)",
    )

    raw = llm_provider.complete_sync(
        prompt,
        system=(
            "You are a friendly intake assistant for a clinical trial matching "
            "service. Respond only with the JSON object specified, no prose. "
            "Be brief and finish the interview early rather than late."
        ),
        # A next question is one sentence and the final profile is a small
        # object, so a tight budget keeps each turn fast. Reasoning models
        # spend tokens before emitting, hence not going lower than this.
        max_tokens=1200,
        json_only=True,
    )
    return llm_provider.parse_json(raw)


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

Questions you have ALREADY asked. Never ask any of these again, in any
rewording:
{already_asked}

Constraints:
- You have asked {turns_so_far} of a maximum of {max_turns} questions.
  You have {remaining} left. Finish before running out.
- Ask ONE short, plain-language question at a time.
- NEVER repeat a question already listed above, and never ask for information
  the user has already given anywhere in the transcript.

Handling refusals, which matters more than gathering every detail:
- If the user answers "no", "none", "skip", "I don't know", "not sure", or
  anything similar, that topic is CLOSED. Record it as unknown and move to a
  different topic. Do not rephrase and try again.
- If the user declines twice, or asks you to stop or move on, set
  complete=true immediately with whatever you have.
- A shorter interview that returns results beats a thorough one the user
  abandons. When in doubt, finish.

What to gather, in priority order:
1. condition (required)
2. location (required; "United States" is acceptable if they won't say)
3. treatment_history, or "none"
4. medications, or ["none"]
5. Only if clearly relevant and turns remain: biomarkers for oncology
   (KRAS, EGFR, HER2, BRCA, MSI, PD-L1), age, last_treatment_date

Set complete=true as soon as you have items 1 and 2 plus a reasonable attempt
at 3 and 4. Do not keep asking for optional detail.

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
