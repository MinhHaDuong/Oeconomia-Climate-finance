"""Data loading and matrix building for the convergence figure."""

import os

import numpy as np
import pandas as pd
from _divergence_io import infer_channel as method_channel, load_divergence_tables
from utils import get_logger

log = get_logger("_convergence_data")

# Method order for heatmap (grouped by channel)
METHOD_ORDER_SEM = ["S1_MMD", "S2_energy", "S3_sliced_wasserstein", "S4_frechet"]
METHOD_ORDER_LEX = ["L1", "L2", "L3"]
METHOD_ORDER_CIT = [
    "G1_pagerank",
    "G2_spectral",
    "G3_coupling_age",
    "G4_cross_tradition",
    "G5_pref_attachment",
    "G6_entropy",
    "G7_disruption",
    "G8_betweenness",
]


def load_divergence_for_heatmap(breaks_path):
    """Load breaks table and auto-discover divergence CSVs in same directory."""
    import glob as globmod

    breaks_df = pd.read_csv(breaks_path)
    tables_dir = os.path.dirname(breaks_path)

    div_paths = sorted(globmod.glob(os.path.join(tables_dir, "tab_div_*.csv")))
    if not div_paths:
        div_paths = sorted(
            globmod.glob(os.path.join(tables_dir, "tab_*_divergence.csv"))
        )

    div_df, _ = load_divergence_tables(div_paths)
    return breaks_df, div_df


def _pick_representative_series(mdf):
    """Pick one representative series for a method: prefer window=3."""
    windows = mdf["window"].unique()
    if "3" in windows or 3 in windows:
        sub = mdf[mdf["window"].astype(str) == "3"]
    elif "cumulative" in windows:
        sub = mdf[mdf["window"] == "cumulative"]
    else:
        sub = mdf[mdf["window"] == mdf["window"].iloc[0]]

    hps = sub["hyperparams"].unique()
    return sub[sub["hyperparams"] == hps[0]]


def _zscore(series):
    """Z-score a pandas Series."""
    mean, std = series.mean(), series.std()
    if std > 0:
        return (series - mean) / std
    return series * 0.0


def build_heatmap_matrix(div_df):
    """Build a method x year z-scored matrix for the heatmap.

    Uses window=3 (or first available) and first hyperparams variant.
    Returns (matrix, method_labels, years, channel_boundaries).
    """
    if div_df.empty:
        return None, [], [], {}

    methods_present = div_df["method"].unique()

    all_ordered = METHOD_ORDER_SEM + METHOD_ORDER_LEX + METHOD_ORDER_CIT
    ordered_methods = [m for m in all_ordered if m in methods_present]
    extra = [m for m in methods_present if m not in ordered_methods]
    ordered_methods.extend(sorted(extra))

    rows = {}
    for method in ordered_methods:
        mdf = div_df[div_df["method"] == method].dropna(subset=["value"])
        if mdf.empty:
            continue

        sub = _pick_representative_series(mdf)
        series = sub.set_index("year")["value"].sort_index()
        if len(series) < 3:
            continue

        rows[method] = _zscore(series)

    if not rows:
        return None, [], [], {}

    all_years = sorted(set().union(*(r.index for r in rows.values())))
    matrix = np.full((len(rows), len(all_years)), np.nan)
    method_labels = list(rows.keys())
    for i, m in enumerate(method_labels):
        for j, year in enumerate(all_years):
            if year in rows[m].index:
                matrix[i, j] = rows[m].loc[year]

    channel_bounds = {}
    for i, m in enumerate(method_labels):
        ch = method_channel(m)
        if ch not in channel_bounds:
            channel_bounds[ch] = [i, i]
        else:
            channel_bounds[ch][1] = i

    return matrix, method_labels, all_years, channel_bounds


def get_pelt_breaks(breaks_df, method, penalty=3):
    """Get PELT break years for a method at given penalty."""
    if breaks_df.empty or "break_years" not in breaks_df.columns:
        return set()
    mask = (
        (breaks_df["method"] == method)
        & (breaks_df["detector"] == "pelt")
        & (breaks_df["detector_params"] == f"pen={penalty}")
    )
    years = set()
    for val in breaks_df.loc[mask, "break_years"].dropna():
        for y in str(val).split(";"):
            y = y.strip()
            if y:
                try:
                    years.add(int(float(y)))
                except ValueError:
                    pass
    return years
