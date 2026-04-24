"""Permutation null model drivers for G1, G5, G6, G8 citation methods.

Extracted from compute_null_model.py to keep that module under 800 lines.
All drivers follow the _build_union_digraph / node-permutation pattern:
  1. Build G_before and G_after for each (year, window)
  2. Compute the observed statistic abs(metric(G_after) - metric(G_before))
  3. Pool all nodes into a directed union graph
  4. For each permutation: shuffle node-to-window assignment, recompute metric
"""

import numpy as np
import pandas as pd
from _divergence_io import _make_window_rngs
from utils import get_logger

log = get_logger("_permutation_citation")


# ---------------------------------------------------------------------------
# Tiny row helpers (mirrored from compute_null_model._result_row etc.)
# ---------------------------------------------------------------------------


def _result_row(year, window, observed, null_mean, null_std, z, p):
    return {
        "year": year,
        "window": str(window),
        "observed": observed,
        "null_mean": null_mean,
        "null_std": null_std,
        "z_score": z,
        "p_value": p,
    }


def _nan_row(year, window):
    return _result_row(year, window, np.nan, np.nan, np.nan, np.nan, np.nan)


def _finalize_row(y, w, observed, null_stats):
    null_mean = float(np.mean(null_stats))
    null_std = float(np.std(null_stats))
    z = (observed - null_mean) / null_std if null_std > 0 else 0.0
    p_value = float(np.mean(null_stats >= observed))
    log.info("  year=%d window=%d z=%.2f p=%.3f", y, w, z, p_value)
    return _result_row(y, w, observed, null_mean, null_std, z, p_value)


# ---------------------------------------------------------------------------
# Shared helper: node-permutation null distribution for abs-diff methods
# ---------------------------------------------------------------------------


def _node_permutation_null_distribution(
    G_union, all_nodes, n_before, n_perm, perm_rng, metric_fn
):
    """Shuffle node-to-window assignments and recompute |Δ metric| per permutation.

    Used by G5, G6, G8 — any method whose statistic is
    abs(metric(G_after) - metric(G_before)) for a scalar graph metric.
    """
    null_stats = np.empty(n_perm)
    for i in range(n_perm):
        perm = perm_rng.permutation(len(all_nodes))
        before_set = {all_nodes[j] for j in perm[:n_before]}
        after_set = {all_nodes[j] for j in perm[n_before:]}
        val_b = metric_fn(G_union.subgraph(before_set))
        val_a = metric_fn(G_union.subgraph(after_set))
        if np.isnan(val_b) or np.isnan(val_a):
            null_stats[i] = np.nan
        else:
            null_stats[i] = abs(val_a - val_b)
    return null_stats[~np.isnan(null_stats)]


def _build_union_digraph(G_before, G_after, internal_edges):
    """Build a directed union graph from two window DiGraphs.

    Unlike _build_union_graph (undirected, for community detection), this
    preserves edge direction so in-degree metrics work on subgraphs.
    """
    import networkx as nx

    union_nodes = set(G_before.nodes()) | set(G_after.nodes())
    G_union = nx.DiGraph()
    G_union.add_nodes_from(union_nodes)

    mask = internal_edges["source_doi"].isin(union_nodes) & internal_edges[
        "ref_doi"
    ].isin(union_nodes)
    edges = internal_edges.loc[mask, ["source_doi", "ref_doi"]].values
    G_union.add_edges_from(edges)
    return G_union


def _abs_diff_one_window(y, w, works, internal_edges, n_perm, seed, metric_fn, gap=1):
    """Process one (year, window) for any abs-diff citation null model.

    Shared scaffold for G5, G6, G8.
    """
    from _divergence_citation import _sliding_window_graph

    _, perm_rng = _make_window_rngs(seed, y, w)

    G_before = _sliding_window_graph(works, internal_edges, y, w, "before", gap=gap)
    G_after = _sliding_window_graph(works, internal_edges, y, w, "after", gap=gap)

    before_nodes = list(G_before.nodes())
    after_nodes = list(G_after.nodes())

    if len(before_nodes) < 3 or len(after_nodes) < 3:
        return _nan_row(y, w)

    val_b_obs = metric_fn(G_before)
    val_a_obs = metric_fn(G_after)
    if np.isnan(val_b_obs) or np.isnan(val_a_obs):
        return _nan_row(y, w)
    observed = abs(val_a_obs - val_b_obs)

    G_union = _build_union_digraph(G_before, G_after, internal_edges)
    all_nodes = before_nodes + after_nodes
    n_before_count = len(before_nodes)

    null_stats = _node_permutation_null_distribution(
        G_union, all_nodes, n_before_count, n_perm, perm_rng, metric_fn
    )

    if len(null_stats) == 0:
        return _nan_row(y, w)

    return _finalize_row(y, w, observed, null_stats)


def _run_abs_diff_permutations(
    label, metric_fn, works, internal_edges, div_df, cfg, n_jobs=1, n_perm_override=None
):
    """Parallel permutation test for any abs-diff citation scalar metric.

    Parameters
    ----------
    label : str
        Method label for logging (e.g. "G6").
    metric_fn : callable(G) -> float
        Graph scalar metric.
    n_perm_override : int or None
        If set, caps n_perm to this value (used by G8 for tractability).

    """
    from joblib import Parallel, delayed

    div_cfg = cfg["divergence"]
    n_perm = div_cfg["permutation"]["n_perm"]
    if n_perm_override is not None and n_perm > n_perm_override:
        log.warning(
            "%s: capping n_perm from %d to %d for tractability",
            label,
            n_perm,
            n_perm_override,
        )
        n_perm = n_perm_override

    seed = div_cfg["random_seed"]
    gap = div_cfg.get("gap", 1)

    year_windows = div_df[["year", "window"]].drop_duplicates()
    pairs = [
        (int(row["year"]), int(row["window"])) for _, row in year_windows.iterrows()
    ]

    log.info(
        "%s parallel: %d (year, window) pairs, n_jobs=%d", label, len(pairs), n_jobs
    )
    rows = Parallel(n_jobs=n_jobs)(
        delayed(_abs_diff_one_window)(
            y, w, works, internal_edges, n_perm, seed, metric_fn, gap=gap
        )
        for y, w in pairs
    )
    for row in rows:
        log.info(
            "  year=%d window=%s z=%.2f p=%.3f",
            row["year"],
            row["window"],
            row["z_score"],
            row["p_value"],
        )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# G6: Citation entropy null model
# ---------------------------------------------------------------------------


def _run_g6_permutations(works, internal_edges, div_df, cfg, n_jobs=1):
    """Permutation test for G6 citation entropy divergence."""
    from _citation_methods import _citation_entropy

    return _run_abs_diff_permutations(
        "G6", _citation_entropy, works, internal_edges, div_df, cfg, n_jobs=n_jobs
    )


# ---------------------------------------------------------------------------
# G8: Betweenness centrality null model
# ---------------------------------------------------------------------------

_G8_MAX_N_PERM = 50  # betweenness inside permutation loop is expensive


def _run_g8_permutations(works, internal_edges, div_df, cfg, n_jobs=1):
    """Permutation test for G8 betweenness centrality divergence.

    n_perm is capped at 50 because betweenness is O(n*m) per permutation.
    """
    from _citation_methods import _mean_betweenness

    max_nodes = cfg["divergence"]["citation"]["G8_betweenness"]["max_nodes"]

    def _betweenness(G):
        return _mean_betweenness(G, max_nodes)

    return _run_abs_diff_permutations(
        "G8",
        _betweenness,
        works,
        internal_edges,
        div_df,
        cfg,
        n_jobs=n_jobs,
        n_perm_override=_G8_MAX_N_PERM,
    )


# ---------------------------------------------------------------------------
# G5: Preferential attachment exponent null model
# ---------------------------------------------------------------------------


def _run_g5_permutations(works, internal_edges, div_df, cfg, n_jobs=1):
    """Permutation test for G5 preferential attachment exponent divergence."""
    from _citation_methods import _pa_exponent

    return _run_abs_diff_permutations(
        "G5", _pa_exponent, works, internal_edges, div_df, cfg, n_jobs=n_jobs
    )


# ---------------------------------------------------------------------------
# G1: PageRank distribution null model
# ---------------------------------------------------------------------------


def _g1_pagerank_one_window(
    y, w, works, internal_edges, n_perm, seed, damping, n_bins, gap=1
):
    """Process one (year, window) for G1 PageRank null model."""
    from _citation_methods import _compare_pagerank_distributions, _pagerank_vector
    from _divergence_citation import _sliding_window_graph

    _, perm_rng = _make_window_rngs(seed, y, w)

    G_before = _sliding_window_graph(works, internal_edges, y, w, "before", gap=gap)
    G_after = _sliding_window_graph(works, internal_edges, y, w, "after", gap=gap)

    before_nodes = list(G_before.nodes())
    after_nodes = list(G_after.nodes())

    if len(before_nodes) < 3 or len(after_nodes) < 3:
        return _nan_row(y, w)

    pr_b_obs = _pagerank_vector(G_before, damping)
    pr_a_obs = _pagerank_vector(G_after, damping)
    if pr_b_obs is None or pr_a_obs is None:
        return _nan_row(y, w)

    observed = _compare_pagerank_distributions(pr_b_obs, pr_a_obs, n_bins)
    if np.isnan(observed):
        return _nan_row(y, w)

    G_union = _build_union_digraph(G_before, G_after, internal_edges)
    all_nodes = before_nodes + after_nodes
    n_before_count = len(before_nodes)

    null_stats = np.empty(n_perm)
    for i in range(n_perm):
        perm = perm_rng.permutation(len(all_nodes))
        before_set = [all_nodes[j] for j in perm[:n_before_count]]
        after_set = [all_nodes[j] for j in perm[n_before_count:]]
        pr_b_perm = _pagerank_vector(G_union.subgraph(before_set), damping)
        pr_a_perm = _pagerank_vector(G_union.subgraph(after_set), damping)
        if pr_b_perm is None or pr_a_perm is None:
            null_stats[i] = np.nan
        else:
            val = _compare_pagerank_distributions(pr_b_perm, pr_a_perm, n_bins)
            null_stats[i] = val if not np.isnan(val) else np.nan

    null_stats = null_stats[~np.isnan(null_stats)]
    if len(null_stats) == 0:
        return _nan_row(y, w)

    return _finalize_row(y, w, observed, null_stats)


def _run_g1_permutations(works, internal_edges, div_df, cfg, n_jobs=1):
    """Permutation test for G1 PageRank distribution divergence."""
    from joblib import Parallel, delayed

    div_cfg = cfg["divergence"]
    n_perm = div_cfg["permutation"]["n_perm"]
    seed = div_cfg["random_seed"]
    gap = div_cfg.get("gap", 1)
    g1_cfg = div_cfg["citation"]["G1_pagerank"]
    damping = g1_cfg["damping"]
    n_bins = g1_cfg.get("n_bins", 20)

    year_windows = div_df[["year", "window"]].drop_duplicates()
    pairs = [
        (int(row["year"]), int(row["window"])) for _, row in year_windows.iterrows()
    ]

    log.info("G1 parallel: %d (year, window) pairs, n_jobs=%d", len(pairs), n_jobs)
    rows = Parallel(n_jobs=n_jobs)(
        delayed(_g1_pagerank_one_window)(
            y, w, works, internal_edges, n_perm, seed, damping, n_bins, gap=gap
        )
        for y, w in pairs
    )
    for row in rows:
        log.info(
            "  year=%d window=%s z=%.2f p=%.3f",
            row["year"],
            row["window"],
            row["z_score"],
            row["p_value"],
        )
    return pd.DataFrame(rows)
