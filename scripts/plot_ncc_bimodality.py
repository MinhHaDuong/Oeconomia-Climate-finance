"""NCC Figure (c): Efficiency-accountability bimodality KDE.

Compact panel figure combining the overall KDE (with GMM overlay) and
the period-decomposed KDE showing emergence of bimodality after 2015.
Formatted for Nature Climate Change specifications.

Reads:
  content/tables/tab_pole_papers.csv — per-paper axis scores and metadata

Writes:
  content/figures/fig_ncc_bimodality.png (and .pdf if --pdf)

Usage:
    uv run python scripts/plot_ncc_bimodality.py \
        --output content/figures/fig_ncc_bimodality.png
"""

import argparse
import os

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.stats import gaussian_kde, norm
from sklearn.mixture import GaussianMixture
from script_io_args import parse_io_args, validate_io
from utils import BASE_DIR, get_logger, load_analysis_periods, save_figure

log = get_logger("plot_ncc_bimodality")

TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")

# NCC specifications
NCC_DOUBLE_COL_MM = 183
NCC_DPI = 450
NCC_FONT = "Arial"
NCC_FONTSIZE = 7

FIGWIDTH = NCC_DOUBLE_COL_MM / 25.4

# Color palette: accessible, period-coded
PERIOD_COLORS = ["#8da0cb", "#fc8d62", "#66c2a5"]
COLOR_KDE = "#333333"
COLOR_GMM1 = "#457B9D"
COLOR_GMM2 = "#E63946"
COLOR_FILL = "#DDDDDD"


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


def _plot_overall_kde(ax, scores):
    """Plot overall KDE with 2-component GMM overlay."""
    x = np.linspace(scores.min() - 0.3, scores.max() + 0.3, 500)
    kde = gaussian_kde(scores)
    density = kde(x)

    # Fit GMMs for BIC comparison
    scores_2d = scores.reshape(-1, 1)
    gmm2 = GaussianMixture(n_components=2, random_state=42).fit(scores_2d)
    gmm1 = GaussianMixture(n_components=1, random_state=42).fit(scores_2d)
    delta_bic = gmm1.bic(scores_2d) - gmm2.bic(scores_2d)

    # Plot KDE
    ax.fill_between(x, density, color=COLOR_FILL, alpha=0.6)
    ax.plot(x, density, color=COLOR_KDE, linewidth=1.0, label="KDE")

    # Plot GMM components
    for k in range(2):
        mu = gmm2.means_[k, 0]
        sigma = np.sqrt(gmm2.covariances_[k, 0, 0])
        weight = gmm2.weights_[k]
        comp = weight * norm.pdf(x, mu, sigma)
        color = COLOR_GMM1 if k == 0 else COLOR_GMM2
        ax.plot(x, comp, "--", color=color, linewidth=0.7,
                label=f"GMM component {k + 1}")

    ax.axvline(0, color="grey", linewidth=0.4, linestyle=":")
    ax.text(
        0.97, 0.93, f"\u0394BIC = {delta_bic:,.0f}",
        transform=ax.transAxes, ha="right", va="top",
        fontsize=5.5, color=COLOR_KDE,
    )
    ax.set_xlabel("\u2190 Accountability    Score    Efficiency \u2192")
    ax.set_ylabel("Density")
    ax.set_title("a  Overall distribution", fontsize=8, pad=6)
    ax.legend(loc="upper left", frameon=False)


def _plot_period_kde(axes, df, period_tuples, period_labels):
    """Plot KDE for each period on separate axes."""
    for i, (ax, label, (y_start, y_end)) in enumerate(
        zip(axes, period_labels, period_tuples)
    ):
        mask = (df["year"] >= y_start) & (df["year"] <= y_end)
        scores = df.loc[mask, "axis_score"].values

        if len(scores) < 10:
            ax.set_title(f"{label}\n(n={len(scores)}, insufficient)")
            continue

        x = np.linspace(scores.min() - 0.5, scores.max() + 0.5, 500)
        kde = gaussian_kde(scores, bw_method=0.15)
        y = kde(x)

        ax.fill_between(x, y, alpha=0.25, color=PERIOD_COLORS[i])
        ax.plot(x, y, color=PERIOD_COLORS[i], linewidth=1.2)

        # GMM overlay
        if len(scores) >= 20:
            g2 = GaussianMixture(n_components=2, random_state=42).fit(
                scores.reshape(-1, 1)
            )
            for k in range(2):
                mu = g2.means_[k, 0]
                sigma = np.sqrt(g2.covariances_[k, 0, 0])
                weight = g2.weights_[k]
                comp = weight * norm.pdf(x, mu, sigma)
                ax.plot(x, comp, "--", color="grey", alpha=0.4, linewidth=0.6)

        ax.axvline(0, color="black", linestyle=":", alpha=0.2)
        panel_letter = chr(ord("b") + i)
        ax.set_title(
            f"{panel_letter}  {label} (n={len(scores):,})",
            fontsize=7, pad=4,
        )
        ax.set_xlabel("\u2190 Accountability    Efficiency \u2192")

    axes[0].set_ylabel("Density")


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    parser = argparse.ArgumentParser(
        description="NCC bimodality KDE panel figure"
    )
    parser.add_argument("--pdf", action="store_true", help="Also save PDF output")
    args = parser.parse_args(extra)

    _apply_ncc_style()

    # --- Load data ---
    if io_args.input:
        input_path = io_args.input[0]
    else:
        input_path = os.path.join(TABLES_DIR, "tab_pole_papers.csv")

    df = pd.read_csv(input_path)
    df["year"] = pd.to_numeric(df["year"], errors="coerce").astype(int)
    scores = df["axis_score"].dropna().values
    log.info("Loaded %d papers from %s", len(df), input_path)

    # Load periods from config
    period_tuples, period_labels = load_analysis_periods()

    # --- Figure layout: 1 overall + 3 period panels ---
    fig = plt.figure(figsize=(FIGWIDTH, FIGWIDTH * 0.42))

    # Top row: overall KDE spanning full width
    ax_overall = fig.add_axes([0.06, 0.55, 0.88, 0.40])

    # Bottom row: three period KDEs
    ax_periods = []
    for i in range(3):
        left = 0.06 + i * 0.32
        ax_periods.append(fig.add_axes([left, 0.08, 0.27, 0.38]))

    _plot_overall_kde(ax_overall, scores)
    _plot_period_kde(ax_periods, df, period_tuples, period_labels)

    out_stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, out_stem, pdf=args.pdf, dpi=NCC_DPI)
    log.info("Saved %s", io_args.output)
    plt.close(fig)


if __name__ == "__main__":
    main()
