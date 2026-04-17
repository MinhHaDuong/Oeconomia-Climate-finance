"""Compute bootstrap CIs for one divergence method (ticket 0047).

For each (year, window) in the existing divergence CSV, resample
with replacement K times and recompute the statistic to build a
bootstrap distribution for confidence intervals.

Usage:
    uv run python scripts/compute_divergence_bootstrap.py --method S2_energy \
        --output content/tables/tab_boot_S2_energy.csv \
        --div-csv content/tables/tab_div_S2_energy.csv

    # Smoke fixture:
    CLIMATE_FINANCE_DATA=tests/fixtures/smoke \
        uv run python scripts/compute_divergence_bootstrap.py --method S2_energy \
        --output /tmp/tab_boot_S2_energy.csv \
        --div-csv /tmp/tab_div_S2_energy.csv
"""

import argparse

import numpy as np
import pandas as pd
from compute_divergence import METHODS
from compute_null_model import (
    SUPPORTED_CHANNELS,
    _make_lexical_statistic,
    _make_semantic_statistic,
)
from pipeline_loaders import load_analysis_config
from schemas import BootstrapSchema
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("compute_divergence_bootstrap")


# ---------------------------------------------------------------------------
# Core bootstrap
# ---------------------------------------------------------------------------


def bootstrap_one_window(X_before, Y_after, statistic_fn, k, seed):
    """Run bootstrap resampling on two samples.

    Parameters
    ----------
    X_before, Y_after : array-like
        The two samples (numpy arrays or lists).
    statistic_fn : callable
        Function(a, b) -> float that computes the test statistic.
    k : int
        Number of bootstrap replicates.
    seed : int
        Base seed for reproducibility.

    Returns
    -------
    list[float]
        K bootstrap replicate values.

    """
    is_array = isinstance(X_before, np.ndarray)
    n_before = len(X_before)
    n_after = len(Y_after)

    replicates = []
    for i in range(k):
        rng = np.random.RandomState(seed + i)
        idx_b = rng.choice(n_before, n_before, replace=True)
        idx_a = rng.choice(n_after, n_after, replace=True)

        if is_array:
            boot_before = X_before[idx_b]
            boot_after = Y_after[idx_a]
        else:
            boot_before = [X_before[j] for j in idx_b]
            boot_after = [Y_after[j] for j in idx_a]

        replicates.append(float(statistic_fn(boot_before, boot_after)))

    return replicates


# ---------------------------------------------------------------------------
# Per-channel bootstrap drivers
# ---------------------------------------------------------------------------


def _collect_bootstrap_rows(window_iter, method_name, statistic_fn, k, seed, log):
    """Run bootstrap over window iterator, collecting replicate rows.

    Shared logic for both semantic and lexical channels.
    """
    rows = []
    for y, w, X, Y, _rng in window_iter:
        # Wider spacing than null model seeds to avoid collisions:
        # null model uses seed + y*100 + w (subsample) and +50000 (perm).
        # Bootstrap uses seed + y*100000 + w*1000 + offset per replicate.
        boot_seed = seed + y * 100_000 + w * 1000
        values = bootstrap_one_window(X, Y, statistic_fn, k, boot_seed)

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
        log.info("  year=%d window=%d k=%d", y, w, k)
    return pd.DataFrame(rows)


def _run_semantic_bootstrap(method_name, div_df, cfg, k):
    """Bootstrap for semantic methods (S1-S4)."""
    from _divergence_io import iter_semantic_windows

    statistic_fn = _make_semantic_statistic(method_name, cfg)
    seed = cfg["divergence"]["random_seed"]
    return _collect_bootstrap_rows(
        iter_semantic_windows(div_df, cfg), method_name, statistic_fn, k, seed, log
    )


def _run_lexical_bootstrap(method_name, div_df, cfg, k):
    """Bootstrap for lexical methods (L1)."""
    from _divergence_io import fit_lexical_vectorizer, iter_lexical_windows

    statistic_fn = _make_lexical_statistic(fit_lexical_vectorizer(cfg))
    seed = cfg["divergence"]["random_seed"]
    return _collect_bootstrap_rows(
        iter_lexical_windows(div_df, cfg), method_name, statistic_fn, k, seed, log
    )


# ---------------------------------------------------------------------------
# Citation-channel bootstrap (ticket 0069)
# ---------------------------------------------------------------------------


def _make_citation_statistic(method_name, cfg, internal_edges):
    """Return a statistic_fn(G_before, G_after) -> float for a citation method."""
    if method_name == "G2_spectral":
        from _citation_methods import _spectral_gap

        def g2_fn(G_b, G_a):
            gap_b = _spectral_gap(G_b)
            gap_a = _spectral_gap(G_a)
            if np.isnan(gap_b) or np.isnan(gap_a):
                return float("nan")
            return float(abs(gap_a - gap_b))

        return g2_fn

    if method_name == "G9_community":
        from _divergence_community import _community_js_for_pair

        div_cfg = cfg["divergence"]
        seed = div_cfg["random_seed"]
        resolution = (
            div_cfg.get("citation", {}).get("G9_community", {}).get("resolution", 1.0)
        )

        def g9_fn(G_b, G_a):
            return _community_js_for_pair(G_b, G_a, internal_edges, resolution, seed)

        return g9_fn

    raise ValueError(f"No citation bootstrap statistic for method '{method_name}'")


def _run_citation_bootstrap(method_name, div_df, cfg, k):
    """Variance-estimation replicates for citation-channel methods (G2, G9).

    Uses node subsampling *without* replacement at a configured fraction
    (`bootstrap.citation_subsample_fraction`, Politis & Romano 1994), not
    nonparametric bootstrap. Duplicating nodes is ill-defined for spectral
    gap (linearly-dependent rows give spurious zero eigenvalues) and for
    Louvain community structure. Subsampling is the honest fallback —
    each replicate is a true subgraph and CIs are conservative.

    The function name and output schema match the semantic / lexical
    bootstrap drivers so the dispatcher and `export_divergence_summary`
    treat all channels uniformly.

    For each (year, window):
      1. Build before/after sliding-window graphs.
      2. K times: subsample n*fraction nodes from each side without
         replacement, take the induced subgraph, compute the statistic.
    """
    from _divergence_citation import _sliding_window_graph, load_citation_data

    works, _, internal_edges = load_citation_data(None)
    div_cfg = cfg["divergence"]
    seed = div_cfg["random_seed"]
    fraction = div_cfg.get("bootstrap", {}).get("citation_subsample_fraction", 0.8)
    if not 0.0 < fraction <= 1.0:
        raise ValueError(
            f"citation_subsample_fraction must be in (0, 1], got {fraction}"
        )
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

        if len(before_nodes) < 3 or len(after_nodes) < 3:
            continue

        n_b = max(2, int(round(len(before_nodes) * fraction)))
        n_a = max(2, int(round(len(after_nodes) * fraction)))

        boot_seed = seed + y * 100_000 + w * 1000
        for rep in range(k):
            rng = np.random.RandomState(boot_seed + rep)
            idx_b = rng.choice(len(before_nodes), n_b, replace=False)
            idx_a = rng.choice(len(after_nodes), n_a, replace=False)
            sampled_before = [before_nodes[j] for j in idx_b]
            sampled_after = [after_nodes[j] for j in idx_a]
            G_b_boot = G_before.subgraph(sampled_before)
            G_a_boot = G_after.subgraph(sampled_after)
            value = statistic_fn(G_b_boot, G_a_boot)
            rows.append(
                {
                    "method": method_name,
                    "year": y,
                    "window": str(w),
                    "hyperparams": f"subsample={fraction}",
                    "replicate": rep,
                    "value": float(value),
                }
            )
        log.info(
            "  year=%d window=%d k=%d subsample=%.2f n_b=%d n_a=%d",
            y,
            w,
            k,
            fraction,
            n_b,
            n_a,
        )

    return pd.DataFrame(rows)


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
        "--k",
        type=int,
        default=None,
        help="Number of bootstrap replicates (default: from config bootstrap.k)",
    )
    args = parser.parse_args(extra)

    method_name = args.method
    _, _, channel, _, _ = METHODS[method_name]

    if channel not in SUPPORTED_CHANNELS:
        raise ValueError(
            f"Bootstrap not yet supported for channel '{channel}'. "
            f"Supported: {SUPPORTED_CHANNELS}"
        )

    cfg = load_analysis_config()
    k = args.k if args.k is not None else cfg["divergence"]["bootstrap"]["k"]
    log.info("=== Bootstrap: %s (channel=%s, k=%d) ===", method_name, channel, k)

    div_df = pd.read_csv(args.div_csv)
    log.info("Loaded %d rows from %s", len(div_df), args.div_csv)

    if channel == "semantic":
        result = _run_semantic_bootstrap(method_name, div_df, cfg, k)
    elif channel == "lexical":
        result = _run_lexical_bootstrap(method_name, div_df, cfg, k)
    elif channel == "citation":
        result = _run_citation_bootstrap(method_name, div_df, cfg, k)
    else:
        raise ValueError(f"Unsupported channel: {channel}")

    # Validate contract
    BootstrapSchema.validate(result)

    result.to_csv(io_args.output, index=False)
    log.info("Saved %s (%d rows) -> %s", method_name, len(result), io_args.output)


if __name__ == "__main__":
    main()
