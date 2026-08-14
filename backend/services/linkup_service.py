"""
DEPRECATED. Linkup has been removed from TrialFinder.

Search now runs through services/search_service.py, which uses:
  - ClinicalTrials.gov v2 API for the trial registry (free, no key)
  - Claude's built-in web_search tool for supplementary context

This shim remains only so any stale import fails loudly with a useful
message instead of an obscure ModuleNotFoundError. Safe to delete.
"""

_MESSAGE = (
    "linkup_service has been removed. Use services.search_service instead: "
    "search_for_trials() for the matching pipeline, web_search() for "
    "supplementary lookups, fetch_ctgov_trials() for registry data."
)


async def search_for_trials(*args, **kwargs):
    raise RuntimeError(_MESSAGE)


def _build_queries(*args, **kwargs):
    raise RuntimeError(_MESSAGE)


def _load_mock_fixture(*args, **kwargs):
    raise RuntimeError(_MESSAGE)
