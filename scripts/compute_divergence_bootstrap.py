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
    _make_window_rngs,
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
        rng = np.random.RandomState(seed + i * 1000)
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


def _run_semantic_bootstrap(method_name, div_df, cfg, k):
    """Bootstrap for semantic methods (S1-S4)."""
    from _divergence_io import subsample_equal_n
    from _divergence_semantic import (
        _get_window_embeddings,
        _get_years_and_params,
        load_semantic_data,
    )

    df, emb = load_semantic_data(None)
    div_cfg = cfg["divergence"]
    seed = div_cfg["random_seed"]

    _, min_papers, max_subsample, _, equal_n = _get_years_and_params(df, emb, cfg)

    statistic_fn = _make_semantic_statistic(method_name, cfg)

    year_windows = div_df[["year", "window"]].drop_duplicates()

    rows = []
    for _, row in year_windows.iterrows():
        y = int(row["year"])
        w = int(row["window"])

        subsample_rng, _ = _make_window_rngs(seed, y, w)

        X = _get_window_embeddings(
            df, emb, y, w, "before", min_papers, max_subsample, rng=subsample_rng
        )
        Y = _get_window_embeddings(
            df, emb, y, w, "after", min_papers, max_subsample, rng=subsample_rng
        )
        if X is None or Y is None:
            continue

        if equal_n and len(X) != len(Y):
            eq_result = subsample_equal_n(X, Y, min_papers, subsample_rng)
            if eq_result is None:
                continue
            X, Y = eq_result

        # Per-window deterministic seed for bootstrap
        boot_seed = seed + y * 100 + w
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


def _run_lexical_bootstrap(method_name, div_df, cfg, k):
    """Bootstrap for lexical methods (L1)."""
    from _divergence_io import get_min_papers, subsample_equal_n
    from _divergence_lexical import load_lexical_data
    from sklearn.feature_extraction.text import TfidfVectorizer

    df = load_lexical_data(None)
    div_cfg = cfg["divergence"]
    lex_cfg = div_cfg["lexical"]
    seed = div_cfg["random_seed"]

    min_papers = get_min_papers(len(df), cfg)
    equal_n = div_cfg.get("equal_n", False)

    tfidf_max_features = lex_cfg["tfidf_max_features"]
    tfidf_min_df = lex_cfg["tfidf_min_df"]

    all_texts = df["abstract"].tolist()
    vec = TfidfVectorizer(
        stop_words="english",
        max_features=tfidf_max_features,
        min_df=min(tfidf_min_df, max(1, len(all_texts) - 1)),
        sublinear_tf=True,
    )
    vec.fit(all_texts)

    statistic_fn = _make_lexical_statistic(vec)

    year_windows = div_df[["year", "window"]].drop_duplicates()

    rows = []
    for _, row in year_windows.iterrows():
        y = int(row["year"])
        w = int(row["window"])

        subsample_rng, _ = _make_window_rngs(seed, y, w)

        mask_before = (df["year"] >= y - w) & (df["year"] <= y)
        mask_after = (df["year"] >= y + 1) & (df["year"] <= y + 1 + w)

        texts_before = df.loc[mask_before, "abstract"].tolist()
        texts_after = df.loc[mask_after, "abstract"].tolist()

        if len(texts_before) < min_papers or len(texts_after) < min_papers:
            continue

        if equal_n and len(texts_before) != len(texts_after):
            eq_result = subsample_equal_n(
                texts_before, texts_after, min_papers, subsample_rng
            )
            if eq_result is None:
                continue
            texts_before, texts_after = eq_result

        boot_seed = seed + y * 100 + w
        values = bootstrap_one_window(
            texts_before, texts_after, statistic_fn, k, boot_seed
        )

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
        default=200,
        help="Number of bootstrap replicates (default 200)",
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
    log.info("=== Bootstrap: %s (channel=%s, k=%d) ===", method_name, channel, args.k)

    div_df = pd.read_csv(args.div_csv)
    log.info("Loaded %d rows from %s", len(div_df), args.div_csv)

    if channel == "semantic":
        result = _run_semantic_bootstrap(method_name, div_df, cfg, args.k)
    elif channel == "lexical":
        result = _run_lexical_bootstrap(method_name, div_df, cfg, args.k)
    else:
        raise ValueError(f"Unsupported channel: {channel}")

    # Validate contract
    BootstrapSchema.validate(result)

    result.to_csv(io_args.output, index=False)
    log.info("Saved %s (%d rows) -> %s", method_name, len(result), io_args.output)


if __name__ == "__main__":
    main()
