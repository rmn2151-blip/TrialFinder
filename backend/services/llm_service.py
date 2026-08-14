"""
LLM ranking service. Takes a patient profile plus aggregated search results
and returns a structured list of ranked trials with personalized reasoning.

Runs on whichever provider is configured (Gemini by default, Claude as an
alternative) through services/llm_provider.py.
"""

import json
import logging
import os
from pathlib import Path

from models.patient import PatientProfile
from models.trial import (
    Citation,
    ExcludedTrial,
    MatchResponse,
    RankedTrial,
    ScoreComponent,
)
from services import llm_provider

logger = logging.getLogger(__name__)

_MOCK_MODE = (
    os.getenv("MOCK_SEARCH", os.getenv("MOCK_LINKUP", "false")).lower() == "true"
)
_MAX_TRIALS = int(os.getenv("MAX_TRIALS_RETURNED", "5"))

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "ranker.txt"
_MOCK_MATCH_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "match_mock.json"

DISCLAIMER = (
    "This information is for educational purposes only and does not constitute "
    "medical advice. Always consult with a qualified healthcare provider before "
    "making any treatment decisions or enrolling in a clinical trial."
)


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


async def rank_and_reason(
    patient: PatientProfile,
    linkup_data: dict,
) -> MatchResponse:
    """
    Given a patient profile and Linkup search aggregation, call Claude to
    extract, rank, and annotate the best-matching trials.

    Returns a MatchResponse ready to send to the frontend.
    """
    if not llm_provider.is_configured():
        if _MOCK_MODE:
            logger.info("Mock mode with no provider key. Returning fixture response.")
            return _load_mock_match(patient)
        raise ValueError(
            "No LLM provider configured. Set GEMINI_API_KEY (recommended) or "
            "ANTHROPIC_API_KEY in your .env file."
        )

    prompt = _build_prompt(patient, linkup_data)

    provider = llm_provider.active_provider()
    logger.info(
        "Ranking trials for condition='%s' using %s", patient.condition, provider
    )

    raw_json = await llm_provider.complete(
        prompt,
        system=(
            "You are a clinical trial matching specialist. Respond with a "
            "single valid JSON object and nothing else. No markdown fences, "
            "no commentary before or after the JSON."
        ),
        max_tokens=8000,
        json_only=True,
    )
    return _parse_response(raw_json, patient)


def _load_mock_match(patient: PatientProfile) -> MatchResponse:
    """Return a fixture-based MatchResponse for dev/demo without Anthropic."""
    if _MOCK_MATCH_PATH.exists():
        raw = _MOCK_MATCH_PATH.read_text(encoding="utf-8")
    else:
        raw = json.dumps({"trials": [], "search_context": "Mock fixture missing."})
    response = _parse_response(raw, patient)
    response.condition_searched = patient.condition
    response.search_context = (
        response.search_context or f"Mock results for {patient.condition}"
    )
    return response


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def _build_prompt(patient: PatientProfile, search_data: dict) -> str:
    """
    Fill the ranker template.

    Deliberately uses explicit string replacement rather than str.format().
    The template contains a literal JSON example, and format() treats every
    '{' in that example as a placeholder, which raised
    KeyError: '\\n  "trials"' and made every real search fail. Replacement
    only touches the exact tokens we define, so the JSON example is safe and
    editing the prompt cannot break the code.
    """
    template = _PROMPT_PATH.read_text(encoding="utf-8")

    patient_json = json.dumps(patient.model_dump(exclude_none=True), indent=2)

    replacements = {
        "{patient_json}": patient_json,
        "{trial_listings}": search_data.get("trial_listings")
        or "No trial listing data found.",
        "{recent_results}": search_data.get("recent_results")
        or "No recent results data available.",
        "{mechanism_coverage}": search_data.get("mechanism_coverage")
        or "No mechanism coverage available.",
        "{max_trials}": str(_MAX_TRIALS),
    }

    prompt = template
    for token, value in replacements.items():
        prompt = prompt.replace(token, value)

    return prompt


# ---------------------------------------------------------------------------
# Response parsing
# ---------------------------------------------------------------------------


def _parse_response(raw_json: str, patient: PatientProfile) -> MatchResponse:
    """
    Parse Claude's JSON output into a MatchResponse. Handles common
    failure modes: extra markdown fences, truncated JSON, missing fields.
    """
    # Strip markdown code fences if Claude added them despite instructions
    cleaned = raw_json.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        # Remove first and last lines if they're fences
        if lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines)

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as e:
        logger.error(f"Claude returned invalid JSON: {e}\nRaw: {raw_json[:500]}")
        # Return an empty response rather than crashing
        return MatchResponse(
            trials=[],
            search_context="Unable to parse trial results. Please try again.",
            disclaimer=DISCLAIMER,
            condition_searched=patient.condition,
        )

    trials_raw = data.get("trials", [])
    trials = []

    for i, t in enumerate(trials_raw):
        try:
            trial = RankedTrial(
                rank=t.get("rank", i + 1),
                title=t.get("title", "Untitled Trial"),
                nct_id=_clean_nct_id(t.get("nct_id")),
                phase=t.get("phase"),
                sponsor=t.get("sponsor"),
                location=t.get("location"),
                status=t.get("status", "Recruiting"),
                fit_score=int(t.get("fit_score", 50)),
                why_this_fits=t.get("why_this_fits", ""),
                plain_english=t.get("plain_english", ""),
                eligibility_summary=t.get("eligibility_summary"),
                warning_flags=t.get("warning_flags", []),
                source_url=t.get("source_url"),
                intervention_type=t.get("intervention_type"),
                score_breakdown=_parse_breakdown(t.get("score_breakdown")),
                citations=_parse_citations(t.get("citations")),
                washout_weeks=_parse_int(t.get("washout_weeks"), lo=0, hi=52),
                biomarker_match=_parse_str(t.get("biomarker_match")),
                matched_biomarkers=_parse_str_list(t.get("matched_biomarkers")),
                insurance_coverage=_parse_str_list(t.get("insurance_coverage"))[:6],
                insurance_note=_parse_str(t.get("insurance_note")),
            )
            # Compute the earliest enrollable date if we have both the patient's
            # last treatment date and the trial's washout period.
            trial.earliest_enrollable_date = _compute_earliest_date(
                trial.washout_weeks, patient.last_treatment_date
            )
            trials.append(trial)
        except Exception as e:
            logger.warning(f"Skipping malformed trial entry {i}: {e}")
            continue

    # Hard filter — only actively recruiting trials survive. The prompt asks
    # for this too, but this belt-and-braces check ensures a non-recruiting
    # trial can never leak through no matter what the LLM returns.
    trials = [t for t in trials if _is_recruiting(t.status)]

    # Sort by fit_score descending in case Claude didn't fully comply
    trials.sort(key=lambda t: t.fit_score, reverse=True)
    # Re-number ranks after sort
    for i, trial in enumerate(trials):
        trial.rank = i + 1

    return MatchResponse(
        trials=trials,
        excluded=_parse_excluded(data.get("excluded_trials")),
        search_context=data.get("search_context", f"Searched for {patient.condition}"),
        disclaimer=DISCLAIMER,
        condition_searched=data.get("condition_searched", patient.condition),
    )


def _parse_breakdown(raw) -> list[ScoreComponent]:
    """Parse score_breakdown entries, skipping any that are malformed."""
    out: list[ScoreComponent] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        try:
            score = int(item.get("score", 0))
            out.append(
                ScoreComponent(
                    label=str(item.get("label", "")).strip() or "Factor",
                    score=max(0, min(100, score)),
                    reason=item.get("reason"),
                    source_url=item.get("source_url"),
                )
            )
        except (ValueError, TypeError):
            continue
    return out


def _parse_citations(raw) -> list[Citation]:
    """Parse citation entries; require both a label and a url."""
    out: list[Citation] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        url = item.get("url")
        if not url:
            continue
        out.append(Citation(label=str(item.get("label", "Source")).strip() or "Source", url=url))
    return out


def _parse_excluded(raw) -> list[ExcludedTrial]:
    """Parse excluded_trials entries; require a title and a reason."""
    out: list[ExcludedTrial] = []
    if not isinstance(raw, list):
        return out
    for item in raw:
        if not isinstance(item, dict):
            continue
        title = item.get("title")
        reason = item.get("reason")
        if not title or not reason:
            continue
        try:
            out.append(
                ExcludedTrial(
                    title=str(title),
                    nct_id=_clean_nct_id(item.get("nct_id")),
                    reason=str(reason),
                    source_url=item.get("source_url"),
                )
            )
        except Exception:
            continue
    return out


def _parse_int(raw, *, lo: int, hi: int):
    """Parse an integer in [lo, hi], returning None on anything else."""
    if raw is None:
        return None
    try:
        v = int(raw)
    except (ValueError, TypeError):
        return None
    return max(lo, min(hi, v))


def _parse_str(raw):
    if raw is None:
        return None
    s = str(raw).strip()
    return s or None


def _parse_str_list(raw) -> list[str]:
    if not isinstance(raw, list):
        return []
    return [str(x).strip() for x in raw if str(x).strip()]


# Only these statuses are user-actionable — patients can actually enroll.
# Everything else (Completed, Terminated, Suspended, Withdrawn, Unknown,
# Not yet recruiting, Active/not recruiting, etc.) is hidden.
_ACTIVE_STATUSES = {
    "recruiting",
    "enrolling by invitation",
}


def _is_recruiting(status) -> bool:
    if not status:
        return False
    return str(status).strip().lower() in _ACTIVE_STATUSES


def _compute_earliest_date(washout_weeks, last_treatment_date):
    """If we know washout_weeks and last_treatment_date, return YYYY-MM-DD."""
    if washout_weeks is None or not last_treatment_date:
        return None
    from datetime import datetime, timedelta
    try:
        base = datetime.strptime(last_treatment_date, "%Y-%m-%d")
    except ValueError:
        return None
    return (base + timedelta(weeks=washout_weeks)).strftime("%Y-%m-%d")


def _clean_nct_id(raw: str | None) -> str | None:
    """Validate NCT ID format; return None if invalid to avoid bad data."""
    if not raw:
        return None
    clean = raw.strip().upper()
    import re
    if re.match(r"^NCT\d{8}$", clean):
        return clean
    return None
