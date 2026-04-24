"""Shared I/O helpers for permutation null model drivers.

Core algorithm, row helpers, and window-iteration utilities used by all
``_permutation_*.py`` private modules.  No imports from other
``_permutation_*`` modules — this is the leaf of the dependency graph.
"""

import numpy as np
import pandas as pd
from _divergence_io import _make_window_rngs  # noqa: F401 — re-export
from utils import get_logger

log = get_logger("_permutation_io")


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
# Row helpers
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


# ---------------------------------------------------------------------------
# Shared row collection
# ---------------------------------------------------------------------------


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
