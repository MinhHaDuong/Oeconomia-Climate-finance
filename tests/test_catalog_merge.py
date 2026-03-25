"""Tests for catalog_merge: source provenance flags survive merge.

Ticket #452: from_scispace was never set because the source column in
scispace_works.csv contained a legacy typo ("scispsace") while the merge
script matched against "scispace". The fix normalises source names from
the filename, not the CSV's source column.
"""

import os
import sys
import tempfile

import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from catalog_merge import _dedup_vectorized, _load_and_tag  # noqa: E402
from utils import FROM_COLS, WORKS_COLUMNS  # noqa: E402


def _make_catalog(rows, source_name):
    """Create a minimal catalog DataFrame with the given source."""
    records = []
    for r in rows:
        rec = {c: "" for c in WORKS_COLUMNS}
        rec.update(r)
        rec["source"] = source_name
        records.append(rec)
    return pd.DataFrame(records)


class TestFromScispaceFlagSet:
    """from_scispace must be 1 for records originating from scispace_works.csv,
    regardless of the spelling in the CSV's source column."""

    def test_scispace_flag_set_when_source_column_has_typo(self):
        """_load_and_tag must override source from filename, so even if
        the CSV says 'scispsace', the source becomes 'scispace'."""
        scispace_df = _make_catalog(
            [{"doi": "10.1234/test-scispace", "title": "Climate finance paper",
              "year": "2020", "first_author": "Smith"}],
            source_name="scispsace",  # legacy typo in CSV
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "scispace_works.csv")
            scispace_df.to_csv(path, index=False)

            loaded = _load_and_tag(path)
            assert loaded["source"].iloc[0] == "scispace", \
                "source must be normalised from filename, not CSV content"

    def test_from_scispace_nonzero_after_merge(self):
        """End-to-end: after concat + from_* flag assignment, from_scispace > 0."""
        scispace_df = _make_catalog(
            [{"doi": "10.1234/test-scispace", "title": "Climate finance paper",
              "year": "2020", "first_author": "Smith"}],
            source_name="scispsace",  # legacy typo
        )
        openalex_df = _make_catalog(
            [{"doi": "10.1234/test-openalex", "title": "Another paper",
              "year": "2021", "first_author": "Jones"}],
            source_name="openalex",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            sci_path = os.path.join(tmpdir, "scispace_works.csv")
            oa_path = os.path.join(tmpdir, "openalex_works.csv")
            scispace_df.to_csv(sci_path, index=False)
            openalex_df.to_csv(oa_path, index=False)

            frames = [_load_and_tag(sci_path), _load_and_tag(oa_path)]
            combined = pd.concat(frames, ignore_index=True)

            for col in FROM_COLS:
                src_name = col.replace("from_", "")
                combined[col] = (combined["source"] == src_name).astype(int)

            assert combined["from_scispace"].sum() > 0, \
                "from_scispace must be set for SciSpace records"

    def test_scispace_flag_survives_doi_dedup(self):
        """When a SciSpace record shares a DOI with an OpenAlex record,
        from_scispace must still be 1 after deduplication."""
        shared_doi = "10.1234/shared"
        rows = []
        for src, title in [("openalex", "Paper A"), ("scispace", "Paper A")]:
            rec = {c: "" for c in WORKS_COLUMNS}
            rec["source"] = src
            rec["doi"] = shared_doi
            rec["title"] = title
            rec["year"] = "2020"
            rec["first_author"] = "Smith"
            rows.append(rec)

        df = pd.DataFrame(rows)
        df["_doi_norm"] = shared_doi

        for col in FROM_COLS:
            src_name = col.replace("from_", "")
            df[col] = (df["source"] == src_name).astype(int)

        result = _dedup_vectorized(df, "_doi_norm")
        assert result["from_scispace"].iloc[0] == 1, \
            "from_scispace must survive DOI dedup (max aggregation)"
        assert result["from_openalex"].iloc[0] == 1, \
            "from_openalex must survive DOI dedup (max aggregation)"
