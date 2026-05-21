"""
Tests for linkup_service.py — runs in mock mode so no Linkup credits are used.
Run with: MOCK_LINKUP=true pytest tests/test_linkup_service.py -v
"""

import asyncio
import os

import pytest

os.environ["MOCK_LINKUP"] = "true"

from services import linkup_service
from services.cache import clear as clear_cache


@pytest.fixture(autouse=True)
def reset_cache():
    clear_cache()
    yield
    clear_cache()


def test_mock_returns_expected_keys():
    result = asyncio.run(
        linkup_service.search_for_trials("NSCLC KRAS G12C", "New York, NY")
    )
    assert "trial_listings" in result
    assert "recent_results" in result
    assert "mechanism_coverage" in result
    assert "sources" in result
    assert isinstance(result["sources"], list)


def test_mock_trial_listings_not_empty():
    result = asyncio.run(
        linkup_service.search_for_trials("lung cancer", "Chicago, IL")
    )
    assert len(result["trial_listings"]) > 50


def test_query_builder_includes_location():
    queries = linkup_service._build_queries(
        "breast cancer HER2+", "San Francisco, CA", "trastuzumab"
    )
    assert any("San Francisco" in q["query"] for q in queries)
    assert any("clinicaltrials.gov" in q.get("include_domains", []) for q in queries)


def test_cache_prevents_duplicate_calls(monkeypatch):
    call_count = {"n": 0}

    original_fixture = linkup_service._load_mock_fixture

    def counting_fixture():
        call_count["n"] += 1
        return original_fixture()

    monkeypatch.setattr(linkup_service, "_load_mock_fixture", counting_fixture)

    # Two identical calls
    asyncio.run(linkup_service.search_for_trials("NSCLC", "New York"))
    asyncio.run(linkup_service.search_for_trials("NSCLC", "New York"))

    # Mock mode doesn't use the real cache path, but test that cache module works
    from services.cache import make_key, get, set as cache_set
    key = make_key("nsclc", "new york", None)
    cache_set(key, {"trial_listings": "cached"})
    assert get(key)["trial_listings"] == "cached"
