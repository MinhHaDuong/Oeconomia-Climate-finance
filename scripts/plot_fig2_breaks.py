#!/usr/bin/env python3
"""Plot Figure 2: Structural break detection via two divergence metrics.

Shows both Jensen-Shannon (solid) and cosine (dashed) z-scores (window=3).
2007 is a cosine break, 2013 is a JS break. Paris and Glasgow are not breaks.

Inputs:
  - content/tables/tab_breakpoints.csv

Outputs:
  - content/figures/fig2_breaks.png (+.pdf if --pdf)

Usage:
    uv run python scripts/plot_fig2_breaks.py [--pdf]
"""

import argparse
import os

import numpy as np
import pandas as pd
from plot_style import DARK, DPI, FIGWIDTH, LIGHT, MED, apply_style
from utils import BASE_DIR, save_figure

apply_style()
import matplotlib.pyplot as plt


def main():
    parser = argparse.ArgumentParser(description="Figure 2: structural breaks")
    parser.add_argument("--pdf", action="store_true", help="Also save PDF output")
    args = parser.parse_args()

    # Load data
    csv_path = os.path.join(BASE_DIR, "content", "tables", "tab_breakpoints.csv")
    df = pd.read_csv(csv_path)
    years = df["year"].values
    z_js = df["z_js_w3"].values
    z_cos = df["z_cos_w3"].values

    # Figure
    fig, ax = plt.subplots(figsize=(FIGWIDTH, 3.0))

    # Two lines: JS solid, cosine dashed
    ax.plot(years, z_js, color="black", linewidth=1.0, label="Jensen-Shannon")
    ax.plot(years, z_cos, color=MED, linewidth=0.8, linestyle="--",
            label="Cosine distance")

    # Significance threshold
    ax.axhline(1.5, color=LIGHT, linewidth=0.5, linestyle=":")

    # Break markers: 2007 on cosine line, 2013 on JS line
    for yr, metric, line_vals, label in [
        (2007, "cosine", z_cos, "2007\n(Bali)"),
        (2013, "JS", z_js, "2013"),
    ]:
        idx = np.where(years == yr)[0][0]
        ax.plot(yr, line_vals[idx], "o", color="black", markersize=5, zorder=5)
        ax.annotate(
            label,
            xy=(yr, line_vals[idx]),
            xytext=(0, 8),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=7,
            color=DARK,
        )

    # Non-break markers on the max of both lines
    for yr, label, x_off in [(2015, "Paris 2015", 6), (2021, "Glasgow 2021", 6)]:
        idx = np.where(years == yr)[0][0]
        y_val = max(z_js[idx], z_cos[idx])
        ax.plot(yr, y_val, "o", markersize=4,
                markerfacecolor="white", markeredgecolor=MED, zorder=5)
        ax.annotate(
            label,
            xy=(yr, y_val),
            xytext=(x_off, 4),
            textcoords="offset points",
            ha="left",
            va="bottom",
            fontsize=6,
            color=MED,
        )

    # Legend (compact, upper right)
    ax.legend(loc="upper right", frameon=False, fontsize=6.5)

    # Axes
    ax.set_xticks(years)
    ax.set_xticklabels(years.astype(int), rotation=45, ha="right")
    ax.set_ylabel("Structural divergence (z-score)")

    fig.tight_layout()

    # Save
    out_path = os.path.join(BASE_DIR, "content", "figures", "fig_breaks")
    save_figure(fig, out_path, pdf=args.pdf, dpi=DPI)
    plt.close(fig)


if __name__ == "__main__":
    main()
