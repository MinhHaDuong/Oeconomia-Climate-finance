"""NCC Figure (a): Sliding-window divergence showing 2009 peak.

Overlays baseline (k=0) and censored-gap (k=2) JS divergence curves
to show that the single surviving breakpoint is 2009. Formatted for
Nature Climate Change specifications (Arial, 5-8pt, 89mm or 183mm width).

Reads:
  content/tables/tab_breakpoints.csv         — baseline divergence series
  content/tables/tab_breakpoints_censor2.csv — censored-gap k=2 series
  content/tables/tab_breakpoint_robustness_censor2.csv — robust breaks (k=2)

Writes:
  content/figures/fig_ncc_divergence.png (and .pdf if --pdf)

Usage:
    uv run python scripts/plot_ncc_divergence.py \
        --output content/figures/fig_ncc_divergence.png \
        --input content/tables/tab_breakpoints.csv \
               content/tables/tab_breakpoints_censor2.csv \
               content/tables/tab_breakpoint_robustness_censor2.csv
"""

import argparse
import os

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import pandas as pd
from script_io_args import parse_io_args, validate_io
from utils import BASE_DIR, get_logger, save_figure

log = get_logger("plot_ncc_divergence")

TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")

# NCC specifications
NCC_SINGLE_COL_MM = 89
NCC_DOUBLE_COL_MM = 183
NCC_DPI = 450
NCC_FONT = "Arial"
NCC_FONTSIZE = 7  # 5-8pt range, 7pt is optimal

# Use double-column width for this figure (divergence curves need space)
FIGWIDTH = NCC_DOUBLE_COL_MM / 25.4  # inches

# Color palette: accessible, avoids red/green contrast
COLOR_BASELINE = "#457B9D"   # steel blue
COLOR_CENSOR = "#E63946"     # warm red
COLOR_BREAK = "#F4A261"      # orange
COLOR_GREY = "#888888"


def _apply_ncc_style():
    """Apply NCC figure style: Arial, 5-8pt, clean axes."""
    matplotlib.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": [NCC_FONT, "Helvetica", "DejaVu Sans"],
        "font.size": NCC_FONTSIZE,
        "axes.titlesize": 8,
        "axes.labelsize": NCC_FONTSIZE,
        "xtick.labelsize": 6,
        "ytick.labelsize": 6,
        "legend.fontsize": 6,
        "figure.dpi": NCC_DPI,
        "savefig.dpi": NCC_DPI,
        "axes.linewidth": 0.5,
        "xtick.major.width": 0.4,
        "ytick.major.width": 0.4,
        "lines.linewidth": 1.0,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": False,
    })


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    parser = argparse.ArgumentParser(
        description="NCC divergence figure: baseline vs censor-gap k=2"
    )
    parser.add_argument("--pdf", action="store_true", help="Also save PDF output")
    parser.add_argument(
        "--window", type=int, default=3,
        help="Window size to plot (default: 3)"
    )
    args = parser.parse_args(extra)

    _apply_ncc_style()

    # --- Resolve input paths ---
    if io_args.input and len(io_args.input) >= 3:
        bp_baseline_path = io_args.input[0]
        bp_censor_path = io_args.input[1]
        robust_censor_path = io_args.input[2]
    else:
        bp_baseline_path = os.path.join(TABLES_DIR, "tab_breakpoints.csv")
        bp_censor_path = os.path.join(TABLES_DIR, "tab_breakpoints_censor2.csv")
        robust_censor_path = os.path.join(
            TABLES_DIR, "tab_breakpoint_robustness_censor2.csv"
        )

    # --- Load data ---
    bp_baseline = pd.read_csv(bp_baseline_path)
    bp_censor = pd.read_csv(bp_censor_path)

    try:
        robust_df = pd.read_csv(robust_censor_path)
    except (pd.errors.EmptyDataError, FileNotFoundError):
        robust_df = pd.DataFrame()

    w = args.window
    col = f"z_js_w{w}"

    # --- Plot ---
    fig, ax = plt.subplots(figsize=(FIGWIDTH, FIGWIDTH * 0.38))

    # Baseline curve (k=0)
    valid_b = bp_baseline[["year", col]].dropna()
    ax.plot(
        valid_b["year"], valid_b[col],
        "-", color=COLOR_BASELINE, linewidth=0.8, alpha=0.5,
        label=f"Baseline (k=0, w={w})",
    )

    # Censored-gap curve (k=2)
    valid_c = bp_censor[["year", col]].dropna()
    ax.plot(
        valid_c["year"], valid_c[col],
        "-o", color=COLOR_CENSOR, markersize=3, linewidth=1.2,
        label=f"Censored gap (k=2, w={w})",
    )

    # Mark robust breakpoints from k=2
    for i, bp in enumerate(robust_df.to_dict("records")[:3]):
        ax.axvspan(
            bp["year"] - 0.3, bp["year"] + 0.3,
            alpha=0.2, color=COLOR_BREAK, zorder=0,
            label="Data-derived break" if i == 0 else "",
        )

    # Reference lines for z-score thresholds
    ax.axhspan(-1.5, 1.5, alpha=0.05, color="grey", zorder=0)
    ax.axhline(1.5, color="grey", linestyle=":", alpha=0.3, linewidth=0.5)
    ax.axhline(2.0, color="grey", linestyle="--", alpha=0.3, linewidth=0.5)
    ax.axhline(-1.5, color="grey", linestyle=":", alpha=0.3, linewidth=0.5)

    # Threshold labels
    ax.text(
        2024.2, 1.5, "z = 1.5", fontsize=5, va="center",
        color=COLOR_GREY, alpha=0.7,
    )
    ax.text(
        2024.2, 2.0, "z = 2.0", fontsize=5, va="center",
        color=COLOR_GREY, alpha=0.7,
    )

    # Key COP events (sparse: only relevant ones)
    for yr, label in [(2007, "Bali"), (2009, "Copenhagen"), (2015, "Paris")]:
        ax.axvline(yr, color=COLOR_GREY, linestyle="--", alpha=0.3, linewidth=0.5)
        ax.text(
            yr, ax.get_ylim()[1] * 0.92 if ax.get_ylim()[1] > 0 else 2.5,
            label, ha="center", va="top", fontsize=5, color=COLOR_GREY,
        )

    ax.set_xlabel("Year")
    ax.set_ylabel("Structural divergence (z-score)")
    ax.xaxis.set_major_locator(ticker.MaxNLocator(integer=True))
    ax.legend(loc="upper left", frameon=False, borderaxespad=0.3)

    fig.tight_layout()

    out_stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, out_stem, pdf=args.pdf, dpi=NCC_DPI)
    log.info("Saved %s", io_args.output)
    plt.close(fig)


if __name__ == "__main__":
    main()
