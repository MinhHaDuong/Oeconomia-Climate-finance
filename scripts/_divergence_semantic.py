"""Semantic distributional divergence: implementation functions (S1-S4).

Private module — no main, no argparse. Called by compute_divergence.py.

Methods:
  S1  MMD (Maximum Mean Discrepancy) with RBF kernel
  S2  Energy distance (multivariate)
  S3  Sliced Wasserstein distance
  S4  Frechet distance (Gaussian fit)

"""

import os

import numpy as np
import pandas as pd
from pipeline_loaders import load_analysis_corpus
from utils import get_logger

log = get_logger("_divergence_semantic")


# ── Data loading ───────────────────────────────────────────────────────────


def load_semantic_data(input_paths):
    """Load works CSV and embeddings.

    Parameters
    ----------
    input_paths : list[str] | None
        If provided, [works_csv, embeddings_npz] (used by tests).

    Returns
    -------
    (df, emb) : tuple[pd.DataFrame, np.ndarray]

    """
    if input_paths:
        csv_path = input_paths[0]
        emb_path = (
            input_paths[1]
            if len(input_paths) > 1
            else os.path.join(os.path.dirname(csv_path), "refined_embeddings.npz")
        )
        df = pd.read_csv(csv_path, usecols=["year", "cited_by_count"])
        df["year"] = df["year"].astype("Int64")
        df = df.dropna(subset=["year"]).reset_index(drop=True)
        emb = np.load(emb_path)["vectors"]
    else:
        df, emb = load_analysis_corpus(with_embeddings=True)

    log.info("Loaded %d works, embeddings %s", len(df), emb.shape)
    return df, emb


# ── Shared helpers ─────────────────────────────────────────────────────────


def _get_years_and_params(df, emb, cfg):
    """Derive year range and smoke-safe parameters from config.

    Returns (years, min_papers, max_subsample, windows).
    """
    div_cfg = cfg["divergence"]
    windows = div_cfg["windows"]
    max_subsample = div_cfg["max_subsample"]

    from _divergence_io import get_min_papers

    min_papers = get_min_papers(len(df), cfg)

    start_year = int(df["year"].min()) + max(windows)
    end_year = int(df["year"].max()) - max(windows) - 1
    if start_year > end_year:
        start_year = int(df["year"].min()) + min(windows)
        end_year = int(df["year"].max()) - min(windows) - 1

    years = list(range(start_year, end_year + 1))
    return years, min_papers, max_subsample, windows


def _get_window_embeddings(
    df, emb, year, window, side, min_papers, max_subsample, rng=None
):
    """Extract embeddings for a time window.

    side='before': [year - window, year]
    side='after':  [year + 1, year + 1 + window]
    """
    if side == "before":
        mask = (df["year"] >= year - window) & (df["year"] <= year)
    else:
        mask = (df["year"] >= year + 1) & (df["year"] <= year + 1 + window)

    idx = df.index[mask]
    if len(idx) < min_papers:
        return None

    vecs = emb[idx]
    if len(vecs) > max_subsample:
        if rng is None:
            raise ValueError(
                "rng required when subsampling (pass from cfg random_seed)"
            )
        chosen = rng.choice(len(vecs), max_subsample, replace=False)
        vecs = vecs[chosen]
    return vecs


def _iter_window_pairs(
    df, emb, years, windows, min_papers, max_subsample, rng=None, equal_n=False
):
    """Yield (year, window, X, Y) for each valid before/after window pair.

    Centralises the nested loop and skip logic shared by S1-S4.
    When equal_n is True, the larger window is subsampled to match
    the smaller, removing growth-rate bias (ticket 0045).
    """
    for w in windows:
        for y in years:
            X = _get_window_embeddings(
                df, emb, y, w, "before", min_papers, max_subsample, rng=rng
            )
            Y = _get_window_embeddings(
                df, emb, y, w, "after", min_papers, max_subsample, rng=rng
            )
            if X is None or Y is None:
                continue
            if equal_n and len(X) != len(Y):
                n = min(len(X), len(Y))
                if n < min_papers:
                    continue
                if rng is None:
                    raise ValueError("rng required for equal_n subsampling")
                if len(X) > n:
                    X = X[rng.choice(len(X), n, replace=False)]
                if len(Y) > n:
                    Y = Y[rng.choice(len(Y), n, replace=False)]
            yield y, w, X, Y


# ── S1: MMD with RBF kernel ───────────────────────────────────────────────


def _median_heuristic(X, Y, n_sample=1000, rng=None):
    """Median of pairwise distances (sampled for speed)."""
    combined = np.vstack([X, Y])
    if len(combined) > n_sample:
        if rng is None:
            raise ValueError(
                "rng required when subsampling (pass from cfg random_seed)"
            )
        idx = rng.choice(len(combined), n_sample, replace=False)
        combined = combined[idx]
    from scipy.spatial.distance import pdist

    dists = pdist(combined, metric="sqeuclidean")
    return float(np.median(dists))


def compute_mmd_rbf(X, Y, bandwidth):
    """MMD^2 with RBF kernel at given bandwidth (sigma^2)."""
    gamma = 1.0 / (2.0 * bandwidth) if bandwidth > 0 else 1.0

    from scipy.spatial.distance import cdist

    K_XX = np.exp(-gamma * cdist(X, X, metric="sqeuclidean"))
    K_YY = np.exp(-gamma * cdist(Y, Y, metric="sqeuclidean"))
    K_XY = np.exp(-gamma * cdist(X, Y, metric="sqeuclidean"))

    n = len(X)
    m = len(Y)

    # Unbiased estimator: exclude diagonal for K_XX, K_YY
    mmd2 = (
        (K_XX.sum() - np.trace(K_XX)) / (n * (n - 1))
        + (K_YY.sum() - np.trace(K_YY)) / (m * (m - 1))
        - 2.0 * K_XY.mean()
    )
    return max(float(mmd2), 0.0)


def _mmd_rbf_torch(X, Y, bandwidth):
    """MMD^2 via torch on CUDA — same algorithm as compute_mmd_rbf."""
    import torch
    from _divergence_backend import to_tensor

    gamma = 1.0 / (2.0 * bandwidth) if bandwidth > 0 else 1.0
    Xt = to_tensor(X)
    Yt = to_tensor(Y)

    K_XX = torch.exp(-gamma * torch.cdist(Xt, Xt).pow(2))
    K_YY = torch.exp(-gamma * torch.cdist(Yt, Yt).pow(2))
    K_XY = torch.exp(-gamma * torch.cdist(Xt, Yt).pow(2))

    n = Xt.shape[0]
    m = Yt.shape[0]

    mmd2 = (
        (K_XX.sum() - K_XX.trace()) / (n * (n - 1))
        + (K_YY.sum() - K_YY.trace()) / (m * (m - 1))
        - 2.0 * K_XY.mean()
    )
    return max(float(mmd2.item()), 0.0)


def compute_s1_mmd(df, emb, cfg):
    """S1: MMD with RBF kernel at 0.5x, 1x, 2x median bandwidth.

    Returns DataFrame with columns: year, window, hyperparams, value
    """
    from _divergence_backend import get_backend

    backend = get_backend(cfg)
    mmd_fn = _mmd_rbf_torch if backend == "torch" else compute_mmd_rbf

    seed = cfg["divergence"].get("random_seed", 42)
    rng = np.random.RandomState(seed)

    years, min_papers, max_subsample, windows = _get_years_and_params(df, emb, cfg)
    if not years:
        return pd.DataFrame(columns=["year", "window", "hyperparams", "value"])

    sem_cfg = cfg["divergence"]["semantic"]
    bandwidth_multipliers = sem_cfg["S1_MMD"]["bandwidth_multipliers"]

    equal_n = cfg["divergence"].get("equal_n", False)

    results = []
    last_w = None
    for y, w, X, Y in _iter_window_pairs(
        df,
        emb,
        years,
        windows,
        min_papers,
        max_subsample,
        rng=rng,
        equal_n=equal_n,
    ):
        if last_w is not None and w != last_w:
            log.info("S1 MMD window=%d done", last_w)
        last_w = w

        med = _median_heuristic(X, Y, rng=rng)
        for mult in bandwidth_multipliers:
            bw = med * mult
            val = mmd_fn(X, Y, bw)
            results.append(
                {
                    "year": int(y),
                    "window": str(w),
                    "hyperparams": f"bw={mult}x_median",
                    "value": val,
                }
            )
    if last_w is not None:
        log.info("S1 MMD window=%d done", last_w)
    return pd.DataFrame(results)


# ── S2: Energy distance ──────────────────────────────────────────────────


def _energy_distance_torch(X, Y):
    """Energy distance via torch on CUDA.

    E(X,Y) = 2*E[||X-Y||] - E[||X-X'||] - E[||Y-Y'||]

    Uses V-statistic (includes diagonal) to match dcor.energy_distance.
    """
    import torch
    from _divergence_backend import to_tensor

    Xt = to_tensor(X)
    Yt = to_tensor(Y)

    dXY = torch.cdist(Xt, Yt).mean()
    dXX = torch.cdist(Xt, Xt).mean()
    dYY = torch.cdist(Yt, Yt).mean()

    return float((2.0 * dXY - dXX - dYY).item())


def compute_s2_energy(df, emb, cfg):
    """S2: Energy distance (multivariate via dcor or torch).

    Returns DataFrame with columns: year, window, hyperparams, value
    """
    from _divergence_backend import get_backend

    backend = get_backend(cfg)

    if backend == "numpy":
        import dcor

    seed = cfg["divergence"].get("random_seed", 42)
    rng = np.random.RandomState(seed)

    years, min_papers, max_subsample, windows = _get_years_and_params(df, emb, cfg)
    if not years:
        return pd.DataFrame(columns=["year", "window", "hyperparams", "value"])

    equal_n = cfg["divergence"].get("equal_n", False)

    results = []
    last_w = None
    for y, w, X, Y in _iter_window_pairs(
        df,
        emb,
        years,
        windows,
        min_papers,
        max_subsample,
        rng=rng,
        equal_n=equal_n,
    ):
        if last_w is not None and w != last_w:
            log.info("S2 energy window=%d done", last_w)
        last_w = w

        if backend == "torch":
            val = _energy_distance_torch(X, Y)
        else:
            val = float(dcor.energy_distance(X, Y))
        results.append(
            {
                "year": int(y),
                "window": str(w),
                "hyperparams": "default",
                "value": val,
            }
        )
    if last_w is not None:
        log.info("S2 energy window=%d done", last_w)
    return pd.DataFrame(results)


# ── S3: Sliced Wasserstein ────────────────────────────────────────────────


def compute_s3_wasserstein(df, emb, cfg):
    """S3: Sliced Wasserstein distance with varying projection counts.

    POT natively supports torch tensors, so GPU dispatch is transparent.

    Returns DataFrame with columns: year, window, hyperparams, value
    """
    import ot
    from _divergence_backend import get_backend, to_tensor

    backend = get_backend(cfg)

    seed = cfg["divergence"].get("random_seed", 42)
    rng = np.random.RandomState(seed)

    years, min_papers, max_subsample, windows = _get_years_and_params(df, emb, cfg)
    if not years:
        return pd.DataFrame(columns=["year", "window", "hyperparams", "value"])

    sem_cfg = cfg["divergence"]["semantic"]
    n_projections_list = sem_cfg["S3_sliced_wasserstein"]["n_projections"]
    equal_n = cfg["divergence"].get("equal_n", False)

    results = []
    last_w = None
    for y, w, X, Y in _iter_window_pairs(
        df,
        emb,
        years,
        windows,
        min_papers,
        max_subsample,
        rng=rng,
        equal_n=equal_n,
    ):
        if last_w is not None and w != last_w:
            log.info("S3 sliced Wasserstein window=%d done", last_w)
        last_w = w

        if backend == "torch":
            Xt, Yt = to_tensor(X), to_tensor(Y)
        else:
            Xt, Yt = X, Y

        for n_proj in n_projections_list:
            val = float(
                ot.sliced_wasserstein_distance(
                    Xt,
                    Yt,
                    n_projections=n_proj,
                    seed=seed,
                )
            )
            results.append(
                {
                    "year": int(y),
                    "window": str(w),
                    "hyperparams": f"n_proj={n_proj}",
                    "value": val,
                }
            )
    if last_w is not None:
        log.info("S3 sliced Wasserstein window=%d done", last_w)
    return pd.DataFrame(results)


# ── S4: Frechet distance ─────────────────────────────────────────────────


def compute_frechet_distance(X, Y):
    """Frechet (FID-style) distance between two sets of embeddings.

    Fits a multivariate Gaussian to each set, then computes:
        d = ||mu1 - mu2||^2 + Tr(C1 + C2 - 2*(C1^{1/2} C2 C1^{1/2})^{1/2})
    """
    from scipy.linalg import sqrtm

    mu1 = X.mean(axis=0)
    mu2 = Y.mean(axis=0)

    # Regularised covariance (add small epsilon for numerical stability)
    eps = 1e-6
    C1 = np.cov(X, rowvar=False) + eps * np.eye(X.shape[1])
    C2 = np.cov(Y, rowvar=False) + eps * np.eye(Y.shape[1])

    diff = mu1 - mu2
    mean_term = diff.dot(diff)

    # Matrix square root of C1
    sqrt_C1 = sqrtm(C1)
    if np.iscomplexobj(sqrt_C1):
        sqrt_C1 = sqrt_C1.real

    product = sqrt_C1 @ C2 @ sqrt_C1
    sqrt_product = sqrtm(product)
    if np.iscomplexobj(sqrt_product):
        sqrt_product = sqrt_product.real

    trace_term = np.trace(C1 + C2 - 2.0 * sqrt_product)
    return float(max(mean_term + trace_term, 0.0))


def _frechet_torch(X, Y):
    """Frechet distance via torch on CUDA.

    Uses eigendecomposition for matrix square root (more stable than sqrtm).
    """
    import torch
    from _divergence_backend import to_tensor

    Xt = to_tensor(X)
    Yt = to_tensor(Y)

    mu1 = Xt.mean(dim=0)
    mu2 = Yt.mean(dim=0)

    eps = 1e-6
    C1 = torch.cov(Xt.T) + eps * torch.eye(Xt.shape[1], device=Xt.device)
    C2 = torch.cov(Yt.T) + eps * torch.eye(Yt.shape[1], device=Yt.device)

    diff = mu1 - mu2
    mean_term = diff.dot(diff)

    # Matrix square root via eigendecomposition: S = V diag(sqrt(λ)) V^T
    def _sqrtm_eigh(M):
        eigvals, eigvecs = torch.linalg.eigh(M)
        eigvals = eigvals.clamp(min=0.0)
        return eigvecs @ torch.diag(eigvals.sqrt()) @ eigvecs.T

    sqrt_C1 = _sqrtm_eigh(C1)
    product = sqrt_C1 @ C2 @ sqrt_C1
    sqrt_product = _sqrtm_eigh(product)

    trace_term = torch.trace(C1 + C2 - 2.0 * sqrt_product)
    return float(max((mean_term + trace_term).item(), 0.0))


def compute_s4_frechet(df, emb, cfg):
    """S4: Frechet distance (Gaussian fit).

    Returns DataFrame with columns: year, window, hyperparams, value
    """
    from _divergence_backend import get_backend

    backend = get_backend(cfg)
    frechet_fn = _frechet_torch if backend == "torch" else compute_frechet_distance

    seed = cfg["divergence"].get("random_seed", 42)
    rng = np.random.RandomState(seed)

    years, min_papers, max_subsample, windows = _get_years_and_params(df, emb, cfg)
    if not years:
        return pd.DataFrame(columns=["year", "window", "hyperparams", "value"])

    equal_n = cfg["divergence"].get("equal_n", False)

    results = []
    last_w = None
    for y, w, X, Y in _iter_window_pairs(
        df,
        emb,
        years,
        windows,
        min_papers,
        max_subsample,
        rng=rng,
        equal_n=equal_n,
    ):
        if last_w is not None and w != last_w:
            log.info("S4 Frechet window=%d done", last_w)
        last_w = w

        # Frechet needs n > d for full-rank covariance.
        # With smoke data, n << 1024, so we PCA-reduce first.
        d = X.shape[1]
        n_eff = min(len(X), len(Y))
        if n_eff < d:
            from sklearn.decomposition import PCA

            n_components = max(2, n_eff - 1)
            pca = PCA(n_components=n_components, random_state=seed)
            combined = np.vstack([X, Y])
            combined_r = pca.fit_transform(combined)
            X_r = combined_r[: len(X)]
            Y_r = combined_r[len(X) :]
        else:
            X_r, Y_r = X, Y

        val = frechet_fn(X_r, Y_r)
        results.append(
            {
                "year": int(y),
                "window": str(w),
                "hyperparams": "gaussian",
                "value": val,
            }
        )
    if last_w is not None:
        log.info("S4 Frechet window=%d done", last_w)
    return pd.DataFrame(results)
