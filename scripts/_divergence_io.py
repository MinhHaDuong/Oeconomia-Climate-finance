"""Shared I/O helpers for the divergence pipeline.

Provides extract_method_from_path, infer_channel, load_divergence_tables,
get_min_papers, iter_semantic_windows, iter_lexical_windows — used by
compute_changepoints, plot_divergence, compute_convergence,
compute_null_model, compute_divergence_bootstrap, and the _divergence_*
modules.
"""

import os
import re

import numpy as np
import pandas as pd
from utils import get_logger

log = get_logger("_divergence_io")

# ── Channel inference ───────────────────────────────────────────────────

CHANNELS = ("semantic", "lexical", "citation")

_PREFIX_TO_CHANNEL = {"S": "semantic", "L": "lexical", "G": "citation"}


def infer_channel(method_name):
    """Infer channel from method name prefix (S/L/G)."""
    for prefix, channel in _PREFIX_TO_CHANNEL.items():
        if method_name.startswith(prefix):
            return channel
    return "unknown"


# ── Method name extraction ──────────────────────────────────────────────


def extract_method_from_path(path):
    """Extract method name from divergence CSV filename.

    Supports: tab_div_{method}.csv, tab_sens_pca_{method}.csv,
    tab_sens_jl_{method}.csv.
    """
    basename = os.path.splitext(os.path.basename(path))[0]
    if basename.startswith("tab_div_"):
        return basename[len("tab_div_") :]
    m = re.match(r"tab_sens_(?:pca|jl)_(.+)", basename)
    if m:
        return m.group(1)
    return None


# ── Divergence table loading ────────────────────────────────────────────


def load_divergence_tables(input_paths):
    """Load and concatenate divergence CSVs, adding method from filename.

    Supports both new (tab_div_{method}.csv, no 'method' column) and legacy
    (tab_{channel}_divergence.csv, has 'method' column) formats.

    Returns (div_df, breaks_df) where breaks_df comes from companion
    _breaks.csv files if present.
    """
    div_frames = []
    breaks_frames = []

    for path in input_paths:
        if not os.path.exists(path):
            log.warning("Input not found: %s", path)
            continue
        df = pd.read_csv(path)

        if "method" not in df.columns:
            method = extract_method_from_path(path)
            if method is None:
                log.warning("Cannot determine method from filename: %s", path)
                continue
            df["method"] = method

        if "channel" not in df.columns:
            df["channel"] = df["method"].apply(infer_channel)

        expected = {"year", "channel", "window", "hyperparams", "value"}
        if not expected.issubset(set(df.columns)):
            log.warning(
                "Skipping %s: missing columns %s", path, expected - set(df.columns)
            )
            continue
        div_frames.append(df)

        breaks_path = os.path.splitext(path)[0] + "_breaks.csv"
        if os.path.exists(breaks_path):
            breaks_frames.append(pd.read_csv(breaks_path))

    div_df = pd.concat(div_frames, ignore_index=True) if div_frames else pd.DataFrame()
    breaks_df = (
        pd.concat(breaks_frames, ignore_index=True) if breaks_frames else pd.DataFrame()
    )
    log.info(
        "Loaded %d divergence rows, %d break rows from %d files",
        len(div_df),
        len(breaks_df),
        len(div_frames),
    )
    return div_df, breaks_df


# ── Smoke-mode parameter selection ──────────────────────────────────────


def get_min_papers(method=None, *, cfg=None, n_works=None):
    """Return appropriate min_papers for a given method and corpus size.

    Lookup order:
    1. Per-method override from config (S4_frechet=300, c2st/C2ST_*=50).
    2. Smoke mode: if n_works < 200, use min_papers_smoke (default 5).
    3. Global min_papers (default 30).

    When cfg is None, loads config/analysis.yaml automatically.
    """
    if cfg is None:
        from pipeline_loaders import load_analysis_config

        cfg = load_analysis_config()
    div_cfg = cfg["divergence"]

    # Per-method overrides take precedence over smoke mode
    if method == "S4_frechet":
        return div_cfg["semantic"]["S4_frechet"].get(
            "min_papers", div_cfg["min_papers"]
        )
    if method in ("c2st", "C2ST_embedding", "C2ST_lexical"):
        return div_cfg["c2st"].get("min_papers", div_cfg["min_papers"])

    # Smoke mode (small corpus)
    if n_works is not None and n_works < 200:
        mp = div_cfg.get("min_papers_smoke", 5)
        log.info("Smoke mode: n_works=%d < 200, min_papers=%d", n_works, mp)
        return mp

    return div_cfg.get("min_papers", 30)


def per_window_year_ranges(df, windows):
    """Per-window valid anchor years for sliding-pair iteration.

    For each window width w, the anchor year y must satisfy
    year_min <= y - w and y + 1 + w <= year_max so both windows fit
    inside the corpus. That gives y in range(year_min + w, year_max - w).

    Returns a dict mapping each w to its sorted list of valid years.
    Narrower windows reach later years; wider windows stop earlier.
    """
    year_min = int(df["year"].min())
    year_max = int(df["year"].max())
    return {w: list(range(year_min + w, year_max - w)) for w in windows}


def empty_divergence_df():
    """Empty DataFrame with the divergence-output column schema.

    Used by compute_* functions as a short-circuit return when the
    corpus has no valid (year, window) anchors.
    """
    return pd.DataFrame(columns=["year", "window", "hyperparams", "value"])


def subsample_equal_n(before, after, min_papers, rng):
    """Subsample the larger collection to match the smaller.

    Works on both numpy arrays and Python lists.
    Returns (before_sub, after_sub), or None if min(len) < min_papers.
    """

    n = min(len(before), len(after))
    if n < min_papers:
        return None
    if len(before) > n:
        idx = rng.choice(len(before), n, replace=False)
        before = (
            before[idx] if isinstance(before, np.ndarray) else [before[i] for i in idx]
        )
    if len(after) > n:
        idx = rng.choice(len(after), n, replace=False)
        after = after[idx] if isinstance(after, np.ndarray) else [after[i] for i in idx]
    return before, after


# ── Window iterators for null model / bootstrap ───────────────────────


def _make_window_rngs(seed, y, w):
    """Return independent (subsample_rng, extra_rng) for a (year, window) pair.

    Each pair gets deterministic seeds derived from (seed, y, w) so results
    are identical regardless of which other pairs are processed (ticket 0061).
    The +50000 offset ensures no overlap: subsample seeds span roughly
    [seed+199044, seed+202547], extra seeds [seed+249044, seed+252547].
    """
    window_seed = seed + y * 100 + w
    return np.random.RandomState(window_seed), np.random.RandomState(
        window_seed + 50000
    )


def _make_subsample_rng(seed, y, w, r):
    """Return an independent RNG for the r-th equal-n subsample draw at (y, w).

    Seeds are at offset +100000 from the window base, stepped by 53 per
    replicate.  This places them in [seed+299042, seed+304567] for the
    supported year/window/replicate range — well above the null-model
    subsample range (~199044–202546) and permutation range (~249044–252546)
    used by _make_window_rngs.  The prime step (53) ensures distinct seeds
    even when (y, w) differ only by one unit.
    """
    subsample_seed = seed + y * 100 + w + 100_000 + r * 53
    return np.random.RandomState(subsample_seed)


def iter_semantic_windows(div_df, cfg):
    """Yield (year, window, X, Y, extra_rng) for each valid semantic window.

    Loads semantic data, iterates over (year, window) pairs from div_df,
    extracts before/after embeddings, and applies equal-n subsampling.
    Shared by compute_null_model and compute_divergence_bootstrap.

    Yields
    ------
    (y, w, X, Y, extra_rng) where X, Y are numpy arrays and extra_rng
    is a per-window RNG available for downstream use (permutation / bootstrap).

    """
    from _divergence_semantic import (
        _get_window_embeddings,
        _get_years_and_params,
        load_semantic_data,
    )

    df, emb = load_semantic_data(None)
    div_cfg = cfg["divergence"]
    seed = div_cfg["random_seed"]
    gap = div_cfg.get("gap", 1)

    _, min_papers, max_subsample, equal_n = _get_years_and_params(df, emb, cfg)

    year_windows = div_df[["year", "window"]].drop_duplicates()

    for _, row in year_windows.iterrows():
        y = int(row["year"])
        w = int(row["window"])

        subsample_rng, extra_rng = _make_window_rngs(seed, y, w)

        X = _get_window_embeddings(
            df,
            emb,
            y,
            w,
            "before",
            min_papers,
            max_subsample,
            rng=subsample_rng,
            gap=gap,
        )
        Y = _get_window_embeddings(
            df,
            emb,
            y,
            w,
            "after",
            min_papers,
            max_subsample,
            rng=subsample_rng,
            gap=gap,
        )
        if X is None or Y is None:
            continue

        if equal_n and len(X) != len(Y):
            eq_result = subsample_equal_n(X, Y, min_papers, subsample_rng)
            if eq_result is None:
                continue
            X, Y = eq_result

        yield y, w, X, Y, extra_rng


def iter_lexical_windows(div_df, cfg):
    """Yield (year, window, texts_before, texts_after, extra_rng) for each valid lexical window.

    Loads lexical data, iterates over (year, window) pairs from div_df,
    extracts before/after text lists, and applies equal-n subsampling.
    Shared by compute_null_model and compute_divergence_bootstrap.

    Yields
    ------
    (y, w, texts_before, texts_after, extra_rng)

    """
    from _divergence_lexical import load_lexical_data

    df = load_lexical_data(None)
    div_cfg = cfg["divergence"]
    seed = div_cfg["random_seed"]
    gap = div_cfg.get("gap", 1)

    min_papers = get_min_papers(cfg=cfg, n_works=len(df))
    equal_n = div_cfg.get("equal_n", False)

    year_windows = div_df[["year", "window"]].drop_duplicates()

    for _, row in year_windows.iterrows():
        y = int(row["year"])
        w = int(row["window"])

        subsample_rng, extra_rng = _make_window_rngs(seed, y, w)

        mask_before = (df["year"] >= y - w) & (df["year"] <= y - gap)
        mask_after = (df["year"] >= y + gap) & (df["year"] <= y + w)

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

        yield y, w, texts_before, texts_after, extra_rng


def fit_lexical_vectorizer(cfg):
    """Fit and return a TF-IDF vectorizer on the full lexical corpus.

    Shared by compute_null_model and compute_divergence_bootstrap.
    """
    from _divergence_lexical import load_lexical_data
    from sklearn.feature_extraction.text import TfidfVectorizer

    df = load_lexical_data(None)
    lex_cfg = cfg["divergence"]["lexical"]

    all_texts = df["abstract"].tolist()
    vec = TfidfVectorizer(
        stop_words="english",
        max_features=lex_cfg["tfidf_max_features"],
        min_df=min(lex_cfg["tfidf_min_df"], max(1, len(all_texts) - 1)),
        sublinear_tf=True,
    )
    vec.fit(all_texts)
    return vec
