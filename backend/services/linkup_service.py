"""
Linkup search service — wraps the Linkup SDK to fire 3 targeted queries
per patient request and aggregate the results.

Set MOCK_LINKUP=true in .env to skip real API calls during development.
"""

import asyncio
import json
import logging
import os
from pathlib import Path

from linkup import LinkupClient

from services.cache import get as cache_get
from services.cache import make_key, set as cache_set

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_LINKUP_API_KEY = os.getenv("LINKUP_API_KEY", "")
_MOCK_MODE = os.getenv("MOCK_LINKUP", "false").lower() == "true"
_DEPTH = os.getenv("LINKUP_DEPTH", "standard")  # "standard" dev, "deep" for demos

_MOCK_FIXTURE_PATH = Path(__file__).parent.parent / "tests" / "fixtures" / "linkup_mock.json"


# ---------------------------------------------------------------------------
# Public interface
# ---------------------------------------------------------------------------


async def search_for_trials(
    condition: str,
    location: str,
    treatment_history: str | None = None,
) -> dict:
    """
    Fire three Linkup queries in parallel and return an aggregated dict:
    {
        "trial_listings":  <sourcedAnswer text from query 1>,
        "recent_results":  <sourcedAnswer text from query 2>,
        "mechanism_coverage": <sourcedAnswer text from query 3>,
        "sources": [ {name, url, snippet}, ... ]   # deduplicated across all queries
    }
    """
    if _MOCK_MODE:
        logger.info("MOCK_LINKUP=true — returning fixture data")
        return _load_mock_fixture()

    if not _LINKUP_API_KEY:
        raise ValueError("LINKUP_API_KEY is not set. Add it to your .env file.")

    # Check cache before hitting Linkup
    cache_key = make_key(condition, location, treatment_history)
    cached = cache_get(cache_key)
    if cached is not None:
        return cached

    queries = _build_queries(condition, location, treatment_history)

    logger.info(f"Firing {len(queries)} Linkup queries for condition='{condition}' location='{location}'")

    # Run all three queries concurrently to keep latency down
    results = await asyncio.gather(
        *[_linkup_search(q["query"], q["include_domains"]) for q in queries],
        return_exceptions=True,
    )

    aggregated = _aggregate_results(results, condition)

    # Cache the result to protect budget
    cache_set(cache_key, aggregated)

    return aggregated


# ---------------------------------------------------------------------------
# Query construction
# ---------------------------------------------------------------------------


def _build_queries(
    condition: str,
    location: str,
    treatment_history: str | None,
) -> list[dict]:
    """
    Build three focused queries.
    Q1: recruiting trials on clinicaltrials.gov
    Q2: recent trial results & news
    Q3: mechanism / plain-English trial coverage from journals
    """
    year_hint = "2024 2025 2026"

    q1 = (
        f'clinical trial recruiting "{condition}" {location} {year_hint}'
    )
    q2 = (
        f'"{condition}" clinical trial results efficacy outcomes {year_hint}'
    )
    # For the mechanism query, strip location — broader coverage is better
    q3 = (
        f'"{condition}" clinical trial treatment mechanism how it works {year_hint}'
    )

    return [
        {
            "query": q1,
            "include_domains": ["clinicaltrials.gov"],   # Pin Q1 to CT.gov
        },
        {
            "query": q2,
            "include_domains": [],  # No domain restriction — cast wide
        },
        {
            "query": q3,
            "include_domains": [],
        },
    ]


# ---------------------------------------------------------------------------
# Linkup SDK wrapper (sync SDK called in a thread pool)
# ---------------------------------------------------------------------------


async def _linkup_search(query: str, include_domains: list[str]) -> dict:
    """
    Calls the Linkup SDK synchronously inside a thread pool so it doesn't
    block the async event loop.
    """
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(
        None, _sync_linkup_search, query, include_domains
    )


def _sync_linkup_search(query: str, include_domains: list[str]) -> dict:
    client = LinkupClient(api_key=_LINKUP_API_KEY)

    kwargs: dict = {
        "query": query,
        "depth": _DEPTH,
        "output_type": "sourcedAnswer",
    }
    if include_domains:
        kwargs["include_domains"] = include_domains

    try:
        response = client.search(**kwargs)
        return {
            "query": query,
            "answer": getattr(response, "answer", ""),
            "sources": _extract_sources(response),
        }
    except Exception as exc:
        logger.warning(f"Linkup query failed: '{query}' — {exc}")
        return {"query": query, "answer": "", "sources": [], "error": str(exc)}


def _extract_sources(response) -> list[dict]:
    """Parse sources from a Linkup response object."""
    sources = []
    raw_sources = getattr(response, "sources", []) or []
    for s in raw_sources:
        sources.append(
            {
                "name": getattr(s, "name", "") or "",
                "url": getattr(s, "url", "") or "",
                "snippet": getattr(s, "snippet", "") or "",
            }
        )
    return sources


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------


def _aggregate_results(results: list, condition: str) -> dict:
    """
    Merge results from all three queries into one dict the LLM service
    can consume. Gracefully handles exceptions from individual queries.
    """
    trial_listings = ""
    recent_results = ""
    mechanism_coverage = ""
    all_sources: list[dict] = []
    seen_urls: set[str] = set()

    labels = ["trial_listings", "recent_results", "mechanism_coverage"]
    texts = [trial_listings, recent_results, mechanism_coverage]

    for i, result in enumerate(results):
        if isinstance(result, Exception):
            logger.warning(f"Query {i+1} raised exception: {result}")
            continue

        texts[i] = result.get("answer", "")

        for src in result.get("sources", []):
            url = src.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                all_sources.append(src)

    # Fallback: if trial_listings is empty try ClinicalTrials.gov direct API
    if not texts[0].strip():
        logger.info("Linkup returned no trial listings — will rely on ClinicalTrials.gov fallback")

    return {
        "trial_listings": texts[0],
        "recent_results": texts[1],
        "mechanism_coverage": texts[2],
        "sources": all_sources,
        "condition": condition,
    }


# ---------------------------------------------------------------------------
# Mock fixture
# ---------------------------------------------------------------------------


def _load_mock_fixture() -> dict:
    if _MOCK_FIXTURE_PATH.exists():
        with open(_MOCK_FIXTURE_PATH) as f:
            return json.load(f)

    # Inline fallback mock so dev works out-of-the-box with no fixture file
    return {
        "trial_listings": (
            "NCT05555201 — Phase II trial of sotorasib (AMG-510) in KRAS G12C NSCLC patients "
            "who have received prior platinum therapy. Recruiting at MSK New York and Dana-Farber Boston. "
            "NCT05123456 — Phase III trial of adagrasib + pembrolizumab in KRAS G12C+ NSCLC. "
            "Recruiting at multiple US sites including New York Presbyterian. "
            "NCT04956640 — CodeBreaK 200: sotorasib vs docetaxel in previously treated NSCLC. "
            "Enrolling by invitation at MD Anderson and MSK."
        ),
        "recent_results": (
            "NEJM 2024: Sotorasib demonstrated 37.1% objective response rate in KRAS G12C NSCLC "
            "after prior therapy. Median PFS 6.3 months. Grade 3+ adverse events in 19% of patients. "
            "ASCO 2025: Adagrasib + pembrolizumab combination showed 63% ORR in treatment-naive NSCLC."
        ),
        "mechanism_coverage": (
            "KRAS G12C inhibitors like sotorasib and adagrasib work by locking the KRAS protein "
            "in its inactive state. KRAS G12C is a specific mutation found in ~13% of lung adenocarcinomas. "
            "Unlike traditional chemotherapy, these are once-daily oral pills that specifically target "
            "the cancer's driving mutation with fewer off-target effects."
        ),
        "sources": [
            {
                "name": "ClinicalTrials.gov — NCT05555201",
                "url": "https://clinicaltrials.gov/study/NCT05555201",
                "snippet": "Phase II sotorasib KRAS G12C NSCLC",
            },
            {
                "name": "NEJM — Sotorasib in KRAS G12C NSCLC",
                "url": "https://www.nejm.org/doi/full/10.1056/NEJMoa2309171",
                "snippet": "37.1% ORR, median PFS 6.3 months",
            },
        ],
        "condition": "NSCLC KRAS G12C (mock)",
    }
