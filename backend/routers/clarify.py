"""
Ambiguity resolution endpoint.

  POST /api/clarify — takes a patient profile, trial, and the prior Q&A
                      history, returns either the next clarifying question
                      or an eligibility verdict.
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from services import clarify_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/clarify", tags=["clarify"])


class QA(BaseModel):
    question: str
    answer: str


class ClarifyRequest(BaseModel):
    patient: dict
    trial: dict
    history: list[QA] = Field(default_factory=list)


class ClarifyResponse(BaseModel):
    verdict: str = Field(..., description="'ask' | 'eligible' | 'ineligible' | 'stop'")
    question: Optional[str] = None
    reason: Optional[str] = None
    remaining: int = Field(default=0)


@router.post("", response_model=ClarifyResponse)
def clarify(body: ClarifyRequest):
    try:
        result = clarify_service.clarify(
            patient=body.patient,
            trial=body.trial,
            history=[q.model_dump() for q in body.history],
        )
    except Exception as e:
        logger.exception("Clarify failed: %s", e)
        raise HTTPException(status_code=500, detail="Couldn't compute a clarification.")
    return ClarifyResponse(**result)
