"""Tests for bootstrap CI computation (ticket 0047).

Tests:
1. Bootstrap output schema — required columns and types
2. Bootstrap produces K replicates per (method, year, window)
3. Bootstrap replicates vary (resampling introduces variation)
4. Summary table joins all sources correctly
5. Significant flag logic
6. Schema validation for BootstrapSchema and DivergenceSummarySchema
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


# ---------------------------------------------------------------------------
# Synthetic data helpers
# ---------------------------------------------------------------------------


def _make_synthetic_null_df():
    """Minimal null model CSV for testing summary."""
    return pd.DataFrame(
        {
            "year": [2005, 2006],
            "window": ["3", "3"],
            "observed": [0.55, 0.75],
            "null_mean": [0.30, 0.35],
            "null_std": [0.10, 0.12],
            "z_score": [2.5, 3.33],
            "p_value": [0.01, 0.002],
        }
    )


def _make_synthetic_boot_df(k=10):
    """Minimal bootstrap replicates CSV for testing summary."""
    rows = []
    rng = np.random.RandomState(42)
    for year in [2005, 2006]:
        for rep in range(k):
            rows.append(
                {
                    "method": "S2_energy",
                    "year": year,
                    "window": "3",
                    "hyperparams": "",
                    "replicate": rep,
                    "value": rng.uniform(0.4, 0.9),
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Bootstrap computation tests
# ---------------------------------------------------------------------------


class TestBootstrapComputation:
    """Test the bootstrap_one_window function."""

    def test_bootstrap_output_schema(self):
        """Bootstrap output has required columns."""
        from compute_divergence_bootstrap import bootstrap_one_window

        rng = np.random.RandomState(42)
        X = rng.randn(30, 10)
        Y = rng.randn(30, 10)

        def stat_fn(a, b):
            return float(np.mean(np.abs(a.mean(axis=0) - b.mean(axis=0))))

        result = bootstrap_one_window(X, Y, stat_fn, k=5, seed=42)

        assert isinstance(result, list)
        assert len(result) == 5
        # Each element should be a float
        for v in result:
            assert isinstance(v, float)

    def test_bootstrap_produces_k_replicates(self):
        """bootstrap_one_window should produce exactly K replicates."""
        from compute_divergence_bootstrap import bootstrap_one_window

        rng = np.random.RandomState(42)
        X = rng.randn(50, 10)
        Y = rng.randn(50, 10)

        def stat_fn(a, b):
            return float(np.linalg.norm(a.mean(axis=0) - b.mean(axis=0)))

        for k in [1, 5, 20]:
            result = bootstrap_one_window(X, Y, stat_fn, k=k, seed=42)
            assert len(result) == k, f"Expected {k} replicates, got {len(result)}"

    def test_bootstrap_replicates_vary(self):
        """Replicates should not all be identical."""
        from compute_divergence_bootstrap import bootstrap_one_window

        rng = np.random.RandomState(42)
        X = rng.randn(50, 10)
        Y = rng.randn(50, 10)

        def stat_fn(a, b):
            return float(np.linalg.norm(a.mean(axis=0) - b.mean(axis=0)))

        result = bootstrap_one_window(X, Y, stat_fn, k=20, seed=42)
        # Not all values should be identical
        assert len(set(result)) > 1, "All bootstrap replicates are identical"

    def test_bootstrap_reproducible(self):
        """Same seed produces same replicates."""
        from compute_divergence_bootstrap import bootstrap_one_window

        rng = np.random.RandomState(42)
        X = rng.randn(30, 10)
        Y = rng.randn(30, 10)

        def stat_fn(a, b):
            return float(np.linalg.norm(a.mean(axis=0) - b.mean(axis=0)))

        r1 = bootstrap_one_window(X, Y, stat_fn, k=10, seed=99)
        r2 = bootstrap_one_window(X, Y, stat_fn, k=10, seed=99)
        assert r1 == r2, "Bootstrap not reproducible with same seed"

    def test_bootstrap_list_inputs(self):
        """bootstrap_one_window works with list inputs (for lexical channel)."""
        from compute_divergence_bootstrap import bootstrap_one_window

        texts_before = [f"word{i} climate finance" for i in range(30)]
        texts_after = [f"word{i} green bond" for i in range(30)]

        def stat_fn(a, b):
            return float(len(set(a)) + len(set(b)))

        result = bootstrap_one_window(texts_before, texts_after, stat_fn, k=5, seed=42)
        assert len(result) == 5


class TestCitationBootstrap:
    """Tests for graph-channel bootstrap (G2, G9). Ticket 0069."""

    def test_citation_channel_supported(self):
        """compute_divergence_bootstrap should accept citation channel."""
        from compute_divergence_bootstrap import SUPPORTED_CHANNELS

        assert "citation" in SUPPORTED_CHANNELS

    def test_run_citation_bootstrap_exists(self):
        """_run_citation_bootstrap should be importable."""
        from compute_divergence_bootstrap import _run_citation_bootstrap

        assert callable(_run_citation_bootstrap)

    @pytest.mark.parametrize("method", ["G2_spectral", "G9_community"])
    def test_citation_bootstrap_schema(self, method):
        """Citation bootstrap output matches BootstrapSchema."""
        from unittest.mock import patch

        from compute_divergence_bootstrap import _run_citation_bootstrap
        from schemas import BootstrapSchema

        rng = np.random.RandomState(42)
        n_years = 15
        papers_per_year = 25
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
            result = _run_citation_bootstrap(method, div_df, cfg, k=5)

        BootstrapSchema.validate(result)
        assert len(result) > 0
        assert (result["method"] == method).all()
        assert set(result["replicate"].unique()).issubset(set(range(5)))

    def test_citation_bootstrap_is_proper_subsampling(self):
        """Replicates must be true subsamples — each draws fraction*n distinct
        nodes without replacement. Regression for the original bug where
        rng.choice(replace=True) was collapsed into a set, yielding a random
        ~63%-of-unique-nodes subset (subsampling at a noisy fraction).
        """
        from unittest.mock import patch

        from compute_divergence_bootstrap import _run_citation_bootstrap

        rng = np.random.RandomState(0)
        years = np.repeat(np.arange(2000, 2015), 25)
        dois = [f"10.1000/x.{i}" for i in range(len(years))]
        works = pd.DataFrame({"doi": dois, "year": years, "cited_by_count": 10})

        edges = []
        doi_years = dict(zip(works["doi"], works["year"]))
        for _ in range(len(dois) * 3):
            src = rng.choice(dois)
            ref = rng.choice(dois)
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

        fraction = 0.8
        cfg = {
            "divergence": {
                "windows": [3],
                "random_seed": 42,
                "min_papers_fraction": 0.001,
                "min_papers_floor": 3,
                "bootstrap": {"citation_subsample_fraction": fraction},
                "citation": {},
            }
        }
        div_df = pd.DataFrame({"year": [2007], "window": [3]})

        from _divergence_citation import _sliding_window_graph

        captured_b: list[int] = []
        captured_a: list[int] = []

        def fake_stat(G_b, G_a):
            captured_b.append(G_b.number_of_nodes())
            captured_a.append(G_a.number_of_nodes())
            return 0.0

        with (
            patch(
                "_divergence_citation.load_citation_data",
                return_value=(works, None, internal_edges),
            ),
            patch(
                "compute_divergence_bootstrap._make_citation_statistic",
                return_value=fake_stat,
            ),
        ):
            _run_citation_bootstrap("G2_spectral", div_df, cfg, k=10)

        G_before = _sliding_window_graph(works, internal_edges, 2007, 3, "before")
        G_after = _sliding_window_graph(works, internal_edges, 2007, 3, "after")
        expected_b = max(2, round(G_before.number_of_nodes() * fraction))
        expected_a = max(2, round(G_after.number_of_nodes() * fraction))

        # Every replicate must hit exactly the configured fraction (without-
        # replacement subsampling). With-replacement + set() would give
        # variable counts averaging ~63% of n.
        assert all(n == expected_b for n in captured_b), (
            f"Bootstrap collapsed multiplicities: subgraph sizes {captured_b} "
            f"vs expected {expected_b}."
        )
        assert all(n == expected_a for n in captured_a), captured_a
        assert len(captured_b) == 10


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestBootstrapSchema:
    """BootstrapSchema validation."""

    def test_valid_dataframe_passes(self):
        from schemas import BootstrapSchema

        df = pd.DataFrame(
            {
                "method": ["S2_energy", "S2_energy"],
                "year": [2010, 2010],
                "window": ["3", "3"],
                "hyperparams": ["", ""],
                "replicate": [0, 1],
                "value": [0.5, 0.6],
            }
        )
        BootstrapSchema.validate(df)

    def test_extra_column_rejected(self):
        from schemas import BootstrapSchema

        df = pd.DataFrame(
            {
                "method": ["S2_energy"],
                "year": [2010],
                "window": ["3"],
                "hyperparams": [""],
                "replicate": [0],
                "value": [0.5],
                "extra": ["oops"],
            }
        )
        with pytest.raises(Exception):
            BootstrapSchema.validate(df)

    def test_coercion_works(self):
        from schemas import BootstrapSchema

        df = pd.DataFrame(
            {
                "method": ["S2_energy"],
                "year": ["2010"],
                "window": ["3"],
                "hyperparams": [""],
                "replicate": ["0"],
                "value": ["0.5"],
            }
        )
        validated = BootstrapSchema.validate(df)
        assert validated["year"].dtype in (int, "int64")


class TestDivergenceSummarySchema:
    """DivergenceSummarySchema validation."""

    def test_valid_dataframe_passes(self):
        from schemas import DivergenceSummarySchema

        df = pd.DataFrame(
            {
                "method": ["S2_energy"],
                "year": [2010],
                "window": ["3"],
                "hyperparams": [""],
                "point_estimate": [0.55],
                "boot_median": [0.54],
                "boot_q025": [0.40],
                "boot_q975": [0.70],
                "z_score": [2.5],
                "p_value": [0.01],
                "significant": [True],
            }
        )
        DivergenceSummarySchema.validate(df)

    def test_extra_column_rejected(self):
        from schemas import DivergenceSummarySchema

        df = pd.DataFrame(
            {
                "method": ["S2_energy"],
                "year": [2010],
                "window": ["3"],
                "hyperparams": [""],
                "point_estimate": [0.55],
                "boot_median": [0.54],
                "boot_q025": [0.40],
                "boot_q975": [0.70],
                "z_score": [2.5],
                "p_value": [0.01],
                "significant": [True],
                "extra": ["oops"],
            }
        )
        with pytest.raises(Exception):
            DivergenceSummarySchema.validate(df)


# ---------------------------------------------------------------------------
# Summary table tests
# ---------------------------------------------------------------------------


class TestSummaryTable:
    """Test export_divergence_summary logic."""

    def test_summary_joins_all_sources(self):
        """Summary table has all expected columns from the three sources."""
        from export_divergence_summary import build_summary

        div_df = pd.DataFrame(
            {
                "year": [2005, 2006],
                "channel": ["semantic", "semantic"],
                "window": ["3", "3"],
                "hyperparams": ["", ""],
                "value": [0.55, 0.75],
            }
        )
        null_df = _make_synthetic_null_df()
        boot_df = _make_synthetic_boot_df(k=10)

        result = build_summary(div_df, null_df, boot_df, method="S2_energy")

        expected_cols = {
            "method",
            "year",
            "window",
            "hyperparams",
            "point_estimate",
            "boot_median",
            "boot_q025",
            "boot_q975",
            "z_score",
            "p_value",
            "significant",
        }
        assert expected_cols == set(result.columns), (
            f"Columns mismatch: {set(result.columns)}"
        )
        assert len(result) == 2  # one row per (year, window)
        # z_score is forwarded verbatim from the null model
        assert list(result.sort_values("year")["z_score"]) == [2.5, 3.33]

    def test_summary_preserves_negative_z_score(self):
        """Negative z (divergence below null mean) must survive the join.

        Sign carries directional information (concentration increase vs
        decrease) that p-value alone discards. The build_summary pipeline
        must not clip, abs, or otherwise transform z_score.
        """
        from export_divergence_summary import build_summary

        div_df = pd.DataFrame(
            {
                "year": [2005],
                "channel": ["semantic"],
                "window": ["3"],
                "hyperparams": [""],
                "value": [0.20],
            }
        )
        null_df = pd.DataFrame(
            {
                "year": [2005],
                "window": ["3"],
                "observed": [0.20],
                "null_mean": [0.35],
                "null_std": [0.10],
                "z_score": [-1.5],  # observed below null mean
                "p_value": [0.134],  # two-sided p for |z|=1.5
            }
        )
        boot_df = _make_synthetic_boot_df(k=10)
        boot_df = boot_df[boot_df["year"] == 2005].copy()

        result = build_summary(div_df, null_df, boot_df, method="S2_energy")

        assert len(result) == 1
        assert result.iloc[0]["z_score"] == -1.5

    def test_summary_significant_flag(self):
        """significant should be True when p_value < 0.05."""
        from export_divergence_summary import build_summary

        div_df = pd.DataFrame(
            {
                "year": [2005, 2006],
                "channel": ["semantic", "semantic"],
                "window": ["3", "3"],
                "hyperparams": ["", ""],
                "value": [0.55, 0.75],
            }
        )
        null_df = pd.DataFrame(
            {
                "year": [2005, 2006],
                "window": ["3", "3"],
                "observed": [0.55, 0.75],
                "null_mean": [0.30, 0.35],
                "null_std": [0.10, 0.12],
                "z_score": [2.5, 0.5],
                "p_value": [0.01, 0.30],  # first significant, second not
            }
        )
        boot_df = _make_synthetic_boot_df(k=10)

        result = build_summary(div_df, null_df, boot_df, method="S2_energy")

        row_2005 = result[result["year"] == 2005].iloc[0]
        row_2006 = result[result["year"] == 2006].iloc[0]

        assert row_2005["significant"] is True or row_2005["significant"] == True
        assert row_2006["significant"] is False or row_2006["significant"] == False

    def test_summary_bootstrap_quantiles(self):
        """Bootstrap quantiles should bracket the median."""
        from export_divergence_summary import build_summary

        div_df = pd.DataFrame(
            {
                "year": [2005],
                "channel": ["semantic"],
                "window": ["3"],
                "hyperparams": [""],
                "value": [0.55],
            }
        )
        null_df = pd.DataFrame(
            {
                "year": [2005],
                "window": ["3"],
                "observed": [0.55],
                "null_mean": [0.30],
                "null_std": [0.10],
                "z_score": [2.5],
                "p_value": [0.01],
            }
        )
        boot_df = _make_synthetic_boot_df(k=50)
        # Filter to year 2005 only
        boot_df = boot_df[boot_df["year"] == 2005].reset_index(drop=True)

        result = build_summary(div_df, null_df, boot_df, method="S2_energy")
        row = result.iloc[0]

        assert row["boot_q025"] <= row["boot_median"] <= row["boot_q975"], (
            f"Quantiles out of order: q025={row['boot_q025']}, "
            f"median={row['boot_median']}, q975={row['boot_q975']}"
        )
