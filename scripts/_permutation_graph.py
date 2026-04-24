"""Permutation null model drivers for undirected graph methods (G2, G9).

G2 — spectral gap divergence (|Δ spectral gap|)
G9 — community divergence (JS^2 of community distributions)

Private module — no main, no argparse.  Called by compute_null_model.py.
"""

import numpy as np
import pandas as pd
from _permutation_io import _finalize_row, _make_window_rngs, _nan_row, _result_row
from utils import get_logger

log = get_logger("_permutation_graph")


# ---------------------------------------------------------------------------
# G9: Community divergence
# ---------------------------------------------------------------------------


def _community_node_comm_map(partition):
    """Build sorted community list and node->community-index lookup.

    Returns (n_communities, comm_to_idx) or None if < 2 communities.
    """
    all_communities = sorted(set(partition.values()))
    n_communities = len(all_communities)
    if n_communities < 2:
        return None
    comm_to_idx = {c: i for i, c in enumerate(all_communities)}
    return n_communities, comm_to_idx


def _community_null_distribution(
    all_nodes, n_before, node_comm, n_communities, n_perm, perm_rng
):
    """Shuffle node-to-window assignments and compute JS^2 for each permutation.

    Returns null_stats array (NaN entries removed).
    """
    from scipy.spatial.distance import jensenshannon

    null_stats = np.empty(n_perm)
    for i in range(n_perm):
        perm_indices = perm_rng.permutation(len(all_nodes))
        p_bef = np.zeros(n_communities)
        p_aft = np.zeros(n_communities)

        for j in perm_indices[:n_before]:
            node = all_nodes[j]
            if node in node_comm:
                p_bef[node_comm[node]] += 1

        for j in perm_indices[n_before:]:
            node = all_nodes[j]
            if node in node_comm:
                p_aft[node_comm[node]] += 1

        if p_bef.sum() == 0 or p_aft.sum() == 0:
            null_stats[i] = np.nan
            continue

        p_bef = p_bef / p_bef.sum()
        p_aft = p_aft / p_aft.sum()
        js = jensenshannon(p_bef, p_aft)
        null_stats[i] = float(js**2)

    return null_stats[~np.isnan(null_stats)]


def _g9_one_window(y, w, works, internal_edges, n_perm, seed, resolution, gap=1):
    """Process one (year, window) for G9 community permutation test."""
    import community as community_louvain
    from _divergence_citation import _sliding_window_graph
    from _divergence_community import _build_union_graph, _community_js_for_pair

    _, perm_rng = _make_window_rngs(seed, y, w)

    G_before = _sliding_window_graph(works, internal_edges, y, w, "before", gap=gap)
    G_after = _sliding_window_graph(works, internal_edges, y, w, "after", gap=gap)

    before_nodes = list(G_before.nodes())
    after_nodes = list(G_after.nodes())

    if len(before_nodes) < 3 or len(after_nodes) < 3:
        return _nan_row(y, w)

    observed = _community_js_for_pair(
        G_before, G_after, internal_edges, resolution, seed
    )
    if np.isnan(observed):
        return _nan_row(y, w)

    G_union = _build_union_graph(G_before, G_after, internal_edges)
    if G_union.number_of_nodes() < 3 or G_union.number_of_edges() < 1:
        return _nan_row(y, w)

    partition = community_louvain.best_partition(
        G_union, resolution=resolution, random_state=seed
    )

    comm_info = _community_node_comm_map(partition)
    if comm_info is None:
        return _result_row(y, w, observed, 0.0, 0.0, 0.0, 1.0)

    n_communities, comm_to_idx = comm_info

    all_nodes = before_nodes + after_nodes
    n_before_count = len(before_nodes)

    node_comm = {
        node: comm_to_idx[partition[node]] for node in all_nodes if node in partition
    }

    null_stats = _community_null_distribution(
        all_nodes, n_before_count, node_comm, n_communities, n_perm, perm_rng
    )

    if len(null_stats) == 0:
        return _nan_row(y, w)

    return _finalize_row(y, w, observed, null_stats)


def _run_g9_community_permutations(works, internal_edges, div_df, cfg, n_jobs=1):
    """Permutation test for G9 community divergence (parallel across windows)."""
    from joblib import Parallel, delayed

    div_cfg = cfg["divergence"]
    n_perm = div_cfg["permutation"]["n_perm"]
    seed = div_cfg["random_seed"]
    gap = div_cfg.get("gap", 1)
    resolution = (
        div_cfg.get("citation", {}).get("G9_community", {}).get("resolution", 1.0)
    )

    year_windows = div_df[["year", "window"]].drop_duplicates()
    pairs = [
        (int(row["year"]), int(row["window"])) for _, row in year_windows.iterrows()
    ]

    log.info("G9 parallel: %d (year, window) pairs, n_jobs=%d", len(pairs), n_jobs)
    rows = Parallel(n_jobs=n_jobs)(
        delayed(_g9_one_window)(
            y, w, works, internal_edges, n_perm, seed, resolution, gap=gap
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
# G2: Spectral gap divergence
# ---------------------------------------------------------------------------


def _spectral_null_distribution(G_union, all_nodes, n_before, n_perm, perm_rng):
    """Shuffle node-to-window assignments and recompute |Δ spectral gap|."""
    from _citation_methods import _spectral_gap

    null_stats = np.empty(n_perm)
    for i in range(n_perm):
        perm = perm_rng.permutation(len(all_nodes))
        before_set = {all_nodes[j] for j in perm[:n_before]}
        after_set = {all_nodes[j] for j in perm[n_before:]}
        gap_b = _spectral_gap(G_union.subgraph(before_set))
        gap_a = _spectral_gap(G_union.subgraph(after_set))
        if np.isnan(gap_b) or np.isnan(gap_a):
            null_stats[i] = np.nan
        else:
            null_stats[i] = abs(gap_a - gap_b)
    return null_stats[~np.isnan(null_stats)]


def _g2_spectral_one_window(y, w, works, internal_edges, n_perm, seed, gap=1):
    """Process one (year, window) for G2 spectral permutation test."""
    from _citation_methods import _spectral_gap
    from _divergence_citation import _sliding_window_graph
    from _divergence_community import _build_union_graph

    _, perm_rng = _make_window_rngs(seed, y, w)

    G_before = _sliding_window_graph(works, internal_edges, y, w, "before", gap=gap)
    G_after = _sliding_window_graph(works, internal_edges, y, w, "after", gap=gap)

    before_nodes = list(G_before.nodes())
    after_nodes = list(G_after.nodes())

    if len(before_nodes) < 3 or len(after_nodes) < 3:
        return _nan_row(y, w)

    gap_b_obs = _spectral_gap(G_before)
    gap_a_obs = _spectral_gap(G_after)
    if np.isnan(gap_b_obs) or np.isnan(gap_a_obs):
        return _nan_row(y, w)
    observed = abs(gap_a_obs - gap_b_obs)

    G_union = _build_union_graph(G_before, G_after, internal_edges)
    all_nodes = before_nodes + after_nodes
    n_before_count = len(before_nodes)

    null_stats = _spectral_null_distribution(
        G_union, all_nodes, n_before_count, n_perm, perm_rng
    )

    if len(null_stats) == 0:
        return _nan_row(y, w)

    return _finalize_row(y, w, observed, null_stats)


def _run_g2_spectral_permutations(works, internal_edges, div_df, cfg, n_jobs=1):
    """Permutation test for G2 spectral-gap divergence (parallel across windows)."""
    from joblib import Parallel, delayed

    div_cfg = cfg["divergence"]
    n_perm = div_cfg["permutation"]["n_perm"]
    seed = div_cfg["random_seed"]
    gap = div_cfg.get("gap", 1)

    year_windows = div_df[["year", "window"]].drop_duplicates()
    pairs = [
        (int(row["year"]), int(row["window"])) for _, row in year_windows.iterrows()
    ]

    log.info("G2 parallel: %d (year, window) pairs, n_jobs=%d", len(pairs), n_jobs)
    rows = Parallel(n_jobs=n_jobs)(
        delayed(_g2_spectral_one_window)(
            y, w, works, internal_edges, n_perm, seed, gap=gap
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
