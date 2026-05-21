from pydantic import BaseModel, Field
from typing import Optional


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


class MatchResponse(BaseModel):
    trials: list[RankedTrial]
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
