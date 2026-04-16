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
from _convergence_data import (
    build_heatmap_matrix,
    get_pelt_breaks,
    load_divergence_for_heatmap,
)
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

CONVERGENCE_THRESHOLD = 0.50


def _draw_heatmap(fig, ax, breaks_df, div_df):
    """Draw the divergence z-score heatmap with PELT break markers."""
    matrix, method_labels, years, channel_bounds = build_heatmap_matrix(div_df)

    if matrix is None or len(method_labels) == 0:
        ax.text(
            0.5,
            0.5,
            "Insufficient data for heatmap",
            ha="center",
            va="center",
            transform=ax.transAxes,
        )
        return

    im = ax.imshow(
        matrix,
        aspect="auto",
        cmap="RdYlBu_r",
        interpolation="nearest",
        vmin=-2,
        vmax=2,
    )
    ax.set_xticks(range(len(years)))
    ax.set_xticklabels(years, rotation=45, ha="right", fontsize=5)
    ax.set_yticks(range(len(method_labels)))
    ax.set_yticklabels(method_labels, fontsize=5)

    # Break markers (dots)
    for i, method in enumerate(method_labels):
        break_yrs = get_pelt_breaks(breaks_df, method, penalty=3)
        for by in break_yrs:
            if by in years:
                j = years.index(by)
                ax.plot(
                    j,
                    i,
                    "ko",
                    markersize=3,
                    markerfacecolor="none",
                    markeredgewidth=0.8,
                )

    # Channel labels on the right
    for ch, (start, end) in channel_bounds.items():
        mid = (start + end) / 2
        ax.text(
            len(years) + 0.5,
            mid,
            ch.capitalize(),
            ha="left",
            va="center",
            fontsize=6,
            color=CHANNEL_COLORS.get(ch, DARK),
            fontweight="bold",
        )

    fig.colorbar(im, ax=ax, label="z-score", shrink=0.6, pad=0.12)
    ax.set_title("Divergence z-scores with PELT breaks (pen=3)", fontsize=8)


def _draw_convergence_bars(ax, convergence_df):
    """Draw the stacked convergence bar chart by channel."""
    cdf = convergence_df.sort_values("year")
    years = cdf["year"].values
    x = np.arange(len(years))
    width = 0.8

    bottom = np.zeros(len(years))
    for ch in CHANNEL_ORDER:
        col = f"n_{ch}"
        if col in cdf.columns:
            vals = cdf[col].values
            ax.bar(
                x,
                vals,
                width,
                bottom=bottom,
                color=CHANNEL_COLORS[ch],
                label=ch.capitalize(),
                edgecolor="white",
                linewidth=0.3,
            )
            bottom += vals

    # Threshold line
    total_possible = bottom.max() / CONVERGENCE_THRESHOLD if bottom.max() > 0 else 1
    if "pct_total" in cdf.columns:
        total_possible = (
            cdf["n_total"].max() / cdf["pct_total"].max()
            if cdf["pct_total"].max() > 0
            else 1
        )
    threshold_y = total_possible * CONVERGENCE_THRESHOLD
    ax.axhline(
        threshold_y,
        color=MED,
        linewidth=0.7,
        linestyle="--",
        label=f"{int(CONVERGENCE_THRESHOLD * 100)}% threshold",
    )

    # Highlight years exceeding threshold
    for i, (_, row) in enumerate(cdf.iterrows()):
        if row.get("pct_total", 0) >= CONVERGENCE_THRESHOLD:
            ax.axvspan(i - 0.45, i + 0.45, color="#FFD700", alpha=0.2, zorder=0)

    ax.set_xticks(x)
    ax.set_xticklabels([str(y) for y in years], rotation=45, ha="right", fontsize=6)
    ax.set_ylabel("Detection count")
    ax.set_title("Cross-method convergence by channel", fontsize=8)
    ax.legend(loc="upper left", fontsize=6, frameon=False)


def plot_convergence(breaks_df, div_df, convergence_df, output_stem):
    """Assemble the two-panel convergence figure."""
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
        n_panels,
        1,
        figsize=(FIGWIDTH, 2.5 * n_panels),
        gridspec_kw={"height_ratios": height_ratios} if n_panels > 1 else None,
        squeeze=False,
    )
    axes = axes.flatten()
    ax_idx = 0

    if has_heatmap:
        _draw_heatmap(fig, axes[ax_idx], breaks_df, div_df)
        ax_idx += 1

    if has_bars:
        _draw_convergence_bars(axes[ax_idx], convergence_df)

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
    breaks_df, div_df = load_divergence_for_heatmap(breaks_path)

    # Load convergence table (second --input, or sibling file)
    if len(io_args.input) >= 2:
        conv_path = io_args.input[1]
    else:
        conv_path = os.path.join(os.path.dirname(breaks_path), "tab_convergence.csv")
    if os.path.exists(conv_path):
        convergence_df = pd.read_csv(conv_path)
    else:
        log.warning("Convergence file not found: %s", conv_path)
        convergence_df = pd.DataFrame()

    output_stem = os.path.splitext(io_args.output)[0]
    plot_convergence(breaks_df, div_df, convergence_df, output_stem)


if __name__ == "__main__":
    main()
