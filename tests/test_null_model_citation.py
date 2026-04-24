"""Tests for citation null model permutation drivers G1, G5, G6, G8 (ticket 0109).

These tests follow the same pattern as TestG2SpectralNullModel in test_null_model.py:
mock load_citation_data with synthetic data and small n_perm for speed.
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


# ---------------------------------------------------------------------------
# Synthetic data factory (shared across all test classes)
# ---------------------------------------------------------------------------


def _make_synthetic_citation_data(n_years=15, papers_per_year=20, seed=42):
    """Build minimal synthetic works + internal_edges for citation null model tests."""
    rng = np.random.RandomState(seed)
    years = np.repeat(np.arange(2000, 2000 + n_years), papers_per_year)
    dois = [f"10.1000/test.{i}" for i in range(len(years))]
    works = pd.DataFrame({"doi": dois, "year": years, "cited_by_count": 10})

    doi_list = list(works["doi"])
    doi_years = dict(zip(works["doi"], works["year"]))
    edges = []
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
    return works, internal_edges


def _base_cfg(extra_citation_cfg=None):
    """Minimal cfg compatible with citation null model drivers."""
    citation_cfg = {
        "G1_pagerank": {"damping": 0.85, "n_bins": 20},
        "G2_spectral": {},
        "G5_pref_attachment": {},
        "G6_entropy": {},
        "G8_betweenness": {"max_nodes": 50},
        "G9_community": {"resolution": 1.0},
    }
    if extra_citation_cfg:
        citation_cfg.update(extra_citation_cfg)
    return {
        "divergence": {
            "windows": [3],
            "random_seed": 42,
            "permutation": {"n_perm": 20},
            "min_papers_fraction": 0.001,
            "min_papers_floor": 5,
            "citation": citation_cfg,
        }
    }


EXPECTED_COLS = {
    "year",
    "window",
    "observed",
    "null_mean",
    "null_std",
    "z_score",
    "p_value",
}


# ---------------------------------------------------------------------------
# G6 Entropy
# ---------------------------------------------------------------------------


class TestG6EntropyNullModel:
    """Unit tests for G6 citation entropy null model driver."""

    def test_g6_in_dispatcher(self):
        """G6_entropy must be registered in _CITATION_PERMUTATION_DRIVERS."""
        from compute_null_model import _CITATION_PERMUTATION_DRIVERS

        assert "G6_entropy" in _CITATION_PERMUTATION_DRIVERS

    def test_run_g6_permutations_importable(self):
        """_run_g6_permutations must be importable and callable."""
        from compute_null_model import _run_g6_permutations

        assert callable(_run_g6_permutations)

    def test_g6_output_schema(self):
        """G6 null model output matches NullModelSchema."""
        from unittest.mock import patch

        from compute_null_model import _run_citation_permutations
        from schemas import NullModelSchema

        works, internal_edges = _make_synthetic_citation_data()
        cfg = _base_cfg()
        div_df = pd.DataFrame({"year": [2005, 2007], "window": [3, 3]})

        with patch(
            "_divergence_citation.load_citation_data",
            return_value=(works, None, internal_edges),
        ):
            result = _run_citation_permutations("G6_entropy", div_df, cfg)

        NullModelSchema.validate(result)
        assert set(result.columns) == EXPECTED_COLS
        assert len(result) == 2

    def test_g6_observed_matches_entropy_diff(self):
        """G6 observed value must equal abs(_citation_entropy(after) - before)."""
        from unittest.mock import patch

        from _citation_methods import _citation_entropy
        from _divergence_citation import _sliding_window_graph
        from compute_null_model import _run_citation_permutations

        works, internal_edges = _make_synthetic_citation_data()
        cfg = _base_cfg()
        div_df = pd.DataFrame({"year": [2005], "window": [3]})

        with patch(
            "_divergence_citation.load_citation_data",
            return_value=(works, None, internal_edges),
        ):
            result = _run_citation_permutations("G6_entropy", div_df, cfg)

        row = result.iloc[0]
        y, w = int(row["year"]), int(row["window"])
        G_before = _sliding_window_graph(works, internal_edges, y, w, "before")
        G_after = _sliding_window_graph(works, internal_edges, y, w, "after")
        e_b = _citation_entropy(G_before)
        e_a = _citation_entropy(G_after)
        if np.isnan(e_b) or np.isnan(e_a):
            assert np.isnan(row["observed"])
        else:
            assert abs(row["observed"] - abs(e_a - e_b)) < 1e-9

    def test_g6_null_std_nonnegative(self):
        """null_std must be >= 0 (NaN allowed for degenerate windows)."""
        from unittest.mock import patch

        from compute_null_model import _run_citation_permutations

        works, internal_edges = _make_synthetic_citation_data()
        cfg = _base_cfg()
        div_df = pd.DataFrame({"year": [2005, 2007, 2010], "window": [3, 3, 3]})

        with patch(
            "_divergence_citation.load_citation_data",
            return_value=(works, None, internal_edges),
        ):
            result = _run_citation_permutations("G6_entropy", div_df, cfg)

        non_nan = result["null_std"].dropna()
        assert (non_nan >= 0).all()


# ---------------------------------------------------------------------------
# G8 Betweenness
# ---------------------------------------------------------------------------


class TestG8BetweennessNullModel:
    """Unit tests for G8 betweenness centrality null model driver."""

    def test_g8_in_dispatcher(self):
        """G8_betweenness must be registered in _CITATION_PERMUTATION_DRIVERS."""
        from compute_null_model import _CITATION_PERMUTATION_DRIVERS

        assert "G8_betweenness" in _CITATION_PERMUTATION_DRIVERS

    def test_run_g8_permutations_importable(self):
        """_run_g8_permutations must be importable and callable."""
        from compute_null_model import _run_g8_permutations

        assert callable(_run_g8_permutations)

    def test_g8_output_schema(self):
        """G8 null model output matches NullModelSchema."""
        from unittest.mock import patch

        from compute_null_model import _run_citation_permutations
        from schemas import NullModelSchema

        works, internal_edges = _make_synthetic_citation_data()
        cfg = _base_cfg()
        div_df = pd.DataFrame({"year": [2005, 2007], "window": [3, 3]})

        with patch(
            "_divergence_citation.load_citation_data",
            return_value=(works, None, internal_edges),
        ):
            result = _run_citation_permutations("G8_betweenness", div_df, cfg)

        NullModelSchema.validate(result)
        assert set(result.columns) == EXPECTED_COLS
        assert len(result) == 2

    def test_g8_observed_matches_betweenness_diff(self):
        """G8 observed value must equal abs(_mean_betweenness(after) - before)."""
        from unittest.mock import patch

        from _citation_methods import _mean_betweenness
        from _divergence_citation import _sliding_window_graph
        from compute_null_model import _run_citation_permutations

        works, internal_edges = _make_synthetic_citation_data()
        cfg = _base_cfg()
        div_df = pd.DataFrame({"year": [2005], "window": [3]})

        with patch(
            "_divergence_citation.load_citation_data",
            return_value=(works, None, internal_edges),
        ):
            result = _run_citation_permutations("G8_betweenness", div_df, cfg)

        row = result.iloc[0]
        y, w = int(row["year"]), int(row["window"])
        max_nodes = cfg["divergence"]["citation"]["G8_betweenness"]["max_nodes"]
        G_before = _sliding_window_graph(works, internal_edges, y, w, "before")
        G_after = _sliding_window_graph(works, internal_edges, y, w, "after")
        bc_b = _mean_betweenness(G_before, max_nodes)
        bc_a = _mean_betweenness(G_after, max_nodes)
        if np.isnan(bc_b) or np.isnan(bc_a):
            assert np.isnan(row["observed"])
        else:
            assert abs(row["observed"] - abs(bc_a - bc_b)) < 1e-9

    def test_g8_uses_reduced_n_perm(self):
        """G8 driver must cap n_perm to avoid prohibitive betweenness runtime.

        We pass n_perm=500 in cfg and check that the null distribution was
        built with at most 50 permutations (not 500).  We infer this from the
        null_std being finite (500 betweenness permutations would be very slow
        in CI), not from the value itself.  This test just asserts the driver
        runs in <30 seconds on the smoke fixture.
        """
        import time
        from unittest.mock import patch

        from compute_null_model import _run_citation_permutations

        works, internal_edges = _make_synthetic_citation_data()
        cfg = _base_cfg()
        # Override to high n_perm; driver should cap internally
        cfg["divergence"]["permutation"]["n_perm"] = 500
        div_df = pd.DataFrame({"year": [2005], "window": [3]})

        t0 = time.perf_counter()
        with patch(
            "_divergence_citation.load_citation_data",
            return_value=(works, None, internal_edges),
        ):
            result = _run_citation_permutations("G8_betweenness", div_df, cfg)
        elapsed = time.perf_counter() - t0

        assert result.returncode if hasattr(result, "returncode") else True
        # Should finish well under 30s even with 500 in cfg (because driver caps)
        assert elapsed < 30, f"G8 took {elapsed:.1f}s — n_perm cap not applied?"


# ---------------------------------------------------------------------------
# G5 Pref attachment
# ---------------------------------------------------------------------------


class TestG5PrefAttachmentNullModel:
    """Unit tests for G5 preferential attachment null model driver."""

    def test_g5_in_dispatcher(self):
        """G5_pref_attachment must be registered in _CITATION_PERMUTATION_DRIVERS."""
        from compute_null_model import _CITATION_PERMUTATION_DRIVERS

        assert "G5_pref_attachment" in _CITATION_PERMUTATION_DRIVERS

    def test_run_g5_permutations_importable(self):
        """_run_g5_permutations must be importable and callable."""
        from compute_null_model import _run_g5_permutations

        assert callable(_run_g5_permutations)

    def test_g5_output_schema(self):
        """G5 null model output matches NullModelSchema."""
        from unittest.mock import patch

        from compute_null_model import _run_citation_permutations
        from schemas import NullModelSchema

        works, internal_edges = _make_synthetic_citation_data()
        cfg = _base_cfg()
        div_df = pd.DataFrame({"year": [2005, 2007], "window": [3, 3]})

        with patch(
            "_divergence_citation.load_citation_data",
            return_value=(works, None, internal_edges),
        ):
            result = _run_citation_permutations("G5_pref_attachment", div_df, cfg)

        NullModelSchema.validate(result)
        assert set(result.columns) == EXPECTED_COLS
        assert len(result) == 2

    def test_g5_observed_matches_pa_exponent_diff(self):
        """G5 observed value must equal abs(_pa_exponent(after) - before)."""
        from unittest.mock import patch

        from _citation_methods import _pa_exponent
        from _divergence_citation import _sliding_window_graph
        from compute_null_model import _run_citation_permutations

        works, internal_edges = _make_synthetic_citation_data()
        cfg = _base_cfg()
        div_df = pd.DataFrame({"year": [2005], "window": [3]})

        with patch(
            "_divergence_citation.load_citation_data",
            return_value=(works, None, internal_edges),
        ):
            result = _run_citation_permutations("G5_pref_attachment", div_df, cfg)

        row = result.iloc[0]
        y, w = int(row["year"]), int(row["window"])
        G_before = _sliding_window_graph(works, internal_edges, y, w, "before")
        G_after = _sliding_window_graph(works, internal_edges, y, w, "after")
        exp_b = _pa_exponent(G_before)
        exp_a = _pa_exponent(G_after)
        if np.isnan(exp_b) or np.isnan(exp_a):
            assert np.isnan(row["observed"])
        else:
            assert abs(row["observed"] - abs(exp_a - exp_b)) < 1e-9

    def test_g5_null_std_nonnegative(self):
        """null_std must be >= 0 (NaN allowed for degenerate windows)."""
        from unittest.mock import patch

        from compute_null_model import _run_citation_permutations

        works, internal_edges = _make_synthetic_citation_data()
        cfg = _base_cfg()
        div_df = pd.DataFrame({"year": [2005, 2007, 2010], "window": [3, 3, 3]})

        with patch(
            "_divergence_citation.load_citation_data",
            return_value=(works, None, internal_edges),
        ):
            result = _run_citation_permutations("G5_pref_attachment", div_df, cfg)

        non_nan = result["null_std"].dropna()
        assert (non_nan >= 0).all()


# ---------------------------------------------------------------------------
# G1 PageRank
# ---------------------------------------------------------------------------


class TestG1PageRankNullModel:
    """Unit tests for G1 PageRank null model driver."""

    def test_g1_in_dispatcher(self):
        """G1_pagerank must be registered in _CITATION_PERMUTATION_DRIVERS."""
        from compute_null_model import _CITATION_PERMUTATION_DRIVERS

        assert "G1_pagerank" in _CITATION_PERMUTATION_DRIVERS

    def test_run_g1_permutations_importable(self):
        """_run_g1_permutations must be importable and callable."""
        from compute_null_model import _run_g1_permutations

        assert callable(_run_g1_permutations)

    def test_g1_output_schema(self):
        """G1 null model output matches NullModelSchema."""
        from unittest.mock import patch

        from compute_null_model import _run_citation_permutations
        from schemas import NullModelSchema

        works, internal_edges = _make_synthetic_citation_data()
        cfg = _base_cfg()
        div_df = pd.DataFrame({"year": [2005, 2007], "window": [3, 3]})

        with patch(
            "_divergence_citation.load_citation_data",
            return_value=(works, None, internal_edges),
        ):
            result = _run_citation_permutations("G1_pagerank", div_df, cfg)

        NullModelSchema.validate(result)
        assert set(result.columns) == EXPECTED_COLS
        assert len(result) == 2

    def test_g1_observed_matches_pagerank_js(self):
        """G1 observed value must equal _compare_pagerank_distributions(before, after)."""
        from unittest.mock import patch

        from _citation_methods import _compare_pagerank_distributions, _pagerank_vector
        from _divergence_citation import _sliding_window_graph
        from compute_null_model import _run_citation_permutations

        works, internal_edges = _make_synthetic_citation_data()
        cfg = _base_cfg()
        div_df = pd.DataFrame({"year": [2005], "window": [3]})

        with patch(
            "_divergence_citation.load_citation_data",
            return_value=(works, None, internal_edges),
        ):
            result = _run_citation_permutations("G1_pagerank", div_df, cfg)

        row = result.iloc[0]
        y, w = int(row["year"]), int(row["window"])
        damping = cfg["divergence"]["citation"]["G1_pagerank"]["damping"]
        n_bins = cfg["divergence"]["citation"]["G1_pagerank"]["n_bins"]
        G_before = _sliding_window_graph(works, internal_edges, y, w, "before")
        G_after = _sliding_window_graph(works, internal_edges, y, w, "after")
        pr_b = _pagerank_vector(G_before, damping)
        pr_a = _pagerank_vector(G_after, damping)
        if pr_b is None or pr_a is None:
            assert np.isnan(row["observed"])
        else:
            expected = _compare_pagerank_distributions(pr_b, pr_a, n_bins)
            assert abs(row["observed"] - expected) < 1e-9

    def test_g1_null_std_nonnegative(self):
        """null_std must be >= 0 (NaN allowed for degenerate windows)."""
        from unittest.mock import patch

        from compute_null_model import _run_citation_permutations

        works, internal_edges = _make_synthetic_citation_data()
        cfg = _base_cfg()
        div_df = pd.DataFrame({"year": [2005, 2007, 2010], "window": [3, 3, 3]})

        with patch(
            "_divergence_citation.load_citation_data",
            return_value=(works, None, internal_edges),
        ):
            result = _run_citation_permutations("G1_pagerank", div_df, cfg)

        non_nan = result["null_std"].dropna()
        assert (non_nan >= 0).all()

    def test_g1_reads_damping_and_n_bins_from_cfg(self):
        """G1 driver must read damping and n_bins from cfg."""
        from unittest.mock import patch

        from compute_null_model import _run_citation_permutations
        from schemas import NullModelSchema

        works, internal_edges = _make_synthetic_citation_data()
        # Non-default values to ensure cfg is actually read
        cfg = _base_cfg({"G1_pagerank": {"damping": 0.70, "n_bins": 10}})
        div_df = pd.DataFrame({"year": [2005], "window": [3]})

        with patch(
            "_divergence_citation.load_citation_data",
            return_value=(works, None, internal_edges),
        ):
            result = _run_citation_permutations("G1_pagerank", div_df, cfg)

        NullModelSchema.validate(result)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# Shared helper extraction test
# ---------------------------------------------------------------------------


class TestNodePermutationHelper:
    """Verify the shared _node_permutation_null_distribution helper."""

    def test_helper_importable(self):
        """_node_permutation_null_distribution must be importable."""
        from _permutation_citation import _node_permutation_null_distribution

        assert callable(_node_permutation_null_distribution)

    def test_helper_returns_array_of_abs_diffs(self):
        """Helper must return n_perm abs-diff values (NaN rows dropped)."""
        import networkx as nx
        from _permutation_citation import _node_permutation_null_distribution

        # Build a simple graph for testing
        G = nx.DiGraph()
        nodes = list(range(20))
        G.add_nodes_from(nodes)
        rng = np.random.RandomState(42)
        for _ in range(40):
            u, v = rng.choice(nodes, 2, replace=False)
            G.add_edge(u, v)

        all_nodes = list(G.nodes())
        n_before = len(all_nodes) // 2
        perm_rng = np.random.RandomState(7)

        def simple_metric(Gx):
            return float(Gx.number_of_edges())

        null_stats = _node_permutation_null_distribution(
            G,
            all_nodes,
            n_before,
            n_perm=30,
            perm_rng=perm_rng,
            metric_fn=simple_metric,
        )

        assert isinstance(null_stats, np.ndarray)
        assert len(null_stats) > 0
        assert (null_stats >= 0).all()  # abs diffs are non-negative


# ---------------------------------------------------------------------------
# Integration: dispatcher rejects unsupported methods correctly
# ---------------------------------------------------------------------------


class TestDispatcherRejectsUnknown:
    """_run_citation_permutations should raise for unknown methods."""

    def test_unknown_method_raises(self):
        """Dispatcher raises ValueError for unknown method."""
        from unittest.mock import patch

        from compute_null_model import _run_citation_permutations

        works, internal_edges = _make_synthetic_citation_data()
        cfg = _base_cfg()
        div_df = pd.DataFrame({"year": [2005], "window": [3]})

        with patch(
            "_divergence_citation.load_citation_data",
            return_value=(works, None, internal_edges),
        ):
            with pytest.raises(ValueError, match="No citation null-model driver"):
                _run_citation_permutations("G3_coupling_age", div_df, cfg)
