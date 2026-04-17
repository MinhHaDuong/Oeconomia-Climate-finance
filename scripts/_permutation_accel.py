"""Accelerated permutation testing backends.

Provides GPU-vectorized and CPU-precomputed alternatives to the sequential
permutation_test() loop in compute_null_model.py.

GPU energy distance
~~~~~~~~~~~~~~~~~~~
Precompute D = cdist(pooled, pooled) once on GPU, then batch all permutations:

    stat_p = -((C[p] @ D) · C[p]).sum()

where C[p, i] = 1/n_b if i ∈ before_p, else -1/n_a.  This replaces n_perm
sequential cdist calls with one cdist + one batched matmul.

GPU MMD (RBF)
~~~~~~~~~~~~~
Precompute K = exp(-γ D²), extract block sums per permutation via indicator
indexing on the precomputed kernel matrix.

Precomputed lexical
~~~~~~~~~~~~~~~~~~~
Vectorize TF-IDF once per window, permute row indices instead of
re-transforming texts 2 × n_perm times.
"""

import numpy as np
from utils import get_logger

log = get_logger("_permutation_accel")


# ── GPU energy distance (S2) ────────────────────────────────────────────


def gpu_energy_permutations(
    X: np.ndarray,
    Y: np.ndarray,
    n_perm: int,
    seed: int,
) -> tuple[float, float, float, float, float]:
    """Vectorized GPU permutation test for energy distance.

    Math: energy distance E(A,B) = 2·E[‖a−b‖] − E[‖a−a′‖] − E[‖b−b′‖].
    Define c[i] = 1/n_b if i ∈ B else −1/n_a.  Then E = −(cᵀ D c).
    Batching: stats = −diag(C D Cᵀ) = −((C D) ⊙ C).sum(dim=1).
    """
    import torch
    from _divergence_backend import to_tensor

    n_b, n_a = len(X), len(Y)
    N = n_b + n_a
    device = torch.device("cuda")

    pooled = to_tensor(np.vstack([X, Y]))  # (N, d)
    D = torch.cdist(pooled, pooled)  # (N, N)
    del pooled

    # Template weights
    template = torch.cat(
        [
            torch.full((n_b,), 1.0 / n_b, device=device),
            torch.full((n_a,), -1.0 / n_a, device=device),
        ]
    )

    # Observed statistic (original split)
    observed = -float((template @ D @ template).item())

    # Generate all permutations at once
    gen = torch.Generator(device=device)
    gen.manual_seed(seed)
    perms = torch.stack(
        [torch.randperm(N, generator=gen, device=device) for _ in range(n_perm)]
    )

    # Build weight matrix: C[p, perms[p, i]] = template[i]
    C = torch.empty(n_perm, N, device=device)
    C.scatter_(1, perms, template.unsqueeze(0).expand(n_perm, -1))
    del perms

    # Batched computation: all n_perm stats in one matmul
    null_stats = -((C @ D) * C).sum(dim=1)

    return _summarize_gpu(observed, null_stats)


# ── GPU MMD with RBF kernel (S1) ────────────────────────────────────────


def gpu_mmd_permutations(
    X: np.ndarray,
    Y: np.ndarray,
    bandwidth: float,
    n_perm: int,
    seed: int,
) -> tuple[float, float, float, float, float]:
    """Vectorized GPU permutation test for MMD² with RBF kernel.

    Precomputes K = exp(−γ D²) and K₀ = K with zeroed diagonal.
    Uses unbiased U-statistic (diagonal excluded for within-group terms).

    Batching: with indicator B[p,i] = 1 if i ∈ before_p:
        bb = ((B @ K₀) ⊙ B).sum(1)  →  ΣK₀[B,B]
        aa = (((1−B) @ K₀) ⊙ (1−B)).sum(1)
        ba = ((B @ K) ⊙ (1−B)).sum(1)
    """
    import torch
    from _divergence_backend import to_tensor

    n_b, n_a = len(X), len(Y)
    N = n_b + n_a
    device = torch.device("cuda")
    gamma = 1.0 / (2.0 * bandwidth) if bandwidth > 0 else 1.0

    pooled = to_tensor(np.vstack([X, Y]))
    D_sq = torch.cdist(pooled, pooled).pow(2)
    K = torch.exp(-gamma * D_sq)
    del pooled, D_sq

    # K with zeroed diagonal for unbiased estimator
    K0 = K.clone()
    K0.fill_diagonal_(0.0)

    # Observed
    obs_bb = K0[:n_b, :n_b].sum() / (n_b * (n_b - 1))
    obs_aa = K0[n_b:, n_b:].sum() / (n_a * (n_a - 1))
    obs_ba = K[:n_b, n_b:].mean()
    observed = max(float((obs_bb + obs_aa - 2.0 * obs_ba).item()), 0.0)

    # Build indicator matrix: B[p, i] = 1 if i ∈ before_p
    gen = torch.Generator(device=device)
    gen.manual_seed(seed)
    perms = torch.stack(
        [torch.randperm(N, generator=gen, device=device) for _ in range(n_perm)]
    )

    B = torch.zeros(n_perm, N, device=device)
    # For each perm, the first n_b indices map to "before"
    ones_template = torch.ones(n_perm, n_b, device=device)
    B.scatter_(1, perms[:, :n_b], ones_template)
    A = 1.0 - B
    del perms, ones_template

    # Batched block sums
    bb = ((B @ K0) * B).sum(dim=1) / (n_b * (n_b - 1))
    aa = ((A @ K0) * A).sum(dim=1) / (n_a * (n_a - 1))
    ba = ((B @ K) * A).sum(dim=1) / (n_b * n_a)

    null_stats = torch.clamp(bb + aa - 2.0 * ba, min=0.0)
    del K, K0, B, A

    return _summarize_gpu(observed, null_stats)


# ── Precomputed lexical JS permutation ──────────────────────────────────


def precomputed_lexical_permutation(
    X_sparse,
    n_before: int,
    n_perm: int,
    rng: np.random.RandomState,
) -> tuple[float, float, float, float, float]:
    """Permutation test for JS divergence with precomputed TF-IDF.

    Parameters
    ----------
    X_sparse : sparse matrix (N, n_features)
        Precomputed TF-IDF for pooled texts (before ++ after).
    n_before : int
        Number of "before" texts (first n_before rows).
    n_perm : int
        Number of permutations.
    rng : np.random.RandomState
        Per-window RNG for reproducibility.

    """
    from _divergence_lexical import _smooth_distribution
    from scipy.spatial.distance import jensenshannon

    N = X_sparse.shape[0]

    def _js_from_split(idx_b, idx_a):
        agg_b = np.asarray(X_sparse[idx_b].mean(axis=0)).flatten()
        agg_a = np.asarray(X_sparse[idx_a].mean(axis=0)).flatten()
        return float(
            jensenshannon(_smooth_distribution(agg_b), _smooth_distribution(agg_a))
        )

    # Observed (original split)
    idx_before = np.arange(n_before)
    idx_after = np.arange(n_before, N)
    observed = _js_from_split(idx_before, idx_after)

    # Null distribution
    null_stats = np.empty(n_perm)
    for i in range(n_perm):
        perm = rng.permutation(N)
        null_stats[i] = _js_from_split(perm[:n_before], perm[n_before:])

    return _summarize_cpu(observed, null_stats)


# ── Helpers ──────────────────────────────────────────────────────────────


def _summarize_gpu(
    observed: float,
    null_stats: "torch.Tensor",
) -> tuple[float, float, float, float, float]:
    """Compute z-score and p-value from GPU null distribution."""
    null_mean = float(null_stats.mean().item())
    null_std = float(null_stats.std(correction=0).item())
    z = (observed - null_mean) / null_std if null_std > 0 else 0.0
    p = float((null_stats >= observed).float().mean().item())
    return observed, null_mean, null_std, z, p


def _summarize_cpu(
    observed: float,
    null_stats: np.ndarray,
) -> tuple[float, float, float, float, float]:
    """Compute z-score and p-value from CPU null distribution."""
    null_mean = float(np.mean(null_stats))
    null_std = float(np.std(null_stats))
    z = (observed - null_mean) / null_std if null_std > 0 else 0.0
    p = float(np.mean(null_stats >= observed))
    return observed, null_mean, null_std, z, p
