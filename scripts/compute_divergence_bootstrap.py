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
    else:
        raise ValueError(f"Unsupported channel: {channel}")

    # Validate contract
    BootstrapSchema.validate(result)

    result.to_csv(io_args.output, index=False)
    log.info("Saved %s (%d rows) -> %s", method_name, len(result), io_args.output)


if __name__ == "__main__":
    main()
