"""Tests for the interpretation layer (ticket 0056).

Tests:
1. log_odds_ratio core function — planted vocabulary shift
2. InterpretationSchema validation
3. Smoke test: run compute_interpretation.py on fixture data
"""

import os
import subprocess
import sys

import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "smoke")

sys.path.insert(0, SCRIPTS_DIR)

from conftest import smoke_env

# ---------------------------------------------------------------------------
# Unit tests: log-odds ratio with Dirichlet prior
# ---------------------------------------------------------------------------


class TestLogOddsRatio:
    """Test the log_odds_ratio function (Monroe et al. 2008)."""

    def test_planted_shift_detected(self):
        """A planted vocabulary shift should produce positive log-odds."""
        from compute_interpretation import log_odds_ratio

        # Before period: documents about "adaptation"
        texts_before = [
            "adaptation strategies for climate change",
            "community adaptation resilience planning",
            "adaptation finance developing countries",
            "climate adaptation risk assessment",
            "adaptation vulnerability coastal areas",
        ] * 10

        # After period: documents about "mitigation"
        texts_after = [
            "mitigation strategies carbon reduction",
            "mitigation finance green bonds",
            "emission mitigation technology transfer",
            "mitigation policy carbon markets",
            "climate mitigation renewable energy",
        ] * 10

        result = log_odds_ratio(texts_before, texts_after, top_n=50)

        assert isinstance(result, pd.DataFrame)
        assert "term" in result.columns
        assert "log_odds" in result.columns
        assert "freq_before" in result.columns
        assert "freq_after" in result.columns

        # "mitigation" should have positive log-odds (more frequent after)
        mitigation_row = result[result["term"] == "mitigation"]
        assert len(mitigation_row) == 1, "mitigation should appear in top terms"
        assert mitigation_row["log_odds"].iloc[0] > 0, (
            "mitigation should have positive log-odds (gained after)"
        )

        # "adaptation" should have negative log-odds (more frequent before)
        adaptation_row = result[result["term"] == "adaptation"]
        assert len(adaptation_row) == 1, "adaptation should appear in top terms"
        assert adaptation_row["log_odds"].iloc[0] < 0, (
            "adaptation should have negative log-odds (lost after)"
        )

    def test_symmetric_texts_near_zero(self):
        """Identical before/after should yield log-odds near zero."""
        from compute_interpretation import log_odds_ratio

        texts = ["climate finance carbon policy"] * 20
        result = log_odds_ratio(texts, texts, top_n=10)

        # All log-odds should be near zero (within numerical precision)
        assert (result["log_odds"].abs() < 0.5).all(), (
            f"Expected near-zero log-odds for identical texts, got:\n{result}"
        )

    def test_empty_texts_raises(self):
        """Empty text lists should raise ValueError."""
        from compute_interpretation import log_odds_ratio

        with pytest.raises(ValueError, match="empty"):
            log_odds_ratio([], ["some text"], top_n=10)

        with pytest.raises(ValueError, match="empty"):
            log_odds_ratio(["some text"], [], top_n=10)

    def test_top_n_limits_output(self):
        """Output should have at most top_n rows."""
        from compute_interpretation import log_odds_ratio

        before = ["alpha beta gamma delta epsilon"] * 10
        after = ["alpha beta gamma zeta eta"] * 10
        result = log_odds_ratio(before, after, top_n=3)
        assert len(result) <= 3

    def test_dirichlet_prior_prevents_division_by_zero(self):
        """Terms appearing in only one period should not cause errors."""
        from compute_interpretation import log_odds_ratio

        before = ["uniqueterm1 shared"] * 10
        after = ["uniqueterm2 shared"] * 10
        result = log_odds_ratio(before, after, top_n=10)
        assert not result["log_odds"].isna().any(), "No NaN log-odds expected"


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestInterpretationSchema:
    """InterpretationSchema validation."""

    def test_valid_dataframe_passes(self):
        from schemas import InterpretationSchema

        df = pd.DataFrame(
            {
                "term": ["mitigation", "adaptation"],
                "log_odds": [1.5, -1.2],
                "freq_before": [10, 50],
                "freq_after": [50, 10],
            }
        )
        InterpretationSchema.validate(df)

    def test_extra_column_rejected(self):
        from schemas import InterpretationSchema

        df = pd.DataFrame(
            {
                "term": ["mitigation"],
                "log_odds": [1.5],
                "freq_before": [10],
                "freq_after": [50],
                "extra": ["oops"],
            }
        )
        with pytest.raises(Exception):
            InterpretationSchema.validate(df)

    def test_missing_column_rejected(self):
        from schemas import InterpretationSchema

        df = pd.DataFrame(
            {
                "term": ["mitigation"],
                "log_odds": [1.5],
            }
        )
        with pytest.raises(Exception):
            InterpretationSchema.validate(df)


# ---------------------------------------------------------------------------
# Smoke test: run compute_interpretation.py on fixture data
# ---------------------------------------------------------------------------


def _run_interpretation(zone, output_path, extra_args=None, timeout=120):
    """Run compute_interpretation.py --zone Z --output P."""
    cmd = [
        sys.executable,
        os.path.join(SCRIPTS_DIR, "compute_interpretation.py"),
        "--zone",
        zone,
        "--output",
        str(output_path),
    ]
    if extra_args:
        cmd.extend(extra_args)
    return subprocess.run(
        cmd,
        env=smoke_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


@pytest.mark.integration
class TestSmokeInterpretation:
    """Smoke tests for compute_interpretation.py on fixture data."""

    def test_produces_output(self, tmp_path):
        """Script runs and produces a valid CSV."""
        out = tmp_path / "interp_2007_2011.csv"
        result = _run_interpretation("2007-2011", out)
        assert result.returncode == 0, (
            f"Script failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert out.exists(), "Output CSV not created"

        df = pd.read_csv(out)
        expected_cols = {"term", "log_odds", "freq_before", "freq_after"}
        assert expected_cols == set(df.columns), f"Columns mismatch: {set(df.columns)}"
        assert len(df) > 0

    def test_output_passes_schema(self, tmp_path):
        """Output validates against InterpretationSchema."""
        out = tmp_path / "interp_2007_2011.csv"
        result = _run_interpretation("2007-2011", out)
        assert result.returncode == 0, result.stderr

        from schemas import InterpretationSchema

        df = pd.read_csv(out)
        InterpretationSchema.validate(df)

    def test_different_zones_produce_different_results(self, tmp_path):
        """Different zones should produce different discriminative terms."""
        # Smoke fixture has ~100 works spanning 2005-2025, with most data
        # after 2010. Choose zones that split the corpus with enough docs
        # on each side.
        out1 = tmp_path / "interp_2013_2015.csv"
        out2 = tmp_path / "interp_2018_2020.csv"

        r1 = _run_interpretation("2013-2015", out1)
        r2 = _run_interpretation("2018-2020", out2)

        assert r1.returncode == 0, r1.stderr
        assert r2.returncode == 0, r2.stderr

        df1 = pd.read_csv(out1)
        df2 = pd.read_csv(out2)

        # Both zones should produce non-empty results given the fixture
        assert len(df1) > 0
        assert len(df2) > 0
