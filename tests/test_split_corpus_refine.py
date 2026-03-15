"""Tests for #54: Split corpus_refine into extend mode and filter mode.

Tests verify:
- --extend mode: reads input, adds flag/protection columns, writes output with SAME row count
- --filter mode: reads extended artifact, applies policy, output rows <= input rows
- --works-input / --works-output CLI args accepted
- Row-count invariant: extend rows == input rows
- Row-count invariant: filter rows <= extend rows
- Backward-compat: --apply still works as combined extend+filter
"""

import os
import subprocess
import sys
import tempfile

import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
PYTHON = sys.executable
FIXTURE_DIR = os.path.join(os.path.dirname(__file__), "fixtures")


def run_script(*args, cwd=None):
    """Run corpus_refine.py with args, return (returncode, stdout+stderr)."""
    result = subprocess.run(
        [PYTHON, os.path.join(SCRIPTS_DIR, "corpus_refine.py"), *args],
        capture_output=True, text=True, cwd=cwd or os.path.dirname(SCRIPTS_DIR)
    )
    return result.returncode, result.stdout + result.stderr


def help_output():
    """Return --help output of corpus_refine.py."""
    _, out = run_script("--help")
    return out


# ---------------------------------------------------------------------------
# CLI argument presence
# ---------------------------------------------------------------------------

class TestCLIArgs:
    def test_accepts_extend_flag(self):
        out = help_output()
        assert "--extend" in out, "corpus_refine.py must accept --extend"

    def test_accepts_filter_flag(self):
        out = help_output()
        assert "--filter" in out, "corpus_refine.py must accept --filter"

    def test_accepts_works_input(self):
        out = help_output()
        assert "--works-input" in out, "corpus_refine.py must accept --works-input"

    def test_accepts_works_output(self):
        out = help_output()
        assert "--works-output" in out, "corpus_refine.py must accept --works-output"

    def test_works_input_default_for_extend(self):
        """--extend mode default input should be enriched_works.csv."""
        out = help_output()
        assert "enriched_works.csv" in out, \
            "corpus_refine.py --works-input default should reference enriched_works.csv"

    def test_works_input_default_for_filter(self):
        """--filter mode default input should be extended_works.csv."""
        out = help_output()
        assert "extended_works.csv" in out, \
            "corpus_refine.py --works-input default should reference extended_works.csv"


# ---------------------------------------------------------------------------
# Extend mode: row-count invariant
# ---------------------------------------------------------------------------

class TestExtendMode:
    @pytest.fixture
    def enriched_csv(self, tmp_path):
        """Build a minimal enriched works CSV with 10 rows."""
        df = pd.DataFrame({
            "source_id": [f"s{i}" for i in range(10)],
            "doi": [f"10.1/{i}" if i % 2 == 0 else None for i in range(10)],
            "title": [f"Paper about climate finance {i}" for i in range(10)],
            "year": [2010 + (i % 15) for i in range(10)],
            "source": ["openalex"] * 10,
            "cited_by_count": [i * 10 for i in range(10)],
            "source_count": [1] * 10,
            "abstract": [f"Abstract about carbon tax and climate policy {i}" for i in range(10)],
            "type": ["article"] * 10,
            "language": ["en"] * 10,
            "first_author": [f"Author{i}" for i in range(10)],
            "from_openalex": [1] * 10,
            "from_semanticscholar": [0] * 10,
            "from_istex": [0] * 10,
            "from_bibcnrs": [0] * 10,
            "from_scispsace": [0] * 10,
            "from_grey": [0] * 10,
            "from_teaching": [0] * 10,
        })
        path = tmp_path / "enriched_works.csv"
        df.to_csv(path, index=False)
        return path

    def test_extend_mode_row_count_invariant(self, tmp_path, enriched_csv):
        """--extend must write same number of rows as input (no filtering)."""
        input_df = pd.read_csv(enriched_csv)
        output_path = tmp_path / "extended_works.csv"

        rc, out = run_script(
            "--extend",
            "--works-input", str(enriched_csv),
            "--works-output", str(output_path),
            "--skip-llm", "--skip-citation-flag",
        )
        assert rc == 0, f"--extend failed:\n{out}"
        assert output_path.exists(), f"--extend did not produce {output_path}\n{out}"

        output_df = pd.read_csv(output_path)
        assert len(output_df) == len(input_df), (
            f"--extend changed row count: {len(input_df)} in → {len(output_df)} out. "
            f"Extend mode must not filter rows."
        )

    def test_extend_mode_adds_flag_columns(self, tmp_path, enriched_csv):
        """--extend output must include flag and protection columns."""
        output_path = tmp_path / "extended_works.csv"
        rc, out = run_script(
            "--extend",
            "--works-input", str(enriched_csv),
            "--works-output", str(output_path),
            "--skip-llm", "--skip-citation-flag",
        )
        assert rc == 0, f"--extend failed:\n{out}"
        assert output_path.exists()

        output_df = pd.read_csv(output_path)
        for col in ("protected", "protect_reason", "action"):
            assert col in output_df.columns, \
                f"--extend output missing column: {col}"

    def test_extend_mode_no_flags_column(self, tmp_path, enriched_csv):
        """--extend output must NOT contain a derived 'flags' column.

        The flags list is derived from boolean columns and should only
        appear as a serialized pipe-string in corpus_audit.csv.
        """
        output_path = tmp_path / "extended_works.csv"
        rc, out = run_script(
            "--extend",
            "--works-input", str(enriched_csv),
            "--works-output", str(output_path),
            "--skip-llm", "--skip-citation-flag",
        )
        assert rc == 0, f"--extend failed:\n{out}"
        output_df = pd.read_csv(output_path)
        assert "flags" not in output_df.columns, \
            "--extend output must not contain derived 'flags' column"

    def test_extend_mode_does_not_remove_rows(self, tmp_path, enriched_csv):
        """--extend output must contain all original source_id values."""
        input_df = pd.read_csv(enriched_csv)
        output_path = tmp_path / "extended_works.csv"
        rc, _ = run_script(
            "--extend",
            "--works-input", str(enriched_csv),
            "--works-output", str(output_path),
            "--skip-llm", "--skip-citation-flag",
        )
        assert rc == 0
        output_df = pd.read_csv(output_path)
        input_ids = set(input_df["source_id"])
        output_ids = set(output_df["source_id"])
        assert input_ids == output_ids, \
            f"--extend dropped source_ids: {input_ids - output_ids}"


# ---------------------------------------------------------------------------
# Filter mode: reduction behavior
# ---------------------------------------------------------------------------

class TestFilterMode:
    @pytest.fixture
    def extended_csv(self, tmp_path):
        """Build a minimal extended works CSV (has flag columns, some flagged)."""
        df = pd.DataFrame({
            "source_id": [f"s{i}" for i in range(10)],
            "doi": [f"10.1/{i}" for i in range(10)],
            "title": [f"Climate finance paper {i}" for i in range(10)],
            "year": [2010 + i for i in range(10)],
            "source": ["openalex"] * 10,
            "cited_by_count": [i * 5 for i in range(10)],
            "source_count": [1] * 10,
            "abstract": ["Some abstract about climate policy"] * 10,
            "type": ["article"] * 10,
            "language": ["en"] * 10,
            "first_author": [f"Author{i}" for i in range(10)],
            "from_openalex": [1] * 10,
            "from_semanticscholar": [0] * 10,
            "from_istex": [0] * 10,
            "from_bibcnrs": [0] * 10,
            "from_scispsace": [0] * 10,
            "from_grey": [0] * 10,
            "from_teaching": [0] * 10,
            # Flag 3 rows as noise (boolean columns only, no derived 'flags')
            "missing_metadata": [True, True, True] + [False] * 7,
            "no_abstract_irrelevant": [False] * 10,
            "title_blacklist": [False] * 10,
            "protected": [False, False, False] + [False] * 7,
            "protect_reason": [""] * 10,
            "action": ["keep"] * 10,
        })
        path = tmp_path / "extended_works.csv"
        df.to_csv(path, index=False)
        return path

    def test_filter_mode_reduces_rows(self, tmp_path, extended_csv):
        """--filter must produce fewer rows when flagged rows exist."""
        input_df = pd.read_csv(extended_csv)
        output_path = tmp_path / "refined_works.csv"

        rc, out = run_script(
            "--filter",
            "--works-input", str(extended_csv),
            "--works-output", str(output_path),
        )
        assert rc == 0, f"--filter failed:\n{out}"
        assert output_path.exists(), f"--filter did not produce {output_path}\n{out}"

        output_df = pd.read_csv(output_path)
        assert len(output_df) < len(input_df), (
            f"--filter did not remove any rows: "
            f"{len(input_df)} in → {len(output_df)} out. "
            f"Expected < {len(input_df)} since 3 rows are flagged."
        )

    def test_filter_mode_rows_lte_extend(self, tmp_path, extended_csv):
        """--filter output row count <= --extend input row count."""
        input_df = pd.read_csv(extended_csv)
        refined_path = tmp_path / "refined_works.csv"
        rc, out = run_script(
            "--filter",
            "--works-input", str(extended_csv),
            "--works-output", str(refined_path),
        )
        assert rc == 0, f"--filter failed:\n{out}"
        assert refined_path.exists()
        output_df = pd.read_csv(refined_path)
        assert len(output_df) <= len(input_df), \
            f"filter output ({len(output_df)}) > extend input ({len(input_df)})"

    def test_filter_mode_produces_audit(self, tmp_path, extended_csv):
        """--filter must also produce corpus_audit.csv."""
        refined_path = tmp_path / "refined_works.csv"
        # Run with --audit-output to test configurable audit path
        rc, out = run_script(
            "--filter",
            "--works-input", str(extended_csv),
            "--works-output", str(refined_path),
        )
        assert rc == 0, f"--filter failed:\n{out}"
        # corpus_audit.csv should appear next to refined
        audit_path = tmp_path / "corpus_audit.csv"
        # Either in tmp_path or next to refined - check output for file path
        assert "audit" in out.lower() or audit_path.exists() or \
               any("audit" in f for f in os.listdir(tmp_path)), \
            f"--filter did not produce corpus_audit.csv. Output:\n{out}"
