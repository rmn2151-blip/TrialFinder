"""Pydantic schemas for trial site / investigator reputation lookup."""

from typing import Optional

from pydantic import BaseModel, Field


class SourceLink(BaseModel):
    label: str
    url: str
    snippet: Optional[str] = None


class Publication(BaseModel):
    title: str
    url: Optional[str] = None
    year: Optional[str] = None


class PressItem(BaseModel):
    title: str
    url: Optional[str] = None
    snippet: Optional[str] = None
    date: Optional[str] = None


class Warning(BaseModel):
    """A serious red flag — FDA warning letter, sanction, or major enforcement action."""

    label: str = Field(..., description="Short headline of the warning")
    url: Optional[str] = Field(default=None)
    date: Optional[str] = Field(default=None, description="Approximate date (YYYY-MM or YYYY)")
    severity: str = Field(
        default="warning",
        description="'warning' (FDA warning letter) or 'note' (lesser concern)",
    )


class Reputation(BaseModel):
    """
    A summary of public information about a trial sponsor / site / investigator
    to help patients judge whether a trial is at a serious center.
    """

    sponsor: str = Field(..., description="The sponsor/site name that was looked up")
    pi: Optional[str] = Field(default=None, description="Principal investigator name if known")

    hospital_reputation: Optional[str] = Field(
        default=None,
        description="Plain-language summary of the institution's standing in this field",
    )
    summary: Optional[str] = Field(
        default=None,
        description="Overall plain-language take ('serious academic center', 'small community site', etc.)",
    )

    publications: list[Publication] = Field(default_factory=list)
    recent_press: list[PressItem] = Field(default_factory=list)
    warnings: list[Warning] = Field(
        default_factory=list,
        description="FDA warning letters or other serious red flags from the last 5 years",
    )
    sources: list[SourceLink] = Field(default_factory=list)

    cached: bool = Field(default=False, description="Whether this response was served from cache")
