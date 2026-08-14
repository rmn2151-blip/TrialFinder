"""
Conversational intake endpoints.

  POST /api/intake/start  — begin a new session, returns first question
  POST /api/intake/answer — submit an answer, returns the next question or
                            (when the agent has enough) the structured profile

Every answer is fed to an LLM, so these are rate limited, quota'd, and the
answer text is sanitized before it reaches the prompt.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request

from middleware.abuse import block_automated_clients, enforce_ai_quota
from middleware.rate_limit import limiter
from models.intake import IntakeAnswerRequest, IntakeAnswerResponse, IntakeStartResponse
from models.validators import clean_freetext_for_llm
from services import intake_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/intake", tags=["intake"])


@router.post(
    "/start",
    response_model=IntakeStartResponse,
    dependencies=[Depends(block_automated_clients)],
)
@limiter.limit("10/minute;30/hour")
def start_intake(request: Request):
    session_id, question = intake_service.start_session()
    return IntakeStartResponse(session_id=session_id, question=question)


@router.post(
    "/answer",
    response_model=IntakeAnswerResponse,
    dependencies=[Depends(block_automated_clients)],
)
@limiter.limit("20/minute;120/hour")
def submit_answer(request: Request, body: IntakeAnswerRequest):
    answer = clean_freetext_for_llm(body.answer, max_length=2000, field="Answer")
    if not answer:
        raise HTTPException(status_code=400, detail="Please enter an answer.")

    enforce_ai_quota(request)

    try:
        result = intake_service.answer(body.session_id, answer)
    except ValueError as e:
        # Unknown or expired session.
        raise HTTPException(status_code=404, detail=str(e))
    except Exception:
        logger.exception("intake.answer_failed")
        raise HTTPException(status_code=500, detail="Couldn't process your answer.")

    return IntakeAnswerResponse(
        session_id=body.session_id,
        question=result.get("question"),
        complete=bool(result.get("complete")),
        profile=result.get("profile"),
        turns_so_far=result.get("turns_so_far", 0),
        max_turns=10,
    )
