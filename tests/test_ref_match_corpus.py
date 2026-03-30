"""Tests for corpus_ref_match — match parsed citation refs to corpus works."""

import os
import sys
import tempfile

import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


def _make_csv(path, rows, columns):
    """Write a CSV from a list of dicts."""
    df = pd.DataFrame(rows, columns=columns)
    df.to_csv(path, index=False)
    return path


REFS_COLUMNS = [
    "source_doi", "source_id", "ref_doi", "ref_title", "ref_first_author",
    "ref_year", "ref_journal", "ref_raw",
]

CORPUS_COLUMNS = [
    "doi", "title", "year", "first_author", "source_id",
]


class TestRefMatchCorpus:
    """Unit tests for the ref-to-corpus matcher."""

    def test_exact_title_year_match(self, tmp_path):
        """Ticket spec: Stern Review matched by exact normalized title + year."""
        from corpus_ref_match import match_refs_to_corpus

        corpus_path = _make_csv(tmp_path / "refined_works.csv", [
            {"doi": "10.1017/CBO9780511817434", "title": "The Economics of Climate Change",
             "year": "2007", "first_author": "Stern", "source_id": ""},
        ], CORPUS_COLUMNS)

        ref_parsed_path = _make_csv(tmp_path / "ref_parsed.csv", [
            {"source_doi": "10.1234/citing", "source_id": "", "ref_doi": "",
             "ref_title": "The Economics of Climate Change", "ref_first_author": "Stern",
             "ref_year": "2007", "ref_journal": "", "ref_raw": ""},
        ], REFS_COLUMNS)

        output_path = tmp_path / "ref_matches.csv"
        n = match_refs_to_corpus(
            ref_parsed_path=str(ref_parsed_path),
            corpus_path=str(corpus_path),
            output_path=str(output_path),
        )

        assert n == 1
        result = pd.read_csv(output_path, dtype=str, keep_default_na=False)
        assert list(result.columns) == REFS_COLUMNS
        assert result.iloc[0]["ref_doi"] == "10.1017/CBO9780511817434"
        assert result.iloc[0]["source_doi"] == "10.1234/citing"

    def test_fuzzy_title_match_grobid_artifact(self, tmp_path):
        """GROBID often prepends 'in ' — fuzzy matching should catch this."""
        from corpus_ref_match import match_refs_to_corpus

        corpus_path = _make_csv(tmp_path / "refined_works.csv", [
            {"doi": "10.1017/ipcc2014", "title": "Climate Change 2014: Mitigation of Climate Change",
             "year": "2014", "first_author": "IPCC", "source_id": ""},
        ], CORPUS_COLUMNS)

        ref_parsed_path = _make_csv(tmp_path / "ref_parsed.csv", [
            {"source_doi": "10.1234/citing2", "source_id": "", "ref_doi": "",
             "ref_title": "in Climate Change 2014: Mitigation of Climate Change",
             "ref_first_author": "IPCC", "ref_year": "2014", "ref_journal": "", "ref_raw": ""},
        ], REFS_COLUMNS)

        output_path = tmp_path / "ref_matches.csv"
        n = match_refs_to_corpus(
            ref_parsed_path=str(ref_parsed_path),
            corpus_path=str(corpus_path),
            output_path=str(output_path),
        )

        assert n == 1
        assert pd.read_csv(output_path, dtype=str).iloc[0]["ref_doi"] == "10.1017/ipcc2014"

    def test_year_off_by_one_matches(self, tmp_path):
        """Year ±1 tolerance catches publication date discrepancies."""
        from corpus_ref_match import match_refs_to_corpus

        corpus_path = _make_csv(tmp_path / "refined_works.csv", [
            {"doi": "10.1234/work1", "title": "Adaptation Finance in Developing Countries",
             "year": "2010", "first_author": "Smith", "source_id": ""},
        ], CORPUS_COLUMNS)

        ref_parsed_path = _make_csv(tmp_path / "ref_parsed.csv", [
            {"source_doi": "10.1234/citing3", "source_id": "", "ref_doi": "",
             "ref_title": "Adaptation Finance in Developing Countries",
             "ref_first_author": "Smith", "ref_year": "2011", "ref_journal": "", "ref_raw": ""},
        ], REFS_COLUMNS)

        output_path = tmp_path / "ref_matches.csv"
        n = match_refs_to_corpus(
            ref_parsed_path=str(ref_parsed_path),
            corpus_path=str(corpus_path),
            output_path=str(output_path),
        )

        assert n == 1

    def test_skips_refs_that_already_have_doi(self, tmp_path):
        """Refs with existing ref_doi should not be re-matched."""
        from corpus_ref_match import match_refs_to_corpus

        corpus_path = _make_csv(tmp_path / "refined_works.csv", [
            {"doi": "10.1017/CBO9780511817434", "title": "The Economics of Climate Change",
             "year": "2007", "first_author": "Stern", "source_id": ""},
        ], CORPUS_COLUMNS)

        ref_parsed_path = _make_csv(tmp_path / "ref_parsed.csv", [
            {"source_doi": "10.1234/citing", "source_id": "", "ref_doi": "10.9999/already",
             "ref_title": "The Economics of Climate Change", "ref_first_author": "Stern",
             "ref_year": "2007", "ref_journal": "", "ref_raw": ""},
        ], REFS_COLUMNS)

        output_path = tmp_path / "ref_matches.csv"
        n = match_refs_to_corpus(
            ref_parsed_path=str(ref_parsed_path),
            corpus_path=str(corpus_path),
            output_path=str(output_path),
        )

        assert n == 0

    def test_no_match_below_threshold(self, tmp_path):
        """Unrelated titles should not match even with same year."""
        from corpus_ref_match import match_refs_to_corpus

        corpus_path = _make_csv(tmp_path / "refined_works.csv", [
            {"doi": "10.1234/work1", "title": "The Economics of Climate Change",
             "year": "2007", "first_author": "Stern", "source_id": ""},
        ], CORPUS_COLUMNS)

        ref_parsed_path = _make_csv(tmp_path / "ref_parsed.csv", [
            {"source_doi": "10.1234/citing", "source_id": "", "ref_doi": "",
             "ref_title": "A Completely Different Topic About Fisheries",
             "ref_first_author": "Jones", "ref_year": "2007", "ref_journal": "", "ref_raw": ""},
        ], REFS_COLUMNS)

        output_path = tmp_path / "ref_matches.csv"
        n = match_refs_to_corpus(
            ref_parsed_path=str(ref_parsed_path),
            corpus_path=str(corpus_path),
            output_path=str(output_path),
        )

        assert n == 0

    def test_output_has_refs_columns_schema(self, tmp_path):
        """Output must conform to REFS_COLUMNS schema for merge_citations compatibility."""
        from corpus_ref_match import match_refs_to_corpus

        corpus_path = _make_csv(tmp_path / "refined_works.csv", [
            {"doi": "10.1234/work1", "title": "Green Bonds and Climate Finance",
             "year": "2019", "first_author": "Lee", "source_id": ""},
        ], CORPUS_COLUMNS)

        ref_parsed_path = _make_csv(tmp_path / "ref_parsed.csv", [
            {"source_doi": "10.1234/citing", "source_id": "", "ref_doi": "",
             "ref_title": "Green Bonds and Climate Finance",
             "ref_first_author": "Lee", "ref_year": "2019", "ref_journal": "", "ref_raw": ""},
        ], REFS_COLUMNS)

        output_path = tmp_path / "ref_matches.csv"
        match_refs_to_corpus(
            ref_parsed_path=str(ref_parsed_path),
            corpus_path=str(corpus_path),
            output_path=str(output_path),
        )

        result = pd.read_csv(output_path, dtype=str, keep_default_na=False)
        assert list(result.columns) == REFS_COLUMNS

    def test_empty_ref_parsed_produces_empty_output(self, tmp_path):
        """Empty input should produce empty output with correct schema."""
        from corpus_ref_match import match_refs_to_corpus

        corpus_path = _make_csv(tmp_path / "refined_works.csv", [
            {"doi": "10.1234/work1", "title": "Some Work",
             "year": "2020", "first_author": "Author", "source_id": ""},
        ], CORPUS_COLUMNS)

        ref_parsed_path = _make_csv(tmp_path / "ref_parsed.csv", [], REFS_COLUMNS)

        output_path = tmp_path / "ref_matches.csv"
        n = match_refs_to_corpus(
            ref_parsed_path=str(ref_parsed_path),
            corpus_path=str(corpus_path),
            output_path=str(output_path),
        )

        assert n == 0
        result = pd.read_csv(output_path, dtype=str, keep_default_na=False)
        assert list(result.columns) == REFS_COLUMNS
        assert len(result) == 0

    def test_cache_file_produced(self, tmp_path):
        """After matching, a JSONL cache keyed by normalized_title+year is written."""
        import json as json_mod

        from corpus_ref_match import match_refs_to_corpus

        corpus_path = _make_csv(tmp_path / "refined_works.csv", [
            {"doi": "10.1017/CBO9780511817434",
             "title": "The Economics of Climate Change",
             "year": "2007", "first_author": "Stern", "source_id": ""},
        ], CORPUS_COLUMNS)

        ref_parsed_path = _make_csv(tmp_path / "ref_parsed.csv", [
            {"source_doi": "10.1234/citing", "source_id": "", "ref_doi": "",
             "ref_title": "The Economics of Climate Change",
             "ref_first_author": "Stern",
             "ref_year": "2007", "ref_journal": "", "ref_raw": ""},
        ], REFS_COLUMNS)

        cache_path = tmp_path / "ref_match_cache.jsonl"
        output_path = tmp_path / "ref_matches.csv"
        match_refs_to_corpus(
            ref_parsed_path=str(ref_parsed_path),
            corpus_path=str(corpus_path),
            output_path=str(output_path),
            cache_path=str(cache_path),
        )

        assert cache_path.exists(), "Cache file should be created"
        lines = cache_path.read_text().strip().split("\n")
        assert len(lines) >= 1
        entry = json_mod.loads(lines[0])
        assert "normalized_title" in entry
        assert "year" in entry
        assert "ref_doi" in entry
        assert "score" in entry

    def test_cache_hit_skips_matching(self, tmp_path):
        """Re-run with existing cache produces same results."""
        from corpus_ref_match import match_refs_to_corpus

        corpus_path = _make_csv(tmp_path / "refined_works.csv", [
            {"doi": "10.1017/CBO9780511817434",
             "title": "The Economics of Climate Change",
             "year": "2007", "first_author": "Stern", "source_id": ""},
        ], CORPUS_COLUMNS)

        ref_parsed_path = _make_csv(tmp_path / "ref_parsed.csv", [
            {"source_doi": "10.1234/citing", "source_id": "", "ref_doi": "",
             "ref_title": "The Economics of Climate Change",
             "ref_first_author": "Stern",
             "ref_year": "2007", "ref_journal": "", "ref_raw": ""},
        ], REFS_COLUMNS)

        cache_path = tmp_path / "ref_match_cache.jsonl"
        output_path = tmp_path / "ref_matches.csv"

        n1 = match_refs_to_corpus(
            ref_parsed_path=str(ref_parsed_path),
            corpus_path=str(corpus_path),
            output_path=str(output_path),
            cache_path=str(cache_path),
        )

        n2 = match_refs_to_corpus(
            ref_parsed_path=str(ref_parsed_path),
            corpus_path=str(corpus_path),
            output_path=str(output_path),
            cache_path=str(cache_path),
        )

        assert n1 == n2 == 1

    def test_dedup_input_fans_out(self, tmp_path):
        """Duplicate ref titles from different source_dois both get matched."""
        from corpus_ref_match import match_refs_to_corpus

        corpus_path = _make_csv(tmp_path / "refined_works.csv", [
            {"doi": "10.1017/CBO9780511817434",
             "title": "The Economics of Climate Change",
             "year": "2007", "first_author": "Stern", "source_id": ""},
        ], CORPUS_COLUMNS)

        ref_parsed_path = _make_csv(tmp_path / "ref_parsed.csv", [
            {"source_doi": "10.1234/citing1", "source_id": "", "ref_doi": "",
             "ref_title": "The Economics of Climate Change",
             "ref_first_author": "Stern",
             "ref_year": "2007", "ref_journal": "", "ref_raw": ""},
            {"source_doi": "10.1234/citing2", "source_id": "", "ref_doi": "",
             "ref_title": "The Economics of Climate Change",
             "ref_first_author": "Stern",
             "ref_year": "2007", "ref_journal": "", "ref_raw": ""},
        ], REFS_COLUMNS)

        output_path = tmp_path / "ref_matches.csv"
        n = match_refs_to_corpus(
            ref_parsed_path=str(ref_parsed_path),
            corpus_path=str(corpus_path),
            output_path=str(output_path),
            cache_path=str(tmp_path / "cache.jsonl"),
        )

        assert n == 2
        result = pd.read_csv(output_path, dtype=str, keep_default_na=False)
        assert set(result["source_doi"]) == {
            "10.1234/citing1", "10.1234/citing2"}

    def test_progress_logging(self):
        """Script contains progress logging calls with ETA and dedup info."""
        src_path = os.path.join(SCRIPTS_DIR, "corpus_ref_match.py")
        with open(src_path) as f:
            source = f.read()
        assert "PROGRESS_INTERVAL" in source, "Should define progress interval"
        assert "ETA" in source, "Should log ETA"
        assert "unique" in source.lower(), "Should log dedup stats"
        assert "cache_hits" in source, "Should track cache hits"
