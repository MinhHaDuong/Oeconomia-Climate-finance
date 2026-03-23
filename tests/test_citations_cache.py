"""Tests for #306: Citations cache survives DVC stage re-runs.

The enrich_citations_batch.py script must read its resume cache from
enrich_cache/citations_done.csv (not from citations.csv, which DVC deletes
before re-running the stage).

Tests verify:
- Done DOIs are loaded from enrich_cache/citations_done.csv
- When citations.csv is absent but cache exists, DOIs are still known
- After a run, the cache file is updated with newly processed DOIs
- Fresh runs (no cache) still work
"""

import os
import sys

import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


@pytest.fixture
def tmp_catalogs(tmp_path):
    """Create a temporary catalogs directory with enrich_cache/ subdirectory."""
    cache_dir = tmp_path / "enrich_cache"
    cache_dir.mkdir()
    return tmp_path


class TestDoneCacheLoad:
    """Resume logic must read from enrich_cache/citations_done.csv, not citations.csv."""

    def test_load_done_from_cache_when_citations_csv_missing(self, tmp_catalogs):
        """When citations.csv is deleted (DVC re-run) but cache exists, DOIs are known."""
        from enrich_citations_batch import load_done_dois

        # Write cache file with known DOIs
        cache_path = tmp_catalogs / "enrich_cache" / "citations_done.csv"
        pd.DataFrame({"source_doi": ["10.1/a", "10.1/b", "10.1/c"]}).to_csv(
            cache_path, index=False
        )

        # No citations.csv exists (DVC deleted it)
        citations_path = tmp_catalogs / "citations.csv"
        assert not citations_path.exists()

        done = load_done_dois(str(citations_path), str(cache_path))
        assert done == {"10.1/a", "10.1/b", "10.1/c"}

    def test_load_done_from_cache_and_citations(self, tmp_catalogs):
        """When both files exist, DOIs from both are merged."""
        from enrich_citations_batch import load_done_dois
        from utils import REFS_COLUMNS

        cache_path = tmp_catalogs / "enrich_cache" / "citations_done.csv"
        pd.DataFrame({"source_doi": ["10.1/a", "10.1/b"]}).to_csv(
            cache_path, index=False
        )

        citations_path = tmp_catalogs / "citations.csv"
        pd.DataFrame(
            [{col: "" for col in REFS_COLUMNS} | {"source_doi": "10.1/c"}]
        ).to_csv(citations_path, index=False)

        done = load_done_dois(str(citations_path), str(cache_path))
        assert {"10.1/a", "10.1/b", "10.1/c"} <= done

    def test_load_done_fresh_run(self, tmp_catalogs):
        """Fresh run with neither file returns empty set."""
        from enrich_citations_batch import load_done_dois

        done = load_done_dois(
            str(tmp_catalogs / "citations.csv"),
            str(tmp_catalogs / "enrich_cache" / "citations_done.csv"),
        )
        assert done == set()


class TestDoneCacheSave:
    """After processing, save_done_cache must write the done set to disk."""

    def test_save_creates_cache_file(self, tmp_catalogs):
        """save_done_cache writes source DOIs to enrich_cache/citations_done.csv."""
        from enrich_citations_batch import save_done_cache

        cache_path = tmp_catalogs / "enrich_cache" / "citations_done.csv"
        save_done_cache({"10.1/x", "10.1/y"}, str(cache_path))

        assert cache_path.exists()
        df = pd.read_csv(cache_path)
        saved_dois = set(df["source_doi"])
        assert saved_dois == {"10.1/x", "10.1/y"}

    def test_save_updates_existing_cache(self, tmp_catalogs):
        """Saving a superset overwrites the file correctly."""
        from enrich_citations_batch import save_done_cache

        cache_path = tmp_catalogs / "enrich_cache" / "citations_done.csv"
        save_done_cache({"10.1/a"}, str(cache_path))
        save_done_cache({"10.1/a", "10.1/b"}, str(cache_path))

        df = pd.read_csv(cache_path)
        assert set(df["source_doi"]) == {"10.1/a", "10.1/b"}
