"""
Tests for llm_service.py — validates the JSON parsing logic without
hitting the Anthropic API.
Run with: pytest tests/test_llm_service.py -v
"""

import json

import pytest

from models.patient import PatientProfile
from models.trial import MatchResponse
from services.llm_service import _parse_response, _clean_nct_id


SAMPLE_PATIENT = PatientProfile(
    condition="stage 3 non-small cell lung cancer KRAS G12C",
    treatment_history="carboplatin + paclitaxel 6 cycles",
    location="New York, NY",
    age=58,
    medications=["metformin"],
)

VALID_CLAUDE_RESPONSE = json.dumps({
    "trials": [
        {
            "rank": 1,
            "title": "Phase II Trial of Sotorasib in KRAS G12C NSCLC",
            "nct_id": "NCT05555201",
            "phase": "Phase II",
            "sponsor": "Memorial Sloan Kettering",
            "location": "New York, NY",
            "status": "Recruiting",
            "fit_score": 91,
            "why_this_fits": "This trial directly targets your KRAS G12C mutation. Your prior carboplatin therapy meets the 'previously treated' criterion. MSK is located in New York City.",
            "plain_english": "This trial tests a daily pill that specifically blocks the mutated protein driving your cancer, unlike traditional chemotherapy.",
            "eligibility_summary": "Must have KRAS G12C mutation confirmed. Prior platinum therapy required. ECOG 0-1. No prior KRAS inhibitor.",
            "warning_flags": ["Liver function monitoring required", "Potential interaction with metformin — discuss with oncologist"],
            "source_url": "https://clinicaltrials.gov/study/NCT05555201",
            "intervention_type": "Drug"
        }
    ],
    "search_context": "Found 5 open KRAS G12C trials; ranked top 1",
    "condition_searched": "Non-small cell lung cancer, KRAS G12C mutation"
})


def test_parse_valid_response():
    result = _parse_response(VALID_CLAUDE_RESPONSE, SAMPLE_PATIENT)
    assert isinstance(result, MatchResponse)
    assert len(result.trials) == 1
    assert result.trials[0].fit_score == 91
    assert result.trials[0].nct_id == "NCT05555201"
    assert "KRAS G12C" in result.trials[0].why_this_fits


def test_parse_response_with_markdown_fences():
    fenced = f"```json\n{VALID_CLAUDE_RESPONSE}\n```"
    result = _parse_response(fenced, SAMPLE_PATIENT)
    assert len(result.trials) == 1


def test_parse_invalid_json_returns_empty():
    result = _parse_response("this is not json", SAMPLE_PATIENT)
    assert isinstance(result, MatchResponse)
    assert result.trials == []


def test_parse_sorts_by_fit_score():
    data = json.dumps({
        "trials": [
            {"rank": 1, "title": "Trial A", "fit_score": 60, "why_this_fits": "x", "plain_english": "x", "status": "Recruiting"},
            {"rank": 2, "title": "Trial B", "fit_score": 90, "why_this_fits": "y", "plain_english": "y", "status": "Recruiting"},
        ],
        "search_context": "2 trials",
        "condition_searched": "test condition"
    })
    result = _parse_response(data, SAMPLE_PATIENT)
    assert result.trials[0].fit_score == 90   # higher score first
    assert result.trials[0].rank == 1


def test_clean_nct_id_valid():
    assert _clean_nct_id("NCT05555201") == "NCT05555201"
    assert _clean_nct_id("nct05555201") == "NCT05555201"


def test_clean_nct_id_invalid():
    assert _clean_nct_id("12345678") is None
    assert _clean_nct_id("NCT123") is None
    assert _clean_nct_id(None) is None


def test_disclaimer_always_present():
    result = _parse_response(VALID_CLAUDE_RESPONSE, SAMPLE_PATIENT)
    assert "not" in result.disclaimer.lower()
    assert len(result.disclaimer) > 20
