"""
Doctor briefing endpoint.

  POST /api/briefing/pdf — accepts a patient + MatchResponse, returns a PDF
                           the patient can hand to their oncologist.
"""

import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict

from middleware.abuse import block_automated_clients
from middleware.rate_limit import limiter

from models.patient import PatientProfile
from models.trial import MatchResponse
from services.briefing_service import render_briefing_pdf

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/briefing", tags=["briefing"])


class BriefingRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # PatientProfile runs its own sanitizing validators, so the text that
    # reaches the PDF renderer is already scrubbed of control characters and
    # markup. That matters here because reportlab renders a mini-markup
    # dialect, and unescaped input could otherwise corrupt the document.
    patient: PatientProfile
    match: MatchResponse


@router.post("/pdf", dependencies=[Depends(block_automated_clients)])
@limiter.limit("10/minute;30/hour")
def briefing_pdf(request: Request, body: BriefingRequest):
    if not body.match.trials:
        raise HTTPException(status_code=400, detail="No trials to brief on.")
    if len(body.match.trials) > 50:
        raise HTTPException(status_code=400, detail="Too many trials to brief on.")
    try:
        pdf_bytes = render_briefing_pdf(body.patient, body.match)
    except Exception:
        logger.exception("briefing.pdf_failed")
        raise HTTPException(
            status_code=500, detail="Couldn't generate the briefing PDF."
        )

    filename = "trialfinder-briefing.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
