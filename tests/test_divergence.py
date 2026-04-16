"""Tests for the refactored divergence pipeline.

Tests:
1. DivergenceSchema validation
2. Smoke test: run compute_divergence.py --method for each method type
3. Module function availability checks
4. Seed reproducibility (same seed -> same output, different seed -> different)
5. Property tests for S1-S4 metric axioms
6. _get_break_years helper tests
7. G1 PageRank on disjoint sliding windows (ticket 0059)
"""

import copy
import os
import sys

import numpy as np
import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "smoke")
ROOT_DIR = os.path.join(os.path.dirname(__file__), "..")

sys.path.insert(0, SCRIPTS_DIR)


from conftest import run_compute as _run_compute

# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestDivergenceSchema:
    """DivergenceSchema validation."""

    def test_valid_dataframe_passes(self):
        from schemas import DivergenceSchema

        df = pd.DataFrame(
            {
                "year": [2010, 2011],
                "channel": ["semantic", "semantic"],
                "window": ["3", "3"],
                "hyperparams": ["default", "default"],
                "value": [0.5, 0.6],
            }
        )
        DivergenceSchema.validate(df)

    def test_extra_column_rejected(self):
        from schemas import DivergenceSchema

        df = pd.DataFrame(
            {
                "year": [2010],
                "channel": ["semantic"],
                "window": ["3"],
                "hyperparams": ["default"],
                "value": [0.5],
                "extra": ["oops"],
            }
        )
        with pytest.raises(Exception):
            DivergenceSchema.validate(df)

    def test_bad_channel_rejected(self):
        from schemas import DivergenceSchema

        df = pd.DataFrame(
            {
                "year": [2010],
                "channel": ["unknown"],
                "window": ["3"],
                "hyperparams": ["default"],
                "value": [0.5],
            }
        )
        with pytest.raises(Exception):
            DivergenceSchema.validate(df)

    def test_nullable_value_accepted(self):
        import numpy as np
        from schemas import DivergenceSchema

        df = pd.DataFrame(
            {
                "year": [2010],
                "channel": ["citation"],
                "window": ["cumulative"],
                "hyperparams": [""],
                "value": [np.nan],
            }
        )
        DivergenceSchema.validate(df)

    def test_coercion_works(self):
        """String year and float value should be coerced."""
        from schemas import DivergenceSchema

        df = pd.DataFrame(
            {
                "year": ["2010"],
                "channel": ["lexical"],
                "window": ["3"],
                "hyperparams": ["w=3"],
                "value": ["0.5"],
            }
        )
        validated = DivergenceSchema.validate(df)
        assert validated["year"].dtype in (int, "int64")


# ---------------------------------------------------------------------------
# Module function availability
# ---------------------------------------------------------------------------


class TestModuleFunctions:
    """Verify each private module exposes the expected functions."""

    def test_semantic_module_has_all_functions(self):
        import _divergence_semantic as mod

        for fn in [
            "compute_s1_mmd",
            "compute_s2_energy",
            "compute_s3_wasserstein",
            "compute_s4_frechet",
            "load_semantic_data",
        ]:
            assert hasattr(mod, fn), f"Missing: {fn}"
            assert callable(getattr(mod, fn)), f"Not callable: {fn}"

    def test_lexical_module_has_all_functions(self):
        import _divergence_lexical as mod

        for fn in [
            "compute_l1_js",
            "compute_l2_novelty",
            "compute_l3_bursts",
            "load_lexical_data",
        ]:
            assert hasattr(mod, fn), f"Missing: {fn}"
            assert callable(getattr(mod, fn)), f"Not callable: {fn}"

    def test_citation_module_has_all_functions(self):
        import _citation_methods as methods
        import _divergence_citation as infra

        for fn in [
            "compute_g1_pagerank",
            "compute_g2_spectral",
            "compute_g3_age_shift",
            "compute_g4_cross_trad",
            "compute_g5_pa_exponent",
            "compute_g6_entropy",
            "compute_g7_disruption",
            "compute_g8_betweenness",
        ]:
            assert hasattr(methods, fn), f"Missing: {fn}"
            assert callable(getattr(methods, fn)), f"Not callable: {fn}"
        assert hasattr(infra, "load_citation_data")
        assert callable(infra.load_citation_data)

    def test_dispatcher_registry_complete(self):
        from compute_divergence import METHODS

        assert len(METHODS) == 17
        # Verify all three channels present
        channels = {v[2] for v in METHODS.values()}
        assert channels == {"semantic", "lexical", "citation"}


# ---------------------------------------------------------------------------
# Smoke tests: run dispatcher on fixture data
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.integration
class TestSmokeSemantic:
    """Semantic methods on 100-row fixture."""

    @pytest.mark.parametrize(
        "method",
        [
            "S1_MMD",
            "S2_energy",
            "S3_sliced_wasserstein",
            "S4_frechet",
        ],
    )
    def test_compute_method(self, method, tmp_path):
        out = tmp_path / f"tab_div_{method}.csv"
        result = _run_compute(method, out)
        assert result.returncode == 0, (
            f"{method} failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert out.exists(), f"Output CSV not created for {method}"
        df = pd.read_csv(out)
        assert {"year", "channel", "window", "hyperparams", "value"} == set(df.columns)
        assert (df["channel"] == "semantic").all()
        assert len(df) > 0


@pytest.mark.slow
@pytest.mark.integration
class TestSmokeLexical:
    """Lexical methods on 100-row fixture."""

    @pytest.mark.parametrize("method", ["L1", "L2", "L3"])
    def test_compute_method(self, method, tmp_path):
        out = tmp_path / f"tab_div_{method}.csv"
        result = _run_compute(method, out)
        assert result.returncode == 0, (
            f"{method} failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert out.exists(), f"Output CSV not created for {method}"
        df = pd.read_csv(out)
        assert {"year", "channel", "window", "hyperparams", "value"} == set(df.columns)
        assert (df["channel"] == "lexical").all()
        assert len(df) > 0


@pytest.mark.slow
@pytest.mark.integration
class TestSmokeCitation:
    """Citation methods on 100-row fixture."""

    @pytest.mark.parametrize(
        "method",
        [
            "G1_pagerank",
            "G2_spectral",
            "G3_coupling_age",
            "G4_cross_tradition",
            "G5_pref_attachment",
            "G6_entropy",
            "G7_disruption",
            "G8_betweenness",
        ],
    )
    def test_compute_method(self, method, tmp_path):
        out = tmp_path / f"tab_div_{method}.csv"
        result = _run_compute(method, out)
        assert result.returncode == 0, (
            f"{method} failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert out.exists(), f"Output CSV not created for {method}"
        df = pd.read_csv(out)
        assert {"year", "channel", "window", "hyperparams", "value"} == set(df.columns)
        assert (df["channel"] == "citation").all()
        assert len(df) > 0

    def test_g3_has_valid_values(self, tmp_path):
        """G3 (age shift) uses ref_year, should produce values even without internal edges."""
        out = tmp_path / "tab_div_G3_coupling_age.csv"
        _run_compute("G3_coupling_age", out)
        df = pd.read_csv(out)
        valid = df["value"].dropna()
        assert len(valid) >= 5, f"G3 should have >= 5 valid values, got {len(valid)}"


# ---------------------------------------------------------------------------
# Schema validation on smoke output
# ---------------------------------------------------------------------------


@pytest.mark.slow
@pytest.mark.integration
class TestSchemaValidationOnOutput:
    """Verify that actual smoke outputs pass DivergenceSchema."""

    def test_s2_output_passes_schema(self, tmp_path):
        out = tmp_path / "tab_div_S2_energy.csv"
        result = _run_compute("S2_energy", out)
        assert result.returncode == 0, result.stderr

        from schemas import DivergenceSchema

        df = pd.read_csv(out)
        DivergenceSchema.validate(df)

    def test_l1_output_passes_schema(self, tmp_path):
        out = tmp_path / "tab_div_L1.csv"
        result = _run_compute("L1", out)
        assert result.returncode == 0, result.stderr

        from schemas import DivergenceSchema

        df = pd.read_csv(out)
        DivergenceSchema.validate(df)

    def test_g3_output_passes_schema(self, tmp_path):
        out = tmp_path / "tab_div_G3_coupling_age.csv"
        result = _run_compute("G3_coupling_age", out)
        assert result.returncode == 0, result.stderr

        from schemas import DivergenceSchema

        df = pd.read_csv(out)
        DivergenceSchema.validate(df)


# ---------------------------------------------------------------------------
# Seed reproducibility
# ---------------------------------------------------------------------------


def _smoke_cfg(seed=42):
    """Load analysis config and override random_seed."""
    from pipeline_loaders import load_analysis_config

    cfg = copy.deepcopy(load_analysis_config())
    cfg["divergence"]["random_seed"] = seed
    return cfg


def _load_smoke_semantic():
    """Load smoke semantic data (works + embeddings)."""
    from _divergence_semantic import load_semantic_data

    catalogs = os.path.join(FIXTURES_DIR, "catalogs")
    input_paths = [
        os.path.join(catalogs, "refined_works.csv"),
        os.path.join(catalogs, "refined_embeddings.npz"),
    ]
    return load_semantic_data(input_paths)


@pytest.mark.slow
class TestSeedReproducibility:
    """Verify that configurable random_seed controls reproducibility."""

    def test_same_seed_same_output(self):
        """Running S1_MMD twice with the same seed gives identical results."""
        from _divergence_semantic import compute_s1_mmd

        df, emb = _load_smoke_semantic()
        cfg = _smoke_cfg(seed=42)
        result_a = compute_s1_mmd(df, emb, cfg)
        result_b = compute_s1_mmd(df, emb, cfg)
        assert len(result_a) > 0, "S1_MMD produced no rows on smoke data"
        pd.testing.assert_frame_equal(result_a, result_b)

    def test_different_seed_different_output(self):
        """Running S1_MMD with different seeds gives different results.

        On the 100-row smoke fixture, windows are small enough that
        subsampling may not trigger. If values are identical despite
        different seeds, skip rather than silently pass.
        """
        from _divergence_semantic import compute_s1_mmd

        df, emb = _load_smoke_semantic()
        cfg_a = _smoke_cfg(seed=42)
        cfg_b = _smoke_cfg(seed=99)
        result_a = compute_s1_mmd(df, emb, cfg_a)
        result_b = compute_s1_mmd(df, emb, cfg_b)
        assert len(result_a) > 0, "S1_MMD produced no rows on smoke data"
        if len(result_a) != len(result_b):
            return  # different shapes = definitely different
        if np.allclose(result_a["value"].values, result_b["value"].values):
            pytest.skip("Smoke data too small to trigger seed-dependent subsampling")


# ---------------------------------------------------------------------------
# Property tests for S1-S4 metric axioms
# ---------------------------------------------------------------------------


class TestMetricProperties:
    """Verify basic metric axioms for the S1-S4 distance functions."""

    @pytest.fixture
    def random_arrays(self):
        """Two small random arrays for property testing."""
        rng = np.random.RandomState(99)
        X = rng.randn(50, 10)
        Y = rng.randn(50, 10) + 0.5  # shifted to ensure non-zero distance
        return X, Y

    def test_self_distance_near_zero(self, random_arrays):
        """distance(X, X) should be approximately 0 for all S1-S4."""
        X, _ = random_arrays

        # S1: MMD
        from _divergence_semantic import _median_heuristic, compute_mmd_rbf

        med = _median_heuristic(X, X)
        mmd = compute_mmd_rbf(X, X, med)
        assert mmd < 0.05, f"MMD self-distance too large: {mmd}"

        # S2: Energy distance
        import dcor

        e = dcor.energy_distance(X, X)
        assert e < 1e-10, f"Energy self-distance too large: {e}"

        # S3: Sliced Wasserstein
        import ot

        sw = ot.sliced_wasserstein_distance(X, X, n_projections=100, seed=42)
        assert sw < 1e-10, f"Sliced Wasserstein self-distance too large: {sw}"

        # S4: Frechet
        from _divergence_semantic import compute_frechet_distance

        fd = compute_frechet_distance(X, X)
        assert fd < 0.01, f"Frechet self-distance too large: {fd}"

    def test_non_negative(self, random_arrays):
        """distance(X, Y) should be >= 0 for all S1-S4."""
        X, Y = random_arrays

        # S1: MMD
        from _divergence_semantic import _median_heuristic, compute_mmd_rbf

        med = _median_heuristic(X, Y)
        assert compute_mmd_rbf(X, Y, med) >= 0, "MMD returned negative"

        # S2: Energy distance
        import dcor

        assert dcor.energy_distance(X, Y) >= 0, "Energy distance returned negative"

        # S3: Sliced Wasserstein
        import ot

        sw = ot.sliced_wasserstein_distance(X, Y, n_projections=100, seed=42)
        assert sw >= 0, "Sliced Wasserstein returned negative"

        # S4: Frechet
        from _divergence_semantic import compute_frechet_distance

        assert compute_frechet_distance(X, Y) >= 0, "Frechet distance returned negative"


# ---------------------------------------------------------------------------
# _get_break_years helper tests
# ---------------------------------------------------------------------------


class TestGetBreakYears:
    """Test the _get_break_years helper in plot_divergence.py."""

    def test_detector_params_format(self):
        """_get_break_years finds breaks with detector_params='pen=3'."""
        from plot_divergence import _get_break_years

        breaks_df = pd.DataFrame(
            {
                "method": ["S1_MMD", "S1_MMD", "L1"],
                "detector": ["pelt", "pelt", "pelt"],
                "detector_params": ["pen=3", "pen=5", "pen=3"],
                "break_years": ["2007;2013", "2007", "2010"],
            }
        )
        years = _get_break_years(breaks_df, "S1_MMD", penalty=3)
        assert years == {2007, 2013}

    def test_legacy_penalty_format(self):
        """_get_break_years finds breaks with penalty=3 integer column."""
        from plot_divergence import _get_break_years

        breaks_df = pd.DataFrame(
            {
                "method": ["S1_MMD", "S1_MMD"],
                "penalty": [3, 5],
                "break_years": ["2007;2013", "2007"],
            }
        )
        years = _get_break_years(breaks_df, "S1_MMD", penalty=3)
        assert years == {2007, 2013}

    def test_empty_breaks(self):
        """_get_break_years returns empty set for empty DataFrame."""
        from plot_divergence import _get_break_years

        breaks_df = pd.DataFrame()
        years = _get_break_years(breaks_df, "S1_MMD", penalty=3)
        assert years == set()

    def test_no_matching_method(self):
        """_get_break_years returns empty set when method not found."""
        from plot_divergence import _get_break_years

        breaks_df = pd.DataFrame(
            {
                "method": ["L1"],
                "detector": ["pelt"],
                "detector_params": ["pen=3"],
                "break_years": ["2007"],
            }
        )
        years = _get_break_years(breaks_df, "S1_MMD", penalty=3)
        assert years == set()


# ---------------------------------------------------------------------------
# Equal-N growth-bias correction (ticket 0045)
# ---------------------------------------------------------------------------


def _growth_counts(n_years=20, base=5, growth_factor=10):
    """Return per-year paper counts with linear growth for equal-n tests."""
    return [
        max(base, int(base + (growth_factor - 1) * base * i / (n_years - 1)))
        for i in range(n_years)
    ]


def _make_growth_data(n_years=20, start_year=2000, growth_factor=10, dim=16):
    """Synthetic corpus with growth for equal-n tests (semantic).

    Returns (df, emb) with ~few papers in early years and many later.
    """
    rng = np.random.RandomState(42)
    counts = _growth_counts(n_years, base=5, growth_factor=growth_factor)
    years = []
    vecs = []
    for i, n in enumerate(counts):
        y = start_year + i
        years.extend([y] * n)
        vecs.append(rng.randn(n, dim))
    df = pd.DataFrame({"year": years, "cited_by_count": 0})
    emb = np.vstack(vecs).astype(np.float32)
    return df, emb


def _make_growth_text_data(n_years=15, start_year=2000, growth_factor=10):
    """Synthetic corpus with growth for equal-n tests (lexical).

    Returns DataFrame with year + abstract columns.
    """
    rng = np.random.RandomState(42)
    words = ["climate", "finance", "carbon", "green", "bond", "risk", "policy"]
    counts = _growth_counts(n_years, base=6, growth_factor=growth_factor)
    rows = []
    for i, n in enumerate(counts):
        y = start_year + i
        for _ in range(n):
            text = " ".join(rng.choice(words, size=10))
            rows.append({"year": y, "abstract": text})
    return pd.DataFrame(rows)


def _equal_n_cfg(equal_n=True):
    """Minimal config for equal-n tests, built on _smoke_cfg."""
    cfg = _smoke_cfg(seed=42)
    cfg["divergence"]["windows"] = [2]
    cfg["divergence"]["max_subsample"] = 5000
    cfg["divergence"]["equal_n"] = equal_n
    return cfg


class TestEqualN:
    """Verify equal-n growth-bias correction for _iter_window_pairs."""

    def test_equal_n_produces_equal_sized_windows(self):
        """With equal_n, both windows should have the same number of samples."""
        from _divergence_semantic import _get_years_and_params, _iter_window_pairs

        df, emb = _make_growth_data()
        cfg = _equal_n_cfg(equal_n=True)
        years, min_papers, max_subsample, windows, _equal_n = _get_years_and_params(
            df, emb, cfg
        )
        rng = np.random.RandomState(42)

        for y, w, X, Y in _iter_window_pairs(
            df,
            emb,
            years,
            windows,
            min_papers,
            max_subsample,
            rng=rng,
            equal_n=True,
        ):
            assert len(X) == len(Y), (
                f"year={y}, w={w}: len(X)={len(X)} != len(Y)={len(Y)}"
            )

    def test_equal_n_false_allows_unequal(self):
        """Without equal_n, windows may have different sizes."""
        from _divergence_semantic import _get_years_and_params, _iter_window_pairs

        df, emb = _make_growth_data()
        cfg = _equal_n_cfg(equal_n=False)
        years, min_papers, max_subsample, windows, _equal_n = _get_years_and_params(
            df, emb, cfg
        )
        rng = np.random.RandomState(42)

        sizes = []
        for y, w, X, Y in _iter_window_pairs(
            df,
            emb,
            years,
            windows,
            min_papers,
            max_subsample,
            rng=rng,
            equal_n=False,
        ):
            sizes.append((len(X), len(Y)))

        # At least some pairs should be unequal in the growth data
        unequal = [pair for pair in sizes if pair[0] != pair[1]]
        assert len(unequal) > 0, "Expected some unequal window sizes in growth data"

    def test_equal_n_s2_not_correlated_with_size(self):
        """Corrected S2 energy should not strongly correlate with window size."""
        from _divergence_semantic import compute_s2_energy

        df, emb = _make_growth_data(n_years=20, growth_factor=10, dim=16)

        # With equal_n
        cfg_eq = _equal_n_cfg(equal_n=True)
        result_eq = compute_s2_energy(df, emb, cfg_eq)

        # Without equal_n
        cfg_raw = _equal_n_cfg(equal_n=False)
        result_raw = compute_s2_energy(df, emb, cfg_raw)

        if len(result_eq) < 3 or len(result_raw) < 3:
            pytest.skip("Not enough data points for correlation test")

        # Compute min(n_before, n_after) for each year
        year_counts = df["year"].value_counts().to_dict()
        w = 2  # single window

        def min_n_for_year(y):
            n_before = sum(year_counts.get(yy, 0) for yy in range(y - w, y + 1))
            n_after = sum(year_counts.get(yy, 0) for yy in range(y + 1, y + w + 2))
            return min(n_before, n_after)

        # Merge min_n into results
        for result in [result_eq, result_raw]:
            result["min_n"] = result["year"].apply(min_n_for_year)

        corr_eq = abs(result_eq["value"].corr(result_eq["min_n"]))
        corr_raw = abs(result_raw["value"].corr(result_raw["min_n"]))

        # The corrected version should have lower correlation with size.
        # Fallback: if both correlations are low (< 0.3), the correction is
        # not needed but isn't harmful -- accept that as a pass.  The previous
        # threshold of 0.5 was loose enough to mask regressions.
        assert corr_eq < corr_raw or corr_eq < 0.3, (
            f"equal_n correlation ({corr_eq:.3f}) not lower than raw ({corr_raw:.3f})"
        )

    def test_l1_js_equal_n_produces_equal_sized_inputs(self):
        """L1 JS subsampling path should equalise before/after text counts.

        Verifies at the iterator level that TF-IDF matrices have equal
        row counts when equal_n is True, not just that results are non-empty.
        """
        from _divergence_lexical import _iter_lexical_window_pairs, compute_l1_js

        df = _make_growth_text_data()
        cfg_eq = _equal_n_cfg(equal_n=True)
        cfg_raw = _equal_n_cfg(equal_n=False)

        # Verify that equal_n produces equal-sized TF-IDF windows
        for y, w, X_before, X_after, _vec in _iter_lexical_window_pairs(df, cfg_eq):
            assert X_before.shape[0] == X_after.shape[0], (
                f"year={y}, w={w}: before={X_before.shape[0]} != after={X_after.shape[0]}"
            )

        # Verify that raw (equal_n=False) produces at least some unequal windows
        sizes = []
        for y, w, X_before, X_after, _vec in _iter_lexical_window_pairs(df, cfg_raw):
            sizes.append((X_before.shape[0], X_after.shape[0]))
        unequal = [s for s in sizes if s[0] != s[1]]
        assert len(unequal) > 0, "Expected some unequal window sizes in growth data"

        # Both should still produce non-empty results via compute_l1_js
        result_eq = compute_l1_js(df, cfg_eq)
        result_raw = compute_l1_js(df, cfg_raw)
        assert len(result_eq) > 0, "equal_n L1 JS produced no results"
        assert len(result_raw) > 0, "raw L1 JS produced no results"


# ---------------------------------------------------------------------------
# G1 PageRank on disjoint sliding windows (ticket 0059)
# ---------------------------------------------------------------------------


class TestG1DisjointWindows:
    """G1 PageRank should distinguish similar vs different distributions
    even on disjoint sliding windows (ticket 0059).

    The old implementation compared per-node PageRank with union+zero-padding,
    which is meaningless on disjoint node sets. The fix uses distributional
    comparison (Jensen-Shannon divergence on PageRank value histograms).
    """

    def _g1_cfg(self):
        """Minimal config for G1 tests."""
        cfg = _smoke_cfg(seed=42)
        cfg["divergence"]["windows"] = [2]
        cfg["divergence"]["min_papers"] = 3
        cfg["divergence"]["min_papers_smoke"] = 3
        return cfg

    def test_g1_disjoint_windows_not_degenerate(self):
        """G1 must produce different values for similar vs different distributions.

        Pair A: two star graphs (both have concentrated PageRank) → low divergence.
        Pair B: star graph vs ring graph (concentrated vs uniform PageRank) → high divergence.
        """
        import networkx as nx
        from _citation_methods import _pagerank_vector

        # Build two star graphs (similar concentrated distributions)
        G_star1 = nx.DiGraph()
        G_star1.add_nodes_from([f"s1_{i}" for i in range(20)])
        for i in range(1, 20):
            G_star1.add_edge(f"s1_{i}", "s1_0")
        pr_star1 = _pagerank_vector(G_star1, damping=0.85)

        G_star2 = nx.DiGraph()
        G_star2.add_nodes_from([f"s2_{i}" for i in range(20)])
        for i in range(1, 20):
            G_star2.add_edge(f"s2_{i}", "s2_0")
        pr_star2 = _pagerank_vector(G_star2, damping=0.85)

        # Build a ring graph (uniform distribution)
        G_ring = nx.DiGraph()
        ring_nodes = [f"r_{i}" for i in range(20)]
        G_ring.add_nodes_from(ring_nodes)
        for i in range(20):
            G_ring.add_edge(ring_nodes[i], ring_nodes[(i + 1) % 20])
        pr_ring = _pagerank_vector(G_ring, damping=0.85)

        assert pr_star1 is not None
        assert pr_star2 is not None
        assert pr_ring is not None

        # Node sets are completely disjoint in all cases
        assert set(pr_star1[0]).isdisjoint(set(pr_star2[0]))
        assert set(pr_star1[0]).isdisjoint(set(pr_ring[0]))

        # Now use the actual comparison method from G1
        from _citation_methods import _compare_pagerank_distributions

        # Similar distributions (star vs star) → low divergence
        val_similar = _compare_pagerank_distributions(pr_star1, pr_star2)
        # Different distributions (star vs ring) → high divergence
        val_different = _compare_pagerank_distributions(pr_star1, pr_ring)

        assert not np.isnan(val_similar), "Similar pair should not be NaN"
        assert not np.isnan(val_different), "Different pair should not be NaN"
        assert val_different > val_similar, (
            f"Star-vs-ring ({val_different:.4f}) should exceed "
            f"star-vs-star ({val_similar:.4f})"
        )

    def test_g1_output_matches_schema(self):
        """G1 output should match DivergenceSchema regardless of implementation."""
        from _citation_methods import compute_g1_pagerank
        from schemas import DivergenceSchema

        # Create a synthetic corpus spanning years 2005-2015 so that
        # _iter_sliding_pairs (window=2) produces valid pairs.
        # Each year gets 5 papers with star-topology edges.
        rows = []
        edge_rows = []
        for y in range(2005, 2016):
            prefix = f"y{y}"
            center = f"{prefix}_0"
            nodes = [center] + [f"{prefix}_{i}" for i in range(1, 5)]
            for n in nodes:
                rows.append({"doi": n, "year": y, "cited_by_count": 10})
            for i in range(1, 5):
                edge_rows.append(
                    {
                        "source_doi": f"{prefix}_{i}",
                        "ref_doi": center,
                        "source_year": y,
                    }
                )

        works = pd.DataFrame(rows)
        internal_edges = pd.DataFrame(edge_rows)
        citations = internal_edges.copy()
        citations["ref_year"] = citations["source_year"]

        cfg = self._g1_cfg()
        result = compute_g1_pagerank(works, citations, internal_edges, cfg)

        assert len(result) > 0, "G1 should produce at least one row"
        assert set(result.columns) == {"year", "window", "hyperparams", "value"}

        # Add channel column for schema validation
        result["channel"] = "citation"
        DivergenceSchema.validate(result)

    def test_g1_value_bounded_0_1(self):
        """Jensen-Shannon divergence squared is bounded in [0, 1]."""
        import networkx as nx
        from _citation_methods import _compare_pagerank_distributions, _pagerank_vector

        # Star graph
        G1 = nx.DiGraph()
        G1.add_nodes_from(range(20))
        for i in range(1, 20):
            G1.add_edge(i, 0)

        # Chain graph
        G2 = nx.DiGraph()
        G2.add_nodes_from(range(100, 120))
        for i in range(100, 119):
            G2.add_edge(i, i + 1)

        pr1 = _pagerank_vector(G1, 0.85)
        pr2 = _pagerank_vector(G2, 0.85)
        assert pr1 is not None and pr2 is not None

        val = _compare_pagerank_distributions(pr1, pr2)
        assert 0.0 <= val <= 1.0, f"Value {val} out of [0, 1] bounds"
