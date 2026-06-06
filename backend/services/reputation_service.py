"""
Site / principal-investigator reputation lookup.

For each trial sponsor (and optional PI name), we fire a single Linkup query
asking for institutional reputation, recent publications, and recent press —
then ask the LLM to normalize the result into a structured Reputation object.

Lazy and cached: the endpoint is hit on user demand (when they expand the
"site reputation" disclosure in the UI), and results are cached for an hour
per sponsor to protect the $20 Linkup budget.

Mock mode (MOCK_LINKUP=true) returns fixture data so dev/demo flows work
without spending credits.
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import time
from typing import Optional

import anthropic

from models.reputation import (
    PressItem,
    Publication,
    Reputation,
    SourceLink,
    Warning,
)

logger = logging.getLogger(__name__)

_LINKUP_API_KEY = os.getenv("LINKUP_API_KEY", "")
_ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_MOCK_MODE = os.getenv("MOCK_LINKUP", "false").lower() == "true"
_DEPTH = os.getenv("LINKUP_DEPTH", "standard")

_CACHE_TTL_SECONDS = 3600  # one hour
# { key: (timestamp, Reputation dict) }
_cache: dict[str, tuple[float, dict]] = {}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


async def get_reputation(sponsor: str, pi: Optional[str] = None) -> Reputation:
    """
    Return a Reputation snapshot for a sponsor (and optional PI). Cached.
    """
    sponsor = (sponsor or "").strip()
    if not sponsor:
        raise ValueError("sponsor is required")

    key = _cache_key(sponsor, pi)
    cached = _cache_get(key)
    if cached is not None:
        return Reputation(**{**cached, "cached": True})

    if _MOCK_MODE:
        rep = _mock_reputation(sponsor, pi)
    else:
        rep = await _live_reputation(sponsor, pi)

    _cache_set(key, rep.model_dump())
    return rep


# ---------------------------------------------------------------------------
# Live lookup (Linkup search + Claude normalization)
# ---------------------------------------------------------------------------


async def _live_reputation(sponsor: str, pi: Optional[str]) -> Reputation:
    if not _LINKUP_API_KEY:
        raise ValueError(
            "LINKUP_API_KEY is not set. Set MOCK_LINKUP=true for dev or add the key."
        )

    query = _build_query(sponsor, pi)
    logger.info("Reputation lookup: %s", query)

    linkup_result = await _linkup_search(query)

    if not _ANTHROPIC_API_KEY:
        # Without the LLM we can still return raw sources as a thin response.
        return _from_raw_sources(sponsor, pi, linkup_result)

    return await _normalize_with_llm(sponsor, pi, linkup_result)


def _build_query(sponsor: str, pi: Optional[str]) -> str:
    pi_part = f' "{pi}" principal investigator publications' if pi else ""
    return (
        f'"{sponsor}" clinical research reputation hospital cancer center'
        f' "FDA warning letter" OR sanction OR enforcement'
        f' recent press 2020 2021 2022 2023 2024 2025{pi_part}'
    )


async def _linkup_search(query: str) -> dict:
    """Single Linkup sourcedAnswer call, in a thread pool (SDK is sync)."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, _sync_linkup_search, query)


def _sync_linkup_search(query: str) -> dict:
    from linkup import LinkupClient

    client = LinkupClient(api_key=_LINKUP_API_KEY)
    try:
        response = client.search(
            query=query, depth=_DEPTH, output_type="sourcedAnswer"
        )
    except Exception as exc:
        logger.warning("Linkup reputation query failed: %s", exc)
        return {"answer": "", "sources": []}

    sources = []
    for s in getattr(response, "sources", []) or []:
        sources.append(
            {
                "name": getattr(s, "name", "") or "",
                "url": getattr(s, "url", "") or "",
                "snippet": getattr(s, "snippet", "") or "",
            }
        )
    return {"answer": getattr(response, "answer", "") or "", "sources": sources}


def _from_raw_sources(sponsor: str, pi: Optional[str], linkup_result: dict) -> Reputation:
    """Fallback path when no Anthropic key is set — return what Linkup gave us."""
    sources = [
        SourceLink(label=s.get("name") or s.get("url"), url=s["url"], snippet=s.get("snippet"))
        for s in linkup_result.get("sources", [])
        if s.get("url")
    ]
    return Reputation(
        sponsor=sponsor,
        pi=pi,
        summary=linkup_result.get("answer", "") or None,
        sources=sources,
    )


async def _normalize_with_llm(
    sponsor: str, pi: Optional[str], linkup_result: dict
) -> Reputation:
    """Ask Claude to produce a structured Reputation JSON from the Linkup data."""
    prompt = _NORMALIZE_PROMPT.format(
        sponsor=sponsor,
        pi=pi or "Not provided",
        answer=linkup_result.get("answer", "")[:6000],
        sources=json.dumps(linkup_result.get("sources", [])[:10], indent=2),
    )

    loop = asyncio.get_event_loop()
    raw = await loop.run_in_executor(None, _sync_claude_call, prompt)

    parsed = _parse_llm_json(raw)
    return _build_reputation(sponsor, pi, parsed, linkup_result)


def _sync_claude_call(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=_ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system=(
            "You are a research assistant. Respond with valid JSON only — "
            "no markdown fences, no prose outside the JSON."
        ),
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _parse_llm_json(raw: str) -> dict:
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```$", "", cleaned)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        logger.warning("Reputation LLM returned invalid JSON: %s", exc)
        return {}


def _build_reputation(
    sponsor: str, pi: Optional[str], parsed: dict, linkup_result: dict
) -> Reputation:
    pubs = []
    for p in (parsed.get("publications") or [])[:8]:
        if not isinstance(p, dict) or not p.get("title"):
            continue
        pubs.append(
            Publication(
                title=str(p["title"])[:300],
                url=p.get("url"),
                year=str(p["year"])[:8] if p.get("year") else None,
            )
        )

    warnings = []
    for w in (parsed.get("warnings") or [])[:5]:
        if not isinstance(w, dict) or not w.get("label"):
            continue
        sev = str(w.get("severity") or "warning").lower()
        if sev not in ("warning", "note"):
            sev = "warning"
        warnings.append(
            Warning(
                label=str(w["label"])[:300],
                url=w.get("url"),
                date=str(w["date"])[:12] if w.get("date") else None,
                severity=sev,
            )
        )

    press = []
    for n in (parsed.get("recent_press") or [])[:8]:
        if not isinstance(n, dict) or not n.get("title"):
            continue
        press.append(
            PressItem(
                title=str(n["title"])[:300],
                url=n.get("url"),
                snippet=str(n["snippet"])[:300] if n.get("snippet") else None,
                date=str(n["date"])[:32] if n.get("date") else None,
            )
        )

    # Sources fall back to whatever Linkup returned if the LLM didn't echo them.
    sources_raw = parsed.get("sources") or [
        {"label": s.get("name") or s["url"], "url": s["url"], "snippet": s.get("snippet")}
        for s in linkup_result.get("sources", [])
        if s.get("url")
    ]
    sources = []
    for s in sources_raw[:12]:
        if not isinstance(s, dict) or not s.get("url"):
            continue
        sources.append(
            SourceLink(
                label=str(s.get("label") or s["url"])[:200],
                url=s["url"],
                snippet=s.get("snippet"),
            )
        )

    return Reputation(
        sponsor=sponsor,
        pi=pi,
        hospital_reputation=parsed.get("hospital_reputation"),
        summary=parsed.get("summary"),
        publications=pubs,
        recent_press=press,
        warnings=warnings,
        sources=sources,
    )


_NORMALIZE_PROMPT = """\
You are given web search results about a clinical trial sponsor / hospital and
optionally its principal investigator. Produce a JSON object that summarizes
the institution's reputation for a patient deciding whether to enroll.

Sponsor: {sponsor}
Principal investigator: {pi}

Web answer:
{answer}

Sources (with URLs):
{sources}

Return JSON only, with this shape:

{{
  "hospital_reputation": "2–3 sentence plain-English assessment of the institution's standing in clinical research and oncology (or relevant field).",
  "summary": "One-line overall take, e.g. 'Major academic cancer center with active KRAS G12C research'.",
  "publications": [
    {{"title": "Paper title", "url": "https://...", "year": "2024"}}
  ],
  "recent_press": [
    {{"title": "Headline", "url": "https://...", "snippet": "1-sentence summary", "date": "2025-02"}}
  ],
  "warnings": [
    {{"label": "FDA warning letter cited deficiencies in clinical trial conduct", "url": "https://www.fda.gov/...", "date": "2023-08", "severity": "warning"}}
  ],
  "sources": [
    {{"label": "Source label", "url": "https://...", "snippet": "optional"}}
  ]
}}

Rules:
- Use ONLY URLs that appear in the sources list. Never fabricate URLs.
- If you don't have enough info for a field, omit it or use an empty list.
- Keep summaries plain-language and patient-friendly.
- No medical advice, no recommendations to enroll or not.
- For "warnings", ONLY include items if the sources mention an actual FDA warning letter, sanction, debarment, or major enforcement action against THIS sponsor within the last 5 years. Do not invent warnings. If none are mentioned, return an empty list.
"""


# ---------------------------------------------------------------------------
# Mock mode (MOCK_LINKUP=true)
# ---------------------------------------------------------------------------


def _mock_reputation(sponsor: str, pi: Optional[str]) -> Reputation:
    s = sponsor.lower()
    if "memorial sloan" in s or "msk" in s:
        return Reputation(
            sponsor=sponsor,
            pi=pi,
            hospital_reputation=(
                "Memorial Sloan Kettering is one of the largest and oldest "
                "cancer centers in the United States and is consistently "
                "ranked among the top two cancer hospitals in U.S. News & "
                "World Report. It runs an active portfolio of early-phase "
                "oncology trials, including KRAS G12C-targeted studies."
            ),
            summary="Major academic cancer center with deep KRAS G12C trial experience.",
            publications=[
                Publication(
                    title="Adagrasib in KRAS G12C–Mutated Non–Small-Cell Lung Cancer",
                    url="https://www.nejm.org/doi/full/10.1056/NEJMoa2204619",
                    year="2022",
                ),
                Publication(
                    title="KRAS G12C inhibition with sotorasib in advanced NSCLC",
                    url="https://www.nejm.org/doi/full/10.1056/NEJMoa2103695",
                    year="2021",
                ),
            ],
            recent_press=[
                PressItem(
                    title="MSK opens new precision oncology unit for KRAS-targeted therapies",
                    url="https://www.mskcc.org/news/example",
                    snippet="The center announced a dedicated unit focused on KRAS G12C and other targeted therapies.",
                    date="2025-03",
                ),
            ],
            sources=[
                SourceLink(label="MSKCC official", url="https://www.mskcc.org/", snippet=None),
                SourceLink(label="U.S. News Best Hospitals", url="https://health.usnews.com/best-hospitals", snippet=None),
            ],
        )
    if "dana-farber" in s or "dana farber" in s:
        return Reputation(
            sponsor=sponsor,
            pi=pi,
            hospital_reputation="Dana-Farber Cancer Institute is a leading academic cancer center affiliated with Harvard Medical School with significant clinical trial activity in thoracic and lung cancers.",
            summary="Top-tier academic cancer center with strong thoracic oncology program.",
            publications=[
                Publication(title="Targeted therapies in advanced NSCLC", url="https://example.org/dfci-paper", year="2024"),
            ],
            recent_press=[],
            sources=[SourceLink(label="Dana-Farber", url="https://www.dana-farber.org/")],
        )
    # Generic fallback — for demo, "sketchy" in the name triggers a fake warning
    # so the fraud-detection UI is visible without a live FDA query.
    warnings = []
    if "sketchy" in s or "questionable" in s:
        warnings.append(
            Warning(
                label="FDA warning letter cited protocol deviations in clinical trial conduct (2023)",
                url="https://www.fda.gov/inspections-compliance-enforcement-and-criminal-investigations/warning-letters",
                date="2023-08",
                severity="warning",
            )
        )
    return Reputation(
        sponsor=sponsor,
        pi=pi,
        hospital_reputation=(
            f"{sponsor} appears in clinical trial registries, but we don't have "
            "detailed reputation information for it in mock mode. Live searches "
            "will return real publication and press coverage."
        ),
        summary="No detailed reputation data available in mock mode.",
        publications=[],
        recent_press=[],
        warnings=warnings,
        sources=[],
    )


# ---------------------------------------------------------------------------
# Cache helpers
# ---------------------------------------------------------------------------


def _cache_key(sponsor: str, pi: Optional[str]) -> str:
    raw = f"{sponsor.lower().strip()}|{(pi or '').lower().strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def _cache_get(key: str) -> Optional[dict]:
    entry = _cache.get(key)
    if entry is None:
        return None
    ts, data = entry
    if time.time() - ts > _CACHE_TTL_SECONDS:
        _cache.pop(key, None)
        return None
    return data


def _cache_set(key: str, data: dict) -> None:
    _cache[key] = (time.time(), data)


def clear_cache() -> None:
    _cache.clear()
