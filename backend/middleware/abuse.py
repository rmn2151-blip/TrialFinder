"""
Abuse protection for expensive and scrapeable endpoints.

Three layers:

  1. Per-IP rate limits (slowapi decorators on the routes themselves).
  2. Per-account daily quotas on AI generation, so one logged-in user cannot
     burn the whole Gemini quota.
  3. Bot heuristics: obvious scraper user-agents and clients that request far
     too fast to be human.

State is in-process. That is correct for a single instance and is the right
scope for a hackathon deployment. If you scale to multiple workers, move the
counters to Redis so limits are shared; the interfaces below stay the same.
"""

import logging
import os
import time
from collections import defaultdict, deque
from datetime import date

from fastapi import HTTPException, Request, status

logger = logging.getLogger("security.abuse")

# --- AI generation quotas ---------------------------------------------------
# These calls cost money and quota, so they are capped per identity per day.
AI_DAILY_LIMIT_ACCOUNT = int(os.getenv("AI_DAILY_LIMIT_ACCOUNT", "50"))
AI_DAILY_LIMIT_ANON = int(os.getenv("AI_DAILY_LIMIT_ANON", "15"))

# identity -> (date, count)
_ai_usage: dict[str, tuple[date, int]] = {}

# --- Bot heuristics ---------------------------------------------------------
_BOT_UA_MARKERS = (
    "curl/", "wget/", "python-requests", "python-httpx", "go-http-client",
    "java/", "libwww-perl", "scrapy", "httpclient", "okhttp", "axios/",
    "bot", "crawler", "spider", "scraper", "headlesschrome", "phantomjs",
)

# Requests faster than a human can plausibly drive the UI.
_BURST_WINDOW_SECONDS = 10
_BURST_THRESHOLD = 25
_ip_hits: dict[str, deque] = defaultdict(lambda: deque(maxlen=200))

# Endpoints worth protecting from scraping. Read-only lookups that would let
# someone harvest our enriched data in bulk.
SCRAPEABLE_PREFIXES = (
    "/api/reputation",
    "/api/drug-intel",
    "/api/results",
)


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


# ---------------------------------------------------------------------------
# AI quota
# ---------------------------------------------------------------------------


def enforce_ai_quota(request: Request, account_id: int | None = None) -> None:
    """
    Count one AI generation against the caller's daily quota.

    Logged-in users are tracked by account id so they cannot reset their
    quota by changing IP. Anonymous callers are tracked by IP with a much
    smaller allowance.
    """
    if account_id is not None:
        identity = f"account:{account_id}"
        limit = AI_DAILY_LIMIT_ACCOUNT
    else:
        identity = f"ip:{client_ip(request)}"
        limit = AI_DAILY_LIMIT_ANON

    today = date.today()
    stored_day, count = _ai_usage.get(identity, (today, 0))
    if stored_day != today:
        count = 0  # new day, reset

    if count >= limit:
        logger.warning(
            "abuse.ai_quota_exceeded identity=%s limit=%s path=%s",
            identity,
            limit,
            request.url.path,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=(
                f"You have reached the daily limit of {limit} AI searches. "
                "This protects the service from abuse. Please try again tomorrow."
            ),
            headers={"Retry-After": "3600"},
        )

    _ai_usage[identity] = (today, count + 1)


# ---------------------------------------------------------------------------
# Bot detection
# ---------------------------------------------------------------------------


def _looks_like_bot(user_agent: str) -> bool:
    ua = (user_agent or "").lower()
    if not ua:
        return True  # browsers always send a UA
    return any(marker in ua for marker in _BOT_UA_MARKERS)


def _is_bursting(ip: str) -> bool:
    now = time.time()
    hits = _ip_hits[ip]
    hits.append(now)
    cutoff = now - _BURST_WINDOW_SECONDS
    while hits and hits[0] < cutoff:
        hits.popleft()
    return len(hits) > _BURST_THRESHOLD


def block_automated_clients(request: Request) -> None:
    """
    FastAPI dependency. Attach to endpoints that should only ever be driven
    by a real browser session.

    This is deliberately a speed bump, not a guarantee: a determined scraper
    can forge a user agent. It stops casual scripted scraping and, combined
    with the rate limits, makes bulk harvesting slow and noisy in the logs.
    """
    ip = client_ip(request)
    ua = request.headers.get("user-agent", "")

    if _looks_like_bot(ua):
        logger.warning(
            "abuse.bot_blocked ip=%s ua=%r path=%s", ip, ua[:120], request.url.path
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Automated access is not permitted. Please use the web app.",
        )

    if _is_bursting(ip):
        logger.warning(
            "abuse.burst_blocked ip=%s path=%s threshold=%s/%ss",
            ip,
            request.url.path,
            _BURST_THRESHOLD,
            _BURST_WINDOW_SECONDS,
        )
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Please slow down.",
            headers={"Retry-After": "10"},
        )


def reset_state() -> None:
    """Test helper."""
    _ai_usage.clear()
    _ip_hits.clear()
