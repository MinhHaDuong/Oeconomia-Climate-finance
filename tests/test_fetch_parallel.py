"""Tests for parallel fetch stage (#265).

Verifies:
1. Different hosts are fetched concurrently (wall-clock speedup).
2. Same-host requests are rate-limited to ~1 req/s.
3. JSONL checkpoint writes are thread-safe (no corrupted lines).
"""

import json
import os
import sys
import time
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def _make_search_record(url):
    """Create a minimal search result record for the fetch stage."""
    return {
        "url": url,
        "title": "Test",
        "snippet": "",
        "query": "test",
        "language": "en",
        "source_tier": "search",
    }


def _mock_response(url, text="<html><body>Hello</body></html>", status=200):
    """Create a mock requests.Response."""
    resp = MagicMock()
    resp.status_code = status
    resp.headers = {"Content-Type": "text/html"}
    resp.text = text
    resp.content = text.encode()
    return resp


class TestFetchParallelDifferentHosts:
    """10 URLs on 10 different hosts should complete much faster than sequential."""

    def test_parallel_speedup(self, tmp_path):
        """Mock 10 URLs on 10 different hosts — all complete in <3s wall-clock.

        Sequential with 0.5s polite_get delay + per-host politeness would take
        ~5-8s. Parallel should finish in ~1-2s.
        """
        from collect_syllabi import PAGES_PATH, SEARCH_PATH, stage_fetch

        urls = [f"http://host{i}.example.com/syllabus" for i in range(10)]
        search_records = [_make_search_record(u) for u in urls]

        # Write search results
        search_path = tmp_path / "search_results.jsonl"
        pages_path = tmp_path / "pages.jsonl"
        pdf_dir = tmp_path / "pdfs"
        pdf_dir.mkdir()

        with open(search_path, "w") as f:
            for rec in search_records:
                f.write(json.dumps(rec) + "\n")

        def slow_polite_get(url, headers=None, delay=0.5, **kwargs):
            """Simulate network latency — 0.5s per request."""
            time.sleep(0.5)
            return _mock_response(url)

        with patch("collect_syllabi.SEARCH_PATH", str(search_path)), \
             patch("collect_syllabi.PAGES_PATH", str(pages_path)), \
             patch("collect_syllabi.PDF_DIR", str(pdf_dir)), \
             patch("collect_syllabi.polite_get", side_effect=slow_polite_get):

            t0 = time.monotonic()
            stage_fetch()
            elapsed = time.monotonic() - t0

        # All 10 should be fetched
        with open(pages_path) as f:
            results = [json.loads(line) for line in f if line.strip()]
        assert len(results) == 10

        # Parallel: should be well under 3s (sequential would be ~5-8s)
        assert elapsed < 3.0, f"Took {elapsed:.1f}s — not parallel enough"


class TestFetchPerHostPoliteness:
    """5 URLs on the SAME host should be rate-limited (~1s spacing)."""

    def test_same_host_rate_limited(self, tmp_path):
        """5 URLs on one host should take ≥4s (1s spacing between requests)."""
        from collect_syllabi import stage_fetch

        urls = [f"http://same-host.example.com/page{i}" for i in range(5)]
        search_records = [_make_search_record(u) for u in urls]

        search_path = tmp_path / "search_results.jsonl"
        pages_path = tmp_path / "pages.jsonl"
        pdf_dir = tmp_path / "pdfs"
        pdf_dir.mkdir()

        with open(search_path, "w") as f:
            for rec in search_records:
                f.write(json.dumps(rec) + "\n")

        call_times = []

        def tracking_polite_get(url, headers=None, delay=0.5, **kwargs):
            """Track when each request happens."""
            call_times.append((url, time.monotonic()))
            return _mock_response(url)

        with patch("collect_syllabi.SEARCH_PATH", str(search_path)), \
             patch("collect_syllabi.PAGES_PATH", str(pages_path)), \
             patch("collect_syllabi.PDF_DIR", str(pdf_dir)), \
             patch("collect_syllabi.polite_get", side_effect=tracking_polite_get):

            t0 = time.monotonic()
            stage_fetch()
            elapsed = time.monotonic() - t0

        with open(pages_path) as f:
            results = [json.loads(line) for line in f if line.strip()]
        assert len(results) == 5

        # With 1s per-host rate limiting, 5 requests = ≥4s gaps
        assert elapsed >= 4.0, f"Only {elapsed:.1f}s — per-host rate limiting not enforced"


class TestFetchCheckpointIntegrity:
    """Concurrent writes to JSONL must not produce corrupted lines."""

    def test_no_corrupted_lines(self, tmp_path):
        """Fetch 20 URLs across 20 hosts — every JSONL line must be valid JSON."""
        from collect_syllabi import stage_fetch

        urls = [f"http://host{i}.example.com/page" for i in range(20)]
        search_records = [_make_search_record(u) for u in urls]

        search_path = tmp_path / "search_results.jsonl"
        pages_path = tmp_path / "pages.jsonl"
        pdf_dir = tmp_path / "pdfs"
        pdf_dir.mkdir()

        with open(search_path, "w") as f:
            for rec in search_records:
                f.write(json.dumps(rec) + "\n")

        def fast_polite_get(url, headers=None, delay=0.5, **kwargs):
            time.sleep(0.05)  # Small delay to create contention
            return _mock_response(url)

        with patch("collect_syllabi.SEARCH_PATH", str(search_path)), \
             patch("collect_syllabi.PAGES_PATH", str(pages_path)), \
             patch("collect_syllabi.PDF_DIR", str(pdf_dir)), \
             patch("collect_syllabi.polite_get", side_effect=fast_polite_get):
            stage_fetch()

        # Every line must be valid JSON
        with open(pages_path) as f:
            lines = [line for line in f if line.strip()]

        assert len(lines) == 20
        for i, line in enumerate(lines):
            try:
                rec = json.loads(line)
                assert "url" in rec, f"Line {i} missing 'url' key"
            except json.JSONDecodeError:
                pytest.fail(f"Corrupted JSONL at line {i}: {line[:100]}")
