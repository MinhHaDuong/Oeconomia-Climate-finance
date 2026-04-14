"""Plot semantic divergence curves (S1-S4) with PELT-detected breaks.

Reads the long-format CSV produced by compute_divergence_semantic.py and
its companion _breaks.csv, then produces one figure per method:

  fig_divergence_S1.png  (MMD)
  fig_divergence_S2.png  (Energy distance)
  fig_divergence_S3.png  (Sliced Wasserstein)
  fig_divergence_S4.png  (Frechet)

Usage:
    python3 scripts/plot_divergence_semantic.py \
        --output content/figures/fig_divergence_S1.png \
        [--input content/tables/tab_semantic_divergence.csv]
"""

import os
import sys

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

# -- path setup --
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from script_io_args import parse_io_args, validate_io
from utils import get_logger, save_figure

log = get_logger("plot_divergence_semantic")

# Apply style manually (avoid importing plot_style which needs config/analysis.yaml)
matplotlib.rcParams.update({
    "font.family": "serif",
    "font.size": 8,
    "axes.titlesize": 10,
    "axes.labelsize": 8,
    "xtick.labelsize": 7,
    "ytick.labelsize": 7,
    "legend.fontsize": 6,
    "figure.dpi": 300,
    "savefig.dpi": 300,
    "axes.linewidth": 0.5,
    "lines.linewidth": 0.8,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": False,
})

DPI = 300
FIGWIDTH = 135 / 25.4  # 5.3 inches

# Method metadata
METHOD_INFO = {
    "S1_MMD": {
        "title": "S1: Maximum Mean Discrepancy (RBF kernel)",
        "suffix": "S1",
        "ylabel": "MMD\u00b2",
    },
    "S2_energy": {
        "title": "S2: Energy Distance",
        "suffix": "S2",
        "ylabel": "Energy distance",
    },
    "S3_sliced_wasserstein": {
        "title": "S3: Sliced Wasserstein Distance",
        "suffix": "S3",
        "ylabel": "Sliced Wasserstein distance",
    },
    "S4_frechet": {
        "title": "S4: Fr\u00e9chet Distance",
        "suffix": "S4",
        "ylabel": "Fr\u00e9chet distance",
    },
}

# Visual encoding
WINDOW_STYLES = {2: "-", 3: "--", 4: "-.", 5: ":"}
DARK = "#333333"
MED = "#777777"
# Colors for hyperparams within each method
COLORS = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd",
           "#8c564b", "#e377c2", "#7f7f7f"]


def _load_tables(io_args):
    """Load divergence and breaks tables."""
    if io_args.input:
        div_path = io_args.input[0]
    else:
        # Infer from output path: output is content/figures/fig_divergence_S1.png
        # data should be at content/tables/tab_semantic_divergence.csv
        base = os.path.dirname(os.path.dirname(io_args.output))
        div_path = os.path.join(base, "tables", "tab_semantic_divergence.csv")

    breaks_path = os.path.splitext(div_path)[0] + "_breaks.csv"

    div_df = pd.read_csv(div_path)
    breaks_df = pd.read_csv(breaks_path) if os.path.exists(breaks_path) else pd.DataFrame()

    log.info("Loaded %d divergence rows, %d break rows", len(div_df), len(breaks_df))
    return div_df, breaks_df


def _get_break_years(breaks_df, method, penalty=3):
    """Extract break years for a method at the given penalty."""
    if breaks_df.empty:
        return set()

    mask = (breaks_df["method"] == method) & (breaks_df["penalty"] == penalty)
    sub = breaks_df[mask]
    years = set()
    for _, row in sub.iterrows():
        bp_str = str(row.get("break_years", ""))
        if bp_str and bp_str != "nan":
            for y in bp_str.split(";"):
                y = y.strip()
                if y:
                    years.add(int(y))
    return years


def plot_method(div_df, breaks_df, method, out_stem):
    """Plot one figure for a single method."""
    info = METHOD_INFO[method]
    mdf = div_df[div_df["method"] == method].copy()

    if mdf.empty:
        log.warning("No data for method %s; skipping", method)
        return

    # Unique hyperparams
    hparams = sorted(mdf["hyperparams"].unique())
    color_map = {hp: COLORS[i % len(COLORS)] for i, hp in enumerate(hparams)}

    fig, ax = plt.subplots(figsize=(FIGWIDTH, 3.2))

    for hp in hparams:
        for w in sorted(mdf["window"].unique()):
            sub = mdf[(mdf["hyperparams"] == hp) & (mdf["window"] == w)]
            sub = sub.sort_values("year")
            if sub.empty:
                continue

            ls = WINDOW_STYLES.get(int(w), "-")
            label = f"w={w}, {hp}" if len(hparams) > 1 else f"w={w}"
            ax.plot(sub["year"], sub["value"],
                    color=color_map[hp], linestyle=ls,
                    linewidth=0.9, label=label)

    # PELT breaks (penalty=3)
    break_years = _get_break_years(breaks_df, method, penalty=3)
    for by in sorted(break_years):
        ax.axvline(by, color="red", linewidth=0.7, linestyle="--", alpha=0.7)

    ax.set_xlabel("Year")
    ax.set_ylabel(info["ylabel"])
    ax.set_title(info["title"])

    # Compact legend
    handles, labels = ax.get_legend_handles_labels()
    if len(handles) <= 12:
        ax.legend(loc="best", frameon=False, fontsize=5.5, ncol=2)
    else:
        ax.legend(loc="best", frameon=False, fontsize=5, ncol=3)

    fig.tight_layout()

    out_path = f"{out_stem}_{info['suffix']}"
    save_figure(fig, out_path, dpi=DPI)
    plt.close(fig)
    log.info("Saved figure -> %s.png", out_path)


def main():
    io_args, _extra = parse_io_args()
    validate_io(output=io_args.output)

    div_df, breaks_df = _load_tables(io_args)

    # Output stem: strip the _S1.png suffix if present, or just use base
    out_base = os.path.splitext(io_args.output)[0]
    # Remove trailing _S1, _S2 etc. if present
    for suffix in ["_S1", "_S2", "_S3", "_S4"]:
        if out_base.endswith(suffix):
            out_base = out_base[:-len(suffix)]
            break

    methods_present = [m for m in METHOD_INFO if m in div_df["method"].values]
    if not methods_present:
        log.warning("No recognized methods in data; nothing to plot")
        return

    for method in methods_present:
        plot_method(div_df, breaks_df, method, out_base)

    log.info("All figures done.")


if __name__ == "__main__":
    main()
