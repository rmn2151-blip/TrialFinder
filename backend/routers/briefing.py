"""
Doctor briefing endpoint.

  POST /api/briefing/pdf — accepts a patient + MatchResponse, returns a PDF
                           the patient can hand to their oncologist.
"""

import logging

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel

from models.patient import PatientProfile
from models.trial import MatchResponse
from services.briefing_service import render_briefing_pdf

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/briefing", tags=["briefing"])


class BriefingRequest(BaseModel):
    patient: PatientProfile
    match: MatchResponse


@router.post("/pdf")
def briefing_pdf(body: BriefingRequest):
    if not body.match.trials:
        raise HTTPException(status_code=400, detail="No trials to brief on.")
    try:
        pdf_bytes = render_briefing_pdf(body.patient, body.match)
    except Exception as exc:
        logger.exception("PDF generation failed: %s", exc)
        raise HTTPException(status_code=500, detail="Couldn't generate the briefing PDF.")

    filename = "trialfinder-briefing.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
