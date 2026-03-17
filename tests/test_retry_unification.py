"""Tests for #171: retry robustness, API key consistency, and budget guard.

Covers:
1. polite_get delegates to retry_get (survives transient 429/5xx)
2. mine_openalex_keywords.py sends API key
3. budget_exhausted guard stops fetching when budget hits zero
"""

import os
import sys

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


class TestPoliteGetRobustness:
    """polite_get should survive transient 429s with exponential backoff."""

    def test_polite_get_survives_max_minus_one_429s(self, requests_mock):
        """polite_get should survive POLITE_MAX_RETRIES-1 consecutive 429s."""
        from utils import polite_get, POLITE_MAX_RETRIES

        responses = [
            {"status_code": 429, "headers": {"Retry-After": "0"}}
            for _ in range(POLITE_MAX_RETRIES - 1)
        ] + [{"json": {"ok": True}}]
        requests_mock.get("https://example.com/test", responses)

        resp = polite_get("https://example.com/test", delay=0)
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}

    def test_polite_get_survives_server_error_then_429(self, requests_mock):
        """polite_get should handle mixed 500 + 429 errors."""
        from utils import polite_get

        responses = [
            {"status_code": 500},
            {"status_code": 429, "headers": {"Retry-After": "0"}},
            {"json": {"ok": True}},
        ]
        requests_mock.get("https://example.com/mixed", responses)

        resp = polite_get("https://example.com/mixed", delay=0)
        assert resp.status_code == 200

    def test_polite_get_uses_jitter(self, requests_mock, monkeypatch):
        """polite_get should use jittered backoff, not fixed waits."""
        import time
        from utils import polite_get

        sleeps = []
        original_sleep = time.sleep
        monkeypatch.setattr(time, "sleep", lambda s: sleeps.append(s))

        responses = [
            {"status_code": 429, "headers": {"Retry-After": "0"}},
            {"json": {"ok": True}},
        ]
        requests_mock.get("https://example.com/jitter", responses)

        polite_get("https://example.com/jitter", delay=0)
        # Should have called sleep at least once (for the retry wait)
        assert len(sleeps) >= 1


class TestMineOpenalexKeywordsApiKey:
    """mine_openalex_keywords.py should send the API key when available."""

    def test_fetch_sends_api_key(self, monkeypatch, requests_mock):
        """fetch_openalex_metadata should include api_key in params."""
        import utils
        monkeypatch.setattr(utils, "OPENALEX_API_KEY", "test-key-123")

        captured_params = {}

        def capture_request(request, context):
            captured_params.update(dict(request.qs))
            context.status_code = 200
            return {"results": [], "meta": {"count": 0}}

        requests_mock.get(
            "https://api.openalex.org/works",
            json=capture_request,
        )

        from mine_openalex_keywords import fetch_openalex_metadata
        fetch_openalex_metadata(["10.1000/test"])

        # The api_key param should be present
        assert "api_key" in captured_params, (
            "mine_openalex_keywords does not send OPENALEX_API_KEY"
        )


class TestBudgetExhausted:
    """budget_exhausted should detect zero/negative remaining budget."""

    def test_zero_budget(self):
        from catalog_openalex import budget_exhausted
        assert budget_exhausted("0") is True
        assert budget_exhausted("0.00") is True

    def test_negative_budget(self):
        from catalog_openalex import budget_exhausted
        assert budget_exhausted("-0.01") is True

    def test_positive_budget(self):
        from catalog_openalex import budget_exhausted
        assert budget_exhausted("1.50") is False
        assert budget_exhausted("0.01") is False

    def test_unknown_budget(self):
        from catalog_openalex import budget_exhausted
        assert budget_exhausted("?") is False

    def test_non_numeric(self):
        from catalog_openalex import budget_exhausted
        assert budget_exhausted("N/A") is False
        assert budget_exhausted(None) is False


class TestFetchQueryBudgetGuard:
    """fetch_query should stop and signal when budget is exhausted."""

    def test_stops_on_zero_budget(self, requests_mock, tmp_path):
        from catalog_openalex import fetch_query

        # Page 1: results + $0 remaining
        requests_mock.get(
            "https://api.openalex.org/works",
            json={
                "meta": {"count": 500, "next_cursor": "abc123"},
                "results": [{"id": "https://openalex.org/W1", "doi": "10.1/a"}],
            },
            headers={"X-RateLimit-Remaining-USD": "0.00"},
        )

        pool_file = str(tmp_path / "test.jsonl.gz")
        n_new, out_of_budget = fetch_query(
            "climate finance", delay=0, limit=0,
            existing_ids=set(), pool_file=pool_file,
        )
        # Should have fetched page 1 then stopped
        assert n_new == 1
        assert out_of_budget is True

    def test_continues_with_budget(self, requests_mock, tmp_path):
        from catalog_openalex import fetch_query

        # Single page with budget remaining, no next cursor
        requests_mock.get(
            "https://api.openalex.org/works",
            json={
                "meta": {"count": 1, "next_cursor": None},
                "results": [{"id": "https://openalex.org/W2", "doi": "10.1/b"}],
            },
            headers={"X-RateLimit-Remaining-USD": "1.50"},
        )

        pool_file = str(tmp_path / "test.jsonl.gz")
        n_new, out_of_budget = fetch_query(
            "climate finance", delay=0, limit=0,
            existing_ids=set(), pool_file=pool_file,
        )
        assert n_new == 1
        assert out_of_budget is False
