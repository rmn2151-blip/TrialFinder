"""
linkup_service was removed when trial data moved to ClinicalTrials.gov and
ranking moved to Gemini/Claude.

The module is kept as a tombstone that raises on use rather than deleted
outright, so a stale import fails with an explanation and a pointer to the
replacement instead of a bare ModuleNotFoundError. These tests pin that
behaviour. The old suite exercised Linkup's mock responses and failed loudly
once the module became a tombstone, which is noise rather than signal.
"""

import asyncio

import pytest

from services import linkup_service


def test_tombstone_explains_itself_and_names_the_replacement():
    # search_for_trials is async, so the RuntimeError surfaces on await, not
    # on the call that builds the coroutine.
    with pytest.raises(RuntimeError) as exc:
        asyncio.run(linkup_service.search_for_trials("anything"))

    message = str(exc.value)
    assert "removed" in message
    # An error that does not name the replacement is just a wall.
    assert "search_service" in message


def test_private_helpers_also_raise():
    """No half-working leftovers that quietly return None."""
    for name in ("_build_queries", "_load_mock_fixture"):
        with pytest.raises(RuntimeError):
            getattr(linkup_service, name)()
