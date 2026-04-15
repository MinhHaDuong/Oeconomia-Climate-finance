"""Convergence analysis figure: heatmap + stacked bars.

Top panel: heatmap of z-scored divergence values with break markers.
Bottom panel: stacked convergence bars by channel.

Usage:
    python3 scripts/plot_convergence.py \
        --output content/figures/fig_convergence.png \
        --input content/tables/tab_changepoints.csv
"""

import os
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from _divergence_io import load_divergence_tables
from pipeline_io import save_figure
from plot_style import DARK, DPI, FIGWIDTH, MED, apply_style
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("plot_convergence")

apply_style()

# Channel colors
CHANNEL_COLORS = {
    "semantic": "#1f77b4",
    "lexical": "#ff7f0e",
    "citation": "#2ca02c",
}

# Channel display order
CHANNEL_ORDER = ["semantic", "lexical", "citation"]

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

CONVERGENCE_THRESHOLD = 0.50


def _load_divergence_for_heatmap(breaks_path):
    """Load breaks table and auto-discover divergence CSVs in same directory."""
    import glob as globmod

    breaks_df = pd.read_csv(breaks_path)
    tables_dir = os.path.dirname(breaks_path)

    div_paths = sorted(globmod.glob(os.path.join(tables_dir, "tab_div_*.csv")))
    if not div_paths:
        div_paths = sorted(globmod.glob(
            os.path.join(tables_dir, "tab_*_divergence.csv")))

    div_df, _ = load_divergence_tables(div_paths)
    return breaks_df, div_df


def _build_heatmap_matrix(div_df):
    """Build a method x year z-scored matrix for the heatmap.

    Uses window=3 (or first available) and first hyperparams variant.
    Returns (matrix, method_labels, years, channel_boundaries).
    """
    if div_df.empty:
        return None, [], [], {}

    # Pick one representative series per method
    # Prefer window=3, then smallest available
    methods_present = div_df["method"].unique()

    # Filter to methods that exist in our ordering
    all_ordered = METHOD_ORDER_SEM + METHOD_ORDER_LEX + METHOD_ORDER_CIT
    ordered_methods = [m for m in all_ordered if m in methods_present]
    # Add any remaining methods not in our ordering
    extra = [m for m in methods_present if m not in ordered_methods]
    ordered_methods.extend(sorted(extra))

    rows = {}
    for method in ordered_methods:
        mdf = div_df[div_df["method"] == method].dropna(subset=["value"])
        if mdf.empty:
            continue
        # Pick preferred window
        windows = mdf["window"].unique()
        if "3" in windows or 3 in windows:
            sub = mdf[mdf["window"].astype(str) == "3"]
        elif "cumulative" in windows:
            sub = mdf[mdf["window"] == "cumulative"]
        else:
            sub = mdf[mdf["window"] == mdf["window"].iloc[0]]

        # Pick first hyperparams variant
        hps = sub["hyperparams"].unique()
        sub = sub[sub["hyperparams"] == hps[0]]

        series = sub.set_index("year")["value"].sort_index()
        if len(series) < 3:
            continue

        # Z-score
        mean, std = series.mean(), series.std()
        if std > 0:
            z = (series - mean) / std
        else:
            z = series * 0.0
        rows[method] = z

    if not rows:
        return None, [], [], {}

    # Build matrix
    all_years = sorted(set().union(*(r.index for r in rows.values())))
    matrix = np.full((len(rows), len(all_years)), np.nan)
    method_labels = list(rows.keys())
    for i, method in enumerate(method_labels):
        for j, year in enumerate(all_years):
            if year in rows[method].index:
                matrix[i, j] = rows[method].loc[year]

    # Channel boundaries for labeling
    channel_bounds = {}
    for i, m in enumerate(method_labels):
        ch = _method_channel(m)
        if ch not in channel_bounds:
            channel_bounds[ch] = [i, i]
        else:
            channel_bounds[ch][1] = i

    return matrix, method_labels, all_years, channel_bounds


from _divergence_io import infer_channel as _method_channel


def _get_pelt_breaks(breaks_df, method, penalty=3):
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


def plot_convergence(breaks_df, div_df, convergence_df, output_stem):
    """Create the two-panel convergence figure."""
    has_heatmap = not div_df.empty
    has_bars = not convergence_df.empty

    if not has_heatmap and not has_bars:
        log.warning("No data for convergence figure")
        return

    n_panels = (1 if has_heatmap else 0) + (1 if has_bars else 0)
    height_ratios = []
    if has_heatmap:
        height_ratios.append(2)
    if has_bars:
        height_ratios.append(1)

    fig, axes = plt.subplots(
        n_panels, 1,
        figsize=(FIGWIDTH, 2.5 * n_panels),
        gridspec_kw={"height_ratios": height_ratios} if n_panels > 1 else None,
        squeeze=False,
    )
    axes = axes.flatten()
    ax_idx = 0

    # ── Top panel: Heatmap ──
    if has_heatmap:
        ax = axes[ax_idx]
        ax_idx += 1

        result = _build_heatmap_matrix(div_df)
        matrix, method_labels, years, channel_bounds = result

        if matrix is not None and len(method_labels) > 0:
            im = ax.imshow(
                matrix, aspect="auto", cmap="RdYlBu_r",
                interpolation="nearest",
                vmin=-2, vmax=2,
            )
            ax.set_xticks(range(len(years)))
            ax.set_xticklabels(years, rotation=45, ha="right", fontsize=5)
            ax.set_yticks(range(len(method_labels)))
            ax.set_yticklabels(method_labels, fontsize=5)

            # Add break markers (dots)
            for i, method in enumerate(method_labels):
                break_yrs = _get_pelt_breaks(breaks_df, method, penalty=3)
                for by in break_yrs:
                    if by in years:
                        j = years.index(by)
                        ax.plot(j, i, "ko", markersize=3, markerfacecolor="none",
                                markeredgewidth=0.8)

            # Channel labels on the right
            for ch, (start, end) in channel_bounds.items():
                mid = (start + end) / 2
                ax.text(len(years) + 0.5, mid, ch.capitalize(),
                        ha="left", va="center", fontsize=6,
                        color=CHANNEL_COLORS.get(ch, DARK),
                        fontweight="bold")

            fig.colorbar(im, ax=ax, label="z-score", shrink=0.6, pad=0.12)
            ax.set_title("Divergence z-scores with PELT breaks (pen=3)",
                         fontsize=8)
        else:
            ax.text(0.5, 0.5, "Insufficient data for heatmap",
                    ha="center", va="center", transform=ax.transAxes)

    # ── Bottom panel: Convergence bars ──
    if has_bars:
        ax = axes[ax_idx]

        cdf = convergence_df.sort_values("year")
        years = cdf["year"].values
        x = np.arange(len(years))
        width = 0.8

        bottom = np.zeros(len(years))
        for ch in CHANNEL_ORDER:
            col = f"n_{ch}"
            if col in cdf.columns:
                vals = cdf[col].values
                ax.bar(x, vals, width, bottom=bottom,
                       color=CHANNEL_COLORS[ch], label=ch.capitalize(),
                       edgecolor="white", linewidth=0.3)
                bottom += vals

        # Threshold line
        total_possible = bottom.max() / CONVERGENCE_THRESHOLD if bottom.max() > 0 else 1
        if "pct_total" in cdf.columns:
            # Use actual total from data
            total_possible = cdf["n_total"].max() / cdf["pct_total"].max() \
                if cdf["pct_total"].max() > 0 else 1
        threshold_y = total_possible * CONVERGENCE_THRESHOLD
        ax.axhline(threshold_y, color=MED, linewidth=0.7, linestyle="--",
                    label=f"{int(CONVERGENCE_THRESHOLD*100)}% threshold")

        # Highlight years exceeding threshold
        for i, (_, row) in enumerate(cdf.iterrows()):
            if row.get("pct_total", 0) >= CONVERGENCE_THRESHOLD:
                ax.axvspan(i - 0.45, i + 0.45, color="#FFD700",
                           alpha=0.2, zorder=0)

        ax.set_xticks(x)
        ax.set_xticklabels([str(y) for y in years], rotation=45,
                           ha="right", fontsize=6)
        ax.set_ylabel("Detection count")
        ax.set_title("Cross-method convergence by channel", fontsize=8)
        ax.legend(loc="upper left", fontsize=6, frameon=False)

    fig.tight_layout()
    save_figure(fig, output_stem, dpi=DPI)
    plt.close(fig)
    log.info("Saved convergence figure -> %s.png", output_stem)


def main():
    io_args, _extra = parse_io_args()
    validate_io(output=io_args.output)

    if not io_args.input:
        log.error("--input required (path to tab_changepoints.csv)")
        sys.exit(1)

    breaks_path = io_args.input[0]
    breaks_df, div_df = _load_divergence_for_heatmap(breaks_path)

    # Load convergence table (sibling file)
    conv_path = os.path.splitext(breaks_path)[0] + "_convergence.csv"
    if os.path.exists(conv_path):
        convergence_df = pd.read_csv(conv_path)
    else:
        log.warning("Convergence file not found: %s", conv_path)
        convergence_df = pd.DataFrame()

    output_stem = os.path.splitext(io_args.output)[0]
    plot_convergence(breaks_df, div_df, convergence_df, output_stem)


if __name__ == "__main__":
    main()
