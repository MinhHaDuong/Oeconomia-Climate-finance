"""Tests for #441: Cache-is-data citation architecture.

The enrich_citations_batch.py script writes directly to
enrich_cache/crossref_refs.csv (append-only). Done DOIs are determined
by reading source_doi from the cache file itself — no separate done-file.

Tests verify:
- Done DOIs are loaded from the cache file (crossref_refs.csv)
- When cache has sentinels, those DOIs are also counted as done
- Fresh runs (no cache) return empty set
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


class TestCacheIsData:
    """Resume logic reads done DOIs from the cache file itself."""

    def test_load_done_from_cache(self, tmp_catalogs):
        """DOIs present as source_doi in cache file are counted as done."""
        from enrich_citations_batch import load_done_dois
        from utils import REFS_COLUMNS

        cache_path = tmp_catalogs / "enrich_cache" / "crossref_refs.csv"
        rows = [
            {"source_doi": "10.1/a", "source_id": "", "ref_doi": "10.2/x",
             "ref_title": "T", "ref_first_author": "A", "ref_year": "2020",
             "ref_journal": "J", "ref_raw": "{}"},
            {"source_doi": "10.1/b", "source_id": "", "ref_doi": "10.2/y",
             "ref_title": "T2", "ref_first_author": "B", "ref_year": "2021",
             "ref_journal": "J2", "ref_raw": "{}"},
        ]
        pd.DataFrame(rows, columns=REFS_COLUMNS).to_csv(cache_path, index=False)

        done = load_done_dois(str(cache_path))
        assert done == {"10.1/a", "10.1/b"}

    def test_load_done_includes_sentinels(self, tmp_catalogs):
        """DOIs with sentinel ref_doi (__NO_REFS__) are also counted as done."""
        from enrich_citations_batch import load_done_dois, SENTINEL_REF_DOI
        from utils import REFS_COLUMNS

        cache_path = tmp_catalogs / "enrich_cache" / "crossref_refs.csv"
        rows = [
            {"source_doi": "10.1/a", "source_id": "", "ref_doi": SENTINEL_REF_DOI,
             "ref_title": "", "ref_first_author": "", "ref_year": "",
             "ref_journal": "", "ref_raw": ""},
        ]
        pd.DataFrame(rows, columns=REFS_COLUMNS).to_csv(cache_path, index=False)

        done = load_done_dois(str(cache_path))
        assert "10.1/a" in done

    def test_load_done_fresh_run(self, tmp_catalogs):
        """Fresh run with no cache file returns empty set."""
        from enrich_citations_batch import load_done_dois

        done = load_done_dois(str(tmp_catalogs / "enrich_cache" / "crossref_refs.csv"))
        assert done == set()

    def test_load_done_empty_cache(self, tmp_catalogs):
        """Cache file with only header returns empty set."""
        from enrich_citations_batch import load_done_dois
        from utils import REFS_COLUMNS

        cache_path = tmp_catalogs / "enrich_cache" / "crossref_refs.csv"
        pd.DataFrame({c: pd.Series(dtype=str) for c in REFS_COLUMNS}).to_csv(
            cache_path, index=False)

        done = load_done_dois(str(cache_path))
        assert done == set()
