from pydantic import BaseModel, Field
from typing import Optional


class PatientProfile(BaseModel):
    condition: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Primary condition or diagnosis in plain English",
        examples=["stage 3 non-small cell lung cancer", "Crohn's disease"],
    )
    treatment_history: Optional[str] = Field(
        default=None,
        max_length=1000,
        description="Prior treatments, medications, procedures the patient has already tried",
        examples=["carboplatin + paclitaxel 6 cycles, then PD-1 inhibitor"],
    )
    location: str = Field(
        ...,
        min_length=2,
        max_length=200,
        description="City, state or zip code for proximity matching",
        examples=["New York, NY", "94102"],
    )
    age: Optional[int] = Field(
        default=None,
        ge=0,
        le=120,
        description="Patient age in years",
    )
    medications: list[str] = Field(
        default_factory=list,
        description="Current medications (used to flag interaction/exclusion criteria)",
        examples=[["metformin", "lisinopril"]],
    )
    additional_context: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Any other relevant details: biomarkers, ECOG status, insurance, etc.",
    )

    model_config = {
        "json_schema_extra": {
            "example": {
                "condition": "stage 3 non-small cell lung cancer KRAS G12C",
                "treatment_history": "carboplatin + paclitaxel 6 cycles",
                "location": "New York, NY",
                "age": 58,
                "medications": ["metformin", "lisinopril"],
                "additional_context": "ECOG performance status 1, no brain metastases",
            }
        }
    }
