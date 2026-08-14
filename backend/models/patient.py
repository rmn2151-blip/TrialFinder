from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing import Optional

from models.validators import clean_freetext_for_llm, clean_str_list


class PatientProfile(BaseModel):
    # extra="forbid" rejects unexpected fields outright instead of silently
    # ignoring them, so a caller cannot smuggle attributes through the API.
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    condition: str = Field(
        ...,
        min_length=3,
        max_length=500,
        description="Primary condition or diagnosis in plain English",
        examples=["stage 3 non-small cell lung cancer", "Crohn's disease"],
    )
    treatment_history: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Prior treatments, medications, procedures the patient has already tried. "
        "Use 'none' if truly treatment-naive.",
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
        ...,
        min_length=1,
        description="Current medications (used to flag interaction/exclusion criteria). "
        "Use ['none'] if the patient takes no medications.",
        examples=[["metformin", "lisinopril"]],
    )
    biomarkers: list[str] = Field(
        default_factory=list,
        description="Genomic / biomarker test results — the #1 reason cancer trial "
        "matches fail. Each entry is a free-text label e.g. 'KRAS G12C+', "
        "'EGFR exon 19 deletion', 'HER2 amplified', 'BRCA1 mutation', "
        "'MSI-high', 'PD-L1 50% TPS', 'BRCA1 negative'.",
        examples=[["KRAS G12C+", "PD-L1 50% TPS"]],
    )
    last_treatment_date: Optional[str] = Field(
        default=None,
        description="Date the patient's most recent systemic therapy ended (YYYY-MM-DD). "
        "Used to compute washout-period eligibility per trial.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
    )
    additional_context: Optional[str] = Field(
        default=None,
        max_length=2000,
        description="Any other relevant details: ECOG status, insurance, etc.",
    )

    # -----------------------------------------------------------------------
    # Sanitization. Every free-text field here is forwarded to an LLM and may
    # later be rendered into a PDF or an HTML email, so it is normalized,
    # stripped of control/invisible characters, and scrubbed of prompt
    # injection attempts before it leaves the request boundary.
    # -----------------------------------------------------------------------

    @field_validator("condition")
    @classmethod
    def _v_condition(cls, v: str) -> str:
        cleaned = clean_freetext_for_llm(v, max_length=500, field="Condition")
        if not cleaned or len(cleaned) < 3:
            raise ValueError("Please enter a condition of at least 3 characters.")
        return cleaned

    @field_validator("treatment_history")
    @classmethod
    def _v_treatment(cls, v: str) -> str:
        cleaned = clean_freetext_for_llm(
            v, max_length=1000, field="Treatment history"
        )
        if not cleaned:
            raise ValueError(
                "Please describe your treatment history, or enter 'none'."
            )
        return cleaned

    @field_validator("location")
    @classmethod
    def _v_location(cls, v: str) -> str:
        cleaned = clean_freetext_for_llm(v, max_length=200, field="Location")
        if not cleaned or len(cleaned) < 2:
            raise ValueError("Please enter a city, state, or ZIP code.")
        return cleaned

    @field_validator("additional_context")
    @classmethod
    def _v_context(cls, v: Optional[str]) -> Optional[str]:
        return clean_freetext_for_llm(v, max_length=2000, field="Additional context")

    @field_validator("medications", mode="before")
    @classmethod
    def _v_meds(cls, v):
        return clean_str_list(v, max_items=40, max_item_length=120, field="Medications")

    @field_validator("biomarkers", mode="before")
    @classmethod
    def _v_biomarkers(cls, v):
        return clean_str_list(v, max_items=40, max_item_length=120, field="Biomarkers")
