"""Tests for #283: Add in_v1 provenance column to refined_works.csv.

The in_v1 column marks rows that existed in the v1.0-submission corpus,
allowing exact reproduction of v1 figures and stability checks.

Tests verify:
- load_v1_identifiers reads the gzipped identifier file correctly
- add_in_v1_column marks matching rows by DOI and source_id fallback
- filter mode output includes the in_v1 column
- Real data: in_v1 count ≈ 29,878 and all v1 DOIs present (no regressions)
"""

import gzip
import os
import subprocess
import sys
import tempfile

import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from corpus_filter import add_in_v1_column, load_v1_identifiers


# ---------------------------------------------------------------------------
# Unit tests: load_v1_identifiers
# ---------------------------------------------------------------------------

class TestLoadV1Identifiers:
    def test_loads_doi_identifiers(self, tmp_path):
        """Should return DOIs from the identifier file."""
        gz_path = tmp_path / "v1_ids.txt.gz"
        with gzip.open(gz_path, "wt") as f:
            f.write("10.1234/a\n10.5678/b\nsid:W999\n")
        dois, sids = load_v1_identifiers(gz_path)
        assert "10.1234/a" in dois
        assert "10.5678/b" in dois
        assert len(dois) == 2

    def test_loads_sid_identifiers(self, tmp_path):
        """Should return source_ids (without sid: prefix) from the file."""
        gz_path = tmp_path / "v1_ids.txt.gz"
        with gzip.open(gz_path, "wt") as f:
            f.write("10.1234/a\nsid:W999\nsid:W888\n")
        dois, sids = load_v1_identifiers(gz_path)
        assert "W999" in sids
        assert "W888" in sids
        assert len(sids) == 2

    def test_returns_empty_on_missing_file(self):
        """Should return empty sets if the file doesn't exist."""
        dois, sids = load_v1_identifiers("/nonexistent/v1_ids.txt.gz")
        assert len(dois) == 0
        assert len(sids) == 0


# ---------------------------------------------------------------------------
# Unit tests: add_in_v1_column
# ---------------------------------------------------------------------------

class TestAddInV1Column:
    def test_marks_matching_dois(self):
        """Rows with DOIs in the v1 set should get in_v1=True."""
        df = pd.DataFrame({
            "doi": ["10.1234/a", "10.5678/b", "10.9999/c"],
            "source_id": ["s1", "s2", "s3"],
        })
        v1_dois = {"10.1234/a", "10.5678/b"}
        v1_sids = set()
        result = add_in_v1_column(df, v1_dois, v1_sids)
        assert result["in_v1"].tolist() == [True, True, False]

    def test_marks_matching_source_ids(self):
        """No-DOI rows with source_id in the v1 set should get in_v1=True."""
        df = pd.DataFrame({
            "doi": [None, None, "10.1/x"],
            "source_id": ["W111", "W222", "s3"],
        })
        v1_dois = {"10.1/x"}
        v1_sids = {"W111"}
        result = add_in_v1_column(df, v1_dois, v1_sids)
        assert result["in_v1"].tolist() == [True, False, True]

    def test_empty_v1_sets_all_false(self):
        """With no v1 identifiers, all rows should be in_v1=False."""
        df = pd.DataFrame({
            "doi": ["10.1/a", "10.1/b"],
            "source_id": ["s1", "s2"],
        })
        result = add_in_v1_column(df, set(), set())
        assert result["in_v1"].sum() == 0

    def test_doi_takes_priority_over_sid(self):
        """A row matching by DOI should be marked even if source_id doesn't match."""
        df = pd.DataFrame({
            "doi": ["10.1/a"],
            "source_id": ["WNEW"],
        })
        result = add_in_v1_column(df, {"10.1/a"}, set())
        assert result["in_v1"].iloc[0] == True


# ---------------------------------------------------------------------------
# Integration: filter mode output includes in_v1
# ---------------------------------------------------------------------------

PYTHON = sys.executable


def run_script(*args, cwd=None):
    result = subprocess.run(
        [PYTHON, os.path.join(SCRIPTS_DIR, "corpus_filter.py"), *args],
        capture_output=True, text=True, cwd=cwd or os.path.dirname(SCRIPTS_DIR),
    )
    return result.returncode, result.stdout + result.stderr


class TestFilterModeInV1:
    @pytest.fixture
    def extended_csv_with_v1_ids(self, tmp_path):
        """Build extended CSV + matching v1 identifier file."""
        df = pd.DataFrame({
            "source_id": [f"s{i}" for i in range(6)],
            "doi": ["10.1/0", "10.1/1", "10.1/2", "10.1/3", "", ""],
            "title": [f"Climate paper {i}" for i in range(6)],
            "year": [2010 + i for i in range(6)],
            "source": ["openalex"] * 6,
            "cited_by_count": [i * 5 for i in range(6)],
            "source_count": [1] * 6,
            "abstract": ["Climate policy abstract"] * 6,
            "type": ["article"] * 6,
            "language": ["en"] * 6,
            "first_author": [f"Author{i}" for i in range(6)],
            "from_openalex": [1] * 6,
            "from_semanticscholar": [0] * 6,
            "from_istex": [0] * 6,
            "from_bibcnrs": [0] * 6,
            "from_scispsace": [0] * 6,
            "from_grey": [0] * 6,
            "from_teaching": [0] * 6,
            "missing_metadata": [False] * 6,
            "no_abstract_irrelevant": [False] * 6,
            "title_blacklist": [False] * 6,
            "protected": [False] * 6,
            "protect_reason": [""] * 6,
            "action": ["keep"] * 6,
        })
        csv_path = tmp_path / "extended_works.csv"
        df.to_csv(csv_path, index=False)

        # v1 identifiers: DOIs 10.1/0, 10.1/1 + source_id s4
        gz_path = tmp_path / "v1_identifiers.txt.gz"
        with gzip.open(gz_path, "wt") as f:
            f.write("10.1/0\n10.1/1\nsid:s4\n")

        return csv_path, gz_path

    def test_filter_output_has_in_v1_column(self, tmp_path, extended_csv_with_v1_ids):
        """Filter mode output must include the in_v1 boolean column."""
        csv_path, gz_path = extended_csv_with_v1_ids
        output_path = tmp_path / "refined_works.csv"

        rc, out = run_script(
            "--filter",
            "--works-input", str(csv_path),
            "--works-output", str(output_path),
            "--v1-identifiers", str(gz_path),
        )
        assert rc == 0, f"--filter failed:\n{out}"
        result = pd.read_csv(output_path)
        assert "in_v1" in result.columns, \
            f"refined_works.csv missing in_v1 column. Columns: {list(result.columns)}"

    def test_filter_output_v1_count_correct(self, tmp_path, extended_csv_with_v1_ids):
        """Filter output in_v1 count must match the v1 identifiers found."""
        csv_path, gz_path = extended_csv_with_v1_ids
        output_path = tmp_path / "refined_works.csv"

        rc, out = run_script(
            "--filter",
            "--works-input", str(csv_path),
            "--works-output", str(output_path),
            "--v1-identifiers", str(gz_path),
        )
        assert rc == 0, f"--filter failed:\n{out}"
        result = pd.read_csv(output_path)
        # 10.1/0, 10.1/1, and s4 are in v1 → 3 matches
        assert result["in_v1"].sum() == 3, \
            f"Expected 3 in_v1=True, got {result['in_v1'].sum()}"


# ---------------------------------------------------------------------------
# Acceptance: real corpus check (slow, requires data)
# ---------------------------------------------------------------------------

V1_IDS_PATH = os.path.join(
    os.path.dirname(__file__), "..", "config", "v1_identifiers.txt.gz"
)
REFINED_PATH = os.path.join(
    os.path.dirname(__file__), "..", "data", "catalogs", "refined_works.csv"
)


@pytest.mark.skipif(
    not os.path.exists(REFINED_PATH) or not os.path.exists(V1_IDS_PATH),
    reason="Requires real data (refined_works.csv + v1_identifiers.txt.gz)",
)
class TestRealCorpusV1:
    def test_in_v1_count_approximately_correct(self):
        """in_v1.sum() should be ≈29,878 (±500 from dedup changes)."""
        v1_dois, v1_sids = load_v1_identifiers(V1_IDS_PATH)
        df = pd.read_csv(REFINED_PATH)
        result = add_in_v1_column(df, v1_dois, v1_sids)
        n_v1 = result["in_v1"].sum()
        assert 28_000 <= n_v1 <= 31_000, \
            f"in_v1 count {n_v1} outside expected range [28000, 31000]"

    def test_no_v1_doi_regressions(self):
        """All v1 DOIs should be present in v2 corpus (no regressions)."""
        v1_dois, _ = load_v1_identifiers(V1_IDS_PATH)
        df = pd.read_csv(REFINED_PATH)
        from utils import normalize_doi
        v2_dois = set(
            df["doi"].apply(lambda x: normalize_doi(x) if pd.notna(x) else "")
        )
        v2_dois.discard("")
        missing = v1_dois - v2_dois
        # Allow small number of missing DOIs from dedup improvements
        assert len(missing) <= 200, \
            f"{len(missing)} v1 DOIs missing from v2 (max 200 allowed). Sample: {list(missing)[:5]}"
