"""Render the static alluvial figure (matplotlib PNG).

Reads:  content/tables/tab_alluvial.csv
        data/catalogs/cluster_labels.json
        content/tables/tab_core_shares.csv  (optional: full corpus only, for "% core" labels)
Writes: content/figures/fig_alluvial.png  (and core/censor variants)

Flags: --core-only, --censor-gap N, --pdf

Run compute_alluvial.py first to generate the input tables.
See plot_alluvial_html.py for the interactive HTML companion.
"""

import argparse
import json
import os

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.path import Path
from utils import BASE_DIR, get_logger, load_analysis_config, save_figure

log = get_logger("plot_fig_alluvial")

# --- Paths ---
FIGURES_DIR = os.path.join(BASE_DIR, "content", "figures")
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)

_cfg = load_analysis_config()
CITE_THRESHOLD = _cfg["clustering"]["cite_threshold"]

# --- Args ---
parser = argparse.ArgumentParser(description="Render static alluvial figure (PNG)")
parser.add_argument("--pdf", action="store_true", help="Also save PDF output")
parser.add_argument("--core-only", action="store_true",
                    help="Use core-only variant of input tables")
parser.add_argument("--censor-gap", type=int, default=0,
                    help="Load censor-gap variant of input tables (affects FIG_AL name only)")
args = parser.parse_args()

# Output naming mirrors compute_alluvial.py
if args.core_only:
    FIG_AL = "fig_alluvial_core"
    TAB_AL = "tab_alluvial_core.csv"
    LABEL_FILE = "cluster_labels_core.json"
else:
    FIG_AL = "fig_alluvial"
    TAB_AL = "tab_alluvial.csv"
    LABEL_FILE = "cluster_labels.json"

if args.censor_gap > 0:
    FIG_AL += f"_censor{args.censor_gap}"

# --- Load tables ---
alluvial_data = pd.read_csv(os.path.join(TABLES_DIR, TAB_AL), index_col=0)
alluvial_data.columns = alluvial_data.columns.astype(int)
period_labels = alluvial_data.index.tolist()
n_periods = len(period_labels)
n_clusters = len(alluvial_data.columns)

with open(os.path.join(TABLES_DIR, LABEL_FILE)) as f:
    cluster_labels_raw = json.load(f)
cluster_labels = {int(k): v for k, v in cluster_labels_raw.items()}

# Core share per cell (full corpus only, for "% core" annotations)
core_crosstab = None
if not args.core_only:
    shares_path = os.path.join(TABLES_DIR, "tab_core_shares.csv")
    if os.path.exists(shares_path):
        core_crosstab = pd.read_csv(shares_path, index_col=0)
        core_crosstab.columns = core_crosstab.columns.astype(int)

# --- Palette and layout constants ---
palette = plt.cm.Set2(np.linspace(0, 1, n_clusters))

# X positions for period columns (leave room for legend on right)
x_positions = np.linspace(0, 0.62, n_periods)
col_width = 0.04  # Half-width of each column bar


# --- Compute period stacks ---
period_stacks = {}
for pi, period in enumerate(period_labels):
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

last_stacks = period_stacks[period_labels[-1]]


# ============================================================
# Step 7: Render alluvial figure
# ============================================================

fig, ax = plt.subplots(figsize=(7, 3.5))

# Draw column bars
for pi, period in enumerate(period_labels):
    x = x_positions[pi]
    stacks = period_stacks[period]
    for c in range(n_clusters):
        if c not in stacks:
            continue
        s = stacks[c]
        if s["height"] > 0:
            rect = plt.Rectangle(
                (x - col_width, s["bottom"]), 2 * col_width, s["height"],
                facecolor=palette[c], edgecolor="white", linewidth=0.5, alpha=0.9,
            )
            ax.add_patch(rect)
            # Label if tall enough
            if s["height"] > 0.04:
                label = f'{s["count"]}'
                if not args.core_only and core_crosstab is not None:
                    n_core = int(core_crosstab.loc[period, c]) if period in core_crosstab.index else 0
                    pct = n_core / s["count"] * 100 if s["count"] > 0 else 0
                    label += f'\n({pct:.0f}% core)'
                ax.text(x, s["bottom"] + s["height"] / 2,
                        label, ha="center", va="center",
                        fontsize=4.5, color="black", fontweight="bold",
                        linespacing=1.2)

# Draw flows between adjacent periods
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
        sa = stacks_a[c]
        sb = stacks_b[c]
        if sa["height"] <= 0 or sb["height"] <= 0:
            continue

        # Draw curved ribbon from cluster c in period_a to cluster c in period_b
        y_a_bot = sa["bottom"]
        y_a_top = sa["bottom"] + sa["height"]
        y_b_bot = sb["bottom"]
        y_b_top = sb["bottom"] + sb["height"]

        # Bezier control points for smooth flow
        cx1 = x_a + (x_b - x_a) * 0.4
        cx2 = x_a + (x_b - x_a) * 0.6

        # Top edge
        verts_top = [
            (x_a, y_a_top), (cx1, y_a_top), (cx2, y_b_top), (x_b, y_b_top),
        ]
        # Bottom edge (reversed)
        verts_bot = [
            (x_b, y_b_bot), (cx2, y_b_bot), (cx1, y_a_bot), (x_a, y_a_bot),
        ]
        verts = verts_top + verts_bot + [(x_a, y_a_top)]  # close path
        codes = (
            [Path.MOVETO] + [Path.CURVE4] * 3 +
            [Path.LINETO] + [Path.CURVE4] * 3 +
            [Path.CLOSEPOLY]
        )
        path = Path(verts, codes)
        patch = mpatches.PathPatch(
            path, facecolor=palette[c], alpha=0.35, edgecolor="none",
        )
        ax.add_patch(patch)

# Period labels
for pi, period in enumerate(period_labels):
    x = x_positions[pi]
    ax.text(x, -0.03, period, ha="center", va="top", fontsize=6, fontweight="bold")

# Legend: labels with leader lines, evenly spaced to avoid overlap
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

# Evenly space labels across the full chart height
label_items.sort(key=lambda it: it["y_band"])
n_labels = len(label_items)
total_label_height = sum(it["height"] for it in label_items)
spacing = (0.95 - total_label_height) / max(n_labels - 1, 1)
y_cursor = 0.02
for it in label_items:
    it["y_label"] = y_cursor + it["height"] / 2
    y_cursor += it["height"] + spacing

x_bar_edge = x_positions[-1] + col_width
x_label = x_bar_edge + 0.06
for it in label_items:
    # Leader line from band midpoint to label
    ax.annotate(
        "", xy=(x_bar_edge + 0.003, it["y_band"]),
        xytext=(x_label - 0.005, it["y_label"]),
        arrowprops=dict(arrowstyle="-", color=palette[it["c"]] * 0.6,
                        lw=0.7, connectionstyle="arc3,rad=0.0"),
    )
    ax.text(x_label, it["y_label"],
            it["text"], ha="left", va="center", fontsize=5.5,
            linespacing=1.3, color=palette[it["c"]] * 0.6)

ax.set_xlim(-0.06, 0.95)
ax.set_ylim(-0.06, 1.0)
total = int(alluvial_data.values.sum())
core_label = f"core papers cited ≥ {CITE_THRESHOLD}, " if args.core_only else ""
ax.set_title(
    f"Thematic recomposition of scholarship around climate finance, 1990–2024\n"
    f"({core_label}N = {total:,} publications; band width = number of publications per thematic cluster)",
    fontsize=7, pad=8,
)
ax.axis("off")

plt.tight_layout()
save_figure(fig, os.path.join(FIGURES_DIR, FIG_AL), pdf=args.pdf)
log.info("  (%s)", FIG_AL)
plt.close()

log.info("Done.")
