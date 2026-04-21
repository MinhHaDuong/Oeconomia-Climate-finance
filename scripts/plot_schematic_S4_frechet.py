"""Schematic figure: S4 Fréchet Distance — ELI15 quality.

Shows two clouds (Before 2000–02, After 2009–11) in 2D PCA space with
fitted 2D Gaussians (1-sigma ellipses), mean vectors, and a thick arrow
labelled with the mean-distance term.

Usage::

    uv run python scripts/plot_schematic_S4_frechet.py \\
        --output /tmp/test_S4.png
"""

import os
import sys

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from pipeline_io import save_figure
from pipeline_loaders import load_analysis_corpus
from plot_style import DARK, DPI, FIGWIDTH, LIGHT, MED, apply_style
from script_io_args import parse_io_args, validate_io
from sklearn.decomposition import PCA
from utils import get_logger

log = get_logger("plot_schematic_S4_frechet")
apply_style()

BEFORE_YEARS = (2000, 2002)
AFTER_YEARS = (2009, 2011)
N_PER_GROUP = 8
SEED = 42

COLOR_BEFORE = "#3A7EC6"  # blue
COLOR_AFTER = "#D94F3D"  # red


def covariance_ellipse(cov, center, n_std=1.0):
    """Return (width, height, angle_deg) for a 2x2 covariance ellipse."""
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    # Sort descending
    order = eigenvalues.argsort()[::-1]
    eigenvalues = eigenvalues[order]
    eigenvectors = eigenvectors[:, order]
    angle = np.degrees(np.arctan2(eigenvectors[1, 0], eigenvectors[0, 0]))
    width = 2.0 * n_std * np.sqrt(max(eigenvalues[0], 0.0))
    height = 2.0 * n_std * np.sqrt(max(eigenvalues[1], 0.0))
    return width, height, angle


def main():
    io_args, _ = parse_io_args()
    validate_io(output=io_args.output)

    log.info("Loading corpus with embeddings…")
    works_df, embeddings = load_analysis_corpus(with_embeddings=True)

    rng = np.random.default_rng(SEED)

    mask_before = (works_df["year"] >= BEFORE_YEARS[0]) & (
        works_df["year"] <= BEFORE_YEARS[1]
    )
    mask_after = (works_df["year"] >= AFTER_YEARS[0]) & (
        works_df["year"] <= AFTER_YEARS[1]
    )

    idx_before = np.where(mask_before)[0]
    idx_after = np.where(mask_after)[0]
    log.info("Window sizes: before=%d, after=%d", len(idx_before), len(idx_after))

    # Fit PCA on a larger population sample for stable idea-space
    pop_idx = np.concatenate([idx_before, idx_after])
    pop_sample_size = min(500, len(pop_idx))
    pop_sample = rng.choice(pop_idx, size=pop_sample_size, replace=False)
    pca = PCA(n_components=2, random_state=SEED)
    pca.fit(embeddings[pop_sample])

    # Subsample N_PER_GROUP points per window
    sel_before = rng.choice(idx_before, size=N_PER_GROUP, replace=False)
    sel_after = rng.choice(idx_after, size=N_PER_GROUP, replace=False)

    pts_before = pca.transform(embeddings[sel_before])  # (8, 2)
    pts_after = pca.transform(embeddings[sel_after])  # (8, 2)

    all_pts = np.vstack([pts_before, pts_after])
    spread = np.ptp(all_pts, axis=0).mean()

    # Fit Gaussians
    mu_before = pts_before.mean(axis=0)
    mu_after = pts_after.mean(axis=0)
    cov_before = np.cov(pts_before, rowvar=False)
    cov_after = np.cov(pts_after, rowvar=False)

    # --- Build figure ---
    fig, ax = plt.subplots(figsize=(FIGWIDTH, FIGWIDTH * 0.85))

    # --- 1-sigma ellipses ---
    for pts, mu, cov, color in [
        (pts_before, mu_before, cov_before, COLOR_BEFORE),
        (pts_after, mu_after, cov_after, COLOR_AFTER),
    ]:
        w, h, ang = covariance_ellipse(cov, mu, n_std=1.0)
        ellipse = mpatches.Ellipse(
            mu,
            width=w,
            height=h,
            angle=ang,
            facecolor=color,
            edgecolor=color,
            alpha=0.15,
            zorder=2,
            linewidth=1.0,
        )
        ax.add_patch(ellipse)
        ellipse_edge = mpatches.Ellipse(
            mu,
            width=w,
            height=h,
            angle=ang,
            facecolor="none",
            edgecolor=color,
            alpha=0.60,
            zorder=3,
            linewidth=1.0,
        )
        ax.add_patch(ellipse_edge)

    # --- Scatter clouds ---
    ax.scatter(
        pts_before[:, 0],
        pts_before[:, 1],
        color=COLOR_BEFORE,
        s=45,
        zorder=5,
        label="Before (2000–02)",
        edgecolors="white",
        linewidths=0.4,
    )
    ax.scatter(
        pts_after[:, 0],
        pts_after[:, 1],
        color=COLOR_AFTER,
        s=45,
        zorder=5,
        label="After (2009–11)",
        edgecolors="white",
        linewidths=0.4,
    )

    # --- Mean dots ---
    ax.scatter(
        [mu_before[0]],
        [mu_before[1]],
        color=COLOR_BEFORE,
        s=120,
        zorder=7,
        marker="D",
        edgecolors="white",
        linewidths=0.6,
    )
    ax.scatter(
        [mu_after[0]],
        [mu_after[1]],
        color=COLOR_AFTER,
        s=120,
        zorder=7,
        marker="D",
        edgecolors="white",
        linewidths=0.6,
    )

    # --- Thick arrow between means, labelled ‖μ₁−μ₂‖² ---
    ax.annotate(
        "",
        xy=mu_after,
        xytext=mu_before,
        arrowprops=dict(
            arrowstyle="-|>",
            color=DARK,
            lw=1.8,
            mutation_scale=12,
        ),
        zorder=6,
    )
    mid_mu = (mu_before + mu_after) / 2.0
    perp = np.array([-(mu_after - mu_before)[1], (mu_after - mu_before)[0]])
    perp_unit = perp / (np.linalg.norm(perp) + 1e-10)
    label_pos = mid_mu + perp_unit * spread * 0.12
    ax.text(
        label_pos[0],
        label_pos[1],
        r"$\|\mu_1 - \mu_2\|^2$",
        fontsize=7.5,
        color=DARK,
        ha="center",
        va="center",
        zorder=8,
    )

    # --- Formula text box ---
    formula = (
        r"$d_F^2 = \|\mu_1{-}\mu_2\|^2 + \mathrm{tr}\!\left("
        r"\Sigma_1{+}\Sigma_2{-}2(\Sigma_1\Sigma_2)^{1/2}\right)$"
    )
    ax.text(
        0.03,
        0.97,
        formula,
        transform=ax.transAxes,
        fontsize=7,
        va="top",
        ha="left",
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=LIGHT, lw=0.5, alpha=0.88),
    )

    ax.set_xlabel("PC 1  (idea-space axis 1)", fontsize=8)
    ax.set_ylabel("PC 2  (idea-space axis 2)", fontsize=8)
    ax.set_title(
        "Fréchet Distance: compare the fitted Gaussian shapes",
        fontsize=9,
        color=DARK,
    )
    ax.text(
        0.5,
        -0.10,
        "Distance between means + mismatch between covariances",
        transform=ax.transAxes,
        fontsize=7,
        ha="center",
        color=MED,
    )
    ax.legend(fontsize=7, frameon=False, loc="lower right")

    margin = spread * 0.40
    ax.set_xlim(all_pts[:, 0].min() - margin, all_pts[:, 0].max() + margin)
    ax.set_ylim(all_pts[:, 1].min() - margin, all_pts[:, 1].max() + margin)
    ax.set_xticks([])
    ax.set_yticks([])

    fig.tight_layout()
    stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, stem, dpi=DPI)
    plt.close(fig)
    log.info("Done → %s.png", stem)


if __name__ == "__main__":
    sys.exit(main())
