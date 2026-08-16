from pydantic import BaseModel, Field
from typing import Optional


class ScoreComponent(BaseModel):
    """One axis of the overall fit score, with its own sub-score and source."""

    label: str = Field(
        ...,
        description="Component name e.g. 'Eligibility', 'Location', 'Line of therapy'",
    )
    score: int = Field(
        ..., ge=0, le=100, description="0–100 sub-score for this axis"
    )
    reason: Optional[str] = Field(
        default=None,
        description="One-line justification for this sub-score",
    )
    source_url: Optional[str] = Field(
        default=None,
        description="Link to the specific source this sub-score was derived from",
    )


class Citation(BaseModel):
    """A source backing a trial's data, surfaced so users can verify claims."""

    label: str = Field(..., description="Human-readable source label")
    url: str = Field(..., description="Source URL")


class ExcludedTrial(BaseModel):
    """A trial that was considered but filtered out, with the reason why."""

    title: str = Field(..., description="Trial title")
    nct_id: Optional[str] = Field(default=None, pattern=r"^NCT\d{8}$")
    reason: str = Field(
        ...,
        description="Plain-language reason this trial was excluded, ideally "
        "referencing the patient e.g. 'Excludes patients on metformin'",
    )
    source_url: Optional[str] = Field(default=None)


class RankedTrial(BaseModel):
    rank: int = Field(..., ge=1, description="Position in the ranked list (1 = best fit)")
    title: str = Field(..., description="Full trial title")
    nct_id: Optional[str] = Field(
        default=None,
        description="ClinicalTrials.gov identifier e.g. NCT12345678",
        pattern=r"^NCT\d{8}$",
    )
    phase: Optional[str] = Field(
        default=None,
        description="Trial phase: Phase I, Phase II, Phase III, Phase IV, N/A",
    )
    sponsor: Optional[str] = Field(
        default=None, description="Lead sponsor organization"
    )
    location: Optional[str] = Field(
        default=None,
        description="Trial site(s) with proximity note e.g. 'New York, NY — 2.1 miles away'",
    )
    status: str = Field(
        default="Recruiting",
        description="Enrollment status: Recruiting, Enrolling by Invitation, etc.",
    )
    fit_score: int = Field(
        ...,
        ge=0,
        le=100,
        description="0–100 match score. 80+ = strong fit, 60–79 = potential fit, <60 = weak fit",
    )
    why_this_fits: str = Field(
        ...,
        description="2–3 sentence personalized explanation of why this trial matches this patient",
    )
    plain_english: str = Field(
        ...,
        description="1–2 sentence plain-English summary of what the trial is testing",
    )
    eligibility_summary: Optional[str] = Field(
        default=None,
        description="Key inclusion/exclusion criteria in plain language",
    )
    warning_flags: list[str] = Field(
        default_factory=list,
        description="Potential issues e.g. 'Requires biopsy', 'Drug interaction with metformin possible'",
    )
    source_url: Optional[str] = Field(
        default=None,
        description="URL to the trial listing (ClinicalTrials.gov or other source)",
    )
    intervention_type: Optional[str] = Field(
        default=None,
        description="e.g. Drug, Biological, Device, Procedure, Behavioral",
    )
    score_breakdown: list[ScoreComponent] = Field(
        default_factory=list,
        description="Per-axis breakdown of the overall fit_score with sources",
    )
    citations: list[Citation] = Field(
        default_factory=list,
        description="Sources backing this trial's data, for user verification",
    )
    availability: str = Field(
        default="unknown",
        description="What the status means for the patient: 'open' (enrolling "
        "now), 'opening_soon' (not yet recruiting, worth saving for an alert), "
        "or 'closed' (not currently enrolling).",
    )
    washout_weeks: Optional[int] = Field(
        default=None,
        ge=0,
        le=52,
        description="Required weeks off prior systemic therapy before enrollment, "
        "extracted from the trial's eligibility text. 0 = no washout required.",
    )
    earliest_enrollable_date: Optional[str] = Field(
        default=None,
        description="Computed earliest date the patient could enroll (YYYY-MM-DD), "
        "based on last_treatment_date + washout_weeks. Null if not computable.",
    )
    biomarker_match: Optional[str] = Field(
        default=None,
        description="Plain-English note about which patient biomarkers fit (or fail) "
        "this trial's eligibility e.g. 'Matches your KRAS G12C+ status' or "
        "'Requires HER2- but you reported HER2+'",
    )
    matched_biomarkers: list[str] = Field(
        default_factory=list,
        description="Patient biomarkers that satisfy this trial's requirements",
    )
    insurance_coverage: list[str] = Field(
        default_factory=list,
        description="Insurance providers commonly known to cover this trial's "
        "routine costs (Medicare, Blue Cross, UnitedHealthcare, Aetna, "
        "Kaiser, etc.). Sponsors typically cover the experimental drug + "
        "study-only procedures; this list is for the standard-of-care side.",
    )
    insurance_note: Optional[str] = Field(
        default=None,
        description="One-line plain-language note about who typically pays "
        "for what, e.g. 'Sponsor covers the drug; routine visits go through "
        "insurance.'",
    )
    availability: str = Field(
        default="open",
        description=(
            "How the patient can act on this trial right now. "
            "'open': recruiting or enrolling by invitation, contactable today. "
            "'upcoming': not yet recruiting, worth saving so we can alert them "
            "the day it opens. "
            "'closing': active but no longer enrolling, worth saving to be "
            "alerted when results are published."
        ),
    )
    availability_note: Optional[str] = Field(
        default=None,
        description="Short plain-language explanation of the availability "
        "state, e.g. 'Expected to begin enrolling in March 2027.'",
    )


class MatchResponse(BaseModel):
    trials: list[RankedTrial]
    excluded: list[ExcludedTrial] = Field(
        default_factory=list,
        description="Trials considered but filtered out, with reasons — surfaced "
        "as a trust signal so users see what was ruled out and why",
    )
    search_context: str = Field(
        ...,
        description="Summary of what was searched e.g. 'Found 14 open trials, ranked top 5'",
    )
    disclaimer: str = Field(
        default=(
            "This information is for educational purposes only and does not constitute "
            "medical advice. Always consult with a qualified healthcare provider before "
            "making any treatment decisions or enrolling in a clinical trial."
        )
    )
    condition_searched: str = Field(
        ..., description="The condition as interpreted and searched"
    )
