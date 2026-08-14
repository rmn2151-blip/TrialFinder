"""
Trial result tracker.

When a watched trial reaches a completed/terminated status, this service fires
a Linkup query for published results + media coverage and asks Claude to
produce a plain-English summary. Lazy on demand (called from the nightly
watchlist sweep when status flips to Completed, and on the API for any
trial the user asks about).
"""

import asyncio
import json
import logging
import os
import re
from typing import Optional

from pydantic import BaseModel, Field

from services import llm_provider

logger = logging.getLogger(__name__)

_ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
_MOCK_MODE = (
    os.getenv("MOCK_SEARCH", os.getenv("MOCK_LINKUP", "false")).lower() == "true"
)


class TrialResults(BaseModel):
    nct_id: str
    headline: Optional[str] = Field(default=None, description="One-line plain-English bottom line")
    summary: Optional[str] = Field(default=None, description="2–3 sentence plain-English summary")
    primary_outcome: Optional[str] = None
    journal_url: Optional[str] = None
    media_coverage: list[dict] = Field(default_factory=list)
    sources: list[dict] = Field(default_factory=list)


async def fetch_results_summary(nct_id: str, title: Optional[str] = None) -> TrialResults:
    """Look up published results + media coverage for a completed trial."""
    if _MOCK_MODE:
        return _mock_results(nct_id, title)

    from services import search_service

    label = title or nct_id
    query = (
        f"Has clinical trial {nct_id} ({label}) published results? "
        f"Summarize the primary outcome, any journal publication, and media "
        f"coverage from 2024 or 2025."
    )

    raw = await search_service.web_search(query)

    if not llm_provider.is_configured():
        return TrialResults(
            nct_id=nct_id,
            summary=raw.get("answer") or None,
            sources=raw.get("sources", []),
        )

    prompt = _PROMPT.format(
        nct_id=nct_id,
        title=label,
        answer=raw.get("answer", "")[:6000],
        sources=json.dumps(raw.get("sources", [])[:10], indent=2),
    )
    text = await llm_provider.complete(
        prompt,
        system="Respond only with the JSON specified. No prose, no markdown fences.",
        max_tokens=900,
        json_only=True,
    )
    parsed = llm_provider.parse_json(text)
    return _build_results(nct_id, parsed, raw)


def _build_results(nct_id: str, parsed: dict, raw: dict) -> TrialResults:
    media = []
    for m in (parsed.get("media_coverage") or [])[:6]:
        if isinstance(m, dict) and m.get("title"):
            media.append(
                {
                    "title": str(m["title"])[:300],
                    "url": m.get("url"),
                    "snippet": str(m["snippet"])[:300] if m.get("snippet") else None,
                }
            )

    return TrialResults(
        nct_id=nct_id,
        headline=parsed.get("headline"),
        summary=parsed.get("summary"),
        primary_outcome=parsed.get("primary_outcome"),
        journal_url=parsed.get("journal_url"),
        media_coverage=media,
        sources=raw.get("sources", [])[:8],
    )


_PROMPT = """\
The clinical trial below has completed. Based on the web search results, write
a patient-friendly summary of what the trial found.

Trial: {title} ({nct_id})

Web answer:
{answer}

Sources:
{sources}

Return JSON only:
{{
  "headline": "One-line bottom line in patient language (e.g. 'The new drug worked better than chemo for KRAS G12C lung cancer.')",
  "summary": "2-3 sentences explaining what was tested, what they found, and what it means for patients.",
  "primary_outcome": "The primary endpoint result if reported (e.g. 'Median PFS 5.6 months vs 4.5 months, HR 0.66')",
  "journal_url": "Direct link to the published paper if present in sources, else null",
  "media_coverage": [
    {{"title": "Lay-press headline", "url": "https://...", "snippet": "1-sentence summary"}}
  ]
}}

Rules:
- Use ONLY URLs that appear in the sources list. Never fabricate.
- Avoid jargon. Explain endpoints (PFS, OS, ORR) briefly in parentheses if used.
- If results haven't been reported yet, return headline and summary explaining
  that and use empty arrays for the rest.
"""


# ---------------------------------------------------------------------------
# Mock data
# ---------------------------------------------------------------------------


def _mock_results(nct_id: str, title: Optional[str]) -> TrialResults:
    return TrialResults(
        nct_id=nct_id,
        headline="The targeted pill outperformed standard chemo for KRAS G12C lung cancer.",
        summary=(
            "This trial tested whether a KRAS G12C inhibitor was better than docetaxel "
            "chemotherapy in patients with previously treated NSCLC. The targeted drug "
            "kept cancer from growing about a month longer on average and caused fewer "
            "severe side effects. It became a new standard option for KRAS G12C+ patients."
        ),
        primary_outcome="Median PFS 5.6 vs 4.5 months (HR 0.66, p<0.001)",
        journal_url="https://www.thelancet.com/journals/lancet/article/PIIS0140-6736(23)00103-X",
        media_coverage=[
            {
                "title": "FDA approves KRAS G12C inhibitor for lung cancer",
                "url": "https://www.nytimes.com/example",
                "snippet": "Approval covers patients with prior platinum-based chemotherapy.",
            },
        ],
        sources=[
            {"name": "The Lancet", "url": "https://www.thelancet.com/example"},
        ],
    )
