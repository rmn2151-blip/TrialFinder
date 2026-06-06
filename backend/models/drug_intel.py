"""Pydantic schemas for drug-specific intelligence lookups."""

from typing import Optional

from pydantic import BaseModel, Field


class PhaseResult(BaseModel):
    phase: str = Field(..., description="e.g. 'Phase II'")
    summary: str = Field(..., description="Plain-language efficacy / outcomes summary")
    url: Optional[str] = None


class ConferenceSignal(BaseModel):
    conference: str = Field(..., description="e.g. 'ASCO 2025', 'ASH 2024'")
    finding: str = Field(..., description="What was reported, in plain English")
    url: Optional[str] = None


class FDADesignation(BaseModel):
    label: str = Field(..., description="e.g. 'Breakthrough Therapy', 'Fast Track', 'Orphan Drug'")
    date: Optional[str] = None
    url: Optional[str] = None


class DrugIntel(BaseModel):
    """Plain-English intel about an experimental therapy."""

    drug: str = Field(..., description="The drug or therapy name that was looked up")

    summary: Optional[str] = Field(
        default=None,
        description="One-paragraph plain-language overview of the drug, its target, "
        "and where it is in development",
    )
    side_effect_signals: Optional[str] = Field(
        default=None,
        description="Plain-language note on known side effects reported in trials",
    )

    phase_results: list[PhaseResult] = Field(default_factory=list)
    conference_signals: list[ConferenceSignal] = Field(default_factory=list)
    fda_designations: list[FDADesignation] = Field(default_factory=list)

    sources: list[dict] = Field(default_factory=list)
    cached: bool = Field(default=False)
