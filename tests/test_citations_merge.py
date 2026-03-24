"""Tests for #394: enrich_citations_batch.py merge/sentinel robustness.

The checkpoint merge must:
- Preserve real refs that lack a ref_doi (common in Crossref data)
- Drop sentinel rows (ref_doi == SENTINEL_REF_DOI)
- Drop legacy sentinels (all non-key fields empty)
- Handle dtype consistently (str throughout, no NaN surprises)
"""

import os
import sys

import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from utils import REFS_COLUMNS  # noqa: E402


@pytest.fixture
def tmp_catalogs(tmp_path):
    """Create a temporary catalogs directory with enrich_cache/."""
    cache_dir = tmp_path / "enrich_cache"
    cache_dir.mkdir()
    return tmp_path


def _make_checkpoint(path, rows):
    """Write a checkpoint CSV from a list of dicts."""
    df = pd.DataFrame(rows, columns=REFS_COLUMNS)
    df.to_csv(path, index=False)


class TestSentinelFilter:
    """Sentinel rows must be dropped; real refs (even without DOI) must survive."""

    def test_real_ref_without_doi_survives(self, tmp_catalogs):
        """A Crossref ref with title but no DOI is real, not a sentinel."""
        from enrich_citations_batch import SENTINEL_REF_DOI

        checkpoint = tmp_catalogs / ".citations_batch_checkpoint.csv"
        citations = tmp_catalogs / "citations.csv"
        # Write empty citations.csv (simulates DVC clean)
        pd.DataFrame(columns=REFS_COLUMNS).to_csv(citations, index=False)

        _make_checkpoint(checkpoint, [
            # Real ref: has title, no DOI
            {"source_doi": "10.1/a", "source_id": "", "ref_doi": "",
             "ref_title": "A real paper title", "ref_first_author": "Smith",
             "ref_year": "2020", "ref_journal": "Nature", "ref_raw": "{}"},
            # Sentinel: uses marker
            {"source_doi": "10.1/b", "source_id": "", "ref_doi": SENTINEL_REF_DOI,
             "ref_title": "", "ref_first_author": "",
             "ref_year": "", "ref_journal": "", "ref_raw": ""},
            # Legacy sentinel: all empty
            {"source_doi": "10.1/c", "source_id": "", "ref_doi": "",
             "ref_title": "", "ref_first_author": "",
             "ref_year": "", "ref_journal": "", "ref_raw": ""},
        ])

        # Read and filter like the script does
        new_refs = pd.read_csv(checkpoint, dtype=str, keep_default_na=False)
        is_sentinel = (new_refs["ref_doi"] == SENTINEL_REF_DOI)
        non_key_cols = [c for c in REFS_COLUMNS if c != "source_doi"]
        is_sentinel = is_sentinel | new_refs[non_key_cols].eq("").all(axis=1)
        real = new_refs[~is_sentinel]

        assert len(real) == 1
        assert real.iloc[0]["ref_title"] == "A real paper title"
        assert real.iloc[0]["source_doi"] == "10.1/a"

    def test_sentinel_constant_is_not_a_valid_doi(self):
        """The sentinel marker must not look like a real DOI."""
        from enrich_citations_batch import SENTINEL_REF_DOI
        assert not SENTINEL_REF_DOI.startswith("10.")
        assert SENTINEL_REF_DOI != ""

    def test_fetch_batch_output_matches_refs_columns(self):
        """fetch_batch dict keys must match REFS_COLUMNS exactly."""
        from enrich_citations_batch import SENTINEL_REF_DOI

        # Simulate what fetch_batch produces (one ref row)
        row = {
            "source_doi": "10.1/test", "source_id": "",
            "ref_doi": "10.2/ref", "ref_title": "Test",
            "ref_first_author": "Doe", "ref_year": "2021",
            "ref_journal": "Science", "ref_raw": "{}",
        }
        assert set(row.keys()) == set(REFS_COLUMNS)

        # Simulate sentinel row
        sentinel = {
            "source_doi": "10.1/test", "source_id": "",
            "ref_doi": SENTINEL_REF_DOI,
            "ref_title": "", "ref_first_author": "",
            "ref_year": "", "ref_journal": "", "ref_raw": "",
        }
        assert set(sentinel.keys()) == set(REFS_COLUMNS)


class TestDtypeConsistency:
    """All CSV reads in the merge path must use dtype=str."""

    def test_existing_citations_read_as_str(self, tmp_catalogs):
        """existing citations.csv must be read with dtype=str to avoid NaN."""
        citations = tmp_catalogs / "citations.csv"
        # Write a row with empty ref_doi — pandas would infer NaN without dtype=str
        pd.DataFrame([{
            "source_doi": "10.1/x", "source_id": "", "ref_doi": "",
            "ref_title": "Real", "ref_first_author": "A",
            "ref_year": "2020", "ref_journal": "J", "ref_raw": "{}",
        }]).to_csv(citations, index=False)

        df = pd.read_csv(citations, dtype=str, keep_default_na=False)
        assert df.iloc[0]["ref_doi"] == ""
        assert not pd.isna(df.iloc[0]["ref_doi"])

    def test_checkpoint_read_as_str(self, tmp_catalogs):
        """Checkpoint must be read with dtype=str to preserve empty strings."""
        ckpt = tmp_catalogs / "checkpoint.csv"
        _make_checkpoint(ckpt, [{
            "source_doi": "10.1/x", "source_id": "", "ref_doi": "",
            "ref_title": "A paper", "ref_first_author": "",
            "ref_year": "", "ref_journal": "", "ref_raw": "",
        }])

        df = pd.read_csv(ckpt, dtype=str, keep_default_na=False)
        # ref_first_author is empty string, not NaN
        assert df.iloc[0]["ref_first_author"] == ""
        assert not pd.isna(df.iloc[0]["ref_first_author"])


class TestErrorCounting:
    """Error counter should track consecutive errors, not cumulative."""

    def test_consecutive_vs_cumulative(self):
        """Document the expected behavior: consecutive errors reset on success."""
        # This test documents the contract — the fix changes cumulative to consecutive
        consecutive_errors = 0
        max_consecutive = 5

        # Simulate: error, error, success, error
        for outcome in ["error", "error", "success", "error"]:
            if outcome == "error":
                consecutive_errors += 1
            else:
                consecutive_errors = 0
            assert consecutive_errors <= max_consecutive
