"""
Drug-specific intel lookup.

For a given experimental drug, fire a single Linkup query for phase results,
conference signals (ASCO/AHA/ASH/ESMO/ASH/AACR), and FDA designations, then
ask Claude to normalize into a structured DrugIntel object.

Lazy + cached for the same budget reasons as reputation_service.
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

from models.drug_intel import (
    ConferenceSignal,
    DrugIntel,
    FDADesignation,
    PhaseResult,
)

logger = logging.getLogger(__name__)

_LINKUP_API_KEY = os.getenv("LINKUP_API_KEY", "")
_ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_MOCK_MODE = os.getenv("MOCK_LINKUP", "false").lower() == "true"
_DEPTH = os.getenv("LINKUP_DEPTH", "standard")

_CACHE_TTL_SECONDS = 3600
_cache: dict[str, tuple[float, dict]] = {}


async def get_drug_intel(drug: str) -> DrugIntel:
    drug = (drug or "").strip()
    if not drug:
        raise ValueError("drug is required")

    key = _cache_key(drug)
    cached = _cache_get(key)
    if cached is not None:
        return DrugIntel(**{**cached, "cached": True})

    if _MOCK_MODE:
        intel = _mock_intel(drug)
    else:
        intel = await _live_intel(drug)

    _cache_set(key, intel.model_dump())
    return intel


# ---------------------------------------------------------------------------
# Live lookup
# ---------------------------------------------------------------------------


async def _live_intel(drug: str) -> DrugIntel:
    if not _LINKUP_API_KEY:
        raise ValueError("LINKUP_API_KEY is not set.")

    query = (
        f'"{drug}" clinical trial phase results efficacy outcomes'
        f' "ASCO" OR "AHA" OR "ASH" OR "ESMO" OR "AACR" 2024 2025'
        f' "FDA breakthrough" OR "fast track" OR "orphan drug"'
        f' side effects safety'
    )

    loop = asyncio.get_event_loop()
    raw = await loop.run_in_executor(None, _sync_linkup_search, query)

    if not _ANTHROPIC_API_KEY:
        return DrugIntel(
            drug=drug,
            summary=raw.get("answer", "") or None,
            sources=raw.get("sources", []),
        )

    prompt = _NORMALIZE_PROMPT.format(
        drug=drug,
        answer=raw.get("answer", "")[:6000],
        sources=json.dumps(raw.get("sources", [])[:10], indent=2),
    )
    text = await loop.run_in_executor(None, _sync_claude_call, prompt)
    parsed = _parse_llm_json(text)
    return _build_intel(drug, parsed, raw)


def _sync_linkup_search(query: str) -> dict:
    from linkup import LinkupClient

    client = LinkupClient(api_key=_LINKUP_API_KEY)
    try:
        response = client.search(query=query, depth=_DEPTH, output_type="sourcedAnswer")
    except Exception as exc:
        logger.warning("Linkup drug-intel query failed: %s", exc)
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


def _sync_claude_call(prompt: str) -> str:
    client = anthropic.Anthropic(api_key=_ANTHROPIC_API_KEY)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1500,
        system="You are a research assistant. Respond with valid JSON only — no markdown fences.",
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
    except json.JSONDecodeError:
        return {}


def _build_intel(drug: str, parsed: dict, raw: dict) -> DrugIntel:
    phase_results = []
    for p in (parsed.get("phase_results") or [])[:6]:
        if isinstance(p, dict) and p.get("summary"):
            phase_results.append(
                PhaseResult(
                    phase=str(p.get("phase", "Phase ?"))[:32],
                    summary=str(p["summary"])[:500],
                    url=p.get("url"),
                )
            )

    signals = []
    for s in (parsed.get("conference_signals") or [])[:6]:
        if isinstance(s, dict) and s.get("finding"):
            signals.append(
                ConferenceSignal(
                    conference=str(s.get("conference", "Conference"))[:64],
                    finding=str(s["finding"])[:500],
                    url=s.get("url"),
                )
            )

    designations = []
    for d in (parsed.get("fda_designations") or [])[:5]:
        if isinstance(d, dict) and d.get("label"):
            designations.append(
                FDADesignation(
                    label=str(d["label"])[:120],
                    date=str(d["date"])[:12] if d.get("date") else None,
                    url=d.get("url"),
                )
            )

    return DrugIntel(
        drug=drug,
        summary=parsed.get("summary"),
        side_effect_signals=parsed.get("side_effect_signals"),
        phase_results=phase_results,
        conference_signals=signals,
        fda_designations=designations,
        sources=raw.get("sources", [])[:8],
    )


_NORMALIZE_PROMPT = """\
You are given web search results about an experimental therapy. Produce a JSON
object summarizing what's publicly known about it.

Drug: {drug}

Web answer:
{answer}

Sources:
{sources}

Return JSON only, with this shape:

{{
  "summary": "1-paragraph plain-language overview of the drug, its target, and where it is in development.",
  "side_effect_signals": "Plain-language note on the most-reported side effects from trial data.",
  "phase_results": [
    {{"phase": "Phase II", "summary": "ORR 37% in pretreated NSCLC, median PFS 6.3 months", "url": "https://..."}}
  ],
  "conference_signals": [
    {{"conference": "ASCO 2025", "finding": "Combination with pembro showed 63% ORR in treatment-naive cohort", "url": "https://..."}}
  ],
  "fda_designations": [
    {{"label": "Breakthrough Therapy designation for KRAS G12C+ NSCLC", "date": "2024", "url": "https://..."}}
  ]
}}

Rules:
- Use ONLY URLs from the sources list. Never fabricate.
- If a field has no data, return an empty list or omit it.
- Be patient-friendly; avoid jargon when possible.
"""


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------


def _mock_intel(drug: str) -> DrugIntel:
    d = drug.lower()
    if "sotorasib" in d or "adagrasib" in d or "kras" in d:
        return DrugIntel(
            drug=drug,
            summary=(
                f"{drug} is a covalent KRAS G12C inhibitor — a once-daily oral pill "
                "that locks the mutant KRAS protein in its inactive state. It's the "
                "first generation of targeted therapies for the ~13% of lung "
                "adenocarcinomas driven by KRAS G12C."
            ),
            side_effect_signals=(
                "Most-reported issues are liver enzyme elevations, fatigue, GI side "
                "effects (nausea, diarrhea), and occasional pneumonitis. Grade 3+ "
                "events seen in roughly 1 in 5 patients in pivotal trials."
            ),
            phase_results=[
                PhaseResult(
                    phase="Phase II",
                    summary="Sotorasib CodeBreaK 100: 37.1% objective response rate, median PFS 6.3 months in pretreated KRAS G12C NSCLC.",
                    url="https://www.nejm.org/doi/full/10.1056/NEJMoa2103695",
                ),
                PhaseResult(
                    phase="Phase III",
                    summary="CodeBreaK 200: sotorasib vs docetaxel — superior PFS (5.6 vs 4.5 months) in previously treated patients.",
                    url="https://www.thelancet.com/journals/lancet/article/PIIS0140-6736(23)00103-X",
                ),
            ],
            conference_signals=[
                ConferenceSignal(
                    conference="ASCO 2025",
                    finding="KRYSTAL-7: adagrasib + pembrolizumab in 1L KRAS G12C+ NSCLC, ORR 63%, manageable safety profile.",
                    url="https://ascopubs.org/doi/example",
                ),
                ConferenceSignal(
                    conference="ESMO 2024",
                    finding="Real-world data shows similar response rates to pivotal trials, but with higher rates of hepatotoxicity in older patients.",
                    url="https://www.esmo.org/example",
                ),
            ],
            fda_designations=[
                FDADesignation(
                    label="Breakthrough Therapy designation for KRAS G12C+ NSCLC",
                    date="2021",
                    url="https://www.fda.gov/drugs/example",
                ),
            ],
            sources=[
                {"name": "NEJM CodeBreaK 100", "url": "https://www.nejm.org/doi/full/10.1056/NEJMoa2103695"},
                {"name": "ASCO 2025", "url": "https://ascopubs.org/doi/example"},
            ],
        )
    # Generic fallback
    return DrugIntel(
        drug=drug,
        summary=(
            f"We don't have detailed mock intel for {drug}. Live searches will "
            "return real phase results, conference signals, and FDA designations."
        ),
        phase_results=[],
        conference_signals=[],
        fda_designations=[],
        sources=[],
    )


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------


def _cache_key(drug: str) -> str:
    return hashlib.sha256(drug.lower().strip().encode()).hexdigest()[:16]


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
