"""
Tests for reputation_service mock mode + cache. No network calls.
Run: pytest tests/test_reputation_service.py -v
"""

import asyncio
import os

os.environ["MOCK_LINKUP"] = "true"

from services import reputation_service


def setup_function(_):
    reputation_service.clear_cache()


def test_mock_returns_msk_known_institution():
    rep = asyncio.run(reputation_service.get_reputation("Memorial Sloan Kettering Cancer Center"))
    assert rep.sponsor == "Memorial Sloan Kettering Cancer Center"
    assert rep.hospital_reputation and "cancer" in rep.hospital_reputation.lower()
    assert len(rep.publications) >= 1
    assert all(p.url and p.url.startswith("http") for p in rep.publications)
    assert rep.cached is False


def test_mock_generic_fallback_for_unknown_site():
    rep = asyncio.run(reputation_service.get_reputation("Tiny Community Hospital #42"))
    assert rep.sponsor.startswith("Tiny")
    # Generic fallback yields no fabricated publications.
    assert rep.publications == []
    assert rep.recent_press == []


def test_cache_returns_cached_flag_on_second_hit():
    sponsor = "Memorial Sloan Kettering"
    first = asyncio.run(reputation_service.get_reputation(sponsor))
    second = asyncio.run(reputation_service.get_reputation(sponsor))
    assert first.cached is False
    assert second.cached is True


def test_cache_keys_distinguish_pi():
    r1 = asyncio.run(reputation_service.get_reputation("Dana-Farber"))
    r2 = asyncio.run(reputation_service.get_reputation("Dana-Farber", pi="Some PI"))
    # Different PIs hit different cache keys, so the second call is a miss again.
    assert r1.cached is False
    assert r2.cached is False


def test_empty_sponsor_raises():
    import pytest
    with pytest.raises(ValueError):
        asyncio.run(reputation_service.get_reputation(""))
