"""Grayscale KDE of the efficiency-accountability axis scores for the supplement.

Produces:
- content/figures/figS_kde.png (+.pdf with --pdf)
"""

import argparse
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from plot_style import DARK, DPI, FIGWIDTH, FILL, LIGHT, MED, apply_style
from scipy.stats import gaussian_kde
from sklearn.mixture import GaussianMixture
from utils import BASE_DIR, get_logger, save_figure

log = get_logger("plot_figS_kde")

apply_style()


def main():
    parser = argparse.ArgumentParser(description="KDE of bimodality axis scores")
    parser.add_argument("--pdf", action="store_true", help="Also save PDF")
    args = parser.parse_args()

    # Load scores
    path = os.path.join(BASE_DIR, "content", "tables", "tab_pole_papers.csv")
    df = pd.read_csv(path)
    scores = df["axis_score"].dropna().values
    log.info("Loaded %d axis scores from %s", len(scores), path)

    # KDE
    x = np.linspace(scores.min() - 0.1, scores.max() + 0.1, 500)
    kde = gaussian_kde(scores)
    density = kde(x)

    # Fit 2-component GMM
    gmm = GaussianMixture(n_components=2, random_state=42)
    gmm.fit(scores.reshape(-1, 1))

    # Also fit 1-component for BIC comparison
    gmm1 = GaussianMixture(n_components=1, random_state=42)
    gmm1.fit(scores.reshape(-1, 1))
    delta_bic = gmm1.bic(scores.reshape(-1, 1)) - gmm.bic(scores.reshape(-1, 1))

    # Component curves
    from scipy.stats import norm

    for k in range(2):
        mu = gmm.means_[k, 0]
        sigma = np.sqrt(gmm.covariances_[k, 0, 0])
        weight = gmm.weights_[k]
        comp_density = weight * norm.pdf(x, mu, sigma)
        if k == 0:
            comp1 = comp_density
        else:
            comp2 = comp_density

    # Plot
    fig, ax = plt.subplots(figsize=(FIGWIDTH, 3.0))

    ax.fill_between(x, density, color=FILL, alpha=0.7)
    ax.plot(x, density, color=DARK, linewidth=1.0, label="KDE")
    ax.plot(x, comp1, color=MED, linewidth=0.8, linestyle="--", label="GMM component 1")
    ax.plot(x, comp2, color=LIGHT, linewidth=0.8, linestyle="--", label="GMM component 2")

    # Vertical line at 0
    ax.axvline(0, color=MED, linewidth=0.5, linestyle=":")

    # Annotation
    ax.text(
        0.97, 0.93,
        f"\u0394BIC = {delta_bic:,.0f}",
        transform=ax.transAxes,
        ha="right", va="top",
        fontsize=7, color=DARK,
    )

    ax.set_xlabel("\u2190 Accountability \u2014 Score \u2014 Efficiency \u2192")
    ax.set_ylabel("Density")
    ax.legend(loc="upper left", frameon=False)

    fig.tight_layout()

    out_path = os.path.join(BASE_DIR, "content", "figures", "fig_kde")
    save_figure(fig, out_path, pdf=args.pdf, dpi=DPI)
    plt.close(fig)


if __name__ == "__main__":
    main()
