"""NCC Figure (d): Alluvial diagram showing stable cluster structure.

Wrapper around the alluvial rendering logic, formatted for Nature Climate
Change specifications (Arial, 5-8pt, double-column width). Reads the same
data as plot_fig_alluvial.py but applies NCC-specific styling.

Reads:
  content/tables/tab_alluvial.csv        — period x cluster counts
  content/tables/cluster_labels.json     — human-readable cluster names
  content/tables/tab_core_shares.csv     — core % per cluster (optional)

Writes:
  content/figures/fig_ncc_alluvial.png (and .pdf if --pdf)

Usage:
    uv run python scripts/plot_ncc_alluvial.py \
        --output content/figures/fig_ncc_alluvial.png
"""

import argparse
import json
import os

import matplotlib
import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.path import Path
from script_io_args import parse_io_args, validate_io
from utils import BASE_DIR, get_logger, save_figure

log = get_logger("plot_ncc_alluvial")

TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")

# NCC specifications
NCC_DOUBLE_COL_MM = 183
NCC_DPI = 450
NCC_FONT = "Arial"
NCC_FONTSIZE = 7

FIGWIDTH = NCC_DOUBLE_COL_MM / 25.4


def _apply_ncc_style():
    """Apply NCC figure style."""
    matplotlib.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": [NCC_FONT, "Helvetica", "DejaVu Sans"],
        "font.size": NCC_FONTSIZE,
        "axes.titlesize": 8,
        "axes.labelsize": NCC_FONTSIZE,
        "xtick.labelsize": 6,
        "ytick.labelsize": 6,
        "legend.fontsize": 5.5,
        "figure.dpi": NCC_DPI,
        "savefig.dpi": NCC_DPI,
        "axes.linewidth": 0.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
    })


def _compute_stacks(alluvial_data, period_labels, n_clusters):
    """Compute vertical stacks for each period column."""
    period_stacks = {}
    for period in period_labels:
        total = alluvial_data.loc[period].sum() if period in alluvial_data.index else 0
        if total == 0:
            period_stacks[period] = {}
            continue
        max_height = 0.9
        y_bottom = 0.05
        stacks = {}
        for c in range(n_clusters):
            count = alluvial_data.loc[period, c] if period in alluvial_data.index else 0
            height = (count / total) * max_height
            stacks[c] = {"bottom": y_bottom, "height": height, "count": count}
            y_bottom += height
        period_stacks[period] = stacks
    return period_stacks


def _draw_flows(ax, period_labels, x_positions, col_width, period_stacks,
                n_clusters, palette):
    """Draw curved flow ribbons between adjacent periods."""
    n_periods = len(period_labels)
    for pi in range(n_periods - 1):
        period_a = period_labels[pi]
        period_b = period_labels[pi + 1]
        x_a = x_positions[pi] + col_width
        x_b = x_positions[pi + 1] - col_width
        stacks_a = period_stacks[period_a]
        stacks_b = period_stacks[period_b]

        for c in range(n_clusters):
            if c not in stacks_a or c not in stacks_b:
                continue
            sa, sb = stacks_a[c], stacks_b[c]
            if sa["height"] <= 0 or sb["height"] <= 0:
                continue
            cx1 = x_a + (x_b - x_a) * 0.4
            cx2 = x_a + (x_b - x_a) * 0.6
            verts_top = [
                (x_a, sa["bottom"] + sa["height"]),
                (cx1, sa["bottom"] + sa["height"]),
                (cx2, sb["bottom"] + sb["height"]),
                (x_b, sb["bottom"] + sb["height"]),
            ]
            verts_bot = [
                (x_b, sb["bottom"]),
                (cx2, sb["bottom"]),
                (cx1, sa["bottom"]),
                (x_a, sa["bottom"]),
            ]
            verts = verts_top + verts_bot + [(x_a, sa["bottom"] + sa["height"])]
            codes = (
                [Path.MOVETO] + [Path.CURVE4] * 3
                + [Path.LINETO] + [Path.CURVE4] * 3
                + [Path.CLOSEPOLY]
            )
            path = Path(verts, codes)
            patch = mpatches.PathPatch(
                path, facecolor=palette[c], alpha=0.30, edgecolor="none",
            )
            ax.add_patch(patch)


def _draw_column_bars(ax, period_labels, x_positions, col_width, period_stacks,
                      n_clusters, palette, core_crosstab):
    """Draw stacked column bars for each period."""
    for pi, period in enumerate(period_labels):
        x = x_positions[pi]
        stacks = period_stacks[period]
        for c in range(n_clusters):
            if c not in stacks:
                continue
            s = stacks[c]
            if s["height"] <= 0:
                continue
            rect = plt.Rectangle(
                (x - col_width, s["bottom"]), 2 * col_width, s["height"],
                facecolor=palette[c], edgecolor="white", linewidth=0.4,
                alpha=0.85,
            )
            ax.add_patch(rect)
            # Label with count (and core % if available)
            if s["height"] > 0.04:
                label = f'{s["count"]:,}'
                if core_crosstab is not None:
                    n_core = int(core_crosstab.loc[period, c]) if period in core_crosstab.index else 0
                    pct = n_core / s["count"] * 100 if s["count"] > 0 else 0
                    label += f"\n({pct:.0f}% core)"
                ax.text(
                    x, s["bottom"] + s["height"] / 2, label,
                    ha="center", va="center", fontsize=4, color="black",
                    fontweight="bold", linespacing=1.2,
                )


def _draw_legend_labels(ax, last_stacks, cluster_labels, n_clusters,
                        x_bar_edge, palette):
    """Draw legend labels with leader lines to the right of the last column."""
    label_items = []
    for c in range(n_clusters):
        if c not in last_stacks:
            continue
        s = last_stacks[c]
        if s["height"] <= 0:
            continue
        label_text = cluster_labels.get(c, f"Cluster {c}").replace(" / ", "\n")
        n_lines = label_text.count("\n") + 1
        label_items.append({
            "c": c, "y_band": s["bottom"] + s["height"] / 2,
            "text": label_text, "height": n_lines * 0.026,
        })

    label_items.sort(key=lambda it: it["y_band"])
    n_labels = len(label_items)
    total_label_height = sum(it["height"] for it in label_items)
    spacing = (0.95 - total_label_height) / max(n_labels - 1, 1)
    y_cursor = 0.02
    for it in label_items:
        it["y_label"] = y_cursor + it["height"] / 2
        y_cursor += it["height"] + spacing

    x_label = x_bar_edge + 0.05
    for it in label_items:
        ax.annotate(
            "", xy=(x_bar_edge + 0.003, it["y_band"]),
            xytext=(x_label - 0.005, it["y_label"]),
            arrowprops=dict(
                arrowstyle="-", color=palette[it["c"]] * 0.6,
                lw=0.6, connectionstyle="arc3,rad=0.0",
            ),
        )
        ax.text(
            x_label, it["y_label"], it["text"],
            ha="left", va="center", fontsize=5,
            linespacing=1.2, color=palette[it["c"]] * 0.6,
        )


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    parser = argparse.ArgumentParser(
        description="NCC alluvial diagram (stable cluster structure)"
    )
    parser.add_argument("--pdf", action="store_true", help="Also save PDF output")
    args = parser.parse_args(extra)

    _apply_ncc_style()

    # --- Load data ---
    if io_args.input:
        alluvial_data = pd.read_csv(io_args.input[0], index_col=0)
    else:
        alluvial_data = pd.read_csv(
            os.path.join(TABLES_DIR, "tab_alluvial.csv"), index_col=0,
        )
    alluvial_data.columns = alluvial_data.columns.astype(int)
    period_labels = alluvial_data.index.tolist()
    n_periods = len(period_labels)
    n_clusters = len(alluvial_data.columns)

    with open(os.path.join(TABLES_DIR, "cluster_labels.json")) as f:
        cluster_labels_raw = json.load(f)
    cluster_labels = {int(k): v for k, v in cluster_labels_raw.items()}

    # Optional core shares
    core_crosstab = None
    shares_path = os.path.join(TABLES_DIR, "tab_core_shares.csv")
    if os.path.exists(shares_path):
        core_crosstab = pd.read_csv(shares_path, index_col=0)
        core_crosstab.columns = core_crosstab.columns.astype(int)

    # --- Layout ---
    palette = plt.cm.Set2(np.linspace(0, 1, n_clusters))
    x_positions = np.linspace(0, 0.62, n_periods)
    col_width = 0.04

    period_stacks = _compute_stacks(alluvial_data, period_labels, n_clusters)
    last_stacks = period_stacks[period_labels[-1]]

    # --- Render ---
    fig_height = FIGWIDTH * 0.40
    fig, ax = plt.subplots(figsize=(FIGWIDTH, fig_height))

    _draw_column_bars(
        ax, period_labels, x_positions, col_width, period_stacks,
        n_clusters, palette, core_crosstab,
    )
    _draw_flows(
        ax, period_labels, x_positions, col_width, period_stacks,
        n_clusters, palette,
    )

    # Period labels below bars
    for pi, period in enumerate(period_labels):
        ax.text(
            x_positions[pi], -0.03, period, ha="center", va="top",
            fontsize=6, fontweight="bold",
        )

    # Legend labels with leader lines
    _draw_legend_labels(
        ax, last_stacks, cluster_labels, n_clusters,
        x_positions[-1] + col_width, palette,
    )

    ax.set_xlim(-0.06, 0.95)
    ax.set_ylim(-0.06, 1.0)
    total = int(alluvial_data.values.sum())
    ax.set_title(
        "Thematic recomposition of scholarship around climate finance, "
        f"1990\u20132024\n"
        f"(N = {total:,} publications; band width = cluster size)",
        fontsize=7, pad=8,
    )
    ax.axis("off")

    fig.tight_layout()
    out_stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, out_stem, pdf=args.pdf, dpi=NCC_DPI)
    log.info("Saved %s", io_args.output)
    plt.close(fig)


if __name__ == "__main__":
    main()
