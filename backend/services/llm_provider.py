"""
LLM provider adapter.

TrialFinder can run on either Gemini or Claude. Both support grounded web
search natively, so no feature is lost either way and there is no third-party
search dependency.

Choose with the LLM_PROVIDER env var:

    LLM_PROVIDER=gemini   # default. Uses GEMINI_API_KEY.
    LLM_PROVIDER=claude   # Uses ANTHROPIC_API_KEY.

If the configured provider has no key but the other one does, we fall back
automatically and log a warning. That way a missing or exhausted key never
takes the whole app down mid-demo.

Two entry points:
    complete(prompt, system=..., json_only=True) -> str
    search(query)                                -> {"answer": str, "sources": [...]}
"""

import asyncio
import json
import logging
import os
import re
from typing import Optional

logger = logging.getLogger(__name__)

# Model defaults. Override per-provider via env if you want to experiment.
#
# "gemini-flash-latest" is an alias that always points at the current Flash
# model. Pinning an explicit version (e.g. gemini-2.5-flash) eventually breaks
# with "no longer available to new users" once Google closes it to new keys,
# so the alias is the safer default.
_GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-flash-latest")
_CLAUDE_MODEL = os.getenv("CLAUDE_MODEL", "claude-sonnet-4-6")

# Gemini Flash models get briefly overloaded (503) during demand spikes. When
# that happens we try the next model in this chain rather than failing the
# user's search. Ordered newest/best first.
_GEMINI_FALLBACKS = [
    "gemini-3.6-flash",
    "gemini-3.5-flash",
    "gemini-flash-lite-latest",
    "gemini-3.1-flash-lite",
]


def _gemini_model_chain() -> list[str]:
    """Preferred model first, then distinct fallbacks."""
    chain = [_GEMINI_MODEL]
    for m in _GEMINI_FALLBACKS:
        if m not in chain:
            chain.append(m)
    return chain


def _gemini_key() -> str:
    return os.getenv("GEMINI_API_KEY", "") or os.getenv("GOOGLE_API_KEY", "")


def _claude_key() -> str:
    return os.getenv("ANTHROPIC_API_KEY", "")


def active_provider() -> Optional[str]:
    """
    Resolve which provider to actually use, honoring LLM_PROVIDER but falling
    back when its key is missing. Returns None when neither is configured.
    """
    preferred = os.getenv("LLM_PROVIDER", "gemini").strip().lower()

    if preferred == "claude":
        if _claude_key():
            return "claude"
        if _gemini_key():
            logger.warning(
                "LLM_PROVIDER=claude but ANTHROPIC_API_KEY is missing. "
                "Falling back to Gemini."
            )
            return "gemini"
        return None

    # Default path: gemini
    if _gemini_key():
        return "gemini"
    if _claude_key():
        logger.warning(
            "LLM_PROVIDER=gemini but GEMINI_API_KEY is missing. "
            "Falling back to Claude."
        )
        return "claude"
    return None


def is_configured() -> bool:
    return active_provider() is not None


# ---------------------------------------------------------------------------
# Text completion (used for ranking, intake, clarify, normalization)
# ---------------------------------------------------------------------------


async def complete(
    prompt: str,
    *,
    system: Optional[str] = None,
    max_tokens: int = 4000,
    json_only: bool = False,
) -> str:
    """
    Run a single-turn completion and return the raw text.

    json_only=True asks the provider for strict JSON output where supported,
    which meaningfully reduces malformed-JSON retries.
    """
    provider = active_provider()
    if provider is None:
        raise ValueError(
            "No LLM provider configured. Set GEMINI_API_KEY (recommended) or "
            "ANTHROPIC_API_KEY in your .env file."
        )

    loop = asyncio.get_event_loop()
    if provider == "gemini":
        return await loop.run_in_executor(
            None, _gemini_complete, prompt, system, max_tokens, json_only
        )
    return await loop.run_in_executor(
        None, _claude_complete, prompt, system, max_tokens
    )


def complete_sync(
    prompt: str,
    *,
    system: Optional[str] = None,
    max_tokens: int = 4000,
    json_only: bool = False,
) -> str:
    """
    Synchronous version of complete(), for callers that are not async
    (the intake agent and clarify loop run inside sync FastAPI routes,
    which FastAPI already dispatches to a worker thread).
    """
    provider = active_provider()
    if provider is None:
        raise ValueError(
            "No LLM provider configured. Set GEMINI_API_KEY (recommended) or "
            "ANTHROPIC_API_KEY in your .env file."
        )
    if provider == "gemini":
        return _gemini_complete(prompt, system, max_tokens, json_only)
    return _claude_complete(prompt, system, max_tokens)


def _gemini_complete(
    prompt: str, system: Optional[str], max_tokens: int, json_only: bool
) -> str:
    import time

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=_gemini_key())

    config_kwargs = {"max_output_tokens": max_tokens}
    if system:
        config_kwargs["system_instruction"] = system
    if json_only:
        config_kwargs["response_mime_type"] = "application/json"

    # A model can be briefly overloaded (503) or closed to new keys (404).
    # Retry the preferred model once, then walk the fallback chain so a busy
    # model never fails the user's search.
    last_exc: Optional[Exception] = None

    for model in _gemini_model_chain():
        for attempt in range(2):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config=types.GenerateContentConfig(**config_kwargs),
                )
                text = (getattr(response, "text", "") or "").strip()
                if model != _GEMINI_MODEL:
                    logger.info("Gemini served this request via fallback model %s", model)
                return text
            except Exception as exc:
                last_exc = exc
                msg = str(exc)
                busy = "503" in msg or "UNAVAILABLE" in msg or "high demand" in msg
                gone = "404" in msg or "NOT_FOUND" in msg
                quota = "429" in msg or "RESOURCE_EXHAUSTED" in msg

                if gone or quota:
                    logger.warning(
                        "Model %s unusable (%s). Trying next model.",
                        model,
                        "not available" if gone else "quota exhausted",
                    )
                    break  # straight to the next model

                if busy and attempt == 0:
                    time.sleep(1)
                    continue  # one quick retry on the same model

                if busy:
                    logger.warning("Model %s still busy. Trying next model.", model)
                    break

                raise  # genuine error (bad key, malformed request): surface it

    logger.error("All Gemini models failed. Last error: %s", str(last_exc)[:300])
    raise last_exc if last_exc else RuntimeError("Gemini call failed")


def _claude_complete(prompt: str, system: Optional[str], max_tokens: int) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=_claude_key())
    kwargs = {
        "model": _CLAUDE_MODEL,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system

    message = client.messages.create(**kwargs)
    parts = [
        getattr(b, "text", "")
        for b in getattr(message, "content", []) or []
        if getattr(b, "type", None) == "text"
    ]
    return "\n".join(parts).strip()


# ---------------------------------------------------------------------------
# Grounded web search
# ---------------------------------------------------------------------------


# Grounded search has a separate, much smaller quota than plain generation.
# Once it is exhausted, every further call costs a round-trip and returns 429,
# which added ~20s to each search. This circuit breaker skips those calls for
# a cooldown period instead of retrying them on every request.
_SEARCH_DISABLED_UNTIL: float = 0.0
_SEARCH_COOLDOWN_SECONDS = int(os.getenv("SEARCH_COOLDOWN_SECONDS", "900"))


def search_available() -> bool:
    import time as _time

    return _time.time() >= _SEARCH_DISABLED_UNTIL


def _disable_search_temporarily() -> None:
    global _SEARCH_DISABLED_UNTIL
    import time as _time

    _SEARCH_DISABLED_UNTIL = _time.time() + _SEARCH_COOLDOWN_SECONDS
    logger.warning(
        "Grounded web search disabled for %d minutes after a quota error. "
        "Trial matching is unaffected; it runs on ClinicalTrials.gov data.",
        _SEARCH_COOLDOWN_SECONDS // 60,
    )


async def search(query: str, *, max_uses: int = 3) -> dict:
    """
    Run a web-grounded query.

    Returns {"answer": str, "sources": [{"name","url","snippet"}]}.
    Never raises: on failure it logs and returns an empty result so callers
    degrade gracefully instead of failing the whole request.
    """
    provider = active_provider()
    if provider is None:
        logger.warning("No LLM provider configured, skipping web search.")
        return {"answer": "", "sources": []}

    if not search_available():
        # Quota already known to be exhausted. Skip the doomed round-trip.
        return {"answer": "", "sources": []}

    loop = asyncio.get_event_loop()
    try:
        if provider == "gemini":
            return await loop.run_in_executor(None, _gemini_search, query)
        return await loop.run_in_executor(None, _claude_search, query, max_uses)
    except Exception as exc:
        msg = str(exc)
        if "RESOURCE_EXHAUSTED" in msg or "429" in msg:
            _disable_search_temporarily()
            # Grounded search has its own quota, separate from plain generation.
            # Core trial matching runs off ClinicalTrials.gov and is unaffected;
            # only the supplementary panels (drug intel, site reputation,
            # published results) come back empty.
            logger.warning(
                "Web search quota exhausted on %s. Trial matching still works "
                "from ClinicalTrials.gov data. Supplementary panels will be "
                "empty until quota resets.",
                provider,
            )
        else:
            logger.warning("Web search failed for '%s': %s", query[:80], msg[:200])
        return {"answer": "", "sources": []}


def _gemini_search(query: str) -> dict:
    """Gemini with Google Search grounding."""
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=_gemini_key())

    response = client.models.generate_content(
        model=_GEMINI_MODEL,
        contents=query,
        config=types.GenerateContentConfig(
            tools=[types.Tool(google_search=types.GoogleSearch())],
        ),
    )

    answer = (getattr(response, "text", "") or "").strip()
    sources: list[dict] = []
    seen: set[str] = set()

    # Grounding metadata carries the cited sources.
    for cand in getattr(response, "candidates", []) or []:
        meta = getattr(cand, "grounding_metadata", None)
        if meta is None:
            continue
        for chunk in getattr(meta, "grounding_chunks", []) or []:
            web = getattr(chunk, "web", None)
            if web is None:
                continue
            url = getattr(web, "uri", None)
            if not url or url in seen:
                continue
            seen.add(url)
            sources.append(
                {
                    "name": getattr(web, "title", "") or url,
                    "url": url,
                    "snippet": "",
                }
            )

    return {"answer": answer, "sources": sources}


def _claude_search(query: str, max_uses: int) -> dict:
    """Claude with its built-in web_search tool."""
    import anthropic

    client = anthropic.Anthropic(api_key=_claude_key())
    message = client.messages.create(
        model=_CLAUDE_MODEL,
        max_tokens=2500,
        tools=[
            {
                "type": "web_search_20250305",
                "name": "web_search",
                "max_uses": max_uses,
            }
        ],
        messages=[{"role": "user", "content": query}],
    )

    answer_parts: list[str] = []
    sources: list[dict] = []
    seen: set[str] = set()

    for block in getattr(message, "content", []) or []:
        btype = getattr(block, "type", None)
        if btype == "text":
            answer_parts.append(getattr(block, "text", "") or "")
            for cit in getattr(block, "citations", []) or []:
                url = getattr(cit, "url", None)
                if url and url not in seen:
                    seen.add(url)
                    sources.append(
                        {
                            "name": getattr(cit, "title", "") or url,
                            "url": url,
                            "snippet": getattr(cit, "cited_text", "") or "",
                        }
                    )
        elif btype == "web_search_tool_result":
            for item in getattr(block, "content", []) or []:
                url = getattr(item, "url", None)
                if url and url not in seen:
                    seen.add(url)
                    sources.append(
                        {
                            "name": getattr(item, "title", "") or url,
                            "url": url,
                            "snippet": "",
                        }
                    )

    return {"answer": "\n".join(answer_parts).strip(), "sources": sources}


# ---------------------------------------------------------------------------
# Shared JSON helper
# ---------------------------------------------------------------------------


def parse_json(raw: str) -> dict:
    """
    Parse a JSON object out of an LLM response, tolerating markdown fences and
    stray prose around the object. Returns {} when nothing parses.
    """
    if not raw:
        return {}

    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```[a-zA-Z]*\n?", "", cleaned)
        cleaned = re.sub(r"\n?```\s*$", "", cleaned)

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass

    # Last resort: grab the outermost {...} block.
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(cleaned[start : end + 1])
        except json.JSONDecodeError:
            pass

    logger.warning("Could not parse JSON from LLM response: %s", cleaned[:200])
    return {}
