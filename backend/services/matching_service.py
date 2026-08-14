"""
Matching orchestrator. Coordinates trial search and LLM ranking.

Search comes from services/search_service.py, which uses ClinicalTrials.gov
as the authoritative registry plus Claude's web_search tool for supplementary
context. There is no third-party search API and no separate credits to buy.
"""

import logging

from models.patient import PatientProfile
from models.trial import MatchResponse
from services import llm_service, search_service

logger = logging.getLogger(__name__)


async def find_matching_trials(patient: PatientProfile) -> MatchResponse:
    """Main entry point. Runs the search then rank pipeline."""

    search_data = await search_service.search_for_trials(
        condition=patient.condition,
        location=patient.location,
        treatment_history=patient.treatment_history,
    )

    listings = search_data.get("trial_listings", "")
    if not listings.strip():
        logger.info(
            "No recruiting trials found for condition='%s' location='%s'",
            patient.condition,
            patient.location,
        )
        # Retry once without the location filter. Many conditions have trials
        # nationally even when nothing is nearby.
        broader = await search_service.fetch_ctgov_trials(
            patient.condition, location=None
        )
        if broader.strip():
            logger.info("Broader nationwide search found trials.")
            search_data["trial_listings"] = broader

    return await llm_service.rank_and_reason(patient, search_data)
