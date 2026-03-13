#!/usr/bin/env python3
"""Plot Figure 2: Thematic recomposition across three periods.

Vertical alluvial-style chart showing how six thematic clusters
redistribute from Before (1990-2006) through Crystallisation (2007-2014)
to Disputes (2015-2025).

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
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from plot_style import apply_style, FIGWIDTH, DPI, DARK, MED, LIGHT
from utils import BASE_DIR, load_cluster_labels, save_figure

apply_style()
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.path import Path

_ACRONYMS = {"gcf", "cop", "unfccc", "ets", "cdm", "redd", "sdgs", "ndcs", "esg", "co2"}

def _format_term(term):
    """Title-case, but render known acronyms in ALL CAPS."""
    if term.lower() in _ACRONYMS:
        return term.upper()
    return term.capitalize()

def _short_label(terms_str, width=30):
    """Format terms as comma-separated text, wrapped at `width` characters."""
    import textwrap
    terms = [_format_term(t.strip()) for t in terms_str.split("/")]
    flat = ", ".join(terms)
    return textwrap.fill(flat, width=width)

_raw_labels = load_cluster_labels()
CLUSTER_NAMES = {str(k): _short_label(v) for k, v in _raw_labels.items()}

# Six well-spaced solid greys
CLUSTER_COLORS = ["#1a1a1a", "#4d4d4d", "#808080", "#a6a6a6", "#cccccc", "#f0f0f0"]


def _alluvial_ribbon(ax, x0, x1, y_bot0, y_top0, y_bot1, y_top1, color, alpha=0.45):
    """Draw a smooth ribbon (alluvial flow) between two stacked bar segments."""
    n = 50
    xs = np.linspace(x0, x1, n)
    # Sigmoid interpolation for smooth S-curve
    t = (xs - x0) / (x1 - x0)
    t_smooth = 0.5 * (1 - np.cos(np.pi * t))

    y_bot = y_bot0 + (y_bot1 - y_bot0) * t_smooth
    y_top = y_top0 + (y_top1 - y_top0) * t_smooth

    verts = list(zip(xs, y_bot)) + list(zip(xs[::-1], y_top[::-1]))
    verts.append(verts[0])
    codes = [Path.MOVETO] + [Path.LINETO] * (len(verts) - 2) + [Path.CLOSEPOLY]
    ax.add_patch(mpatches.PathPatch(Path(verts, codes), fc=color, ec="none", alpha=alpha))


def main():
    parser = argparse.ArgumentParser(description="Figure 2: thematic recomposition")
    parser.add_argument("--no-pdf", action="store_true", help="skip PDF output")
    args = parser.parse_args()

    # Load alluvial data (period × cluster counts)
    csv_path = os.path.join(BASE_DIR, "content", "tables", "tab_alluvial.csv")
    df = pd.read_csv(csv_path, index_col=0)

    # Convert to percentages
    totals = df.sum(axis=1)
    pct = df.div(totals, axis=0) * 100

    # Reorder clusters: declining first (bottom), growing last (top)
    share_change = pct.iloc[-1] - pct.iloc[0]
    ordered_cols = share_change.sort_values().index.tolist()

    n_periods = len(pct)
    x_pos = np.arange(n_periods)
    bar_width = 0.45

    fig, ax = plt.subplots(figsize=(FIGWIDTH, FIGWIDTH * 1.15))

    # Track segment positions for ribbons and labels
    # segments[period_idx][cluster_col] = (bottom, top)
    segments = [{} for _ in range(n_periods)]

    # Draw stacked vertical bars
    for i, col in enumerate(ordered_cols):
        bottoms = pct[ordered_cols[:i]].sum(axis=1).values if i > 0 else np.zeros(n_periods)
        heights = pct[col].values
        color = CLUSTER_COLORS[i]

        ax.bar(
            x_pos, heights, bottom=bottoms, width=bar_width,
            color=color, edgecolor=DARK, linewidth=0.3, zorder=3,
        )

        for j in range(n_periods):
            segments[j][col] = (bottoms[j], bottoms[j] + heights[j])

        # Percentage labels inside bars
        for j in range(n_periods):
            h = heights[j]
            if h >= 7:
                cy = bottoms[j] + h / 2
                text_color = "white" if i <= 2 else DARK
                ax.text(
                    x_pos[j], cy, f"{h:.0f}%",
                    ha="center", va="center", fontsize=7,
                    fontweight="bold", color=text_color, zorder=4,
                )

    # Draw alluvial ribbons between adjacent periods
    for p in range(n_periods - 1):
        x0 = x_pos[p] + bar_width / 2
        x1 = x_pos[p + 1] - bar_width / 2
        for i, col in enumerate(ordered_cols):
            bot0, top0 = segments[p][col]
            bot1, top1 = segments[p + 1][col]
            _alluvial_ribbon(ax, x0, x1, bot0, top0, bot1, top1,
                             color=CLUSTER_COLORS[i])

    # Category labels on the right of the last bar
    last = n_periods - 1
    for i, col in enumerate(ordered_cols):
        bot, top = segments[last][col]
        mid = (bot + top) / 2
        name = CLUSTER_NAMES.get(col, f"Cluster {col}")
        delta = pct[col].iloc[last] - pct[col].iloc[0]
        arrow_char = "\u2191" if delta > 0 else "\u2193"
        n_arrows = max(1, round(abs(delta) / 5))
        arrows = arrow_char * n_arrows
        text_color = DARK
        if top - bot > 5:
            ax.text(
                x_pos[last] + bar_width / 2 + 0.06, mid,
                f"{name}  {arrows}",
                ha="left", va="center", fontsize=7, color=text_color,
                linespacing=1.2,
            )

    # Period labels below bars, with N counts
    period_labels = ["Before\n1990–2006", "Crystallisation\n2007–2014", "Disputes\n2015–2025"]
    for j, (label, total) in enumerate(zip(period_labels, totals)):
        ax.text(
            x_pos[j], -3.5, f"{label}\nN\u2009=\u2009{int(total):,}",
            ha="center", va="top", fontsize=7, color=DARK, linespacing=1.2,
        )

    # Title and subtitle — placed in data coords above the 100% bars
    ax.text(
        -0.5, 109,
        "Thematic recomposition of climate finance literature",
        fontsize=9, fontweight="bold", color=DARK, va="top", ha="left",
    )
    ax.text(
        -0.5, 105,
        "Share of publications by topic cluster across three periods",
        fontsize=7, color=MED, va="top", ha="left",
    )

    # Clean up: no axis labels, no ticks
    ax.set_xlim(-0.5, x_pos[-1] + bar_width / 2 + 2.0)
    ax.set_ylim(0, 110)
    ax.set_xticks([])
    ax.set_yticks([])
    ax.spines["left"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

    fig.tight_layout()

    # Save
    out_path = os.path.join(BASE_DIR, "content", "figures", "fig_composition")
    save_figure(fig, out_path, no_pdf=args.no_pdf, dpi=DPI)
    plt.close(fig)


if __name__ == "__main__":
    main()
