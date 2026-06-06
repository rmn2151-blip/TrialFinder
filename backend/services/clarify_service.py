"""
Ambiguity resolution loop — when a trial's eligibility is "unclear" for a
patient, the agent generates a single targeted clarifying question rather than
hiding the trial. Runs in a loop for up to 3 questions before deciding
eligible / ineligible / still uncertain.
"""

import json
import logging
import os
import re
from typing import Optional

import anthropic

logger = logging.getLogger(__name__)

_ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
MAX_QUESTIONS = 3


def clarify(
    *,
    patient: dict,
    trial: dict,
    history: list[dict],
) -> dict:
    """
    `history` is a list of {"question": ..., "answer": ...} dicts asked so far.
    Returns one of:
      {"verdict": "eligible" | "ineligible", "reason": "..."}
      {"verdict": "ask", "question": "...", "remaining": N}
      {"verdict": "stop", "reason": "..."}  # hit MAX_QUESTIONS
    """
    if len(history) >= MAX_QUESTIONS:
        return {
            "verdict": "stop",
            "reason": (
                "We've asked the maximum follow-up questions and still can't "
                "determine eligibility from the trial's public listing. Confirm "
                "with the study team."
            ),
        }

    if not _ANTHROPIC_API_KEY:
        return _fallback_clarify(history)

    prompt = _PROMPT.format(
        patient=json.dumps(patient, indent=2),
        trial=json.dumps(_summarize_trial(trial), indent=2),
        history=json.dumps(history, indent=2) if history else "(none yet)",
        remaining=MAX_QUESTIONS - len(history),
    )

    client = anthropic.Anthropic(api_key=_ANTHROPIC_API_KEY)
    msg = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=600,
        system="Respond ONLY with the JSON specified — no prose, no markdown fences.",
        messages=[{"role": "user", "content": prompt}],
    )
    parsed = _parse_json(msg.content[0].text)

    verdict = parsed.get("verdict")
    if verdict not in ("eligible", "ineligible", "ask"):
        return {
            "verdict": "stop",
            "reason": "Couldn't determine eligibility. Confirm with the study team.",
        }

    if verdict == "ask":
        question = parsed.get("question") or "Could you tell me more about your recent treatments?"
        return {
            "verdict": "ask",
            "question": question,
            "remaining": MAX_QUESTIONS - len(history) - 1,
        }

    return {"verdict": verdict, "reason": parsed.get("reason") or ""}


def _summarize_trial(trial: dict) -> dict:
    """Shrink the trial payload sent to the LLM."""
    return {
        "title": trial.get("title"),
        "nct_id": trial.get("nct_id"),
        "eligibility_summary": trial.get("eligibility_summary"),
        "warning_flags": trial.get("warning_flags"),
        "phase": trial.get("phase"),
    }


def _parse_json(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        return {}


def _fallback_clarify(history: list[dict]) -> dict:
    """No LLM available — ask a generic clarifying question, then give up."""
    if not history:
        return {
            "verdict": "ask",
            "question": "Are you currently taking any blood thinners or anticoagulants?",
            "remaining": MAX_QUESTIONS - 1,
        }
    if len(history) == 1:
        return {
            "verdict": "ask",
            "question": "Have you had any cancer treatment in the last 4 weeks?",
            "remaining": MAX_QUESTIONS - 2,
        }
    return {
        "verdict": "stop",
        "reason": "Need confirmation from the study team.",
    }


_PROMPT = """\
You are a clinical trial eligibility assistant.

Patient profile (JSON):
{patient}

Trial in question (summary):
{trial}

Questions already asked, with the patient's answers:
{history}

You have {remaining} clarifying questions remaining (3 total max).

Decide ONE of:
- If you can now firmly determine the patient is eligible, output verdict
  "eligible" with a short reason.
- If you can firmly determine they are ineligible, output verdict
  "ineligible" with a short, patient-friendly reason.
- Otherwise, ask ONE specific clarifying question that — if answered — would
  most likely resolve the ambiguity (e.g. "Do you currently take any blood
  thinners?"). The question must be answerable by the patient without
  consulting their doctor.

Output ONLY this JSON shape:
{{
  "verdict": "eligible" | "ineligible" | "ask",
  "reason": "Short reason if eligible/ineligible, omit if asking",
  "question": "Single specific question if ask, omit if not"
}}
"""
