"""
ClinicalTrials.gov v2 API client for fetching the current state of a single
study by NCT ID. Used by the watchlist change-detection job.

This API is free and needs no key, so the nightly sweep does NOT consume any
Linkup budget.
"""

import logging
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

_CTGOV_STUDY_API = "https://clinicaltrials.gov/api/v2/studies/{nct_id}"

_FIELDS = (
    "NCTId,BriefTitle,OverallStatus,Phase,"
    "PrimaryCompletionDate,CompletionDate,LocationFacility"
)


def fetch_study(nct_id: str, *, timeout: float = 10.0) -> Optional[dict]:
    """
    Fetch a normalized snapshot of one trial. Returns None if the study can't
    be retrieved. Synchronous (the job runs outside the request event loop).
    """
    url = _CTGOV_STUDY_API.format(nct_id=nct_id)
    try:
        resp = httpx.get(url, params={"fields": _FIELDS}, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
    except Exception as exc:  # network error, 404, etc.
        logger.warning("CT.gov fetch failed for %s: %s", nct_id, exc)
        return None

    return _normalize(nct_id, data)


def _normalize(nct_id: str, data: dict) -> dict:
    proto = data.get("protocolSection", {})
    id_mod = proto.get("identificationModule", {})
    status_mod = proto.get("statusModule", {})
    design_mod = proto.get("designModule", {})
    contacts_mod = proto.get("contactsLocationsModule", {})

    phases = design_mod.get("phases", []) or []
    completion = (
        status_mod.get("primaryCompletionDateStruct", {}).get("date")
        or status_mod.get("completionDateStruct", {}).get("date")
    )
    locations = contacts_mod.get("locations", []) or []

    return {
        "nct_id": nct_id,
        "title": id_mod.get("briefTitle"),
        "status": status_mod.get("overallStatus"),
        "phase": phases[0] if phases else None,
        "completion_date": completion,
        "site_count": len(locations),
        "source_url": f"https://clinicaltrials.gov/study/{nct_id}",
    }
