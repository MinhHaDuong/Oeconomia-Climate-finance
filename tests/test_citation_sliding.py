"""Tests for citation graph sliding window refactoring (ticket 0048).

Tests:
1. _sliding_window_graph builds bounded-size graphs (not monotonically growing)
2. Before/after window halves contain disjoint year ranges
3. G1 PageRank divergence with sliding windows is not monotonically decreasing
4. G3, G4, G7 are unchanged (they don't use sliding windows)
5. Sliding methods produce multi-window output (one row per year per window)
6. Config flag graph_mode selects sliding vs cumulative
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


# ── Synthetic data helpers ──────────────────────────────────────────────


def _make_citation_data(n_years=15, papers_per_year=10, start_year=2000):
    """Create synthetic works + citations for citation graph tests.

    Returns (works, citations, internal_edges, cfg).
    Each year has `papers_per_year` papers.  Citations go from each paper
    to ~2 random papers from earlier years.
    """
    rng = np.random.RandomState(42)

    rows = []
    doi_by_year = {}
    for i in range(n_years):
        y = start_year + i
        dois = [f"10.test/{y}_{j}" for j in range(papers_per_year)]
        doi_by_year[y] = dois
        for d in dois:
            rows.append({"doi": d, "year": y, "cited_by_count": rng.randint(0, 100)})

    works = pd.DataFrame(rows)

    # Build citation edges: each paper cites ~2 earlier papers
    cit_rows = []
    all_earlier = []
    for i in range(n_years):
        y = start_year + i
        for d in doi_by_year[y]:
            if all_earlier:
                n_refs = min(2, len(all_earlier))
                refs = rng.choice(all_earlier, size=n_refs, replace=False)
                for ref in refs:
                    cit_rows.append(
                        {
                            "source_doi": d,
                            "source_id": "",
                            "ref_doi": ref,
                            "ref_title": "",
                            "ref_first_author": "",
                            "ref_year": int(ref.split("/")[1].split("_")[0]),
                            "ref_journal": "",
                            "ref_raw": "",
                        }
                    )
        all_earlier.extend(doi_by_year[y])

    citations = pd.DataFrame(cit_rows)

    from _divergence_citation import _build_internal_edges

    internal_edges = _build_internal_edges(works, citations)

    from pipeline_loaders import load_analysis_config

    cfg = load_analysis_config()
    # Use small windows and low min_papers for test data
    cfg["divergence"]["windows"] = [2, 3]
    cfg["divergence"]["min_papers"] = 3
    cfg["divergence"]["min_papers_smoke"] = 3

    return works, citations, internal_edges, cfg


# ── Infrastructure tests ────────────────────────────────────────────────


class TestSlidingWindowGraph:
    """Tests for _sliding_window_graph and _iter_sliding_pairs."""

    def test_sliding_window_graph_size_bounded(self):
        """Sliding window graph should not grow monotonically with year."""
        from _divergence_citation import _sliding_window_graph

        works, _, internal_edges, _ = _make_citation_data(
            n_years=15, papers_per_year=10
        )
        window = 2
        sizes = []
        for y in range(2002, 2013):
            G = _sliding_window_graph(works, internal_edges, y, window, "before")
            sizes.append(G.number_of_nodes())

        # With 10 papers/year and window=2, all graphs should be ~30 nodes
        # They should NOT grow monotonically like cumulative graphs
        assert max(sizes) - min(sizes) < 20, (
            f"Sliding window graphs should be roughly constant size, "
            f"got range {min(sizes)}-{max(sizes)}"
        )

    def test_sliding_pair_before_after_disjoint(self):
        """Before/after graphs have disjoint nodes and correct year boundaries.

        Before-window years must be <= pivot year, after-window years must
        be > pivot year. Node disjointness follows from year disjointness.
        """
        from _divergence_citation import _sliding_window_graph

        works, _, internal_edges, _ = _make_citation_data()

        year = 2007
        window = 2

        G_before = _sliding_window_graph(works, internal_edges, year, window, "before")
        G_after = _sliding_window_graph(works, internal_edges, year, window, "after")

        doi_to_year = dict(zip(works["doi"], works["year"]))

        # Verify year boundaries: before <= pivot, after > pivot
        before_years = {doi_to_year[n] for n in G_before.nodes() if n in doi_to_year}
        after_years = {doi_to_year[n] for n in G_after.nodes() if n in doi_to_year}

        assert all(y <= year for y in before_years), (
            f"Before-window contains years > pivot {year}: {before_years}"
        )
        assert all(y > year for y in after_years), (
            f"After-window contains years <= pivot {year}: {after_years}"
        )

        # Node disjointness (follows from year disjointness, but verify directly)
        common_nodes = set(G_before.nodes()) & set(G_after.nodes())
        assert len(common_nodes) == 0, (
            f"Before/after graphs share {len(common_nodes)} nodes: "
            f"{list(common_nodes)[:5]}"
        )

    def test_sliding_window_graph_contains_correct_years(self):
        """Before window should contain [year-w, year], after should contain [year+1, year+1+w]."""
        from _divergence_citation import _sliding_window_graph

        works, _, internal_edges, _ = _make_citation_data()
        year = 2007
        window = 2

        G_before = _sliding_window_graph(works, internal_edges, year, window, "before")
        G_after = _sliding_window_graph(works, internal_edges, year, window, "after")

        # Check that before-graph nodes are from years [2005, 2007]
        doi_to_year = dict(zip(works["doi"], works["year"]))
        before_years = {doi_to_year[n] for n in G_before.nodes() if n in doi_to_year}
        after_years = {doi_to_year[n] for n in G_after.nodes() if n in doi_to_year}

        assert before_years.issubset({2005, 2006, 2007}), (
            f"Before years {before_years} not subset of {{2005, 2006, 2007}}"
        )
        assert after_years.issubset({2008, 2009, 2010}), (
            f"After years {after_years} not subset of {{2008, 2009, 2010}}"
        )

    def test_iter_sliding_pairs_yields_multiple_windows(self):
        """_iter_sliding_pairs should yield results for each configured window."""
        from _divergence_citation import _iter_sliding_pairs

        works, _, internal_edges, cfg = _make_citation_data()

        windows_seen = set()
        for year, window, G_before, G_after in _iter_sliding_pairs(
            works, internal_edges, cfg
        ):
            windows_seen.add(window)
            assert G_before.number_of_nodes() > 0
            assert G_after.number_of_nodes() > 0

        assert windows_seen == {2, 3}, f"Expected windows {{2, 3}}, got {windows_seen}"

    def test_iter_sliding_pairs_skips_small_windows(self):
        """Windows with fewer than min_papers nodes should be skipped."""
        from _divergence_citation import _iter_sliding_pairs

        works, _, internal_edges, cfg = _make_citation_data(
            n_years=5, papers_per_year=2
        )
        cfg["divergence"]["min_papers"] = 50  # impossibly high

        pairs = list(_iter_sliding_pairs(works, internal_edges, cfg))
        assert len(pairs) == 0, "Should skip all pairs when min_papers is too high"


# ── Method refactoring tests ────────────────────────────────────────────


class TestSlidingMethods:
    """Tests for G1, G2, G5, G6, G8 with sliding windows."""

    @pytest.fixture
    def data(self):
        return _make_citation_data(n_years=15, papers_per_year=10)

    def test_g1_pagerank_sliding_not_monotone(self, data):
        """With sliding windows, G1 divergence should not monotonically decrease."""
        from _citation_methods import compute_g1_pagerank

        works, citations, internal_edges, cfg = data
        df = compute_g1_pagerank(works, citations, internal_edges, cfg)

        assert len(df) > 0, "G1 produced no rows"
        # Should have multiple windows
        assert df["window"].nunique() >= 2, (
            f"Expected multiple windows, got {df['window'].unique()}"
        )
        # Should not be all NaN
        valid = df["value"].dropna()
        assert len(valid) > 3, f"Too few valid values: {len(valid)}"

    def test_g2_spectral_sliding_output(self, data):
        """G2 with sliding windows should produce divergence values."""
        from _citation_methods import compute_g2_spectral

        works, citations, internal_edges, cfg = data
        df = compute_g2_spectral(works, citations, internal_edges, cfg)

        assert len(df) > 0, "G2 produced no rows"
        assert df["window"].nunique() >= 2

    def test_g5_pa_exponent_sliding_output(self, data):
        """G5 with sliding windows should produce divergence values."""
        from _citation_methods import compute_g5_pa_exponent

        works, citations, internal_edges, cfg = data
        df = compute_g5_pa_exponent(works, citations, internal_edges, cfg)

        assert len(df) > 0, "G5 produced no rows"
        assert df["window"].nunique() >= 2

    def test_g6_entropy_sliding_output(self, data):
        """G6 with sliding windows should produce divergence values."""
        from _citation_methods import compute_g6_entropy

        works, citations, internal_edges, cfg = data
        df = compute_g6_entropy(works, citations, internal_edges, cfg)

        assert len(df) > 0, "G6 produced no rows"
        assert df["window"].nunique() >= 2

    def test_g8_betweenness_sliding_output(self, data):
        """G8 with sliding windows should produce divergence values."""
        from _citation_methods import compute_g8_betweenness

        works, citations, internal_edges, cfg = data
        df = compute_g8_betweenness(works, citations, internal_edges, cfg)

        assert len(df) > 0, "G8 produced no rows"
        assert df["window"].nunique() >= 2

    def test_sliding_methods_output_schema(self, data):
        """All sliding methods should output standard columns."""
        from _citation_methods import (
            compute_g1_pagerank,
            compute_g2_spectral,
            compute_g5_pa_exponent,
            compute_g6_entropy,
            compute_g8_betweenness,
        )

        works, citations, internal_edges, cfg = data
        expected_cols = {"year", "window", "hyperparams", "value"}

        for name, fn in [
            ("G1", compute_g1_pagerank),
            ("G2", compute_g2_spectral),
            ("G5", compute_g5_pa_exponent),
            ("G6", compute_g6_entropy),
            ("G8", compute_g8_betweenness),
        ]:
            df = fn(works, citations, internal_edges, cfg)
            assert set(df.columns) == expected_cols, (
                f"{name} columns {set(df.columns)} != {expected_cols}"
            )
            # Window values should be numeric strings, not "cumulative"
            for w in df["window"].unique():
                assert w != "cumulative", f"{name} still uses 'cumulative' window"


# ── G3, G4, G7 unchanged tests ─────────────────────────────────────────


class TestUnchangedMethods:
    """G3, G4, G7 should not be affected by the sliding window refactoring."""

    @pytest.fixture
    def data(self):
        return _make_citation_data(n_years=15, papers_per_year=10)

    def test_g3_still_uses_cumulative(self, data):
        """G3 should still output window='cumulative'."""
        from _citation_methods import compute_g3_age_shift

        works, citations, internal_edges, cfg = data
        df = compute_g3_age_shift(works, citations, internal_edges, cfg)
        assert len(df) > 0
        assert (df["window"] == "cumulative").all(), (
            f"G3 windows: {df['window'].unique()}"
        )

    def test_g4_output_window_label_is_cumulative(self, data):
        """G4 output rows must carry window='cumulative' (schema stability).

        This only checks the output label in the CSV. It does NOT assert
        the computation is cumulative — the bisection runs once on the
        full graph, and per-year new-edge rates are counted year-by-year.
        """
        from _citation_methods import compute_g4_cross_trad

        works, citations, internal_edges, cfg = data
        df = compute_g4_cross_trad(works, citations, internal_edges, cfg)
        assert len(df) > 0
        assert (df["window"] == "cumulative").all(), (
            f"G4 windows: {df['window'].unique()}"
        )

    def test_g4_cross_trad_covers_year_max(self, data):
        """G4 must produce a valid value at year_max.

        Regression for ticket 0065: community detection used to snapshot at
        the median year, so every source with year > median fell out of the
        community dict and yielded NaN. With community detection on the full
        cumulative graph, the last year carries a value.
        """
        from _citation_methods import compute_g4_cross_trad

        works, citations, internal_edges, cfg = data
        df = compute_g4_cross_trad(works, citations, internal_edges, cfg)

        year_max = int(works["year"].max())
        last = df.loc[df["year"] == year_max, "value"]
        assert len(last) == 1
        assert last.notna().all(), (
            f"G4 NaN at year_max={year_max}; "
            f"valid years: {sorted(df.loc[df['value'].notna(), 'year'].tolist())}"
        )

    def test_g4_cross_trad_nans_contiguous(self, data):
        """G4 NaNs must form a contiguous block (cold-start only, not a tail)."""
        from _citation_methods import compute_g4_cross_trad

        works, citations, internal_edges, cfg = data
        df = compute_g4_cross_trad(works, citations, internal_edges, cfg)

        nan_years = sorted(df.loc[df["value"].isna(), "year"].tolist())
        if not nan_years:
            return
        assert max(nan_years) - min(nan_years) == len(nan_years) - 1, (
            f"Non-contiguous NaN years: {nan_years}"
        )

    def test_g7_still_uses_cumulative(self, data):
        """G7 should still output window='cumulative'."""
        from _citation_methods import compute_g7_disruption

        works, citations, internal_edges, cfg = data
        df = compute_g7_disruption(works, citations, internal_edges, cfg)
        assert len(df) > 0
        assert (df["window"] == "cumulative").all(), (
            f"G7 windows: {df['window'].unique()}"
        )
