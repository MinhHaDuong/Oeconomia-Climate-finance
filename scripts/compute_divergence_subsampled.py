"""Compute equal-n subsampling replicates for one divergence method (ticket 0084).

For each (year, window) in the existing divergence CSV, draws R independent
equal-n subsamples and recomputes the statistic to build a subsampling
distribution for Z-score ribbons.

Output schema: DivergenceSubsampleSchema
  (method, year, window, hyperparams, replicate, value)

Usage:
    uv run python scripts/compute_divergence_subsampled.py --method S2_energy \
        --output content/tables/tab_subsample_S2_energy.csv \
        --div-csv content/tables/tab_div_S2_energy.csv

    # Smoke fixture:
    CLIMATE_FINANCE_DATA=tests/fixtures/smoke \
        uv run python scripts/compute_divergence_subsampled.py --method S2_energy \
        --output /tmp/tab_subsample_S2_energy.csv \
        --div-csv /tmp/tab_div_S2_energy.csv
"""

import argparse
import copy

import numpy as np
import pandas as pd
from compute_divergence import METHODS
from compute_null_model import (
    SUPPORTED_CHANNELS,
    _make_lexical_statistic,
    _make_semantic_statistic,
)
from pipeline_loaders import load_analysis_config
from schemas import DivergenceSubsampleSchema
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("compute_divergence_subsampled")


# ---------------------------------------------------------------------------
# Core subsampling
# ---------------------------------------------------------------------------


def subsample_one_window(X_before, Y_after, statistic_fn, R, seed, y, w):
    """Draw R independent equal-n subsamples and compute the statistic each time.

    Each replicate r gets an independent RNG via _make_subsample_rng, which
    is in a seed namespace disjoint from the null-model permutation stream
    (ticket 0084 RNG independence requirement).

    Parameters
    ----------
    X_before, Y_after : np.ndarray or list
        Full before/after samples (not yet equal-n subsampled).
    statistic_fn : callable
        Function(a, b) -> float.
    R : int
        Number of subsampling replicates.
    seed, y, w : int
        Config seed and (year, window) for RNG namespacing.

    Returns
    -------
    list[float]
        R replicate values.

    """
    from _divergence_io import _make_subsample_rng

    n = min(len(X_before), len(Y_after))
    is_array = isinstance(X_before, np.ndarray)

    replicates = []
    for r in range(R):
        rng_r = _make_subsample_rng(seed, y, w, r)

        if is_array:
            X_s = (
                X_before[rng_r.choice(len(X_before), n, replace=False)]
                if len(X_before) > n
                else X_before
            )
            Y_s = (
                Y_after[rng_r.choice(len(Y_after), n, replace=False)]
                if len(Y_after) > n
                else Y_after
            )
        else:
            x_idx = (
                rng_r.choice(len(X_before), n, replace=False)
                if len(X_before) > n
                else range(len(X_before))
            )
            y_idx = (
                rng_r.choice(len(Y_after), n, replace=False)
                if len(Y_after) > n
                else range(len(Y_after))
            )
            X_s = [X_before[i] for i in x_idx]
            Y_s = [Y_after[i] for i in y_idx]

        replicates.append(float(statistic_fn(X_s, Y_s)))

    return replicates


# ---------------------------------------------------------------------------
# Per-channel subsampling drivers
# ---------------------------------------------------------------------------


def _collect_subsample_rows(window_iter, method_name, statistic_fn, R, seed, log):
    rows = []
    for y, w, X, Y, _rng in window_iter:
        values = subsample_one_window(X, Y, statistic_fn, R, seed, y, w)
        for rep, val in enumerate(values):
            rows.append(
                {
                    "method": method_name,
                    "year": y,
                    "window": str(w),
                    "hyperparams": "",
                    "replicate": rep,
                    "value": val,
                }
            )
        log.info("  year=%d window=%d R=%d", y, w, R)
    return pd.DataFrame(rows)


def _run_semantic_subsampled(method_name, div_df, cfg, R):
    """R subsampling replicates for semantic methods (S1–S4)."""
    from _divergence_io import iter_semantic_windows

    statistic_fn = _make_semantic_statistic(method_name, cfg)
    seed = cfg["divergence"]["random_seed"]

    # Disable equal_n so the iterator yields the full unequal-sized arrays.
    # subsample_one_window applies equal-n R times independently.
    cfg_raw = copy.deepcopy(cfg)
    cfg_raw["divergence"]["equal_n"] = False

    return _collect_subsample_rows(
        iter_semantic_windows(div_df, cfg_raw), method_name, statistic_fn, R, seed, log
    )


def _run_lexical_subsampled(method_name, div_df, cfg, R):
    """R subsampling replicates for lexical methods (L1)."""
    from _divergence_io import fit_lexical_vectorizer, iter_lexical_windows

    statistic_fn = _make_lexical_statistic(fit_lexical_vectorizer(cfg))
    seed = cfg["divergence"]["random_seed"]

    cfg_raw = copy.deepcopy(cfg)
    cfg_raw["divergence"]["equal_n"] = False

    return _collect_subsample_rows(
        iter_lexical_windows(div_df, cfg_raw),
        method_name,
        statistic_fn,
        R,
        seed,
        log,
    )


def _run_c2st_embedding_subsampled(method_name, div_df, cfg, R):
    """R subsampling replicates for C2ST_embedding."""
    from _divergence_c2st import _c2st_auc
    from _divergence_io import iter_semantic_windows

    c2st_cfg = cfg["divergence"].get("c2st", {})
    pca_dim = c2st_cfg.get("pca_dim", 32)
    cv_folds = c2st_cfg.get("cv_folds", 5)
    seed = cfg["divergence"]["random_seed"]

    cfg_raw = copy.deepcopy(cfg)
    cfg_raw["divergence"]["equal_n"] = False

    def statistic_fn(X, Y):
        from sklearn.decomposition import PCA

        n_components = min(pca_dim, min(len(X), len(Y)) - 1, X.shape[1])
        n_components = max(2, n_components)
        pca = PCA(n_components=n_components, random_state=seed)
        combined = np.vstack([X, Y])
        combined_r = pca.fit_transform(combined)
        return _c2st_auc(
            combined_r[: len(X)],
            combined_r[len(X) :],
            cv_folds=cv_folds,
            class_weight="balanced",
            seed=seed,
        )["mean"]

    return _collect_subsample_rows(
        iter_semantic_windows(div_df, cfg_raw),
        method_name,
        statistic_fn,
        R,
        seed,
        log,
    )


def _run_c2st_lexical_subsampled(method_name, div_df, cfg, R):
    """R subsampling replicates for C2ST_lexical."""
    from _divergence_c2st import _c2st_auc
    from _divergence_io import iter_lexical_windows

    c2st_cfg = cfg["divergence"].get("c2st", {})
    cv_folds = c2st_cfg.get("cv_folds", 5)
    seed = cfg["divergence"]["random_seed"]

    cfg_raw = copy.deepcopy(cfg)
    cfg_raw["divergence"]["equal_n"] = False

    def statistic_fn(X, Y):
        return _c2st_auc(X, Y, cv_folds=cv_folds, class_weight="balanced", seed=seed)[
            "mean"
        ]

    return _collect_subsample_rows(
        iter_lexical_windows(div_df, cfg_raw),
        method_name,
        statistic_fn,
        R,
        seed,
        log,
    )


def _run_citation_subsampled(method_name, div_df, cfg, R):
    """R equal-n subsampling replicates for citation methods (G2, G9).

    Subsamples min(n_before, n_after) nodes from each side without
    replacement — the equal-n analogue of _run_citation_bootstrap, which
    uses a fixed fraction instead.
    """
    from _divergence_citation import _sliding_window_graph, load_citation_data
    from _divergence_io import _make_subsample_rng
    from compute_divergence_bootstrap import _make_citation_statistic

    works, _, internal_edges = load_citation_data(None)
    div_cfg = cfg["divergence"]
    seed = div_cfg["random_seed"]
    statistic_fn = _make_citation_statistic(method_name, cfg, internal_edges)

    year_windows = div_df[["year", "window"]].drop_duplicates()
    rows = []

    for _, row in year_windows.iterrows():
        y = int(row["year"])
        w = int(row["window"])

        G_before = _sliding_window_graph(works, internal_edges, y, w, "before")
        G_after = _sliding_window_graph(works, internal_edges, y, w, "after")

        before_nodes = list(G_before.nodes())
        after_nodes = list(G_after.nodes())
        n = min(len(before_nodes), len(after_nodes))
        if n < 3:
            continue

        for r in range(R):
            rng_r = _make_subsample_rng(seed, y, w, r)
            idx_b = rng_r.choice(len(before_nodes), n, replace=False)
            idx_a = rng_r.choice(len(after_nodes), n, replace=False)
            G_b_sub = G_before.subgraph([before_nodes[j] for j in idx_b])
            G_a_sub = G_after.subgraph([after_nodes[j] for j in idx_a])
            rows.append(
                {
                    "method": method_name,
                    "year": y,
                    "window": str(w),
                    "hyperparams": "",
                    "replicate": r,
                    "value": float(statistic_fn(G_b_sub, G_a_sub)),
                }
            )
        log.info("  year=%d window=%d R=%d", y, w, R)

    return (
        pd.DataFrame(rows)
        if rows
        else pd.DataFrame(
            columns=["method", "year", "window", "hyperparams", "replicate", "value"]
        )
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    parser = argparse.ArgumentParser()
    parser.add_argument("--method", required=True, choices=METHODS.keys())
    parser.add_argument(
        "--div-csv",
        required=True,
        help="Path to the existing tab_div_{method}.csv",
    )
    parser.add_argument(
        "--r",
        type=int,
        default=None,
        help="Number of subsampling replicates (default: from config divergence.equal_n_r)",
    )
    args = parser.parse_args(extra)

    method_name = args.method
    _, _, channel, _, _ = METHODS[method_name]

    if channel not in SUPPORTED_CHANNELS:
        raise ValueError(
            f"Subsampling not yet supported for channel '{channel}'. "
            f"Supported: {SUPPORTED_CHANNELS}"
        )

    cfg = load_analysis_config()
    R = args.r if args.r is not None else cfg["divergence"].get("equal_n_r", 20)
    log.info("=== Subsampled: %s (channel=%s, R=%d) ===", method_name, channel, R)

    div_df = pd.read_csv(args.div_csv)
    log.info("Loaded %d rows from %s", len(div_df), args.div_csv)

    if method_name == "C2ST_embedding":
        result = _run_c2st_embedding_subsampled(method_name, div_df, cfg, R)
    elif method_name == "C2ST_lexical":
        result = _run_c2st_lexical_subsampled(method_name, div_df, cfg, R)
    elif channel == "semantic":
        result = _run_semantic_subsampled(method_name, div_df, cfg, R)
    elif channel == "lexical":
        result = _run_lexical_subsampled(method_name, div_df, cfg, R)
    elif channel == "citation":
        result = _run_citation_subsampled(method_name, div_df, cfg, R)
    else:
        raise ValueError(f"Unsupported channel: {channel}")

    if result.empty:
        log.warning("No rows produced — smoke fixture may be too small")
        result = pd.DataFrame(
            columns=["method", "year", "window", "hyperparams", "replicate", "value"]
        )

    DivergenceSubsampleSchema.validate(result)

    result.to_csv(io_args.output, index=False)
    log.info("Saved %s (%d rows) -> %s", method_name, len(result), io_args.output)


if __name__ == "__main__":
    main()
