"""Semantic distributional divergence (S1-S4): cluster-free break detection.

Four methods compare embedding distributions between adjacent time windows,
producing divergence series that can be screened for structural breaks.

Methods:
  S1  MMD (Maximum Mean Discrepancy) with RBF kernel
  S2  Energy distance (multivariate)
  S3  Sliced Wasserstein distance
  S4  Frechet distance (Gaussian fit)

Reads:  refined_works.csv, refined_embeddings.npz
Writes: long-format CSV via --output

Usage:
    python3 scripts/compute_divergence_semantic.py \
        --output content/tables/tab_semantic_divergence.csv

    # Smoke fixture:
    CLIMATE_FINANCE_DATA=tests/fixtures/smoke \
        python3 scripts/compute_divergence_semantic.py \
        --output content/tables/tab_semantic_divergence.csv
"""

import os
import sys
import warnings

import numpy as np
import pandas as pd
import ruptures

# -- path setup so imports resolve from scripts/ --
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline_loaders import load_analysis_config
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("compute_divergence_semantic")

warnings.filterwarnings("ignore", category=FutureWarning)

# ── Parameters (from config/analysis.yaml) ─────────────────────────────────

cfg = load_analysis_config()
_div_cfg = cfg["divergence"]
_sem_cfg = _div_cfg["semantic"]

RNG = np.random.RandomState(42)


# ── Data loading ───────────────────────────────────────────────────────────

def _load_data(input_paths):
    """Load works CSV and embeddings from CATALOGS_DIR or --input."""
    from utils import CATALOGS_DIR

    if input_paths:
        csv_path = input_paths[0]
        emb_path = input_paths[1] if len(input_paths) > 1 else None
    else:
        csv_path = os.path.join(CATALOGS_DIR, "refined_works.csv")
        emb_path = os.path.join(CATALOGS_DIR, "refined_embeddings.npz")

    if emb_path is None:
        emb_path = os.path.join(os.path.dirname(csv_path), "refined_embeddings.npz")

    df = pd.read_csv(csv_path, usecols=["year", "cited_by_count"])
    df["year"] = df["year"].astype("Int64")
    df = df.dropna(subset=["year"]).reset_index(drop=True)

    emb = np.load(emb_path)["vectors"]

    # Align: embeddings must match df rows
    if len(emb) != len(df):
        n = min(len(emb), len(df))
        log.warning("Row count mismatch (df=%d, emb=%d); truncating to %d",
                     len(df), len(emb), n)
        df = df.iloc[:n].reset_index(drop=True)
        emb = emb[:n]

    log.info("Loaded %d works, embeddings shape %s, years %d-%d",
             len(df), emb.shape,
             int(df["year"].min()), int(df["year"].max()))
    return df, emb


def _get_window_embeddings(df, emb, year, window, side, min_papers, max_subsample):
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
        chosen = RNG.choice(len(vecs), max_subsample, replace=False)
        vecs = vecs[chosen]
    return vecs


# ── S1: MMD with RBF kernel ───────────────────────────────────────────────

def _median_heuristic(X, Y, n_sample=1000):
    """Median of pairwise distances (sampled for speed)."""
    combined = np.vstack([X, Y])
    if len(combined) > n_sample:
        idx = RNG.choice(len(combined), n_sample, replace=False)
        combined = combined[idx]
    from scipy.spatial.distance import pdist
    dists = pdist(combined, metric="sqeuclidean")
    return float(np.median(dists))


def compute_mmd_rbf(X, Y, bandwidth):
    """MMD^2 with RBF kernel at given bandwidth (sigma^2)."""
    gamma = 1.0 / (2.0 * bandwidth) if bandwidth > 0 else 1.0

    # Kernel values via squared Euclidean distances
    from scipy.spatial.distance import cdist

    K_XX = np.exp(-gamma * cdist(X, X, metric="sqeuclidean"))
    K_YY = np.exp(-gamma * cdist(Y, Y, metric="sqeuclidean"))
    K_XY = np.exp(-gamma * cdist(X, Y, metric="sqeuclidean"))

    n = len(X)
    m = len(Y)

    # Unbiased estimator: exclude diagonal for K_XX, K_YY
    mmd2 = ((K_XX.sum() - np.trace(K_XX)) / (n * (n - 1))
             + (K_YY.sum() - np.trace(K_YY)) / (m * (m - 1))
             - 2.0 * K_XY.mean())
    return max(float(mmd2), 0.0)


def _run_s1(df, emb, years, min_papers, max_subsample):
    """S1: MMD with RBF kernel at 0.5x, 1x, 2x median bandwidth."""
    results = []
    bandwidth_multipliers = _sem_cfg["S1_MMD"]["bandwidth_multipliers"]

    for w in _div_cfg["windows"]:
        for y in years:
            X = _get_window_embeddings(df, emb, y, w, "before", min_papers, max_subsample)
            Y = _get_window_embeddings(df, emb, y, w, "after", min_papers, max_subsample)
            if X is None or Y is None:
                continue

            med = _median_heuristic(X, Y)
            for mult in bandwidth_multipliers:
                bw = med * mult
                val = compute_mmd_rbf(X, Y, bw)
                results.append({
                    "year": int(y), "method": "S1_MMD",
                    "window": w,
                    "hyperparams": f"bw={mult}x_median",
                    "value": val,
                })
        log.info("S1 MMD window=%d done", w)
    return results


# ── S2: Energy distance ──────────────────────────────────────────────────

def _run_s2(df, emb, years, min_papers, max_subsample):
    """S2: Energy distance (multivariate via dcor)."""
    import dcor

    results = []
    for w in _div_cfg["windows"]:
        for y in years:
            X = _get_window_embeddings(df, emb, y, w, "before", min_papers, max_subsample)
            Y = _get_window_embeddings(df, emb, y, w, "after", min_papers, max_subsample)
            if X is None or Y is None:
                continue

            val = float(dcor.energy_distance(X, Y))
            results.append({
                "year": int(y), "method": "S2_energy",
                "window": w,
                "hyperparams": "default",
                "value": val,
            })
        log.info("S2 energy window=%d done", w)
    return results


# ── S3: Sliced Wasserstein ────────────────────────────────────────────────

def _run_s3(df, emb, years, min_papers, max_subsample):
    """S3: Sliced Wasserstein distance with varying projection counts."""
    import ot

    n_projections_list = _sem_cfg["S3_sliced_wasserstein"]["n_projections"]
    results = []
    for w in _div_cfg["windows"]:
        for y in years:
            X = _get_window_embeddings(df, emb, y, w, "before", min_papers, max_subsample)
            Y = _get_window_embeddings(df, emb, y, w, "after", min_papers, max_subsample)
            if X is None or Y is None:
                continue

            for n_proj in n_projections_list:
                val = float(ot.sliced_wasserstein_distance(
                    X, Y, n_projections=n_proj, seed=42,
                ))
                results.append({
                    "year": int(y), "method": "S3_sliced_wasserstein",
                    "window": w,
                    "hyperparams": f"n_proj={n_proj}",
                    "value": val,
                })
        log.info("S3 sliced Wasserstein window=%d done", w)
    return results


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


def _run_s4(df, emb, years, min_papers, max_subsample):
    """S4: Frechet distance (Gaussian fit)."""
    results = []
    for w in _div_cfg["windows"]:
        for y in years:
            X = _get_window_embeddings(df, emb, y, w, "before", min_papers, max_subsample)
            Y = _get_window_embeddings(df, emb, y, w, "after", min_papers, max_subsample)
            if X is None or Y is None:
                continue

            # Frechet needs n > d for full-rank covariance.
            # With smoke data, n << 1024, so we PCA-reduce first.
            d = X.shape[1]
            n_eff = min(len(X), len(Y))
            if n_eff < d:
                from sklearn.decomposition import PCA
                n_components = max(2, n_eff - 1)
                pca = PCA(n_components=n_components, random_state=42)
                combined = np.vstack([X, Y])
                combined_r = pca.fit_transform(combined)
                X_r = combined_r[:len(X)]
                Y_r = combined_r[len(X):]
            else:
                X_r, Y_r = X, Y

            val = compute_frechet_distance(X_r, Y_r)
            results.append({
                "year": int(y), "method": "S4_frechet",
                "window": w,
                "hyperparams": "gaussian",
                "value": val,
            })
        log.info("S4 Frechet window=%d done", w)
    return results


# ── PELT break detection ─────────────────────────────────────────────────

def detect_breaks_pelt(series_df):
    """Apply PELT to each (method, window, hyperparams) series.

    Returns a DataFrame with columns:
        method, channel, window, hyperparams, penalty, break_years
    """
    rows = []
    grouped = series_df.groupby(["method", "window", "hyperparams"])
    for (method, window, hp), grp in grouped:
        grp = grp.sort_values("year").dropna(subset=["value"])
        if len(grp) < 3:
            continue
        signal = grp["value"].values.reshape(-1, 1)
        years_arr = grp["year"].values

        for pen in _div_cfg["pelt_penalties"]:
            try:
                algo = ruptures.Pelt(model="rbf", min_size=2, jump=1)
                result = algo.fit(signal).predict(pen=pen)
                # result contains change point indices (1-based, last is n)
                bp_indices = [r for r in result if r < len(signal)]
                bp_years = [int(years_arr[i]) for i in bp_indices]
            except Exception as exc:
                log.warning("PELT failed for %s w=%d %s pen=%d: %s",
                            method, window, hp, pen, exc)
                bp_years = []

            rows.append({
                "method": method,
                "channel": "semantic",
                "window": window,
                "hyperparams": hp,
                "penalty": pen,
                "break_years": ";".join(str(y) for y in bp_years),
            })
    return pd.DataFrame(rows)


# ── Main ─────────────────────────────────────────────────────────────────

def main():
    io_args, _extra = parse_io_args()
    validate_io(output=io_args.output)

    df, emb = _load_data(io_args.input)

    windows = _div_cfg["windows"]
    max_subsample = _div_cfg["max_subsample"]

    # Use smoke-safe minimum when corpus is tiny
    if len(df) < 200:
        min_papers = _div_cfg["min_papers_smoke"]
        log.info("Smoke mode: min_papers set to %d (n_works=%d)", min_papers, len(df))
    else:
        min_papers = _div_cfg["min_papers"]

    start_year = int(df["year"].min()) + max(windows)
    end_year = int(df["year"].max()) - max(windows) - 1
    if start_year > end_year:
        # Fallback: try smaller range
        start_year = int(df["year"].min()) + min(windows)
        end_year = int(df["year"].max()) - min(windows) - 1

    log.info("Year range for divergence: %d-%d", start_year, end_year)
    years = list(range(start_year, end_year + 1))

    if not years:
        log.warning("No valid year range; writing empty CSV")
        pd.DataFrame(columns=["year", "method", "channel", "window", "hyperparams", "value"]
                     ).to_csv(io_args.output, index=False)
        return

    # Run all four methods
    all_results = []
    all_results.extend(_run_s1(df, emb, years, min_papers, max_subsample))
    all_results.extend(_run_s2(df, emb, years, min_papers, max_subsample))
    all_results.extend(_run_s3(df, emb, years, min_papers, max_subsample))
    all_results.extend(_run_s4(df, emb, years, min_papers, max_subsample))

    result_df = pd.DataFrame(all_results)
    result_df["channel"] = "semantic"
    log.info("Computed %d divergence values across 4 methods", len(result_df))

    # Enforce output column order: year,method,channel,window,hyperparams,value
    result_df = result_df[["year", "method", "channel", "window", "hyperparams", "value"]]

    # PELT break detection
    breaks_df = detect_breaks_pelt(result_df)
    log.info("PELT break detection: %d series analysed", len(breaks_df))

    # Save divergence series
    result_df.to_csv(io_args.output, index=False)
    log.info("Saved divergence table -> %s", io_args.output)

    # Save breaks as a companion file
    breaks_path = os.path.splitext(io_args.output)[0] + "_breaks.csv"
    breaks_df.to_csv(breaks_path, index=False)
    log.info("Saved breaks table -> %s", breaks_path)

    log.info("Done.")


if __name__ == "__main__":
    main()
