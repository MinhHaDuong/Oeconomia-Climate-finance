"""Keyword scatter + marginals (bimodality validation C).

Reads:
  content/tables/tab_pole_papers.csv — per-paper keyword counts and metadata

Produces:
  content/figures/fig_bimodality_keywords.png (and .pdf if --pdf)
"""

import argparse
import os

import matplotlib.pyplot as plt
import pandas as pd
from mpl_toolkits.axes_grid1 import make_axes_locatable
from utils import (
    BASE_DIR,
    get_logger,
    load_analysis_periods,
    save_figure,
)

log = get_logger("plot_bimodality_keywords")

# --- Paths ---
FIGURES_DIR = os.path.join(BASE_DIR, "content", "figures")
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")

# Three-act periods (from config)
_period_tuples, _period_labels = load_analysis_periods()
PERIODS = dict(zip(_period_labels, _period_tuples))
PERIOD_COLORS = dict(zip(_period_labels, ["#8da0cb", "#fc8d62", "#66c2a5"]))


def render_figure(df, output_path, pdf=False):
    """Render keyword co-occurrence scatter with marginal histograms."""
    fig, ax = plt.subplots(figsize=(7, 6))

    for period_label, (y_start, y_end) in PERIODS.items():
        pmask = (df["year"] >= y_start) & (df["year"] <= y_end)
        pdata = df[pmask]
        ax.scatter(
            pdata["eff_count"],
            pdata["acc_count"],
            alpha=0.15,
            s=15,
            color=PERIOD_COLORS[period_label],
            label=f"{period_label} (n={len(pdata):,})",
        )

    ax.set_xlabel("Efficiency keyword count", fontsize=11)
    ax.set_ylabel("Accountability keyword count", fontsize=11)
    ax.set_title(
        "Keyword co-occurrence: efficiency vs. accountability terms", fontsize=12
    )
    ax.legend(fontsize=9, framealpha=0.9)

    # Add marginal histograms as insets
    divider = make_axes_locatable(ax)
    ax_histx = divider.append_axes("top", 0.8, pad=0.1, sharex=ax)
    ax_histy = divider.append_axes("right", 0.8, pad=0.1, sharey=ax)

    ax_histx.hist(
        df["eff_count"],
        bins=range(0, df["eff_count"].max() + 2),
        color="#4C72B0",
        alpha=0.7,
        edgecolor="white",
    )
    ax_histy.hist(
        df["acc_count"],
        bins=range(0, df["acc_count"].max() + 2),
        orientation="horizontal",
        color="#C44E52",
        alpha=0.7,
        edgecolor="white",
    )

    ax_histx.tick_params(labelbottom=False)
    ax_histy.tick_params(labelleft=False)

    out_stem = os.path.splitext(output_path)[0]
    save_figure(fig, out_stem, pdf=pdf)
    log.info("Saved -> %s", output_path)
    plt.close()


def main():
    parser = argparse.ArgumentParser(
        description="Keyword co-occurrence scatter + marginals"
    )
    parser.add_argument(
        "--output",
        default=os.path.join(FIGURES_DIR, "fig_bimodality_keywords.png"),
        help="Output figure path",
    )
    parser.add_argument("--pdf", action="store_true", help="Also save PDF output")
    parser.add_argument(
        "--core-only",
        action="store_true",
        help="Read core variant of pole papers table",
    )
    parser.add_argument(
        "--input",
        default=None,
        help="Input pole papers table path",
    )
    args = parser.parse_args()

    # Resolve input path
    if args.input:
        input_path = args.input
    else:
        suffix = "_core" if args.core_only else ""
        input_path = os.path.join(TABLES_DIR, f"tab_pole_papers{suffix}.csv")

    df = pd.read_csv(input_path)
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype(int)
    log.info("Loaded %d papers from %s", len(df), input_path)

    render_figure(df, args.output, pdf=args.pdf)


if __name__ == "__main__":
    main()
