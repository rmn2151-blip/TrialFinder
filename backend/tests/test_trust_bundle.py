"""
Tests for the trust-bundle additions: score_breakdown, citations, and
excluded_trials parsing in llm_service. All offline (no API calls).
Run: pytest tests/test_trust_bundle.py -v
"""

import json

from models.patient import PatientProfile
from services.llm_service import _parse_response

PATIENT = PatientProfile(
    condition="stage 3 NSCLC KRAS G12C",
    treatment_history="carboplatin + paclitaxel",
    location="New York, NY",
    medications=["metformin"],
)

RESPONSE_WITH_TRUST = json.dumps({
    "trials": [
        {
            "rank": 1,
            "title": "Phase II Adagrasib Trial",
            "nct_id": "NCT04685135",
            "fit_score": 92,
            "status": "Recruiting",
            "why_this_fits": "Targets your KRAS G12C mutation.",
            "plain_english": "A targeted pill.",
            "score_breakdown": [
                {"label": "Eligibility", "score": 90, "reason": "Prior platinum met", "source_url": "https://clinicaltrials.gov/study/NCT04685135"},
                {"label": "Location", "score": 75, "reason": "MSK is nearby"},
                {"label": "Line of therapy", "score": 95, "reason": "2nd-line matches"},
            ],
            "citations": [
                {"label": "CT.gov", "url": "https://clinicaltrials.gov/study/NCT04685135"},
                {"label": "no-url-should-skip"},
            ],
        }
    ],
    "excluded_trials": [
        {
            "title": "First-line-only chemo study",
            "nct_id": "NCT09876543",
            "reason": "Excludes previously treated patients like you.",
            "source_url": "https://clinicaltrials.gov/study/NCT09876543",
        },
        {"title": "missing reason should be skipped"},
    ],
    "search_context": "Found trials",
    "condition_searched": "NSCLC KRAS G12C",
})


def test_score_breakdown_parsed():
    result = _parse_response(RESPONSE_WITH_TRUST, PATIENT)
    trial = result.trials[0]
    assert len(trial.score_breakdown) == 3
    labels = [c.label for c in trial.score_breakdown]
    assert "Eligibility" in labels and "Line of therapy" in labels
    elig = next(c for c in trial.score_breakdown if c.label == "Eligibility")
    assert elig.score == 90
    assert elig.source_url.endswith("NCT04685135")


def test_citations_require_url():
    result = _parse_response(RESPONSE_WITH_TRUST, PATIENT)
    cites = result.trials[0].citations
    # The entry without a url must be dropped.
    assert len(cites) == 1
    assert cites[0].url.endswith("NCT04685135")


def test_excluded_trials_parsed_and_filtered():
    result = _parse_response(RESPONSE_WITH_TRUST, PATIENT)
    # One valid exclusion; the one missing a reason is dropped.
    assert len(result.excluded) == 1
    assert result.excluded[0].nct_id == "NCT09876543"
    assert "previously treated" in result.excluded[0].reason


def test_backward_compatible_without_trust_fields():
    """A response with no trust fields still parses, with empty defaults."""
    minimal = json.dumps({
        "trials": [{
            "rank": 1, "title": "T", "fit_score": 70, "status": "Recruiting",
            "why_this_fits": "x", "plain_english": "y",
        }],
        "search_context": "s", "condition_searched": "c",
    })
    result = _parse_response(minimal, PATIENT)
    assert result.trials[0].score_breakdown == []
    assert result.trials[0].citations == []
    assert result.excluded == []
