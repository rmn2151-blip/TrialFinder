"""Pydantic schemas for the watchlist API."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class WatchRequest(BaseModel):
    """Add a trial to a patient profile's watchlist."""

    profile_id: int = Field(..., description="Patient profile to attach this watch to")
    nct_id: str = Field(..., pattern=r"^NCT\d{8}$", description="Trial to watch")
    title: str = Field(..., min_length=1, description="Trial title for display")
    source_url: Optional[str] = Field(default=None)


class WatchedTrialOut(BaseModel):
    id: int
    profile_id: int
    nct_id: str
    title: str
    source_url: Optional[str] = None
    last_status: Optional[str] = None
    last_phase: Optional[str] = None
    last_completion_date: Optional[str] = None
    last_site_count: Optional[int] = None
    created_at: datetime
    last_checked_at: Optional[datetime] = None
    last_change_at: Optional[datetime] = None

    # Trial result tracker fields
    results_headline: Optional[str] = None
    results_summary: Optional[str] = None
    results_journal_url: Optional[str] = None

    # Enrollment status tracker
    enrollment_status: Optional[str] = None
    enrollment_changed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class WatchlistOut(BaseModel):
    profile_id: int
    trials: list[WatchedTrialOut]


class CheckSummary(BaseModel):
    """Result of running the change-detection sweep."""

    accounts_checked: int
    trials_checked: int
    trials_changed: int
    emails_sent: int
    details: list[str] = Field(default_factory=list)
