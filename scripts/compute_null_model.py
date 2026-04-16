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

# Methods supported for permutation testing (semantic + lexical only)
SUPPORTED_CHANNELS = {"semantic", "lexical"}


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
    else:
        raise ValueError(f"Unsupported channel: {channel}")

    # Validate contract
    NullModelSchema.validate(result)

    result.to_csv(io_args.output, index=False)
    log.info("Saved %s (%d rows) -> %s", method_name, len(result), io_args.output)


if __name__ == "__main__":
    main()
