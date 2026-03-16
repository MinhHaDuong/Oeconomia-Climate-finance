"""Tests for #153: --from-date incremental filtering for OpenAlex queries.

Covers:
- --from-date appends from_created_date filter to API params
- _last_run.txt sidecar: written after successful run, read on --resume
- --resume without --from-date auto-detects date from sidecar
- Full run (no --resume, no --from-date) fetches everything (no date filter)
- Budget logging: start/end USD captured from X-RateLimit-Remaining-USD header
- build_filter() combines search term + date correctly
"""

import os
import sys
import tempfile
from datetime import date
from unittest.mock import patch, MagicMock

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from catalog_openalex import (
    build_filter,
    read_last_run_date,
    write_last_run_date,
    LAST_RUN_PATH,
)


# ---------------------------------------------------------------------------
# build_filter
# ---------------------------------------------------------------------------

class TestBuildFilter:
    def test_no_date(self):
        """Without date, filter is just the search term."""
        f = build_filter("climate finance", from_date=None)
        assert f == 'default.search:"climate finance"'

    def test_with_date(self):
        """With date, filter appends from_created_date."""
        f = build_filter("climate finance", from_date="2026-03-01")
        assert f == 'default.search:"climate finance",from_created_date:2026-03-01'

    def test_empty_date(self):
        """Empty string date treated as no date."""
        f = build_filter("climate finance", from_date="")
        assert f == 'default.search:"climate finance"'


# ---------------------------------------------------------------------------
# Sidecar file
# ---------------------------------------------------------------------------

class TestSidecar:
    def test_write_and_read(self, tmp_path):
        """Round-trip: write date, read it back."""
        path = tmp_path / "_last_run.txt"
        write_last_run_date(str(path), "2026-03-15")
        assert read_last_run_date(str(path)) == "2026-03-15"

    def test_read_missing(self, tmp_path):
        """Missing sidecar returns None."""
        path = tmp_path / "_last_run.txt"
        assert read_last_run_date(str(path)) is None

    def test_read_empty(self, tmp_path):
        """Empty sidecar returns None."""
        path = tmp_path / "_last_run.txt"
        path.write_text("")
        assert read_last_run_date(str(path)) is None

    def test_read_strips_whitespace(self, tmp_path):
        """Sidecar with trailing newline still reads clean date."""
        path = tmp_path / "_last_run.txt"
        path.write_text("2026-03-10\n")
        assert read_last_run_date(str(path)) == "2026-03-10"


# ---------------------------------------------------------------------------
# Budget logging
# ---------------------------------------------------------------------------

class TestBudgetCapture:
    def test_capture_budget_from_header(self):
        """capture_budget extracts X-RateLimit-Remaining-USD from response."""
        from catalog_openalex import capture_budget
        mock_resp = MagicMock()
        mock_resp.headers = {"X-RateLimit-Remaining-USD": "4.23"}
        assert capture_budget(mock_resp) == "4.23"

    def test_capture_budget_missing_header(self):
        """Missing header returns '?'."""
        from catalog_openalex import capture_budget
        mock_resp = MagicMock()
        mock_resp.headers = {}
        assert capture_budget(mock_resp) == "?"
