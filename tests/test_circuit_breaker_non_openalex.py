"""Circuit breaker tests for non-OpenAlex API loops (#602).

Tests that catalog_istex, catalog_semanticscholar, and enrich_abstracts Step 4
abort their loops after CONSECUTIVE_FAIL_LIMIT consecutive 429 responses,
rather than hammering an exhausted API indefinitely.
"""

import sys
from unittest.mock import MagicMock, patch

import pytest

# Ensure scripts/ is importable
sys.path.insert(0, "scripts")

from pipeline_io import CONSECUTIVE_FAIL_LIMIT, RateLimitExhausted  # noqa: E402


# ---------------------------------------------------------------------------
# catalog_istex: fetch_istex_api should abort on consecutive 429s
# ---------------------------------------------------------------------------

class TestIstexCircuitBreaker:
    """ISTEX pagination loop should abort after consecutive 429s."""

    def test_aborts_on_consecutive_429(self):
        """Consecutive 429s in the pagination loop raise RateLimitExhausted."""
        from catalog_istex import fetch_istex_api

        # First call succeeds (gets total), then all subsequent return 429
        first_resp = MagicMock()
        first_resp.status_code = 200
        first_resp.json.return_value = {"total": 500, "hits": [{"id": "a"}] * 100}

        rate_limited = MagicMock()
        rate_limited.status_code = 429
        rate_limited.json.return_value = {}

        responses = [first_resp] + [rate_limited] * (CONSECUTIVE_FAIL_LIMIT + 5)

        with patch("catalog_istex.polite_get", side_effect=responses):
            with pytest.raises(RateLimitExhausted):
                fetch_istex_api("climate finance", year_min=2000, year_max=2020)


# ---------------------------------------------------------------------------
# catalog_semanticscholar: fetch_query should abort on consecutive 429s
# ---------------------------------------------------------------------------

class TestSemanticScholarCircuitBreaker:
    """S2 pagination loop should abort after consecutive 429s."""

    def test_aborts_on_consecutive_429(self):
        """Consecutive 429s in the pagination loop raise RateLimitExhausted."""
        from catalog_semanticscholar import fetch_query

        rate_limited = MagicMock()
        rate_limited.status_code = 429
        rate_limited.json.return_value = {}

        responses = [rate_limited] * (CONSECUTIVE_FAIL_LIMIT + 5)

        with patch("catalog_semanticscholar.s2_get", side_effect=responses):
            with pytest.raises(RateLimitExhausted):
                fetch_query("climate finance", delay=0, limit=0,
                            existing_ids=set(),
                            pool_file="/dev/null")


# ---------------------------------------------------------------------------
# enrich_abstracts step 4: should abort on consecutive 429s
# ---------------------------------------------------------------------------

class TestEnrichAbstractsS2CircuitBreaker:
    """enrich_abstracts Step 4 should abort after consecutive 429s."""

    def test_aborts_on_consecutive_429(self):
        """Consecutive 429s in Step 4 loop raise RateLimitExhausted."""
        import pandas as pd
        from enrich_abstracts import step4_semantic_scholar

        # Build a small DataFrame with missing abstracts + DOIs
        df = pd.DataFrame({
            "doi": [f"10.1234/test{i}" for i in range(20)],
            "abstract": [""] * 20,
            "_missing": [True] * 20,
            "_has_doi": [True] * 20,
        })

        rate_limited = MagicMock()
        rate_limited.status_code = 429
        rate_limited.json.return_value = {}

        counters = {}
        responses = [rate_limited] * (CONSECUTIVE_FAIL_LIMIT + 10)

        with (
            patch("enrich_abstracts.load_cache", return_value={}),
            patch("enrich_abstracts.save_cache"),
            patch("enrich_abstracts.retry_get", side_effect=responses),
        ):
            with pytest.raises(RateLimitExhausted):
                step4_semantic_scholar(df, counters)
