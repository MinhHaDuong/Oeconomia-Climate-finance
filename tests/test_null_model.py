"""Tests for the permutation Z-score null model (tickets 0055, 0061).

Tests:
1. permutation_test core function — null distribution and planted breaks
2. NullModelSchema validation
3. Smoke test: run compute_null_model.py on fixture data
4. Output reuses year/window combos from existing tab_div_{method}.csv
5. Shared-rng contamination regression (ticket 0061)
"""

import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "smoke")

sys.path.insert(0, SCRIPTS_DIR)

from conftest import smoke_env

# ---------------------------------------------------------------------------
# Helper: run compute_null_model.py
# ---------------------------------------------------------------------------


def _run_null_model(method, output_path, extra_args=None, timeout=300):
    """Run compute_null_model.py --method M --output P."""
    cmd = [
        sys.executable,
        os.path.join(SCRIPTS_DIR, "compute_null_model.py"),
        "--method",
        method,
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


# ---------------------------------------------------------------------------
# Unit tests: permutation_test core function
# ---------------------------------------------------------------------------


class TestPermutationTest:
    """Test the permutation_test function directly."""

    def test_z_scores_null_distribution(self):
        """Under H0 (same distribution), Z-scores should be ~N(0,1).

        We generate many (year, window) pairs from the same distribution
        and check the resulting Z-scores are not systematically extreme.
        """
        from compute_null_model import permutation_test

        rng = np.random.RandomState(42)
        z_scores = []
        for _ in range(30):
            X = rng.randn(50, 10)
            Y = rng.randn(50, 10)  # same distribution

            def statistic_fn(a, b):
                return float(np.mean(np.linalg.norm(a - b.mean(axis=0), axis=1)))

            _, _, _, z, _ = permutation_test(X, Y, statistic_fn, n_perm=200, rng=rng)
            z_scores.append(z)

        z_scores = np.array(z_scores)
        # Under H0, Z-scores should not be systematically extreme
        # Mean should be near 0, and most |z| < 3
        assert abs(np.mean(z_scores)) < 2.0, (
            f"Mean Z-score under null = {np.mean(z_scores):.2f}, expected ~0"
        )
        fraction_extreme = np.mean(np.abs(z_scores) > 3.0)
        assert fraction_extreme < 0.3, (
            f"Too many extreme Z-scores under null: {fraction_extreme:.1%}"
        )

    def test_z_scores_detect_planted_break(self):
        """Z > 2 at a planted distribution shift."""
        from compute_null_model import permutation_test

        rng = np.random.RandomState(42)
        # Before: N(0, I), After: N(3, I)  -- large shift
        X_before = rng.randn(80, 10)
        Y_after = rng.randn(80, 10) + 3.0

        def energy_like(a, b):
            from scipy.spatial.distance import cdist

            dXY = cdist(a, b).mean()
            dXX = cdist(a, a).mean()
            dYY = cdist(b, b).mean()
            return 2.0 * dXY - dXX - dYY

        _, _, _, z, p = permutation_test(
            X_before, Y_after, energy_like, n_perm=200, rng=rng
        )
        assert z > 2.0, f"Expected Z > 2 for planted break, got Z={z:.2f}"
        assert p < 0.05, f"Expected p < 0.05, got p={p:.3f}"

    def test_permutation_test_reproducible(self):
        """Same seed gives same Z-score."""
        from compute_null_model import permutation_test

        X = np.random.RandomState(10).randn(30, 5)
        Y = np.random.RandomState(20).randn(30, 5) + 1.0

        def stat(a, b):
            return float(np.linalg.norm(a.mean(axis=0) - b.mean(axis=0)))

        rng1 = np.random.RandomState(42)
        _, _, _, z1, _ = permutation_test(X, Y, stat, n_perm=100, rng=rng1)

        rng2 = np.random.RandomState(42)
        _, _, _, z2, _ = permutation_test(X, Y, stat, n_perm=100, rng=rng2)

        assert z1 == z2, f"Not reproducible: {z1} != {z2}"


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestNullModelSchema:
    """NullModelSchema validation."""

    def test_valid_dataframe_passes(self):
        from schemas import NullModelSchema

        df = pd.DataFrame(
            {
                "year": [2010, 2011],
                "window": ["3", "3"],
                "observed": [0.5, 0.6],
                "null_mean": [0.3, 0.35],
                "null_std": [0.1, 0.12],
                "z_score": [2.0, 2.08],
                "p_value": [0.01, 0.02],
            }
        )
        NullModelSchema.validate(df)

    def test_extra_column_rejected(self):
        from schemas import NullModelSchema

        df = pd.DataFrame(
            {
                "year": [2010],
                "window": ["3"],
                "observed": [0.5],
                "null_mean": [0.3],
                "null_std": [0.1],
                "z_score": [2.0],
                "p_value": [0.01],
                "extra": ["oops"],
            }
        )
        with pytest.raises(Exception):
            NullModelSchema.validate(df)

    def test_nullable_fields(self):
        from schemas import NullModelSchema

        df = pd.DataFrame(
            {
                "year": [2010],
                "window": ["3"],
                "observed": [np.nan],
                "null_mean": [np.nan],
                "null_std": [np.nan],
                "z_score": [np.nan],
                "p_value": [np.nan],
            }
        )
        NullModelSchema.validate(df)

    def test_coercion_works(self):
        from schemas import NullModelSchema

        df = pd.DataFrame(
            {
                "year": ["2010"],
                "window": ["3"],
                "observed": ["0.5"],
                "null_mean": ["0.3"],
                "null_std": ["0.1"],
                "z_score": ["2.0"],
                "p_value": ["0.01"],
            }
        )
        validated = NullModelSchema.validate(df)
        assert validated["year"].dtype in (int, "int64")


# ---------------------------------------------------------------------------
# Smoke tests: run dispatcher on fixture data
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestSmokeNullModel:
    """Smoke tests for compute_null_model.py on fixture data."""

    @pytest.mark.parametrize("method", ["S2_energy", "L1"])
    def test_compute_produces_output(self, method, tmp_path):
        """Script runs and produces a valid CSV."""
        # First, generate the divergence CSV that the null model reads
        from conftest import run_compute

        div_out = tmp_path / f"tab_div_{method}.csv"
        result = run_compute(method, div_out)
        assert result.returncode == 0, f"Divergence {method} failed: {result.stderr}"

        # Now run the null model
        null_out = tmp_path / f"tab_null_{method}.csv"
        result = _run_null_model(
            method,
            null_out,
            extra_args=["--div-csv", str(div_out)],
        )
        assert result.returncode == 0, (
            f"Null model {method} failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert null_out.exists(), f"Output CSV not created for {method}"

        df = pd.read_csv(null_out)
        expected_cols = {
            "year",
            "window",
            "observed",
            "null_mean",
            "null_std",
            "z_score",
            "p_value",
        }
        assert expected_cols == set(df.columns), f"Columns mismatch: {set(df.columns)}"
        assert len(df) > 0

    @pytest.mark.parametrize("method", ["S2_energy", "L1"])
    def test_output_passes_schema(self, method, tmp_path):
        """Output validates against NullModelSchema."""
        from conftest import run_compute

        div_out = tmp_path / f"tab_div_{method}.csv"
        run_compute(method, div_out)

        null_out = tmp_path / f"tab_null_{method}.csv"
        result = _run_null_model(
            method,
            null_out,
            extra_args=["--div-csv", str(div_out)],
        )
        assert result.returncode == 0, result.stderr

        from schemas import NullModelSchema

        df = pd.read_csv(null_out)
        NullModelSchema.validate(df)


@pytest.mark.integration
class TestNullModelReusesYearWindow:
    """Null model should reuse year/window combos from tab_div_{method}.csv."""

    def test_year_window_match(self, tmp_path):
        """Year/window combos in null output match those in divergence CSV."""
        from conftest import run_compute

        method = "S2_energy"
        div_out = tmp_path / f"tab_div_{method}.csv"
        run_compute(method, div_out)

        null_out = tmp_path / f"tab_null_{method}.csv"
        result = _run_null_model(
            method,
            null_out,
            extra_args=["--div-csv", str(div_out)],
        )
        assert result.returncode == 0, result.stderr

        div_df = pd.read_csv(div_out)
        null_df = pd.read_csv(null_out)

        # The null model may only cover the "default" hyperparam rows for S2
        # but year/window pairs should be a subset
        div_pairs = set(zip(div_df["year"], div_df["window"].astype(str)))
        null_pairs = set(zip(null_df["year"], null_df["window"].astype(str)))

        assert null_pairs.issubset(div_pairs), (
            f"Null model has year/window pairs not in divergence CSV: "
            f"{null_pairs - div_pairs}"
        )
        # And the null model should cover most pairs
        assert len(null_pairs) >= len(div_pairs) * 0.5, (
            f"Null model covers too few pairs: {len(null_pairs)} / {len(div_pairs)}"
        )


# ---------------------------------------------------------------------------
# Shared-rng contamination regression tests (ticket 0061)
# ---------------------------------------------------------------------------


def _make_synthetic_data(n_years=20, papers_per_year=60, emb_dim=10, seed=99):
    """Build a synthetic (df, emb) for testing null-model rng isolation.

    Returns a DataFrame with 'year' and 'cited_by_count' columns, plus an
    embedding matrix aligned to df.index.  Years span [2000, 2000+n_years).
    """
    rng = np.random.RandomState(seed)
    years = np.repeat(np.arange(2000, 2000 + n_years), papers_per_year)
    df = pd.DataFrame({"year": years, "cited_by_count": 10})
    emb = rng.randn(len(df), emb_dim).astype(np.float32)
    return df, emb


class TestSharedRngContamination:
    """Ticket 0061 — per-window rng isolation.

    The bug: _run_semantic_permutations and _run_lexical_permutations used a
    single rng for both subsampling and permutation across all (year, window)
    iterations.  Adding or removing earlier windows changed the rng state
    entering later windows, making results non-reproducible.

    The fix: derive per-window seeds so each (year, window) gets independent
    rng instances for subsampling and permutation.
    """

    def test_single_window_reproducible_regardless_of_prior_windows_semantic(self):
        """Semantic: z-score for (year=2005, w=3) must be identical whether
        we process it alone or after (year=2003, w=3).
        """
        from unittest.mock import patch

        from compute_null_model import _run_semantic_permutations

        df, emb = _make_synthetic_data(n_years=20, papers_per_year=60)

        # Minimal config matching what _run_semantic_permutations reads
        cfg = {
            "divergence": {
                "windows": [3],
                "max_subsample": 40,  # Force subsampling (60 > 40)
                "equal_n": False,
                "random_seed": 42,
                "permutation": {"n_perm": 50},
                "min_papers_fraction": 0.001,
                "min_papers_floor": 5,
            }
        }

        # Run 1: only year=2005
        div_df_single = pd.DataFrame({"year": [2005], "window": [3]})

        with patch("_divergence_semantic.load_semantic_data", return_value=(df, emb)):
            result_single = _run_semantic_permutations("S4_frechet", div_df_single, cfg)

        z_single = result_single.loc[result_single["year"] == 2005, "z_score"].iloc[0]

        # Run 2: year=2003 first, then year=2005
        div_df_double = pd.DataFrame({"year": [2003, 2005], "window": [3, 3]})

        with patch("_divergence_semantic.load_semantic_data", return_value=(df, emb)):
            result_double = _run_semantic_permutations("S4_frechet", div_df_double, cfg)

        z_double = result_double.loc[result_double["year"] == 2005, "z_score"].iloc[0]

        assert z_single == z_double, (
            f"Shared-rng contamination: z(2005) alone={z_single:.6f} "
            f"vs after 2003={z_double:.6f}"
        )

    def test_single_window_reproducible_regardless_of_prior_windows_lexical(self):
        """Lexical: z-score for (year=2005, w=3) must be identical whether
        we process it alone or after (year=2003, w=3).
        """
        from unittest.mock import patch

        from compute_null_model import _run_lexical_permutations

        # Build synthetic text data
        rng = np.random.RandomState(77)
        n_years = 20
        papers_per_year = 60
        vocab = [
            "climate",
            "finance",
            "carbon",
            "energy",
            "policy",
            "market",
            "green",
            "bond",
            "risk",
            "fund",
            "investment",
            "emissions",
            "trading",
            "bank",
            "tax",
        ]
        years = np.repeat(np.arange(2000, 2000 + n_years), papers_per_year)
        abstracts = []
        for _ in range(len(years)):
            n_words = rng.randint(10, 30)
            words = rng.choice(vocab, n_words, replace=True)
            abstracts.append(" ".join(words))
        df = pd.DataFrame({"year": years, "abstract": abstracts})

        cfg = {
            "divergence": {
                "windows": [3],
                "equal_n": True,  # Force subsample_equal_n
                "random_seed": 42,
                "permutation": {"n_perm": 50},
                "min_papers_fraction": 0.001,
                "min_papers_floor": 5,
                "lexical": {
                    "tfidf_max_features": 100,
                    "tfidf_min_df": 2,
                },
            }
        }

        div_df_single = pd.DataFrame({"year": [2005], "window": [3]})
        div_df_double = pd.DataFrame({"year": [2003, 2005], "window": [3, 3]})

        with patch("_divergence_lexical.load_lexical_data", return_value=df):
            result_single = _run_lexical_permutations("L1", div_df_single, cfg)

        with patch("_divergence_lexical.load_lexical_data", return_value=df):
            result_double = _run_lexical_permutations("L1", div_df_double, cfg)

        z_single = result_single.loc[result_single["year"] == 2005, "z_score"].iloc[0]
        z_double = result_double.loc[result_double["year"] == 2005, "z_score"].iloc[0]

        assert z_single == z_double, (
            f"Shared-rng contamination (lexical): z(2005) alone={z_single:.6f} "
            f"vs after 2003={z_double:.6f}"
        )
