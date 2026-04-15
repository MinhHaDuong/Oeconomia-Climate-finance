"""Embedding insensitivity analysis: PCA dimensionality sweep and JL random projections.

Tests whether structural break detection survives dimensionality reduction
(PCA) and random projections (Johnson-Lindenstrauss). Addresses the reviewer
concern that results may be specific to BGE-M3 embedding geometry.

Usage:
    python3 scripts/compute_embedding_sensitivity.py \
        --method S1_MMD --projection pca \
        --output content/tables/tab_sens_pca_S1_MMD.csv

    # Smoke fixture:
    CLIMATE_FINANCE_DATA=tests/fixtures/smoke \
        python3 scripts/compute_embedding_sensitivity.py \
        --method S2_energy --projection pca \
        --output /tmp/tab_sens_pca_S2_energy.csv
"""

import copy
import os
import sys

# -- path setup so imports resolve from scripts/ --
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pipeline_loaders import load_analysis_config
from schemas import DivergenceSchema
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("compute_embedding_sensitivity")

# ── Method registry (semantic methods only) ──────────────────────────────

METHOD_FUNCS = {
    "S1_MMD": "compute_s1_mmd",
    "S2_energy": "compute_s2_energy",
    "S3_sliced_wasserstein": "compute_s3_wasserstein",
    "S4_frechet": "compute_s4_frechet",
}

# ── Projection dimensions ────────────────────────────────────────────────

PCA_DIMS = [32, 64, 128, 256, 512]
JL_DIMS = [64, 128, 256]
JL_RUNS = 20


def _get_method_func(method_name):
    """Import and return the method function from _divergence_semantic."""
    from _divergence_semantic import (
        compute_s1_mmd,
        compute_s2_energy,
        compute_s3_wasserstein,
        compute_s4_frechet,
    )
    funcs = {
        "compute_s1_mmd": compute_s1_mmd,
        "compute_s2_energy": compute_s2_energy,
        "compute_s3_wasserstein": compute_s3_wasserstein,
        "compute_s4_frechet": compute_s4_frechet,
    }
    func_name = METHOD_FUNCS[method_name]
    return funcs[func_name]


def _make_sensitivity_cfg(base_cfg):
    """Override config to use only window=3 for the sensitivity analysis."""
    cfg = copy.deepcopy(base_cfg)
    cfg["divergence"]["windows"] = [3]
    return cfg


def _append_projection_tag(df, tag):
    """Append projection=tag to the hyperparams column."""
    if df.empty:
        return df
    df = df.copy()
    df["hyperparams"] = df["hyperparams"].apply(
        lambda hp: f"{hp};projection={tag}" if hp and hp != "default"
        else f"projection={tag}"
    )
    return df


def run_pca_sweep(df, emb, cfg, method_name):
    """Run PCA dimensionality sweep: project to d dims, compute divergence."""
    from sklearn.decomposition import PCA

    func = _get_method_func(method_name)
    sens_cfg = _make_sensitivity_cfg(cfg)
    frames = []

    # Original (full) embeddings as baseline
    log.info("Running %s on original %d-dim embeddings", method_name, emb.shape[1])
    result = func(df, emb, sens_cfg)
    result = _append_projection_tag(result, "original")
    frames.append(result)

    # PCA sweep — skip dims >= min(n_samples, n_features)
    max_components = min(emb.shape[0], emb.shape[1])
    for d in PCA_DIMS:
        if d >= max_components:
            log.info("Skipping PCA d=%d (>= max_components %d)", d, max_components)
            continue
        log.info("PCA projecting to d=%d", d)
        pca = PCA(n_components=d, random_state=42)
        emb_proj = pca.fit_transform(emb)
        result = func(df, emb_proj, sens_cfg)
        result = _append_projection_tag(result, f"pca_{d}")
        frames.append(result)

    import pandas as pd
    combined = pd.concat(frames, ignore_index=True)
    return combined


def run_jl_sweep(df, emb, cfg, method_name):
    """Run Johnson-Lindenstrauss random projection sweep."""
    import pandas as pd
    from sklearn.random_projection import GaussianRandomProjection

    func = _get_method_func(method_name)
    sens_cfg = _make_sensitivity_cfg(cfg)
    frames = []

    for d in JL_DIMS:
        if d >= emb.shape[1]:
            log.info("Skipping JL d=%d (>= original %d)", d, emb.shape[1])
            continue
        for r in range(JL_RUNS):
            seed = 42 + r
            log.info("JL d=%d run=%02d (seed=%d)", d, r, seed)
            transformer = GaussianRandomProjection(
                n_components=d, random_state=seed,
            )
            emb_proj = transformer.fit_transform(emb)
            result = func(df, emb_proj, sens_cfg)
            result = _append_projection_tag(result, f"jl_{d}_run{r:02d}")
            frames.append(result)

    combined = pd.concat(frames, ignore_index=True)
    return combined


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--method", required=True, choices=METHOD_FUNCS.keys())
    parser.add_argument("--projection", required=True, choices=["pca", "jl"])
    args = parser.parse_args(extra)

    cfg = load_analysis_config()

    # Load semantic data
    from _divergence_semantic import load_semantic_data
    df, emb = load_semantic_data(io_args.input)

    if args.projection == "pca":
        result = run_pca_sweep(df, emb, cfg, args.method)
    else:
        result = run_jl_sweep(df, emb, cfg, args.method)

    result["channel"] = "semantic"

    # Validate contract
    DivergenceSchema.validate(result)

    # Write output
    out_dir = os.path.dirname(io_args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    result.to_csv(io_args.output, index=False)
    log.info("Saved %s %s (%d rows) -> %s",
             args.method, args.projection, len(result), io_args.output)


if __name__ == "__main__":
    main()
