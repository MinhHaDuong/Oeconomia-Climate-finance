"""Tests for OpenAlex incremental filtering and per-query sidecar.

Covers:
- build_filter() combines search term + date correctly
- Per-query sidecar: JSON with {slug: date} entries
- Legacy sidecar fallback (_last_run.txt → _global key)
- Budget logging from response headers
"""

import json
import os
import sys
import tempfile
from unittest.mock import MagicMock

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from catalog_openalex import (
    build_filter,
    read_last_run_date,
    write_last_run_date,
    load_query_dates,
    save_query_dates,
    query_slug,
    LAST_RUN_PATH,
)


# ---------------------------------------------------------------------------
# build_filter
# ---------------------------------------------------------------------------

class TestBuildFilter:
    def test_no_date(self):
        f = build_filter("climate finance", from_date=None)
        assert f == 'default.search:"climate finance"'

    def test_with_date(self):
        f = build_filter("climate finance", from_date="2026-03-01")
        assert f == 'default.search:"climate finance",from_created_date:2026-03-01'

    def test_empty_date(self):
        f = build_filter("climate finance", from_date="")
        assert f == 'default.search:"climate finance"'


# ---------------------------------------------------------------------------
# Per-query sidecar
# ---------------------------------------------------------------------------

class TestQueryDates:
    def test_save_and_load(self, tmp_path):
        path = tmp_path / "_query_dates.json"
        dates = {"climate_finance": "2026-03-15", "carbon_finance": "2026-03-15"}
        save_query_dates(dates, str(path))
        loaded = load_query_dates(str(path))
        assert loaded == dates

    def test_load_missing(self, tmp_path):
        """Missing sidecar returns empty dict."""
        path = tmp_path / "_query_dates.json"
        # Also need to patch LAST_RUN_PATH so fallback doesn't find stale file
        import catalog_openalex
        old = catalog_openalex.LAST_RUN_PATH
        catalog_openalex.LAST_RUN_PATH = str(tmp_path / "_last_run.txt")
        try:
            result = load_query_dates(str(path))
        finally:
            catalog_openalex.LAST_RUN_PATH = old
        assert result == {}

    def test_fallback_to_legacy(self, tmp_path):
        """When JSON doesn't exist but _last_run.txt does, return _global key."""
        json_path = tmp_path / "_query_dates.json"
        legacy_path = tmp_path / "_last_run.txt"
        legacy_path.write_text("2026-03-10\n")

        import catalog_openalex
        old = catalog_openalex.LAST_RUN_PATH
        catalog_openalex.LAST_RUN_PATH = str(legacy_path)
        try:
            result = load_query_dates(str(json_path))
        finally:
            catalog_openalex.LAST_RUN_PATH = old
        assert result == {"_global": "2026-03-10"}

    def test_per_query_date_used(self):
        """Verify query_slug produces consistent slugs for date lookup."""
        assert query_slug("climate finance") == "climate_finance"
        assert query_slug("clean development mechanism") == "clean_development_mechanism"
        assert query_slug("finance climatique") == "finance_climatique"

    def test_incremental_save(self, tmp_path):
        """Saving after each query preserves earlier entries."""
        path = tmp_path / "_query_dates.json"
        dates = {"climate_finance": "2026-03-15"}
        save_query_dates(dates, str(path))
        dates["carbon_finance"] = "2026-03-16"
        save_query_dates(dates, str(path))
        loaded = load_query_dates(str(path))
        assert "climate_finance" in loaded
        assert "carbon_finance" in loaded


# ---------------------------------------------------------------------------
# Legacy sidecar (backwards compat)
# ---------------------------------------------------------------------------

class TestLegacySidecar:
    def test_write_and_read(self, tmp_path):
        path = tmp_path / "_last_run.txt"
        write_last_run_date(str(path), "2026-03-15")
        assert read_last_run_date(str(path)) == "2026-03-15"

    def test_read_missing(self, tmp_path):
        path = tmp_path / "_last_run.txt"
        assert read_last_run_date(str(path)) is None

    def test_read_empty(self, tmp_path):
        path = tmp_path / "_last_run.txt"
        path.write_text("")
        assert read_last_run_date(str(path)) is None


# ---------------------------------------------------------------------------
# Budget logging
# ---------------------------------------------------------------------------

class TestBudgetCapture:
    def test_capture_budget_from_header(self):
        from catalog_openalex import capture_budget
        mock_resp = MagicMock()
        mock_resp.headers = {"X-RateLimit-Remaining-USD": "4.23"}
        assert capture_budget(mock_resp) == "4.23"

    def test_capture_budget_missing_header(self):
        from catalog_openalex import capture_budget
        mock_resp = MagicMock()
        mock_resp.headers = {}
        assert capture_budget(mock_resp) == "?"
