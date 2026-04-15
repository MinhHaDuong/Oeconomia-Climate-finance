"""Shared I/O helpers for the divergence pipeline.

Provides extract_method_from_path, infer_channel, load_divergence_tables,
and get_min_papers — used by compute_changepoints, plot_divergence,
compute_convergence, and the _divergence_* modules.
"""

import os
import re

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


def get_min_papers(n_works, cfg):
    """Return appropriate min_papers based on corpus size.

    Uses min_papers_smoke (default 5) when n_works < 200,
    otherwise min_papers (default 30).
    """
    div_cfg = cfg["divergence"]
    if n_works < 200:
        mp = div_cfg.get("min_papers_smoke", 5)
        log.info("Smoke mode: n_works=%d < 200, min_papers=%d", n_works, mp)
        return mp
    return div_cfg.get("min_papers", 30)


def subsample_equal_n(before, after, min_papers, rng):
    """Subsample the larger collection to match the smaller.

    Works on both numpy arrays and Python lists.
    Returns (before_sub, after_sub), or None if min(len) < min_papers.
    """
    import numpy as np

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
