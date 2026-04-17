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

    def test_null_std_zero_returns_z_zero(self):
        """When null_std == 0 (constant statistic), z_score should be 0.0.

        This triggers when all permutations produce the same statistic,
        e.g., identical distributions with a symmetric statistic.
        """
        from compute_null_model import permutation_test

        rng = np.random.RandomState(42)

        # Use a constant statistic function that always returns the same value
        # regardless of input -- this guarantees null_std == 0.
        def constant_statistic(a, b):
            return 1.0

        X = rng.randn(20, 5)
        Y = rng.randn(20, 5)

        observed, null_mean, null_std, z, p = permutation_test(
            X, Y, constant_statistic, n_perm=50, rng=rng
        )
        assert null_std == 0.0, f"Expected null_std=0, got {null_std}"
        assert z == 0.0, f"Expected z=0.0 when null_std=0, got {z}"
        assert observed == 1.0

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


class TestCitationNullModel:
    """Tests for citation channel null model (ticket 0050)."""

    def test_citation_channel_supported(self):
        """compute_null_model should accept citation channel."""
        from compute_null_model import SUPPORTED_CHANNELS

        assert "citation" in SUPPORTED_CHANNELS

    def test_run_citation_permutations_exists(self):
        """_run_citation_permutations should be importable."""
        from compute_null_model import _run_citation_permutations

        assert callable(_run_citation_permutations)

    def test_citation_null_z_score_schema(self):
        """Citation null model output matches NullModelSchema."""
        from unittest.mock import patch

        from compute_null_model import _run_citation_permutations
        from schemas import NullModelSchema

        # Build minimal synthetic data
        rng = np.random.RandomState(42)
        n_years = 15
        papers_per_year = 20
        years = np.repeat(np.arange(2000, 2000 + n_years), papers_per_year)
        dois = [f"10.1000/test.{i}" for i in range(len(years))]
        works = pd.DataFrame({"doi": dois, "year": years, "cited_by_count": 10})

        # Build some citation edges
        edges = []
        doi_list = list(works["doi"])
        doi_years = dict(zip(works["doi"], works["year"]))
        for _ in range(len(doi_list) * 2):
            src = rng.choice(doi_list)
            ref = rng.choice(doi_list)
            if src != ref:
                edges.append(
                    {
                        "source_doi": src,
                        "ref_doi": ref,
                        "source_year": doi_years[src],
                    }
                )
        internal_edges = pd.DataFrame(edges).drop_duplicates(
            subset=["source_doi", "ref_doi"]
        )

        cfg = {
            "divergence": {
                "windows": [3],
                "random_seed": 42,
                "permutation": {"n_perm": 20},
                "min_papers_fraction": 0.001,
                "min_papers_floor": 5,
                "citation": {
                    "G9_community": {"resolution": 1.0},
                },
            }
        }

        div_df = pd.DataFrame({"year": [2005, 2007], "window": [3, 3]})

        with patch(
            "_divergence_citation.load_citation_data",
            return_value=(works, None, internal_edges),
        ):
            result = _run_citation_permutations("G9_community", div_df, cfg)

        # Schema validation
        NullModelSchema.validate(result)

        # Check expected columns
        expected_cols = {
            "year",
            "window",
            "observed",
            "null_mean",
            "null_std",
            "z_score",
            "p_value",
        }
        assert set(result.columns) == expected_cols
        assert len(result) == 2  # one row per (year, window) pair

    def test_citation_null_detects_planted_break(self):
        """Community null model should detect a planted structural break.

        We create two disconnected clusters that map cleanly to before/after,
        so the observed JS should be high and z-score should be significant.
        """
        from unittest.mock import patch

        from compute_null_model import _run_citation_permutations

        # Cluster A: years 2000-2004, Cluster B: years 2005-2009
        # Edges only within clusters => community structure aligns with time
        rng = np.random.RandomState(123)
        dois_a = [f"10.1000/a.{i}" for i in range(60)]
        dois_b = [f"10.1000/b.{i}" for i in range(60)]
        years_a = rng.choice(range(2000, 2005), size=60)
        years_b = rng.choice(range(2005, 2010), size=60)

        works = pd.DataFrame(
            {
                "doi": dois_a + dois_b,
                "year": list(years_a) + list(years_b),
                "cited_by_count": 10,
            }
        )

        # Edges only within each cluster (strong community structure)
        edges = []
        for _ in range(300):
            src = rng.choice(dois_a)
            ref = rng.choice(dois_a)
            if src != ref:
                edges.append({"source_doi": src, "ref_doi": ref})
        for _ in range(300):
            src = rng.choice(dois_b)
            ref = rng.choice(dois_b)
            if src != ref:
                edges.append({"source_doi": src, "ref_doi": ref})

        doi_years = dict(zip(works["doi"], works["year"]))
        for e in edges:
            e["source_year"] = doi_years[e["source_doi"]]
        internal_edges = pd.DataFrame(edges).drop_duplicates(
            subset=["source_doi", "ref_doi"]
        )

        cfg = {
            "divergence": {
                "windows": [3],
                "random_seed": 42,
                "permutation": {"n_perm": 99},
                "min_papers_fraction": 0.001,
                "min_papers_floor": 3,
                "citation": {
                    "G9_community": {"resolution": 1.0},
                },
            }
        }

        # Test at the boundary year (2004) where before=2001-2004, after=2005-2008
        div_df = pd.DataFrame({"year": [2004], "window": [3]})

        with patch(
            "_divergence_citation.load_citation_data",
            return_value=(works, None, internal_edges),
        ):
            result = _run_citation_permutations("G9_community", div_df, cfg)

        z = result["z_score"].iloc[0]
        p = result["p_value"].iloc[0]
        # With two disconnected clusters, the break should be highly significant
        assert z > 1.5, f"Expected significant z-score for planted break, got z={z:.2f}"
        assert p < 0.1, f"Expected small p-value, got p={p:.3f}"


class TestG2SpectralNullModel:
    """Tests for G2_spectral citation channel null model (ticket 0069)."""

    def test_citation_dispatcher_handles_g2(self):
        """_run_citation_permutations should accept G2_spectral, not just G9."""
        from unittest.mock import patch

        from compute_null_model import _run_citation_permutations
        from schemas import NullModelSchema

        rng = np.random.RandomState(42)
        n_years = 15
        papers_per_year = 20
        years = np.repeat(np.arange(2000, 2000 + n_years), papers_per_year)
        dois = [f"10.1000/test.{i}" for i in range(len(years))]
        works = pd.DataFrame({"doi": dois, "year": years, "cited_by_count": 10})

        edges = []
        doi_list = list(works["doi"])
        doi_years = dict(zip(works["doi"], works["year"]))
        for _ in range(len(doi_list) * 3):
            src = rng.choice(doi_list)
            ref = rng.choice(doi_list)
            if src != ref:
                edges.append(
                    {
                        "source_doi": src,
                        "ref_doi": ref,
                        "source_year": doi_years[src],
                    }
                )
        internal_edges = pd.DataFrame(edges).drop_duplicates(
            subset=["source_doi", "ref_doi"]
        )

        cfg = {
            "divergence": {
                "windows": [3],
                "random_seed": 42,
                "permutation": {"n_perm": 20},
                "min_papers_fraction": 0.001,
                "min_papers_floor": 5,
                "citation": {},
            }
        }

        div_df = pd.DataFrame({"year": [2005, 2007], "window": [3, 3]})

        with patch(
            "_divergence_citation.load_citation_data",
            return_value=(works, None, internal_edges),
        ):
            result = _run_citation_permutations("G2_spectral", div_df, cfg)

        NullModelSchema.validate(result)
        expected_cols = {
            "year",
            "window",
            "observed",
            "null_mean",
            "null_std",
            "z_score",
            "p_value",
        }
        assert set(result.columns) == expected_cols
        assert len(result) == 2

        # Observed must match the G2_spectral statistic (not the G9 JS).
        from _citation_methods import _spectral_gap
        from _divergence_citation import _sliding_window_graph

        for _, row in result.iterrows():
            y = int(row["year"])
            w = int(row["window"])
            G_before = _sliding_window_graph(works, internal_edges, y, w, "before")
            G_after = _sliding_window_graph(works, internal_edges, y, w, "after")
            gap_b = _spectral_gap(G_before)
            gap_a = _spectral_gap(G_after)
            if np.isnan(gap_b) or np.isnan(gap_a):
                expected = np.nan
            else:
                expected = abs(gap_a - gap_b)
            obs = row["observed"]
            if np.isnan(expected):
                assert np.isnan(obs), f"year={y} expected NaN, got {obs}"
            else:
                assert abs(obs - expected) < 1e-9, (
                    f"year={y} G2 observed={obs} but spectral diff={expected}"
                )


@pytest.mark.integration
class TestSmokeNullModel:
    """Smoke tests for compute_null_model.py on fixture data."""

    @pytest.mark.parametrize(
        "method", ["S2_energy", "L1", "G9_community", "G2_spectral"]
    )
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

    @pytest.mark.parametrize(
        "method", ["S2_energy", "L1", "G9_community", "G2_spectral"]
    )
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

    def test_single_window_reproducible_regardless_of_prior_windows_citation(self):
        """Citation: z-score for (year=2005, w=3) must be identical whether
        we process it alone or after (year=2003, w=3).
        """
        from unittest.mock import patch

        from compute_null_model import _run_citation_permutations

        # Build synthetic citation graph data
        rng = np.random.RandomState(77)
        n_years = 20
        papers_per_year = 30
        years = np.repeat(np.arange(2000, 2000 + n_years), papers_per_year)
        dois = [f"10.1000/test.{i}" for i in range(len(years))]
        works = pd.DataFrame({"doi": dois, "year": years, "cited_by_count": 10})

        # Build random internal edges (citation graph)
        edges = []
        doi_list = list(works["doi"])
        doi_years = dict(zip(works["doi"], works["year"]))
        for _ in range(len(doi_list) * 3):
            src = rng.choice(doi_list)
            ref = rng.choice(doi_list)
            if src != ref:
                edges.append(
                    {
                        "source_doi": src,
                        "ref_doi": ref,
                        "source_year": doi_years[src],
                    }
                )
        internal_edges = pd.DataFrame(edges).drop_duplicates(
            subset=["source_doi", "ref_doi"]
        )

        cfg = {
            "divergence": {
                "windows": [3],
                "random_seed": 42,
                "permutation": {"n_perm": 50},
                "min_papers_fraction": 0.001,
                "min_papers_floor": 5,
                "citation": {
                    "G9_community": {"resolution": 1.0},
                },
            }
        }

        div_df_single = pd.DataFrame({"year": [2005], "window": [3]})
        div_df_double = pd.DataFrame({"year": [2003, 2005], "window": [3, 3]})

        with patch(
            "_divergence_citation.load_citation_data",
            return_value=(works, None, internal_edges),
        ):
            result_single = _run_citation_permutations(
                "G9_community", div_df_single, cfg
            )

        with patch(
            "_divergence_citation.load_citation_data",
            return_value=(works, None, internal_edges),
        ):
            result_double = _run_citation_permutations(
                "G9_community", div_df_double, cfg
            )

        z_single = result_single.loc[result_single["year"] == 2005, "z_score"].iloc[0]
        z_double = result_double.loc[result_double["year"] == 2005, "z_score"].iloc[0]

        assert z_single == z_double, (
            f"Shared-rng contamination (citation): z(2005) alone={z_single:.6f} "
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


# ---------------------------------------------------------------------------
# Backend comparison tests (ticket 0042)
# ---------------------------------------------------------------------------


class TestBackendComparison:
    """Compare sequential, parallel-CPU, and GPU permutation backends.

    Each pair of backends should produce statistically consistent z-scores
    on the same synthetic data.  Sequential ↔ parallel-CPU should agree
    exactly (same algorithm, same RNG).  GPU uses different RNG sequences
    so we accept a tolerance on z-scores.
    """

    @staticmethod
    def _make_data(n_papers=60, n_years=15, emb_dim=10, seed=42):
        rng = np.random.RandomState(seed)
        years = np.repeat(np.arange(2000, 2000 + n_years), n_papers)
        df = pd.DataFrame({"year": years, "cited_by_count": 10})
        emb = rng.randn(len(df), emb_dim).astype(np.float32)
        return df, emb

    @staticmethod
    def _base_cfg(n_perm=50):
        return {
            "divergence": {
                "windows": [3],
                "max_subsample": 40,
                "equal_n": False,
                "random_seed": 42,
                "permutation": {"n_perm": n_perm},
                "min_papers_fraction": 0.001,
                "min_papers_floor": 5,
                "backend": "cpu",
            }
        }

    def test_sequential_vs_parallel_cpu_energy(self):
        """Parallel CPU must reproduce sequential results exactly."""
        from unittest.mock import patch

        from compute_null_model import _run_semantic_permutations

        df, emb = self._make_data()
        cfg = self._base_cfg()
        div_df = pd.DataFrame({"year": [2005, 2007], "window": [3, 3]})

        with patch("_divergence_semantic.load_semantic_data", return_value=(df, emb)):
            seq = _run_semantic_permutations("S2_energy", div_df, cfg, n_jobs=1)

        with patch("_divergence_semantic.load_semantic_data", return_value=(df, emb)):
            par = _run_semantic_permutations("S2_energy", div_df, cfg, n_jobs=2)

        for _, row_s in seq.iterrows():
            y = row_s["year"]
            row_p = par.loc[par["year"] == y].iloc[0]
            assert row_s["z_score"] == pytest.approx(row_p["z_score"], abs=1e-10), (
                f"year={y}: sequential z={row_s['z_score']:.6f} "
                f"!= parallel z={row_p['z_score']:.6f}"
            )

    def test_precomputed_lexical_vs_original(self):
        """Precomputed TF-IDF path must match the original sequential path.

        The precomputed path permutes row indices into a sparse matrix
        instead of re-transforming texts.  Since vectorizer.transform is
        deterministic and the RNG state is consumed identically (both use
        rng.permutation(N)), results should be very close.
        """
        from unittest.mock import patch

        from compute_null_model import (
            _make_lexical_statistic,
            _run_lexical_permutations,
            permutation_test,
        )
        from sklearn.feature_extraction.text import TfidfVectorizer

        # Build synthetic text data
        rng = np.random.RandomState(77)
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
        ]
        n_years, ppyr = 15, 40
        years = np.repeat(np.arange(2000, 2000 + n_years), ppyr)
        abstracts = [
            " ".join(rng.choice(vocab, rng.randint(10, 30), replace=True))
            for _ in range(len(years))
        ]
        df = pd.DataFrame({"year": years, "abstract": abstracts})

        cfg = {
            "divergence": {
                "windows": [3],
                "equal_n": False,
                "random_seed": 42,
                "permutation": {"n_perm": 50},
                "min_papers_fraction": 0.001,
                "min_papers_floor": 5,
                "lexical": {"tfidf_max_features": 100, "tfidf_min_df": 2},
            }
        }
        div_df = pd.DataFrame({"year": [2005], "window": [3]})

        # Run precomputed path (new default)
        with patch("_divergence_lexical.load_lexical_data", return_value=df):
            result_new = _run_lexical_permutations("L1", div_df, cfg)

        # Run original path manually for comparison
        vec = TfidfVectorizer(
            stop_words="english", max_features=100, min_df=2, sublinear_tf=True
        )
        vec.fit(df["abstract"].tolist())
        stat_fn = _make_lexical_statistic(vec)

        mask_b = (df["year"] >= 2005 - 3) & (df["year"] <= 2005)
        mask_a = (df["year"] >= 2006) & (df["year"] <= 2006 + 3)
        texts_b = df.loc[mask_b, "abstract"].tolist()
        texts_a = df.loc[mask_a, "abstract"].tolist()

        from _divergence_io import _make_window_rngs

        _, perm_rng = _make_window_rngs(42, 2005, 3)
        obs_orig, nm, ns, z_orig, p_orig = permutation_test(
            texts_b, texts_a, stat_fn, 50, perm_rng
        )

        z_new = result_new["z_score"].iloc[0]
        assert z_orig == pytest.approx(z_new, abs=0.5), (
            f"Precomputed vs original: z_orig={z_orig:.4f}, z_new={z_new:.4f}"
        )

    def test_gpu_energy_formula_correct(self):
        """GPU vectorized energy distance formula matches CPU reference.

        Uses a small synthetic example where we can verify against the
        sequential permutation_test() with exact same data.
        """
        try:
            import torch

            if not torch.cuda.is_available():
                pytest.skip("CUDA not available")
        except ImportError:
            pytest.skip("torch not installed")

        from _permutation_accel import gpu_energy_permutations
        from compute_null_model import permutation_test

        rng = np.random.RandomState(42)
        X = rng.randn(30, 10).astype(np.float32)
        Y = rng.randn(30, 10).astype(np.float32) + 1.5

        def energy_fn(a, b):
            from scipy.spatial.distance import cdist

            return 2.0 * cdist(a, b).mean() - cdist(a, a).mean() - cdist(b, b).mean()

        # CPU reference
        cpu_rng = np.random.RandomState(99)
        obs_cpu, _, _, z_cpu, _ = permutation_test(X, Y, energy_fn, 200, cpu_rng)

        # GPU path (different RNG, but same data)
        obs_gpu, _, _, z_gpu, _ = gpu_energy_permutations(X, Y, 200, seed=99)

        # Observed statistic should match closely (same formula, f32 vs f64)
        assert obs_cpu == pytest.approx(obs_gpu, rel=1e-3), (
            f"Observed: CPU={obs_cpu:.6f}, GPU={obs_gpu:.6f}"
        )
        # Both should agree on significance (different RNG → different null
        # distribution, but same conclusion).  With a +1.5 shift on 30 points,
        # z-scores are typically 20-40, so we use relative tolerance.
        assert (z_cpu > 2) == (z_gpu > 2), (
            f"Significance disagreement: z_cpu={z_cpu:.2f}, z_gpu={z_gpu:.2f}"
        )
        assert z_gpu == pytest.approx(z_cpu, rel=0.5), (
            f"Z-scores differ by >50%%: CPU={z_cpu:.2f}, GPU={z_gpu:.2f}"
        )

    def test_gpu_mmd_formula_correct(self):
        """GPU vectorized MMD formula matches CPU reference."""
        try:
            import torch

            if not torch.cuda.is_available():
                pytest.skip("CUDA not available")
        except ImportError:
            pytest.skip("torch not installed")

        from _divergence_semantic import _median_heuristic, compute_mmd_rbf
        from _permutation_accel import gpu_mmd_permutations
        from compute_null_model import permutation_test

        rng = np.random.RandomState(42)
        X = rng.randn(30, 10).astype(np.float32)
        Y = rng.randn(30, 10).astype(np.float32) + 1.0

        med = _median_heuristic(X, Y)

        def mmd_fn(a, b):
            return compute_mmd_rbf(a, b, med)

        # CPU reference
        cpu_rng = np.random.RandomState(99)
        obs_cpu, _, _, z_cpu, _ = permutation_test(X, Y, mmd_fn, 200, cpu_rng)

        # GPU path
        obs_gpu, _, _, z_gpu, _ = gpu_mmd_permutations(X, Y, med, 200, seed=99)

        assert obs_cpu == pytest.approx(obs_gpu, rel=1e-2), (
            f"Observed MMD: CPU={obs_cpu:.6f}, GPU={obs_gpu:.6f}"
        )
        assert (z_cpu > 2) == (z_gpu > 2), (
            f"Significance disagreement: z_cpu={z_cpu:.2f}, z_gpu={z_gpu:.2f}"
        )
        assert z_gpu == pytest.approx(z_cpu, rel=0.5), (
            f"Z-scores differ by >50%%: CPU={z_cpu:.2f}, GPU={z_gpu:.2f}"
        )
