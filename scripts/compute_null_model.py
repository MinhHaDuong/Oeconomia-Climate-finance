"""Compute permutation Z-score null model for one divergence method.

For each (year, window) in the existing divergence CSV, permute labels
B times and recompute the statistic to build a null distribution.
Z(t) = (observed - mean_perm) / std_perm.

Usage:
    uv run python scripts/compute_null_model.py --method S2_energy \
        --output content/tables/tab_null_S2_energy.csv \
        --div-csv content/tables/tab_div_S2_energy.csv

    # Smoke fixture:
    CLIMATE_FINANCE_DATA=tests/fixtures/smoke \
        uv run python scripts/compute_null_model.py --method S2_energy \
        --output /tmp/tab_null_S2_energy.csv \
        --div-csv /tmp/tab_div_S2_energy.csv
"""

import argparse

import numpy as np
import pandas as pd
from compute_divergence import METHODS
from pipeline_loaders import load_analysis_config
from schemas import NullModelSchema
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("compute_null_model")

# Methods supported for permutation testing
SUPPORTED_CHANNELS = {"semantic", "lexical", "citation"}


# ---------------------------------------------------------------------------
# Core permutation test
# ---------------------------------------------------------------------------


def permutation_test(X_before, Y_after, statistic_fn, n_perm, rng):
    """Run a permutation test on two samples.

    Parameters
    ----------
    X_before, Y_after : array-like
        The two samples (numpy arrays or lists).
    statistic_fn : callable
        Function(a, b) -> float that computes the test statistic.
    n_perm : int
        Number of permutations.
    rng : np.random.RandomState
        Random state for reproducibility.

    Returns
    -------
    (observed, null_mean, null_std, z_score, p_value)

    """
    observed = statistic_fn(X_before, Y_after)

    is_array = isinstance(X_before, np.ndarray)
    if is_array:
        pooled = np.vstack([X_before, Y_after])
    else:
        pooled = list(X_before) + list(Y_after)

    n_before = len(X_before)
    null_stats = []

    for _ in range(n_perm):
        if is_array:
            rng.shuffle(pooled)
            perm_before = pooled[:n_before]
            perm_after = pooled[n_before:]
        else:
            indices = rng.permutation(len(pooled))
            perm_before = [pooled[i] for i in indices[:n_before]]
            perm_after = [pooled[i] for i in indices[n_before:]]

        null_stats.append(statistic_fn(perm_before, perm_after))

    null_stats = np.array(null_stats)
    null_mean = float(np.mean(null_stats))
    null_std = float(np.std(null_stats))

    if null_std > 0:
        z = (observed - null_mean) / null_std
    else:
        z = 0.0

    p = float(np.mean(null_stats >= observed))

    return observed, null_mean, null_std, z, p


# ---------------------------------------------------------------------------
# Statistic wrappers (call the same method functions used by divergence)
# ---------------------------------------------------------------------------


def _make_semantic_statistic(method_name, cfg):
    """Return a statistic_fn(X, Y) -> float for a semantic method."""
    if method_name == "S2_energy":
        from _divergence_backend import get_backend

        backend = get_backend(cfg)
        if backend == "torch":
            from _divergence_semantic import _energy_distance_torch

            return _energy_distance_torch
        else:
            import dcor

            def energy_fn(X, Y):
                return float(dcor.energy_distance(X, Y))

            return energy_fn

    elif method_name == "S1_MMD":
        from _divergence_semantic import _median_heuristic, compute_mmd_rbf

        def mmd_fn(X, Y):
            med = _median_heuristic(X, Y)
            return compute_mmd_rbf(X, Y, med)

        return mmd_fn

    elif method_name == "S3_sliced_wasserstein":
        import ot

        seed = cfg["divergence"]["random_seed"]
        # Use middle value from config's n_projections list for null model.
        # The main divergence pipeline sweeps all values; the null model
        # uses a single representative projection count for tractability.
        n_proj = cfg["divergence"]["semantic"]["S3_sliced_wasserstein"][
            "n_projections"
        ][1]

        def sw_fn(X, Y):
            return float(
                ot.sliced_wasserstein_distance(X, Y, n_projections=n_proj, seed=seed)
            )

        return sw_fn

    elif method_name == "S4_frechet":
        from _divergence_semantic import compute_frechet_distance

        return compute_frechet_distance

    else:
        raise ValueError(f"Unsupported semantic method: {method_name}")


def _make_lexical_statistic(vectorizer):
    """Return a statistic_fn(texts_before, texts_after) -> float for L1 JS."""
    from _divergence_lexical import _smooth_distribution
    from scipy.spatial.distance import jensenshannon

    def js_fn(texts_before, texts_after):
        X_before = vectorizer.transform(texts_before)
        X_after = vectorizer.transform(texts_after)
        agg_before = np.asarray(X_before.mean(axis=0)).flatten()
        agg_after = np.asarray(X_after.mean(axis=0)).flatten()
        p = _smooth_distribution(agg_before)
        q = _smooth_distribution(agg_after)
        return float(jensenshannon(p, q))

    return js_fn


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _result_row(year, window, observed, null_mean, null_std, z, p):
    """Return a row dict with computed permutation test results."""
    return {
        "year": year,
        "window": str(window),
        "observed": observed,
        "null_mean": null_mean,
        "null_std": null_std,
        "z_score": z,
        "p_value": p,
    }


# ---------------------------------------------------------------------------
# Per-channel permutation drivers
# ---------------------------------------------------------------------------

# Re-export for backward compatibility (moved to _divergence_io in simplify review).
from _divergence_io import _make_window_rngs  # noqa: F401


def _collect_permutation_rows(window_iter, statistic_fn, n_perm):
    """Run permutation test over window iterator, collecting result rows.

    Shared logic for both semantic and lexical channels.
    """
    rows = []
    for y, w, X, Y, perm_rng in window_iter:
        observed, null_mean, null_std, z, p = permutation_test(
            X, Y, statistic_fn, n_perm, perm_rng
        )
        rows.append(_result_row(y, w, observed, null_mean, null_std, z, p))
        log.info("  year=%d window=%d z=%.2f p=%.3f", y, w, z, p)
    return pd.DataFrame(rows)


def _run_semantic_permutations(method_name, div_df, cfg):
    """Permutation test for semantic methods (S1-S4)."""
    from _divergence_io import iter_semantic_windows

    statistic_fn = _make_semantic_statistic(method_name, cfg)
    n_perm = cfg["divergence"]["permutation"]["n_perm"]
    return _collect_permutation_rows(
        iter_semantic_windows(div_df, cfg), statistic_fn, n_perm
    )


def _run_lexical_permutations(method_name, div_df, cfg):
    """Permutation test for lexical methods (L1)."""
    from _divergence_io import fit_lexical_vectorizer, iter_lexical_windows

    statistic_fn = _make_lexical_statistic(fit_lexical_vectorizer(cfg))
    n_perm = cfg["divergence"]["permutation"]["n_perm"]
    return _collect_permutation_rows(
        iter_lexical_windows(div_df, cfg), statistic_fn, n_perm
    )


def _community_node_comm_map(partition):
    """Build sorted community list and node->community-index lookup.

    Returns (n_communities, comm_to_idx, node_comm) or None if < 2 communities.
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


def _run_citation_permutations(method_name, div_df, cfg):
    """Permutation test for citation community methods (G9).

    For each (year, window):
      1. Build before/after sliding-window graphs
      2. Build union graph, run Louvain once (fixed partition)
      3. Permute which nodes are 'before' vs 'after' (keeping sizes fixed)
      4. Recompute community-share JS divergence under each permutation
      5. Compare observed JS against the null distribution

    This is computationally efficient: Louvain runs once per (year, window),
    and only the node-label shuffle is repeated B times.
    """
    import community as community_louvain
    from _divergence_citation import (
        _sliding_window_graph,
        load_citation_data,
    )
    from _divergence_community import _build_union_graph, _community_js_for_pair

    works, _, internal_edges = load_citation_data(None)
    div_cfg = cfg["divergence"]
    perm_cfg = div_cfg["permutation"]
    n_perm = perm_cfg["n_perm"]
    seed = div_cfg["random_seed"]

    cit_cfg = div_cfg.get("citation", {})
    comm_cfg = cit_cfg.get("G9_community", {})
    resolution = comm_cfg.get("resolution", 1.0)

    year_windows = div_df[["year", "window"]].drop_duplicates()

    rows = []
    for _, row in year_windows.iterrows():
        y = int(row["year"])
        w = int(row["window"])

        _, perm_rng = _make_window_rngs(seed, y, w)

        # Build sliding window graphs
        G_before = _sliding_window_graph(works, internal_edges, y, w, "before")
        G_after = _sliding_window_graph(works, internal_edges, y, w, "after")

        before_nodes = list(G_before.nodes())
        after_nodes = list(G_after.nodes())

        if len(before_nodes) < 3 or len(after_nodes) < 3:
            rows.append(_nan_row(y, w))
            continue

        # Observed value: use the same function as compute_divergence
        observed = _community_js_for_pair(
            G_before, G_after, internal_edges, resolution, seed
        )
        if np.isnan(observed):
            rows.append(_nan_row(y, w))
            continue

        # Build union graph and run Louvain once (shared partition)
        G_union = _build_union_graph(G_before, G_after, internal_edges)
        if G_union.number_of_nodes() < 3 or G_union.number_of_edges() < 1:
            rows.append(_nan_row(y, w))
            continue

        partition = community_louvain.best_partition(
            G_union, resolution=resolution, random_state=seed
        )

        comm_info = _community_node_comm_map(partition)
        if comm_info is None:
            rows.append(_result_row(y, w, observed, 0.0, 0.0, 0.0, 1.0))
            continue

        n_communities, comm_to_idx = comm_info

        # Pool all nodes for permutation
        all_nodes = before_nodes + after_nodes
        n_before = len(before_nodes)

        # Build node->community-index lookup
        node_comm = {
            node: comm_to_idx[partition[node]]
            for node in all_nodes
            if node in partition
        }

        null_stats = _community_null_distribution(
            all_nodes, n_before, node_comm, n_communities, n_perm, perm_rng
        )

        if len(null_stats) == 0:
            rows.append(_nan_row(y, w))
            continue

        null_mean = float(np.mean(null_stats))
        null_std = float(np.std(null_stats))

        if null_std > 0:
            z = (observed - null_mean) / null_std
        else:
            z = 0.0

        p_value = float(np.mean(null_stats >= observed))

        rows.append(_result_row(y, w, observed, null_mean, null_std, z, p_value))
        log.info("  year=%d window=%d z=%.2f p=%.3f", y, w, z, p_value)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    parser = argparse.ArgumentParser()
    parser.add_argument("--method", required=True, choices=METHODS.keys())
    # --div-csv is separate from --input because --input refers to the corpus
    # contract files (via CATALOGS_DIR), while --div-csv is a specific observed
    # divergence table this script compares against.
    parser.add_argument(
        "--div-csv",
        required=True,
        help="Path to the existing tab_div_{method}.csv",
    )
    args = parser.parse_args(extra)

    method_name = args.method
    _, _, channel, _, _ = METHODS[method_name]

    if channel not in SUPPORTED_CHANNELS:
        raise ValueError(
            f"Permutation test not yet supported for channel '{channel}'. "
            f"Supported: {SUPPORTED_CHANNELS}"
        )

    cfg = load_analysis_config()
    log.info("=== Null model: %s (channel=%s) ===", method_name, channel)

    # Load existing divergence CSV for year/window pairs
    div_df = pd.read_csv(args.div_csv)
    log.info("Loaded %d rows from %s", len(div_df), args.div_csv)

    if channel == "semantic":
        result = _run_semantic_permutations(method_name, div_df, cfg)
    elif channel == "lexical":
        result = _run_lexical_permutations(method_name, div_df, cfg)
    elif channel == "citation":
        result = _run_citation_permutations(method_name, div_df, cfg)
    else:
        raise ValueError(f"Unsupported channel: {channel}")

    # Validate contract
    NullModelSchema.validate(result)

    result.to_csv(io_args.output, index=False)
    log.info("Saved %s (%d rows) -> %s", method_name, len(result), io_args.output)


if __name__ == "__main__":
    main()
