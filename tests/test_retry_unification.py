"""Tests for #171: polite_get retry robustness and API key consistency.

Red-phase tests:
1. polite_get crashes after 3 retries on 429 (current fragile behavior)
2. mine_openalex_keywords.py does not send API key

These tests document the bugs. The Green phase will make them pass
by unifying polite_get → retry_get and adding the API key.
"""

import os
import sys

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


class TestPoliteGetRobustness:
    """polite_get should survive transient 429s with exponential backoff."""

    def test_polite_get_survives_four_consecutive_429s(self, requests_mock):
        """polite_get should survive 4 consecutive 429s then succeed (5 retries)."""
        from utils import polite_get

        responses = [
            {"status_code": 429, "headers": {"Retry-After": "0"}}
            for _ in range(4)
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
