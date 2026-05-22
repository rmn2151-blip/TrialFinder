"""
LLM ranking service — takes a patient profile + aggregated Linkup search
results and returns a structured list of ranked trials with personalized
reasoning.

Uses Claude claude-sonnet-4-6 via the Anthropic SDK with JSON output mode.
"""

import json
import logging
import os
from pathlib import Path

import anthropic

from models.patient import PatientProfile
from models.trial import (
    Citation,
    ExcludedTrial,
    MatchResponse,
    RankedTrial,
    ScoreComponent,
)

logger = logging.getLogger(__name__)

_ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_MAX_TRIALS = int(os.getenv("MAX_TRIALS_RETURNED", "5"))

_PROMPT_PATH = Path(__file__).parent.parent / "prompts" / "ranker.txt"

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
    if not _ANTHROPIC_API_KEY:
        raise ValueError("ANTHROPIC_API_KEY is not set. Add it to your .env file.")

    prompt = _build_prompt(patient, linkup_data)

    logger.info(f"Calling Claude to rank trials for condition='{patient.condition}'")

    raw_json = await _call_claude(prompt)
    return _parse_response(raw_json, patient)


# ---------------------------------------------------------------------------
# Prompt construction
# ---------------------------------------------------------------------------


def _build_prompt(patient: PatientProfile, linkup_data: dict) -> str:
    template = _PROMPT_PATH.read_text(encoding="utf-8")

    patient_json = json.dumps(
        patient.model_dump(exclude_none=True), indent=2
    )

    return template.format(
        patient_json=patient_json,
        trial_listings=linkup_data.get("trial_listings") or "No trial listing data found.",
        recent_results=linkup_data.get("recent_results") or "No recent results data found.",
        mechanism_coverage=linkup_data.get("mechanism_coverage") or "No mechanism coverage found.",
        max_trials=_MAX_TRIALS,
    )


# ---------------------------------------------------------------------------
# Claude call
# ---------------------------------------------------------------------------


async def _call_claude(prompt: str) -> str:
    """
    Calls Claude synchronously (Anthropic SDK is sync) and returns the
    raw response text. Runs in a thread pool to avoid blocking the event loop.
    """
    import asyncio

    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_call_claude, prompt)


def _sync_call_claude(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=_ANTHROPIC_API_KEY)

    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=4096,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
        # Ask Claude to think step by step before producing JSON
        system=(
            "You are a clinical trial matching specialist. "
            "You always respond with valid JSON only — no markdown fences, "
            "no preamble, no explanation outside the JSON structure."
        ),
    )

    return message.content[0].text


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
            )
            trials.append(trial)
        except Exception as e:
            logger.warning(f"Skipping malformed trial entry {i}: {e}")
            continue

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


def _clean_nct_id(raw: str | None) -> str | None:
    """Validate NCT ID format; return None if invalid to avoid bad data."""
    if not raw:
        return None
    clean = raw.strip().upper()
    import re
    if re.match(r"^NCT\d{8}$", clean):
        return clean
    return None
