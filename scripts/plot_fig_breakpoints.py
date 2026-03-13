"""Render the structural break detection figure.

Reads:  content/tables/tab_breakpoints.csv
        content/tables/tab_breakpoint_robustness.csv
        content/tables/tab_alluvial.csv  (to compute N for title in --core-only mode)
Writes: content/figures/fig_breakpoints.png  (and core/censor variants)

Flags: --core-only, --censor-gap N, --no-pdf

Run compute_alluvial.py first to generate the input tables.
"""

import argparse
import os

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np
import pandas as pd
import seaborn as sns

from plot_style import COP_EVENTS
from utils import BASE_DIR, save_figure

# --- Paths ---
FIGURES_DIR = os.path.join(BASE_DIR, "content", "figures")
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)

WINDOW_SIZES = [2, 3, 4]
CITE_THRESHOLD = 50

# --- Args ---
parser = argparse.ArgumentParser(description="Render structural break detection figure")
parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation (PNG only)")
parser.add_argument("--core-only", action="store_true",
                    help="Use core-only variant of input tables")
parser.add_argument("--censor-gap", type=int, default=0,
                    help="Load censor-gap variant of input tables")
args = parser.parse_args()

# Output naming mirrors compute_alluvial.py
if args.core_only:
    FIG_BP = "fig_breakpoints_core"
    TAB_BP = "tab_breakpoints_core.csv"
    TAB_BP_ROBUST = "tab_breakpoint_robustness_core.csv"
    TAB_AL = "tab_alluvial_core.csv"
else:
    FIG_BP = "fig_breakpoints"
    TAB_BP = "tab_breakpoints.csv"
    TAB_BP_ROBUST = "tab_breakpoint_robustness.csv"
    TAB_AL = "tab_alluvial.csv"

if args.censor_gap > 0:
    suffix = f"_censor{args.censor_gap}"
    FIG_BP += suffix
    TAB_BP = TAB_BP.replace(".csv", f"{suffix}.csv")
    TAB_BP_ROBUST = TAB_BP_ROBUST.replace(".csv", f"{suffix}.csv")

# --- Load tables ---
bp_df = pd.read_csv(os.path.join(TABLES_DIR, TAB_BP))
robust_df = pd.read_csv(os.path.join(TABLES_DIR, TAB_BP_ROBUST))
robust_list = robust_df.to_dict("records")

# Corpus size from alluvial table (used in title for --core-only mode)
alluvial_df = pd.read_csv(os.path.join(TABLES_DIR, TAB_AL), index_col=0)
n_corpus = int(alluvial_df.values.sum())

# supplementary is always empty (kept for structural compatibility with original)
supplementary = []

# ============================================================
# Step 6: Render breakpoints figure
# ============================================================

sns.set_style("whitegrid")

fig, ax = plt.subplots(figsize=(12, 5))

colors_w = {2: "#E63946", 3: "#457B9D", 4: "#2A9D8F"}
for w in WINDOW_SIZES:
    col = f"z_js_w{w}"
    valid = bp_df[["year", col]].dropna()
    ax.plot(valid["year"], valid[col], "-o", color=colors_w[w], markersize=4,
            label=f"JS div (w={w})", alpha=0.8)

# Mark robust breakpoints (data-derived)
for bp in robust_list[:3]:
    ax.axvspan(bp["year"] - 0.3, bp["year"] + 0.3, alpha=0.25, color="orange",
               zorder=0, label="Data-derived break" if bp == robust_list[0] else "")

# Mark supplementary COP breaks
for yr in supplementary:
    ax.axvspan(yr - 0.3, yr + 0.3, alpha=0.15, color="blue",
               zorder=0, label="COP supplement" if yr == supplementary[0] else "")

# COP event lines
for yr, label in COP_EVENTS.items():
    if 2004 <= yr <= 2024:
        ax.axvline(yr, color="grey", linestyle="--", alpha=0.5, linewidth=0.8)
        ax.text(yr, ax.get_ylim()[1] * 0.95 if ax.get_ylim()[1] > 0 else 2.5,
                label, ha="center", va="top", fontsize=7, color="grey",
                rotation=0)

# Significance bands
ax.axhspan(-1.5, 1.5, alpha=0.08, color="grey", zorder=0)  # non-significant zone
ax.axhline(1.5, color="black", linestyle=":", alpha=0.4, linewidth=0.8)
ax.axhline(2.0, color="black", linestyle="--", alpha=0.4, linewidth=0.8)
ax.axhline(-1.5, color="black", linestyle=":", alpha=0.4, linewidth=0.8)
ax.text(2024.3, 1.5, "z=1.5", fontsize=7, va="center", color="black", alpha=0.5)
ax.text(2024.3, 2.0, "z=2.0", fontsize=7, va="center", color="black", alpha=0.5)
ax.set_xlabel("Year", fontsize=11)
ax.set_ylabel("Structural divergence (z-score)", fontsize=11)
corpus_note = f" (core: cited ≥ {CITE_THRESHOLD}, N={n_corpus:,})" if args.core_only else ""
ax.set_title(f"Detecting structural shifts in scholarship around climate finance{corpus_note}",
             fontsize=12, pad=15)
ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
ax.legend(loc="upper left", fontsize=8, framealpha=0.9)

plt.tight_layout()
save_figure(fig, os.path.join(FIGURES_DIR, FIG_BP), no_pdf=args.no_pdf)
print(f"  ({FIG_BP})")
plt.close()

print("\nDone.")
