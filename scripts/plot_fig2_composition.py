#!/usr/bin/env python3
"""Plot Figure 2: Thematic recomposition across three periods.

Six-panel grouped horizontal bar chart showing how each thematic cluster's
share evolves from Before (1990-2006) through Crystallisation (2007-2014)
to Disputes (2015-2024).

Inputs:
  - content/tables/tab_alluvial.csv  (period × cluster counts)
  - content/tables/cluster_labels.json (cluster names)

Outputs:
  - content/figures/fig_composition.png (+.pdf unless --no-pdf)

Usage:
    uv run python scripts/plot_fig2_composition.py [--no-pdf]
"""

import argparse
import os
import textwrap

import numpy as np
import pandas as pd

from plot_style import apply_style, FIGWIDTH, DPI, DARK, MED, LIGHT
from utils import BASE_DIR, load_cluster_labels, save_figure

apply_style()
import matplotlib.pyplot as plt

# --- Human-curated short labels (keyed by cluster id string) ---
# Derived from TF-IDF terms in cluster_labels.json; update if clusters change.
SHORT_LABELS = {
    "0": "Green bonds & ESG",             # green, bonds, financing, sustainable, innovation
    "1": "$100bn pledge & fund flows",     # 100 billion, funds, GCF, funding, private
    "2": "GHG markets & trading",          # greenhouse gas, kyoto protocol, cap trade, ETS
    "3": "Ecosystems & land use",          # ecosystem services, forest, water, land, REDD
    "4": "CDM & renewable energy",         # kyoto protocol, CDM, energy, renewable, electricity
    "5": "Paris Agreement & governance",   # paris agreement, human rights, loss damage
}

_ACRONYMS = {"gcf", "cop", "unfccc", "ets", "cdm", "redd", "sdgs", "ndcs", "esg", "co2", "ghg"}


def _format_tfidf_line(terms_str, max_terms=9, line_width=35):
    """Format top TF-IDF terms on two lines, wrapped to fit panel width."""
    terms = [t.strip() for t in terms_str.split("/")][:max_terms]
    formatted = []
    for t in terms:
        if t.lower() in _ACRONYMS:
            formatted.append(t.upper())
        else:
            formatted.append(t.lower())
    flat = ", ".join(formatted)
    return textwrap.fill(flat, width=line_width, max_lines=2, placeholder="…")


def main():
    parser = argparse.ArgumentParser(description="Figure 2: thematic recomposition")
    parser.add_argument("--no-pdf", action="store_true", help="skip PDF output")
    parser.add_argument("--alluvial", type=str, default=None,
                        help="Path to alluvial CSV (default: tab_alluvial.csv)")
    parser.add_argument("--labels", type=str, default=None,
                        help="Path to cluster labels JSON (default: cluster_labels.json)")
    args = parser.parse_args()

    # Load data
    csv_path = args.alluvial or os.path.join(BASE_DIR, "content", "tables", "tab_alluvial.csv")
    df = pd.read_csv(csv_path, index_col=0)

    # Convert to percentages
    totals = df.sum(axis=1)
    pct = df.div(totals, axis=0) * 100

    # Load TF-IDF labels for subtitles
    if args.labels:
        import json
        with open(args.labels) as f:
            raw_labels = {int(k): v for k, v in json.load(f).items()}
    else:
        raw_labels = load_cluster_labels()

    # Order clusters: declining first (top-left), growing last (bottom-right)
    share_change = pct.iloc[-1] - pct.iloc[0]
    ordered_cols = share_change.sort_values().index.tolist()

    # Period info
    period_short = ["Before", "Crystallisation", "Disputes"]
    n_periods = len(pct)
    bar_colors = [DARK, MED, LIGHT]

    # Uniform x-axis: round up to nearest 5
    x_max = int(np.ceil(pct.values.max() / 5) * 5)

    # Layout: 3 rows × 2 columns
    fig, axes = plt.subplots(3, 2, figsize=(FIGWIDTH, FIGWIDTH * 1.15))
    axes_flat = axes.flatten()

    y_positions = np.arange(n_periods)[::-1]  # top = Before, bottom = Disputes
    bar_height = 0.55

    for panel_idx, col in enumerate(ordered_cols):
        ax = axes_flat[panel_idx]
        values = pct[col].values

        # Draw horizontal bars
        for j in range(n_periods):
            ax.barh(
                y_positions[j], values[j], height=bar_height,
                color=bar_colors[j], edgecolor=DARK, linewidth=0.3,
            )
            # Percentage at bar end
            ax.text(
                values[j] + 0.5, y_positions[j],
                f"{values[j]:.0f}%",
                ha="left", va="center", fontsize=6.5, color=DARK,
            )

        # Panel title (bold) + TF-IDF subtitle (italic, smaller)
        short = SHORT_LABELS.get(col, f"Cluster {col}")
        tfidf = _format_tfidf_line(raw_labels.get(int(col), ""))
        ax.text(
            0, 1.24, short,
            transform=ax.transAxes, fontsize=7.5, fontweight="bold",
            color=DARK, ha="left", va="bottom",
        )
        if tfidf:
            ax.text(
                0, 1.06, tfidf,
                transform=ax.transAxes, fontsize=5.5, fontstyle="italic",
                color=MED, ha="left", va="bottom",
            )

        # Same x-axis scale for all panels
        ax.set_xlim(0, x_max + 5)
        ax.set_ylim(-0.5, n_periods - 0.5)

        # Y-axis: period labels only in left column
        ax.set_yticks(y_positions)
        if panel_idx % 2 == 0:
            ax.set_yticklabels(period_short, fontsize=6.5)
        else:
            ax.set_yticklabels([])

        # X-axis: ticks on bottom row only
        if panel_idx >= 4:
            ax.set_xlabel("%", fontsize=7)
        else:
            ax.set_xticklabels([])

        # Minimal spines
        ax.spines["left"].set_visible(False)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.tick_params(left=False)

    fig.subplots_adjust(top=0.97, bottom=0.07, hspace=0.75, wspace=0.18)

    # Save
    out_path = os.path.join(BASE_DIR, "content", "figures", "fig_composition")
    save_figure(fig, out_path, no_pdf=args.no_pdf, dpi=DPI)
    plt.close(fig)


if __name__ == "__main__":
    main()
