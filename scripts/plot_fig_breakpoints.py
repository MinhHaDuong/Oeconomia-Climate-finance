"""Render the structural break detection figure.

Reads:  content/tables/tab_breakpoints.csv
        content/tables/tab_breakpoint_robustness.csv
        content/tables/tab_alluvial.csv  (to compute N for title in --core-only mode)
Writes: content/figures/fig_breakpoints.png  (and core/censor variants)

Flags: --core-only, --censor-gap N, --pdf

Usage:
    uv run python scripts/plot_fig_breakpoints.py --output content/figures/fig_breakpoints.png
    uv run python scripts/plot_fig_breakpoints.py --output content/figures/fig_breakpoints_core.png --core-only
"""

import argparse
import os

import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd
import seaborn as sns
from plot_style import COP_EVENTS
from script_io_args import parse_io_args, validate_io
from utils import BASE_DIR, get_logger, load_analysis_config, save_figure

log = get_logger("plot_fig_breakpoints")

TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
WINDOW_SIZES = [2, 3, 4]


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    _cfg = load_analysis_config()
    cite_threshold = _cfg["clustering"]["cite_threshold"]

    parser = argparse.ArgumentParser(description="Render structural break detection figure")
    parser.add_argument("--pdf", action="store_true", help="Also save PDF output")
    parser.add_argument("--core-only", action="store_true",
                        help="Use core-only variant of input tables")
    parser.add_argument("--censor-gap", type=int, default=0,
                        help="Load censor-gap variant of input tables")
    args = parser.parse_args(extra)

    # Derive input table names from mode
    if args.core_only:
        tab_bp = "tab_breakpoints_core.csv"
        tab_bp_robust = "tab_breakpoint_robustness_core.csv"
        tab_al = "tab_alluvial_core.csv"
    else:
        tab_bp = "tab_breakpoints.csv"
        tab_bp_robust = "tab_breakpoint_robustness.csv"
        tab_al = "tab_alluvial.csv"

    if args.censor_gap > 0:
        suffix = f"_censor{args.censor_gap}"
        tab_bp = tab_bp.replace(".csv", f"{suffix}.csv")
        tab_bp_robust = tab_bp_robust.replace(".csv", f"{suffix}.csv")

    # --- Load tables ---
    bp_df = pd.read_csv(os.path.join(TABLES_DIR, tab_bp))
    try:
        robust_df = pd.read_csv(os.path.join(TABLES_DIR, tab_bp_robust))
    except pd.errors.EmptyDataError:
        robust_df = pd.DataFrame()
    robust_list = robust_df.to_dict("records")

    alluvial_df = pd.read_csv(os.path.join(TABLES_DIR, tab_al), index_col=0)
    n_corpus = int(alluvial_df.values.sum())

    # --- Plot ---
    sns.set_style("whitegrid")

    fig, ax = plt.subplots(figsize=(12, 5))

    colors_w = {2: "#E63946", 3: "#457B9D", 4: "#2A9D8F"}
    for w in WINDOW_SIZES:
        col = f"z_js_w{w}"
        valid = bp_df[["year", col]].dropna()
        ax.plot(valid["year"], valid[col], "-o", color=colors_w[w], markersize=4,
                label=f"JS div (w={w})", alpha=0.8)

    for i, bp in enumerate(robust_list[:3]):
        ax.axvspan(bp["year"] - 0.3, bp["year"] + 0.3, alpha=0.25, color="orange",
                   zorder=0, label="Data-derived break" if i == 0 else "")

    for yr, label in COP_EVENTS.items():
        if 2004 <= yr <= 2024:
            ax.axvline(yr, color="grey", linestyle="--", alpha=0.5, linewidth=0.8)
            ax.text(yr, ax.get_ylim()[1] * 0.95 if ax.get_ylim()[1] > 0 else 2.5,
                    label, ha="center", va="top", fontsize=7, color="grey",
                    rotation=0)

    ax.axhspan(-1.5, 1.5, alpha=0.08, color="grey", zorder=0)
    ax.axhline(1.5, color="black", linestyle=":", alpha=0.4, linewidth=0.8)
    ax.axhline(2.0, color="black", linestyle="--", alpha=0.4, linewidth=0.8)
    ax.axhline(-1.5, color="black", linestyle=":", alpha=0.4, linewidth=0.8)
    ax.text(2024.3, 1.5, "z=1.5", fontsize=7, va="center", color="black", alpha=0.5)
    ax.text(2024.3, 2.0, "z=2.0", fontsize=7, va="center", color="black", alpha=0.5)
    ax.set_xlabel("Year", fontsize=11)
    ax.set_ylabel("Structural divergence (z-score)", fontsize=11)
    corpus_note = f" (core: cited \u2265 {cite_threshold}, N={n_corpus:,})" if args.core_only else ""
    ax.set_title(f"Detecting structural shifts in scholarship around climate finance{corpus_note}",
                 fontsize=12, pad=15)
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.legend(loc="upper left", fontsize=8, framealpha=0.9)

    plt.tight_layout()
    out_stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, out_stem, pdf=args.pdf)
    log.info("Saved %s", io_args.output)
    plt.close()

    log.info("Done.")


if __name__ == "__main__":
    main()
