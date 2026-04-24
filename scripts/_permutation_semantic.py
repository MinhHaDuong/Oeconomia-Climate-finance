"""Permutation null model drivers for semantic methods (S1-S4).

Private module — no main, no argparse.  Called by compute_null_model.py.
"""

import numpy as np
from _permutation_io import _collect_permutation_rows, _result_row
from utils import get_logger

log = get_logger("_permutation_semantic")

# Methods with GPU-vectorized permutation paths
_GPU_METHODS = {"S2_energy", "S1_MMD"}


# ---------------------------------------------------------------------------
# Statistic wrappers
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


# ---------------------------------------------------------------------------
# GPU-accelerated permutations
# ---------------------------------------------------------------------------


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

    import pandas as pd

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Main semantic driver
# ---------------------------------------------------------------------------


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
