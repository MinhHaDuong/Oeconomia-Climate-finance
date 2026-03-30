"""Embedding KDE by period with GMM overlay (bimodality validation A).

Reads:
  content/tables/tab_pole_papers.csv — per-paper axis scores and metadata

Produces:
  content/figures/fig_bimodality.png (and .pdf if --pdf)
"""

import argparse
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import gaussian_kde
from sklearn.mixture import GaussianMixture
from utils import (
    BASE_DIR,
    get_logger,
    load_analysis_periods,
    save_figure,
)

log = get_logger("plot_bimodality")

# --- Paths ---
FIGURES_DIR = os.path.join(BASE_DIR, "content", "figures")
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")

# Three-act periods (from config)
_period_tuples, _period_labels = load_analysis_periods()
PERIODS = dict(zip(_period_labels, _period_tuples))
PERIOD_COLORS = dict(zip(_period_labels, ["#8da0cb", "#fc8d62", "#66c2a5"]))


def render_figure(df, output_path, pdf=False):
    """Render KDE of embedding scores by period with GMM overlay."""
    sns.set_style("whitegrid")
    fig, axes = plt.subplots(1, 3, figsize=(14, 4), sharey=True)

    for ax, (period_label, (y_start, y_end)) in zip(axes, PERIODS.items()):
        pmask = (df["year"] >= y_start) & (df["year"] <= y_end)
        pscores = df.loc[pmask, "axis_score"].values

        if len(pscores) < 10:
            ax.set_title(f"{period_label}\n(n={len(pscores)}, too few)")
            continue

        # KDE
        kde = gaussian_kde(pscores, bw_method=0.15)
        x = np.linspace(pscores.min() - 0.5, pscores.max() + 0.5, 500)
        y = kde(x)

        ax.fill_between(x, y, alpha=0.3, color=PERIOD_COLORS[period_label])
        ax.plot(x, y, color=PERIOD_COLORS[period_label], linewidth=2)

        # GMM components overlay
        if len(pscores) >= 20:
            g2 = GaussianMixture(n_components=2, random_state=42).fit(
                pscores.reshape(-1, 1)
            )
            means = g2.means_.flatten()
            stds = np.sqrt(g2.covariances_.flatten())
            weights = g2.weights_

            for i in range(2):
                comp = weights[i] * gaussian_kde(
                    np.random.RandomState(42).normal(means[i], stds[i], 10000),
                    bw_method=0.15,
                )(x)
                ax.plot(x, comp, "--", color="grey", alpha=0.5, linewidth=1)

        ax.axvline(0, color="black", linestyle=":", alpha=0.3)
        ax.set_title(f"{period_label}\n(n={len(pscores):,})", fontsize=11)
        ax.set_xlabel("← Accountability          Efficiency →", fontsize=9)

    axes[0].set_ylabel("Density", fontsize=11)

    fig.suptitle(
        "Distribution of papers along the efficiency–accountability axis",
        fontsize=13,
        y=1.02,
    )
    plt.tight_layout()

    out_stem = os.path.splitext(output_path)[0]
    save_figure(fig, out_stem, pdf=pdf)
    log.info("Saved -> %s", output_path)
    plt.close()


def main():
    parser = argparse.ArgumentParser(
        description="Embedding KDE by period with GMM overlay"
    )
    parser.add_argument(
        "--output",
        default=os.path.join(FIGURES_DIR, "fig_bimodality.png"),
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
