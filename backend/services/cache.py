"""
Simple in-memory cache for Linkup search results.

Keys are SHA-256 hashes of (condition, location, treatment_history).
Entries expire after CACHE_TTL_SECONDS (default 3600 = 1 hour).

This protects your $20 Linkup budget from repeated identical queries
during demos and integration testing.
"""

import hashlib
import logging
import time
from typing import Any

logger = logging.getLogger(__name__)

CACHE_TTL_SECONDS = int(3600)  # 1 hour

# { cache_key: (timestamp, data) }
_cache: dict[str, tuple[float, Any]] = {}


def make_key(condition: str, location: str, treatment_history: str | None) -> str:
    """Produce a stable cache key from the search-relevant patient fields."""
    raw = f"{condition.lower().strip()}|{location.lower().strip()}|{(treatment_history or '').lower().strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def get(key: str) -> Any | None:
    """Return cached value if it exists and hasn't expired, else None."""
    entry = _cache.get(key)
    if entry is None:
        return None
    timestamp, data = entry
    if time.time() - timestamp > CACHE_TTL_SECONDS:
        logger.debug(f"Cache expired for key={key}")
        del _cache[key]
        return None
    logger.info(f"Cache hit for key={key} — skipping Linkup call")
    return data


def set(key: str, data: Any) -> None:
    """Store data in the cache with current timestamp."""
    _cache[key] = (time.time(), data)
    logger.debug(f"Cached result for key={key} ({len(_cache)} entries total)")


def invalidate(key: str) -> None:
    _cache.pop(key, None)


def clear() -> None:
    _cache.clear()
    logger.info("Cache cleared")


def stats() -> dict:
    now = time.time()
    live = sum(1 for ts, _ in _cache.values() if now - ts <= CACHE_TTL_SECONDS)
    return {"total_entries": len(_cache), "live_entries": live}
