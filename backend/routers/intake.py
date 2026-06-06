"""
Conversational intake endpoints.

  POST /api/intake/start  — begin a new session, returns first question
  POST /api/intake/answer — submit a user answer, returns next question or
                            (when the agent has enough) the structured profile
"""

import logging

from fastapi import APIRouter, HTTPException

from models.intake import IntakeAnswerRequest, IntakeAnswerResponse, IntakeStartResponse
from services import intake_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/intake", tags=["intake"])


@router.post("/start", response_model=IntakeStartResponse)
def start_intake():
    session_id, question = intake_service.start_session()
    return IntakeStartResponse(session_id=session_id, question=question)


@router.post("/answer", response_model=IntakeAnswerResponse)
def submit_answer(body: IntakeAnswerRequest):
    try:
        result = intake_service.answer(body.session_id, body.answer)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.exception("Intake answer failed: %s", e)
        raise HTTPException(status_code=500, detail="Couldn't process your answer.")

    return IntakeAnswerResponse(
        session_id=body.session_id,
        question=result.get("question"),
        complete=bool(result.get("complete")),
        profile=result.get("profile"),
        turns_so_far=result.get("turns_so_far", 0),
        max_turns=10,
    )
