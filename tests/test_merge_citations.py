"""Tests for merge_citations: concat cache files, dedup, write citations.csv.

The merge step reads two source-specific cache files:
  - enrich_cache/crossref_refs.csv  (Crossref citations with ref_raw)
  - enrich_cache/openalex_refs.csv  (OpenAlex citations with ref_oa_id)

It produces a single citations.csv with the union of both, deduplicated
on (source_doi, ref_doi).
"""

import os
import sys

import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

CROSSREF_COLS = [
    "source_doi", "source_id", "ref_doi", "ref_title", "ref_first_author",
    "ref_year", "ref_journal", "ref_raw",
]
OPENALEX_COLS = [
    "source_doi", "ref_oa_id", "ref_doi", "ref_title",
    "ref_first_author", "ref_year", "ref_journal",
]
SENTINEL_REF_DOI = "__NO_REFS__"


@pytest.fixture
def cache_dir(tmp_path):
    """Create an enrich_cache directory with sample crossref + openalex files."""
    cache = tmp_path / "enrich_cache"
    cache.mkdir()
    return cache


def _write_crossref(cache_dir, rows):
    df = pd.DataFrame(rows, columns=CROSSREF_COLS)
    df.to_csv(cache_dir / "crossref_refs.csv", index=False)


def _write_openalex(cache_dir, rows):
    df = pd.DataFrame(rows, columns=OPENALEX_COLS)
    df.to_csv(cache_dir / "openalex_refs.csv", index=False)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestMergeCitations:
    def test_concat_both_sources(self, tmp_path, cache_dir):
        """Merge should include rows from both sources."""
        _write_crossref(cache_dir, [
            ["10.1/a", "", "10.2/x", "Title X", "Smith", "2020", "Nature", "{}"],
        ])
        _write_openalex(cache_dir, [
            ["10.1/b", "W123", "10.2/y", "Title Y", "Jones", "2021", "Science"],
        ])
        out = tmp_path / "citations.csv"

        from merge_citations import merge_citations
        merge_citations(cache_dir=str(cache_dir), output_path=str(out))

        result = pd.read_csv(out)
        assert len(result) == 2
        assert set(result["source_doi"]) == {"10.1/a", "10.1/b"}

    def test_dedup_on_source_doi_ref_doi(self, tmp_path, cache_dir):
        """When both sources have the same (source_doi, ref_doi), keep one."""
        _write_crossref(cache_dir, [
            ["10.1/a", "", "10.2/x", "Title X", "Smith", "2020", "Nature", "{}"],
        ])
        _write_openalex(cache_dir, [
            ["10.1/a", "W123", "10.2/x", "Title X OA", "Smith", "2020", "Nature"],
        ])
        out = tmp_path / "citations.csv"

        from merge_citations import merge_citations
        merge_citations(cache_dir=str(cache_dir), output_path=str(out))

        result = pd.read_csv(out)
        assert len(result) == 1

    def test_sentinel_rows_excluded(self, tmp_path, cache_dir):
        """Sentinel rows (ref_doi == __NO_REFS__) should not appear in output."""
        _write_crossref(cache_dir, [
            ["10.1/a", "", SENTINEL_REF_DOI, "", "", "", "", ""],
            ["10.1/b", "", "10.2/x", "Title X", "Smith", "2020", "Nature", "{}"],
        ])
        _write_openalex(cache_dir, [])
        out = tmp_path / "citations.csv"

        from merge_citations import merge_citations
        merge_citations(cache_dir=str(cache_dir), output_path=str(out))

        result = pd.read_csv(out)
        assert len(result) == 1
        assert result.iloc[0]["source_doi"] == "10.1/b"

    def test_no_doi_refs_kept(self, tmp_path, cache_dir):
        """Refs without ref_doi (books, reports) should be kept."""
        _write_crossref(cache_dir, [
            ["10.1/a", "", "", "Climate Book", "Brown", "1996", "", '{"author":"Brown"}'],
        ])
        _write_openalex(cache_dir, [])
        out = tmp_path / "citations.csv"

        from merge_citations import merge_citations
        merge_citations(cache_dir=str(cache_dir), output_path=str(out))

        result = pd.read_csv(out)
        assert len(result) == 1
        assert result.iloc[0]["ref_title"] == "Climate Book"

    def test_missing_cache_files_ok(self, tmp_path, cache_dir):
        """Merge should work even if one or both cache files are missing."""
        out = tmp_path / "citations.csv"

        from merge_citations import merge_citations
        merge_citations(cache_dir=str(cache_dir), output_path=str(out))

        result = pd.read_csv(out)
        assert len(result) == 0

    def test_no_doi_dedup_across_sources(self, tmp_path, cache_dir):
        """Same book ref from both sources should be deduplicated."""
        _write_crossref(cache_dir, [
            ["10.1/a", "", "", "Climate Book", "Brown", "1996", "", '{"author":"Brown"}'],
        ])
        _write_openalex(cache_dir, [
            ["10.1/a", "W999", "", "Climate Book", "Brown", "1996", ""],
        ])
        out = tmp_path / "citations.csv"

        from merge_citations import merge_citations
        merge_citations(cache_dir=str(cache_dir), output_path=str(out))

        result = pd.read_csv(out)
        assert len(result) == 1, \
            f"Expected 1 row (deduped no-DOI ref), got {len(result)}"

    def test_output_columns(self, tmp_path, cache_dir):
        """Output should have the standard REFS_COLUMNS schema."""
        _write_crossref(cache_dir, [
            ["10.1/a", "", "10.2/x", "Title", "Smith", "2020", "Nature", "{}"],
        ])
        _write_openalex(cache_dir, [
            ["10.1/b", "W123", "10.2/y", "Title Y", "Jones", "2021", "Science"],
        ])
        out = tmp_path / "citations.csv"

        from merge_citations import merge_citations
        merge_citations(cache_dir=str(cache_dir), output_path=str(out))

        result = pd.read_csv(out)
        expected_cols = [
            "source_doi", "source_id", "ref_doi", "ref_title",
            "ref_first_author", "ref_year", "ref_journal", "ref_raw",
        ]
        assert list(result.columns) == expected_cols
