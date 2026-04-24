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


def _nan_row(year, window):
    """Return a row dict with NaN entries for skipped (year, window) pairs."""
    return _result_row(year, window, np.nan, np.nan, np.nan, np.nan, np.nan)


# ---------------------------------------------------------------------------
# Per-channel permutation drivers
# ---------------------------------------------------------------------------

# Re-export for backward compatibility (moved to _divergence_io in simplify review).
from _divergence_io import _make_window_rngs


def _collect_permutation_rows(window_iter, statistic_fn, n_perm, n_jobs=1):
    """Run permutation test over window iterator, collecting result rows.

    Shared logic for both semantic and lexical channels.

    Parameters
    ----------
    n_jobs : int
        Number of parallel workers.  1 = sequential (original path),
        -1 = all available cores.

    """
    if n_jobs == 1:
        rows = []
        for y, w, X, Y, perm_rng in window_iter:
            observed, null_mean, null_std, z, p = permutation_test(
                X, Y, statistic_fn, n_perm, perm_rng
            )
            rows.append(_result_row(y, w, observed, null_mean, null_std, z, p))
            log.info("  year=%d window=%d z=%.2f p=%.3f", y, w, z, p)
        return pd.DataFrame(rows)

    from joblib import Parallel, delayed

    pairs = list(window_iter)
    log.info("Parallel: %d (year, window) pairs on %d jobs", len(pairs), n_jobs)

    def _process(y, w, X, Y, perm_rng):
        obs, nm, ns, z, p = permutation_test(X, Y, statistic_fn, n_perm, perm_rng)
        return _result_row(y, w, obs, nm, ns, z, p)

    results = Parallel(n_jobs=n_jobs)(
        delayed(_process)(y, w, X, Y, rng) for y, w, X, Y, rng in pairs
    )
    for row in results:
        log.info(
            "  year=%d window=%s z=%.2f p=%.3f",
            row["year"],
            row["window"],
            row["z_score"],
            row["p_value"],
        )
    return pd.DataFrame(results)


# GPU-accelerated semantic permutations
_GPU_METHODS = {"S2_energy", "S1_MMD"}


def _run_semantic_gpu(method_name, div_df, cfg):
    """GPU-vectorized permutation test for S2_energy and S1_MMD.

    Precomputes the distance/kernel matrix once on GPU, then batches all
    n_perm statistics in a single matmul pass per (year, window).
    """
    from _divergence_io import iter_semantic_windows
    from _permutation_accel import gpu_energy_permutations, gpu_mmd_permutations

    n_perm = cfg["divergence"]["permutation"]["n_perm"]
    seed = cfg["divergence"]["random_seed"]

    rows = []
    for y, w, X, Y, _perm_rng in iter_semantic_windows(div_df, cfg):
        perm_seed = seed + y * 100 + w + 50000

        if method_name == "S2_energy":
            obs, nm, ns, z, p = gpu_energy_permutations(X, Y, n_perm, perm_seed)
        elif method_name == "S1_MMD":
            from _divergence_semantic import _median_heuristic

            med = _median_heuristic(X, Y, rng=np.random.RandomState(perm_seed))
            obs, nm, ns, z, p = gpu_mmd_permutations(X, Y, med, n_perm, perm_seed)
        else:
            raise ValueError(f"No GPU path for {method_name}")

        rows.append(_result_row(y, w, obs, nm, ns, z, p))
        log.info("  year=%d window=%d z=%.2f p=%.3f [GPU]", y, w, z, p)

    return pd.DataFrame(rows)


def _run_semantic_permutations(method_name, div_df, cfg, n_jobs=1):
    """Permutation test for semantic methods (S1-S4).

    Auto-selects GPU-vectorized path for S2_energy and S1_MMD when CUDA
    is available; falls back to CPU (optionally parallel).
    """
    from _divergence_backend import get_backend
    from _divergence_io import iter_semantic_windows

    backend = get_backend(cfg)
    if backend == "torch" and method_name in _GPU_METHODS:
        log.info("Using GPU-vectorized permutation for %s", method_name)
        return _run_semantic_gpu(method_name, div_df, cfg)

    statistic_fn = _make_semantic_statistic(method_name, cfg)
    n_perm = cfg["divergence"]["permutation"]["n_perm"]
    return _collect_permutation_rows(
        iter_semantic_windows(div_df, cfg), statistic_fn, n_perm, n_jobs=n_jobs
    )


def _run_lexical_permutations(method_name, div_df, cfg):
    """Permutation test for lexical methods (L1).

    Precomputes TF-IDF for each (year, window) pool once, then permutes
    row indices into the sparse matrix — avoids 2 × n_perm redundant
    vectorizer.transform() calls per window.
    """
    from _divergence_io import fit_lexical_vectorizer, iter_lexical_windows
    from _permutation_accel import precomputed_lexical_permutation

    vectorizer = fit_lexical_vectorizer(cfg)
    n_perm = cfg["divergence"]["permutation"]["n_perm"]

    rows = []
    for y, w, texts_before, texts_after, perm_rng in iter_lexical_windows(div_df, cfg):
        all_texts = texts_before + texts_after
        X_all = vectorizer.transform(all_texts)
        n_before = len(texts_before)

        obs, nm, ns, z, p = precomputed_lexical_permutation(
            X_all, n_before, n_perm, perm_rng
        )
        rows.append(_result_row(y, w, obs, nm, ns, z, p))
        log.info("  year=%d window=%d z=%.2f p=%.3f", y, w, z, p)

    return pd.DataFrame(rows)


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


def _finalize_row(y, w, observed, null_stats):
    """Compute z, p, mean, std from a finite null distribution and log."""
    null_mean = float(np.mean(null_stats))
    null_std = float(np.std(null_stats))
    if null_std > 0:
        z = (observed - null_mean) / null_std
    else:
        z = 0.0
    p_value = float(np.mean(null_stats >= observed))
    log.info("  year=%d window=%d z=%.2f p=%.3f", y, w, z, p_value)
    return _result_row(y, w, observed, null_mean, null_std, z, p_value)


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


# Citation-channel dispatcher: method_name -> permutation driver.
_CITATION_PERMUTATION_DRIVERS = {
    "G9_community": _run_g9_community_permutations,
    "G2_spectral": _run_g2_spectral_permutations,
}


def _run_citation_permutations(method_name, div_df, cfg, n_jobs=1):
    """Permutation test for citation-channel methods (G2, G9)."""
    from _divergence_citation import load_citation_data

    driver = _CITATION_PERMUTATION_DRIVERS.get(method_name)
    if driver is None:
        raise ValueError(
            f"No citation null-model driver for '{method_name}'. "
            f"Supported: {sorted(_CITATION_PERMUTATION_DRIVERS)}"
        )

    works, _, internal_edges = load_citation_data(None)
    return driver(works, internal_edges, div_df, cfg, n_jobs=n_jobs)


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
    parser.add_argument(
        "--n-jobs",
        type=int,
        default=-1,
        help="Parallel workers for CPU path (-1 = all cores, 1 = sequential)",
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

    import time

    t0 = time.perf_counter()

    if channel == "semantic":
        result = _run_semantic_permutations(
            method_name, div_df, cfg, n_jobs=args.n_jobs
        )
    elif channel == "lexical":
        result = _run_lexical_permutations(method_name, div_df, cfg)
    elif channel == "citation":
        result = _run_citation_permutations(
            method_name, div_df, cfg, n_jobs=args.n_jobs
        )
    else:
        raise ValueError(f"Unsupported channel: {channel}")

    elapsed = time.perf_counter() - t0
    log.info("Permutation testing completed in %.1fs", elapsed)

    # Validate contract
    NullModelSchema.validate(result)

    result.to_csv(io_args.output, index=False)
    log.info("Saved %s (%d rows) -> %s", method_name, len(result), io_args.output)


if __name__ == "__main__":
    main()
