"""
Matching orchestrator — coordinates Linkup search + LLM ranking.
Also handles the ClinicalTrials.gov fallback when Linkup returns thin results.
"""

import asyncio
import logging

import httpx

from models.patient import PatientProfile
from models.trial import MatchResponse
from services import linkup_service, llm_service

logger = logging.getLogger(__name__)

_CTGOV_API = "https://clinicaltrials.gov/api/v2/studies"


async def find_matching_trials(patient: PatientProfile) -> MatchResponse:
    """Main entry point. Runs search + rank pipeline."""

    # 1. Search via Linkup
    linkup_data = await linkup_service.search_for_trials(
        condition=patient.condition,
        location=patient.location,
        treatment_history=patient.treatment_history,
    )

    # 2. Fallback: if Linkup trial listings are sparse, supplement with
    #    ClinicalTrials.gov direct API (free, no key needed)
    if _is_sparse(linkup_data.get("trial_listings", "")):
        logger.info("Linkup trial listings sparse — supplementing with ClinicalTrials.gov API")
        ct_gov_text = await _fetch_ctgov_trials(patient.condition)
        if ct_gov_text:
            linkup_data["trial_listings"] = (
                linkup_data.get("trial_listings", "") + "\n\n" + ct_gov_text
            )

    # 3. Rank + annotate with LLM
    response = await llm_service.rank_and_reason(patient, linkup_data)

    return response


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _is_sparse(text: str) -> bool:
    """Consider results sparse if they're shorter than 200 chars."""
    return len(text.strip()) < 200


async def _fetch_ctgov_trials(condition: str, max_results: int = 10) -> str:
    """
    Pull open recruiting trials from the free ClinicalTrials.gov v2 API
    and return a plain-text summary suitable for the LLM prompt.
    """
    params = {
        "query.cond": condition,
        "filter.overallStatus": "RECRUITING",
        "pageSize": max_results,
        "fields": "NCTId,BriefTitle,Phase,LeadSponsorName,LocationCity,LocationState,EligibilityCriteria,InterventionName",
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(_CTGOV_API, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning(f"ClinicalTrials.gov API fallback failed: {exc}")
        return ""

    studies = data.get("studies", [])
    if not studies:
        return ""

    lines = [f"[ClinicalTrials.gov fallback — {len(studies)} recruiting trials found]"]
    for s in studies:
        proto = s.get("protocolSection", {})
        id_module = proto.get("identificationModule", {})
        status_module = proto.get("statusModule", {})
        desc_module = proto.get("descriptionModule", {})
        design_module = proto.get("designModule", {})
        sponsor_module = proto.get("sponsorCollaboratorsModule", {})
        contacts_module = proto.get("contactsLocationsModule", {})
        eligibility_module = proto.get("eligibilityModule", {})
        interventions_module = proto.get("armsInterventionsModule", {})

        nct_id = id_module.get("nctId", "")
        title = id_module.get("briefTitle", "Untitled")
        phase_list = design_module.get("phases", [])
        phase = phase_list[0] if phase_list else "N/A"
        sponsor = sponsor_module.get("leadSponsor", {}).get("name", "")
        eligibility_text = eligibility_module.get("eligibilityCriteria", "")[:400]
        locations = contacts_module.get("locations", [])
        location_str = ", ".join(
            f"{loc.get('city', '')}, {loc.get('state', '')}"
            for loc in locations[:3]
        )

        interventions = interventions_module.get("interventions", [])
        intervention_names = ", ".join(
            i.get("name", "") for i in interventions[:3]
        )

        lines.append(
            f"\n{nct_id} | {title}\n"
            f"Phase: {phase} | Sponsor: {sponsor} | Sites: {location_str}\n"
            f"Interventions: {intervention_names}\n"
            f"Eligibility (excerpt): {eligibility_text}"
        )

    return "\n".join(lines)
