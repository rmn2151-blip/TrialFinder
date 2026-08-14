"""
Ambiguity resolution endpoint.

  POST /api/clarify — takes a patient profile, a trial, and the prior Q&A
                      history, returns either the next clarifying question
                      or an eligibility verdict.
"""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field, field_validator

from middleware.abuse import block_automated_clients, enforce_ai_quota
from middleware.rate_limit import limiter
from models.validators import clean_freetext_for_llm
from services import clarify_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/clarify", tags=["clarify"])

# Only these keys are forwarded to the model. Anything else the client sends
# is dropped, which bounds both the prompt size and what an attacker can
# inject through a free-form dict.
_ALLOWED_PATIENT_KEYS = {
    "condition",
    "treatment_history",
    "location",
    "age",
    "medications",
    "biomarkers",
    "additional_context",
    "last_treatment_date",
}
_ALLOWED_TRIAL_KEYS = {
    "title",
    "nct_id",
    "phase",
    "status",
    "eligibility_summary",
    "warning_flags",
}

_MAX_VALUE_LEN = 1500
_MAX_LIST_ITEMS = 40


def _sanitize_mapping(raw, allowed: set[str], label: str) -> dict:
    """Whitelist keys, cap sizes, and scrub each value before it reaches an LLM."""
    if not isinstance(raw, dict):
        raise ValueError(f"{label} must be an object.")

    out: dict = {}
    for key in allowed:
        if key not in raw:
            continue
        value = raw[key]

        if isinstance(value, str):
            cleaned = clean_freetext_for_llm(
                value, max_length=_MAX_VALUE_LEN, field=f"{label}.{key}"
            )
            if cleaned:
                out[key] = cleaned
        elif isinstance(value, bool):
            out[key] = value
        elif isinstance(value, int):
            # Bound numerics so nothing absurd reaches the prompt.
            out[key] = max(-10_000, min(10_000, value))
        elif isinstance(value, list):
            items = []
            for item in value[:_MAX_LIST_ITEMS]:
                if not isinstance(item, str):
                    continue
                cleaned = clean_freetext_for_llm(
                    item, max_length=300, field=f"{label}.{key}"
                )
                if cleaned:
                    items.append(cleaned)
            if items:
                out[key] = items
        # Anything else (nested dicts, None) is dropped on purpose.
    return out


class QA(BaseModel):
    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., max_length=500)
    answer: str = Field(..., max_length=1000)

    @field_validator("question", "answer")
    @classmethod
    def _clean(cls, v: str) -> str:
        cleaned = clean_freetext_for_llm(v, max_length=1000, field="Q&A")
        if not cleaned:
            raise ValueError("Question and answer cannot be empty.")
        return cleaned


class ClarifyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient: dict
    trial: dict
    # Hard cap matches the service's 3-question limit; anything longer is a
    # client bug or an attempt to inflate the prompt.
    history: list[QA] = Field(default_factory=list, max_length=5)

    @field_validator("patient")
    @classmethod
    def _v_patient(cls, v):
        return _sanitize_mapping(v, _ALLOWED_PATIENT_KEYS, "patient")

    @field_validator("trial")
    @classmethod
    def _v_trial(cls, v):
        return _sanitize_mapping(v, _ALLOWED_TRIAL_KEYS, "trial")


class ClarifyResponse(BaseModel):
    verdict: str = Field(..., description="'ask' | 'eligible' | 'ineligible' | 'stop'")
    question: Optional[str] = None
    reason: Optional[str] = None
    remaining: int = Field(default=0)


@router.post(
    "",
    response_model=ClarifyResponse,
    dependencies=[Depends(block_automated_clients)],
)
@limiter.limit("15/minute;60/hour")
def clarify(request: Request, body: ClarifyRequest):
    enforce_ai_quota(request)
    try:
        result = clarify_service.clarify(
            patient=body.patient,
            trial=body.trial,
            history=[q.model_dump() for q in body.history],
        )
    except Exception:
        logger.exception("clarify.failed")
        raise HTTPException(
            status_code=500, detail="Couldn't compute a clarification."
        )
    return ClarifyResponse(**result)
