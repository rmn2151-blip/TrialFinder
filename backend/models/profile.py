"""Pydantic schemas for patient profiles."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class ProfileBase(BaseModel):
    label: str = Field(..., min_length=1, max_length=120, description="e.g. 'Mom', 'Myself'")
    condition: str = Field(..., min_length=3, max_length=500)
    treatment_history: Optional[str] = Field(default=None, max_length=1000)
    location: str = Field(..., min_length=2, max_length=200)
    age: Optional[int] = Field(default=None, ge=0, le=120)
    medications: list[str] = Field(default_factory=list)
    biomarkers: list[str] = Field(
        default_factory=list,
        description="Genomic / biomarker results e.g. 'KRAS G12C+', 'HER2 amplified'",
    )
    last_treatment_date: Optional[str] = Field(
        default=None,
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        description="Date most recent systemic therapy ended (YYYY-MM-DD)",
    )
    additional_context: Optional[str] = Field(default=None, max_length=2000)


class ProfileCreate(ProfileBase):
    pass


class ProfileUpdate(ProfileBase):
    pass


class ProfileOut(ProfileBase):
    id: int
    account_id: int
    created_at: datetime

    model_config = {"from_attributes": True}
