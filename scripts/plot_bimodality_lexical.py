"""TF-IDF lexical KDE by period (bimodality validation B).

Reads:
  content/tables/tab_pole_papers.csv — per-paper lex_score and metadata

Produces:
  content/figures/fig_bimodality_lexical.png (and .pdf if --pdf)
"""

import argparse
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import gaussian_kde
from script_io_args import parse_io_args, validate_io
from utils import (
    BASE_DIR,
    get_logger,
    load_analysis_periods,
    save_figure,
)

log = get_logger("plot_bimodality_lexical")

# --- Paths ---
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")

# Three-act periods (from config)
_period_tuples, _period_labels = load_analysis_periods()
PERIODS = dict(zip(_period_labels, _period_tuples))
PERIOD_COLORS = dict(zip(_period_labels, ["#8da0cb", "#fc8d62", "#66c2a5"]))


def render_figure(df, output_path, pdf=False):
    """Render KDE of TF-IDF lexical scores by period."""
    sns.set_style("whitegrid")
    fig, axes = plt.subplots(1, 3, figsize=(14, 4), sharey=True)

    for ax, (period_label, (y_start, y_end)) in zip(axes, PERIODS.items()):
        pmask = (df["year"] >= y_start) & (df["year"] <= y_end)
        pscores = df.loc[pmask, "lex_score"].values

        if len(pscores) < 10:
            ax.set_title(f"{period_label}\n(n={len(pscores)}, too few)")
            continue

        kde = gaussian_kde(pscores, bw_method=0.15)
        x = np.linspace(np.percentile(pscores, 1), np.percentile(pscores, 99), 500)
        y = kde(x)

        ax.fill_between(x, y, alpha=0.3, color=PERIOD_COLORS[period_label])
        ax.plot(x, y, color=PERIOD_COLORS[period_label], linewidth=2)
        ax.axvline(0, color="black", linestyle=":", alpha=0.3)
        ax.set_title(f"{period_label}\n(n={len(pscores):,})", fontsize=11)
        ax.set_xlabel("← Accountability          Efficiency →", fontsize=9)

    axes[0].set_ylabel("Density", fontsize=11)
    fig.suptitle(
        "Distribution along the efficiency–accountability axis (TF-IDF lexical)",
        fontsize=13,
        y=1.02,
    )
    plt.tight_layout()

    out_stem = os.path.splitext(output_path)[0]
    save_figure(fig, out_stem, pdf=pdf)
    log.info("Saved -> %s", output_path)
    plt.close()


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    parser = argparse.ArgumentParser(
        description="TF-IDF lexical KDE by period"
    )
    parser.add_argument("--pdf", action="store_true", help="Also save PDF output")
    parser.add_argument(
        "--core-only",
        action="store_true",
        help="Read core variant of pole papers table",
    )
    args = parser.parse_args(extra)

    # Resolve input path
    if io_args.input:
        input_path = io_args.input[0]
    else:
        suffix = "_core" if args.core_only else ""
        input_path = os.path.join(TABLES_DIR, f"tab_pole_papers{suffix}.csv")

    df = pd.read_csv(input_path)
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype(int)
    log.info("Loaded %d papers from %s", len(df), input_path)

    render_figure(df, io_args.output, pdf=args.pdf)


if __name__ == "__main__":
    main()
