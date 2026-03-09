#!/usr/bin/env python3
"""Plot Figure 2: Thematic recomposition across three periods.

Stacked percentage bars show how the six thematic clusters redistribute
from Before (1990-2006) through Crystallisation (2007-2014) to Disputes
(2015-2025). Self-explanatory for HPS readers: no statistical jargon.

Inputs:
  - content/tables/tab2_alluvial.csv  (period × cluster counts)
  - data/catalogs/cluster_labels.json (cluster names)

Outputs:
  - content/figures/fig2_composition.png (+.pdf unless --no-pdf)

Usage:
    uv run python scripts/plot_fig2_composition.py [--no-pdf]
"""

import argparse
import json
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from plot_style import apply_style, FIGWIDTH, DPI, DARK, MED, LIGHT, FILL
from utils import BASE_DIR, CATALOGS_DIR, save_figure

apply_style()
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches

# Short readable labels for the six clusters
CLUSTER_NAMES = {
    "0": "Climate action &\nadaptation",
    "1": "Green finance &\nbonds",
    "2": "CDM & carbon\nmarkets",
    "3": "Renewable\nenergy",
    "4": "Forestry &\nemissions trading",
    "5": "Social dimensions\n& water",
}

# Grayscale + hatching patterns for 6 clusters (print-friendly)
CLUSTER_STYLES = [
    {"color": "#333333", "hatch": ""},       # 0: dark gray
    {"color": "#666666", "hatch": ""},       # 1: medium-dark
    {"color": "#999999", "hatch": ""},       # 2: medium
    {"color": "#BBBBBB", "hatch": ""},       # 3: light
    {"color": "#DDDDDD", "hatch": ""},       # 4: very light
    {"color": "#FFFFFF", "hatch": ""},       # 5: white with border
]

PERIOD_LABELS = [
    "Before\n1990–2006",
    "Crystallisation\n2007–2014",
    "Disputes\n2015–2025",
]


def main():
    parser = argparse.ArgumentParser(description="Figure 2: thematic recomposition")
    parser.add_argument("--no-pdf", action="store_true", help="skip PDF output")
    args = parser.parse_args()

    # Load alluvial data (period × cluster counts)
    csv_path = os.path.join(BASE_DIR, "content", "tables", "tab2_alluvial.csv")
    df = pd.read_csv(csv_path, index_col=0)
    # Columns are cluster indices as strings: "0", "1", ..., "5"

    # Convert to percentages
    totals = df.sum(axis=1)
    pct = df.div(totals, axis=0) * 100

    n_periods = len(pct)
    n_clusters = len(pct.columns)

    # Figure: horizontal stacked bars (one per period)
    fig, ax = plt.subplots(figsize=(FIGWIDTH, 2.8))

    y_pos = np.arange(n_periods)
    bar_height = 0.55

    for i, col in enumerate(pct.columns):
        left = pct.iloc[:, :i].sum(axis=1).values if i > 0 else np.zeros(n_periods)
        widths = pct[col].values
        style = CLUSTER_STYLES[i]
        bars = ax.barh(
            y_pos, widths, left=left, height=bar_height,
            color=style["color"], hatch=style["hatch"],
            edgecolor=DARK, linewidth=0.3,
        )
        # Add percentage labels inside bars if wide enough
        for j, (w, l) in enumerate(zip(widths, left)):
            if w > 8:  # only label if segment > 8%
                # Choose text color based on bar darkness
                text_color = "white" if i <= 1 else DARK
                ax.text(
                    l + w / 2, y_pos[j],
                    f"{w:.0f}%",
                    ha="center", va="center",
                    fontsize=6.5, color=text_color,
                )

    # Period labels on y-axis
    ax.set_yticks(y_pos)
    ax.set_yticklabels(PERIOD_LABELS, fontsize=8)
    ax.invert_yaxis()  # Top-to-bottom chronological order

    # x-axis
    ax.set_xlim(0, 100)
    ax.set_xlabel("Share of publications (%)", fontsize=8)

    # Remove top/right/bottom spines (Tufte)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_visible(True)

    # Add total paper counts at right margin
    for j, (period, total) in enumerate(zip(PERIOD_LABELS, totals)):
        ax.text(
            101, y_pos[j],
            f"N={int(total):,}",
            ha="left", va="center",
            fontsize=7, color=MED,
        )

    # Legend below the chart
    handles = []
    for i, col in enumerate(pct.columns):
        name = CLUSTER_NAMES.get(col, f"Cluster {col}")
        # Single-line version for legend
        name_oneline = name.replace("\n", " ")
        style = CLUSTER_STYLES[i]
        h = mpatches.Patch(
            facecolor=style["color"], hatch=style["hatch"],
            edgecolor=DARK, linewidth=0.3,
            label=name_oneline,
        )
        handles.append(h)

    ax.legend(
        handles=handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.18),
        ncol=3,
        fontsize=6.5,
        frameon=False,
        handlelength=1.2,
        handletextpad=0.4,
        columnspacing=1.0,
    )

    fig.tight_layout(rect=[0, 0.12, 1, 1])

    # Save
    out_path = os.path.join(BASE_DIR, "content", "figures", "fig2_composition")
    save_figure(fig, out_path, no_pdf=args.no_pdf, dpi=DPI)
    plt.close(fig)


if __name__ == "__main__":
    main()
