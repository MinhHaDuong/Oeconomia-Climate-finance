"""NCC Figure (b): Core vs. full corpus divergence comparison.

Two-panel figure showing that the full corpus exhibits structural breaks
while the core subset (cited >= 50) does not. This is the key evidence
that the "climate finance" category was constructed through peripheral
literature, not through the most-cited works.

Reads:
  content/tables/tab_breakpoints.csv              — full corpus divergence
  content/tables/tab_breakpoint_robustness.csv    — full corpus breaks
  content/tables/tab_breakpoints_core.csv         — core divergence
  content/tables/tab_breakpoint_robustness_core.csv — core breaks
  content/tables/tab_alluvial.csv                 — for N count (full)
  content/tables/tab_alluvial_core.csv            — for N count (core)

Writes:
  content/figures/fig_ncc_core_comparison.png (and .pdf if --pdf)

Usage:
    uv run python scripts/plot_ncc_core_comparison.py \
        --output content/figures/fig_ncc_core_comparison.png
"""

import argparse
import os

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd
from script_io_args import parse_io_args, validate_io
from utils import BASE_DIR, get_logger, load_analysis_config, save_figure

log = get_logger("plot_ncc_core_comparison")

TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")

# NCC specifications
NCC_DOUBLE_COL_MM = 183
NCC_DPI = 450
NCC_FONT = "Arial"
NCC_FONTSIZE = 7

FIGWIDTH = NCC_DOUBLE_COL_MM / 25.4  # inches
WINDOW_SIZES = [2, 3, 4]

# Color palette: accessible
COLORS_W = {2: "#E63946", 3: "#457B9D", 4: "#2A9D8F"}
COLOR_BREAK = "#F4A261"
COLOR_GREY = "#888888"


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
        "xtick.major.width": 0.4,
        "ytick.major.width": 0.4,
        "lines.linewidth": 0.9,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
    })


def _load_panel_data(bp_path, robust_path, alluvial_path):
    """Load divergence series, robust breaks, and corpus size."""
    bp_df = pd.read_csv(bp_path)
    try:
        robust_df = pd.read_csv(robust_path)
    except (pd.errors.EmptyDataError, FileNotFoundError):
        robust_df = pd.DataFrame()
    alluvial_df = pd.read_csv(alluvial_path, index_col=0)
    n_corpus = int(alluvial_df.values.sum())
    return bp_df, robust_df, n_corpus


def _plot_panel(ax, bp_df, robust_df, n_corpus, title, show_ylabel=True):
    """Plot a single divergence panel."""
    for w in WINDOW_SIZES:
        col = f"z_js_w{w}"
        valid = bp_df[["year", col]].dropna()
        ax.plot(
            valid["year"], valid[col],
            "-o", color=COLORS_W[w], markersize=2.5, linewidth=0.8,
            label=f"JS div (w={w})", alpha=0.8,
        )

    # Mark robust breakpoints
    robust_list = robust_df.to_dict("records") if not robust_df.empty else []
    for i, bp in enumerate(robust_list[:3]):
        ax.axvspan(
            bp["year"] - 0.3, bp["year"] + 0.3,
            alpha=0.2, color=COLOR_BREAK, zorder=0,
            label="Data-derived break" if i == 0 else "",
        )

    # Reference bands
    ax.axhspan(-1.5, 1.5, alpha=0.05, color="grey", zorder=0)
    ax.axhline(1.5, color="grey", linestyle=":", alpha=0.3, linewidth=0.5)
    ax.axhline(2.0, color="grey", linestyle="--", alpha=0.3, linewidth=0.5)
    ax.axhline(-1.5, color="grey", linestyle=":", alpha=0.3, linewidth=0.5)

    ax.set_title(f"{title} (N = {n_corpus:,})", fontsize=8, pad=6)
    ax.set_xlabel("Year")
    if show_ylabel:
        ax.set_ylabel("Structural divergence\n(z-score)")
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    _cfg = load_analysis_config()
    cite_threshold = _cfg["clustering"]["cite_threshold"]

    parser = argparse.ArgumentParser(
        description="NCC core vs full corpus comparison panel"
    )
    parser.add_argument("--pdf", action="store_true", help="Also save PDF output")
    args = parser.parse_args(extra)

    _apply_ncc_style()

    # --- Resolve input paths ---
    # If --input provided, expect 6 paths in order:
    #   bp_full, robust_full, alluvial_full, bp_core, robust_core, alluvial_core
    if io_args.input and len(io_args.input) >= 6:
        paths_full = io_args.input[0], io_args.input[1], io_args.input[2]
        paths_core = io_args.input[3], io_args.input[4], io_args.input[5]
    else:
        paths_full = (
            os.path.join(TABLES_DIR, "tab_breakpoints.csv"),
            os.path.join(TABLES_DIR, "tab_breakpoint_robustness.csv"),
            os.path.join(TABLES_DIR, "tab_alluvial.csv"),
        )
        paths_core = (
            os.path.join(TABLES_DIR, "tab_breakpoints_core.csv"),
            os.path.join(TABLES_DIR, "tab_breakpoint_robustness_core.csv"),
            os.path.join(TABLES_DIR, "tab_alluvial_core.csv"),
        )

    bp_full, robust_full, n_full = _load_panel_data(*paths_full)
    bp_core, robust_core, n_core = _load_panel_data(*paths_core)

    # --- Two-panel figure ---
    fig, (ax_full, ax_core) = plt.subplots(
        1, 2, figsize=(FIGWIDTH, FIGWIDTH * 0.33), sharey=True,
    )

    _plot_panel(
        ax_full, bp_full, robust_full, n_full,
        "a  Full corpus", show_ylabel=True,
    )
    _plot_panel(
        ax_core, bp_core, robust_core, n_core,
        f"b  Core subset (cited \u2265 {cite_threshold})",
        show_ylabel=False,
    )

    # Shared legend from the first panel
    handles, labels = ax_full.get_legend_handles_labels()
    fig.legend(
        handles, labels,
        loc="lower center", ncol=4, frameon=False,
        fontsize=5.5, bbox_to_anchor=(0.5, -0.02),
    )

    fig.tight_layout(rect=[0, 0.06, 1, 1])

    out_stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, out_stem, pdf=args.pdf, dpi=NCC_DPI)
    log.info("Saved %s", io_args.output)
    plt.close(fig)


if __name__ == "__main__":
    main()
