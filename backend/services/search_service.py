"""
Search layer. Replaces the old Linkup integration.

Two sources, no third-party search credits required:

1. ClinicalTrials.gov v2 API — the authoritative registry of clinical trials.
   Free, no API key, no rate limit worth worrying about. This is the primary
   source for "what trials exist and are recruiting for this condition".

2. Claude's built-in web_search tool — used only for supplementary context
   (recent results, site reputation, drug intel, media coverage). Runs through
   the ANTHROPIC_API_KEY you already have, so there is no separate provider
   to sign up for or fund.

Set MOCK_SEARCH=true to skip network calls entirely during development.
"""

import asyncio
import logging
import os
from typing import Optional

import httpx

from services import llm_provider

logger = logging.getLogger(__name__)

# MOCK_LINKUP kept as an alias so existing .env files keep working.
_MOCK_MODE = (
    os.getenv("MOCK_SEARCH", os.getenv("MOCK_LINKUP", "false")).lower() == "true"
)

_CTGOV_API = "https://clinicaltrials.gov/api/v2/studies"

# How many trials to pull from CT.gov per search.
# Every trial here becomes ~900 characters of eligibility text in the ranking
# prompt, so this is the single biggest lever on search latency. 12 gives the
# model enough to choose from while keeping the prompt small enough to rank
# quickly. Raise it if you want breadth over speed.
_CTGOV_PAGE_SIZE = int(os.getenv("CTGOV_PAGE_SIZE", "12"))


# ---------------------------------------------------------------------------
# Primary: ClinicalTrials.gov
# ---------------------------------------------------------------------------


# Statuses we surface to patients.
#
# RECRUITING / ENROLLING_BY_INVITATION are actionable today. NOT_YET_RECRUITING
# is included deliberately: a trial opening next month is exactly what a
# watchlist is for, and the alert sweep will email the user the moment it
# flips to recruiting. ACTIVE_NOT_RECRUITING is included so users can watch
# for results being published.
_PATIENT_RELEVANT_STATUSES = (
    "RECRUITING|ENROLLING_BY_INVITATION|NOT_YET_RECRUITING|ACTIVE_NOT_RECRUITING"
)


async def fetch_ctgov_trials(
    condition: str,
    location: Optional[str] = None,
    *,
    recruiting_only: bool = True,
    max_results: Optional[int] = None,
) -> str:
    """
    Query ClinicalTrials.gov for trials matching a condition, and return a
    plain-text block the ranker LLM can read.

    We ask CT.gov itself to filter to actively recruiting studies, so
    non-recruiting trials never enter the pipeline in the first place.
    """
    page_size = max_results or _CTGOV_PAGE_SIZE

    params = {
        "query.cond": condition,
        "pageSize": page_size,
        "format": "json",
    }
    if location:
        params["query.locn"] = location
    if recruiting_only:
        # CT.gov accepts a pipe-separated list of statuses.
        params["filter.overallStatus"] = _PATIENT_RELEVANT_STATUSES

    try:
        async with httpx.AsyncClient(timeout=20.0) as client:
            resp = await client.get(_CTGOV_API, params=params)
            resp.raise_for_status()
            data = resp.json()
    except Exception as exc:
        logger.warning("ClinicalTrials.gov query failed: %s", exc)
        return ""

    studies = data.get("studies", []) or []
    if not studies:
        logger.info("CT.gov returned no recruiting studies for '%s'", condition)
        return ""

    logger.info(
        "CT.gov returned %d recruiting studies for '%s'", len(studies), condition
    )
    return _format_studies(studies, condition)


def _format_studies(studies: list, condition: str) -> str:
    lines = [
        f"[ClinicalTrials.gov — {len(studies)} actively recruiting trials "
        f"for '{condition}']"
    ]

    for s in studies:
        proto = s.get("protocolSection", {})
        ident = proto.get("identificationModule", {})
        status_mod = proto.get("statusModule", {})
        design = proto.get("designModule", {})
        sponsor_mod = proto.get("sponsorCollaboratorsModule", {})
        contacts = proto.get("contactsLocationsModule", {})
        elig = proto.get("eligibilityModule", {})
        arms = proto.get("armsInterventionsModule", {})
        desc = proto.get("descriptionModule", {})

        nct_id = ident.get("nctId", "")
        title = ident.get("briefTitle", "Untitled")
        status = status_mod.get("overallStatus", "")
        phases = design.get("phases", []) or []
        phase = ", ".join(phases) if phases else "N/A"
        sponsor = sponsor_mod.get("leadSponsor", {}).get("name", "")

        # Locations: keep the first few, with city/state/country.
        locations = contacts.get("locations", []) or []
        loc_strs = []
        for loc in locations[:5]:
            bits = [loc.get("city"), loc.get("state"), loc.get("country")]
            loc_strs.append(", ".join(b for b in bits if b))
        loc_line = " | ".join(loc_strs) if loc_strs else "Not specified"

        interventions = arms.get("interventions", []) or []
        interv_line = ", ".join(
            f"{i.get('type', '')}: {i.get('name', '')}".strip(": ")
            for i in interventions[:5]
        )

        criteria = (elig.get("eligibilityCriteria") or "")[:900]
        min_age = elig.get("minimumAge", "")
        max_age = elig.get("maximumAge", "")
        sex = elig.get("sex", "")
        summary = (desc.get("briefSummary") or "")[:600]

        completion = (
            status_mod.get("primaryCompletionDateStruct", {}).get("date")
            or status_mod.get("completionDateStruct", {}).get("date")
            or ""
        )

        lines.append(
            f"\n---\n"
            f"NCT ID: {nct_id}\n"
            f"Title: {title}\n"
            f"Status: {status}\n"
            f"Phase: {phase}\n"
            f"Sponsor: {sponsor}\n"
            f"Sites: {loc_line}\n"
            f"Interventions: {interv_line}\n"
            f"Age range: {min_age} to {max_age} | Sex: {sex}\n"
            f"Primary completion: {completion}\n"
            f"Summary: {summary}\n"
            f"Eligibility criteria: {criteria}\n"
            f"URL: https://clinicaltrials.gov/study/{nct_id}"
        )

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Supplementary: Claude web search
# ---------------------------------------------------------------------------


async def web_search(query: str, *, max_uses: int = 3) -> dict:
    """
    Run a web-grounded search through the configured LLM provider.

    Gemini uses Google Search grounding; Claude uses its web_search tool.
    Either way this returns {"answer": str, "sources": [...]} and never
    raises, so callers degrade gracefully rather than failing the request.
    """
    if _MOCK_MODE:
        return {"answer": "", "sources": []}

    return await llm_provider.search(query, max_uses=max_uses)


# ---------------------------------------------------------------------------
# Combined search used by the matching pipeline
# ---------------------------------------------------------------------------


async def search_for_trials(
    condition: str,
    location: str,
    treatment_history: Optional[str] = None,
) -> dict:
    """
    Gather everything the ranker needs. Shape is unchanged from the old
    Linkup service so downstream callers keep working:

        {
          "trial_listings": str,      # CT.gov, authoritative
          "recent_results": str,      # web search
          "mechanism_coverage": str,  # web search
          "sources": [...],
          "condition": str,
        }
    """
    if _MOCK_MODE:
        logger.info("MOCK_SEARCH=true — using fixture data")
        return _mock_bundle(condition)

    # CT.gov is the source of truth for what's recruiting. Run the two
    # supplementary web searches alongside it.
    listings_task = fetch_ctgov_trials(condition, location)
    results_task = web_search(
        f"What did recent clinical trials for {condition} find? "
        f"Summarize efficacy results and outcomes reported in 2024 and 2025."
    )
    mechanism_task = web_search(
        f"Explain in plain English how current experimental treatments for "
        f"{condition} work, and what is being tested in clinical trials now."
    )

    listings, recent, mechanism = await asyncio.gather(
        listings_task, results_task, mechanism_task, return_exceptions=True
    )

    if isinstance(listings, Exception):
        logger.warning("CT.gov task failed: %s", listings)
        listings = ""
    if isinstance(recent, Exception):
        logger.warning("Recent-results search failed: %s", recent)
        recent = {"answer": "", "sources": []}
    if isinstance(mechanism, Exception):
        logger.warning("Mechanism search failed: %s", mechanism)
        mechanism = {"answer": "", "sources": []}

    sources: list[dict] = []
    seen: set[str] = set()
    for bundle in (recent, mechanism):
        for s in bundle.get("sources", []):
            url = s.get("url")
            if url and url not in seen:
                seen.add(url)
                sources.append(s)

    return {
        "trial_listings": listings,
        "recent_results": recent.get("answer", ""),
        "mechanism_coverage": mechanism.get("answer", ""),
        "sources": sources,
        "condition": condition,
    }


def _mock_bundle(condition: str) -> dict:
    return {
        "trial_listings": (
            f"[Mock data — no live search. Condition requested: {condition}]\n"
            "NCT05555201 | Phase II trial of sotorasib in KRAS G12C NSCLC. "
            "Status: Recruiting. Sponsor: Memorial Sloan Kettering. "
            "Sites: New York, NY. "
            "Eligibility: prior platinum therapy required, ECOG 0-1. "
            "URL: https://clinicaltrials.gov/study/NCT05555201"
        ),
        "recent_results": "Mock: recent trial results unavailable in mock mode.",
        "mechanism_coverage": "Mock: mechanism coverage unavailable in mock mode.",
        "sources": [],
        "condition": f"{condition} (mock)",
    }
