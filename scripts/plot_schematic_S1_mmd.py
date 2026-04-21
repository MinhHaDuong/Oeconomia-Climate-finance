"""Schematic figure: S1 Maximum Mean Discrepancy (MMD) — ELI15 quality.

Shows two small clouds (Before 2000–02, After 2009–11) in 2D PCA space,
with an RBF kernel centered on one blue point (concentric circles) and a
smooth elliptical "witness boundary" separating the two clouds.

Usage::

    uv run python scripts/plot_schematic_S1_mmd.py \\
        --output /tmp/test_S1.png
"""

import os
import sys

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from pipeline_io import save_figure
from pipeline_loaders import load_analysis_corpus
from plot_style import DARK, DPI, FIGWIDTH, LIGHT, apply_style
from script_io_args import parse_io_args, validate_io
from sklearn.decomposition import PCA
from utils import get_logger

log = get_logger("plot_schematic_S1_mmd")
apply_style()

BEFORE_YEARS = (2000, 2002)
AFTER_YEARS = (2009, 2011)
N_PER_GROUP = 5
SEED = 42

COLOR_BEFORE = "#3A7EC6"  # blue
COLOR_AFTER = "#D94F3D"  # red


def main():
    io_args, _ = parse_io_args()
    validate_io(output=io_args.output)

    log.info("Loading corpus with embeddings…")
    works_df, embeddings = load_analysis_corpus(with_embeddings=True)

    rng = np.random.default_rng(SEED)

    # Select indices for each window
    mask_before = (works_df["year"] >= BEFORE_YEARS[0]) & (
        works_df["year"] <= BEFORE_YEARS[1]
    )
    mask_after = (works_df["year"] >= AFTER_YEARS[0]) & (
        works_df["year"] <= AFTER_YEARS[1]
    )

    idx_before = np.where(mask_before)[0]
    idx_after = np.where(mask_after)[0]
    log.info("Window sizes: before=%d, after=%d", len(idx_before), len(idx_after))

    # Fit PCA on a larger population sample for stability
    pop_idx = np.concatenate([idx_before, idx_after])
    pop_sample_size = min(500, len(pop_idx))
    pop_sample = rng.choice(pop_idx, size=pop_sample_size, replace=False)
    pca = PCA(n_components=2, random_state=SEED)
    pca.fit(embeddings[pop_sample])

    # Subsample N_PER_GROUP points per window
    sel_before = rng.choice(idx_before, size=N_PER_GROUP, replace=False)
    sel_after = rng.choice(idx_after, size=N_PER_GROUP, replace=False)

    pts_before = pca.transform(embeddings[sel_before])  # (5, 2)
    pts_after = pca.transform(embeddings[sel_after])  # (5, 2)

    all_pts = np.vstack([pts_before, pts_after])
    centroid = all_pts.mean(axis=0)

    # --- Build figure ---
    fig, ax = plt.subplots(figsize=(FIGWIDTH, FIGWIDTH * 0.85))

    # --- RBF kernel contours centred on one blue point ---
    # Use the blue point closest to the centroid for clean placement
    dists_to_centroid = np.linalg.norm(pts_before - centroid, axis=1)
    kernel_center_idx = np.argmin(dists_to_centroid)
    kc = pts_before[kernel_center_idx]

    # Draw concentric circles for the RBF kernel
    # Scale sigma to be roughly half the spread of all points
    spread = np.ptp(all_pts, axis=0).mean()
    sigma = spread * 0.30
    for r_factor in [0.6, 1.0, 1.5, 2.1]:
        radius = sigma * r_factor
        circle = mpatches.Circle(
            kc,
            radius=radius,
            fill=False,
            edgecolor=COLOR_BEFORE,
            linewidth=0.5,
            linestyle="--",
            alpha=0.25,
            zorder=1,
        )
        ax.add_patch(circle)

    # --- Witness boundary: an ellipse separating the two clouds ---
    before_centroid = pts_before.mean(axis=0)
    after_centroid = pts_after.mean(axis=0)
    midpoint = (before_centroid + after_centroid) / 2.0
    diff = after_centroid - before_centroid
    angle_deg = np.degrees(np.arctan2(diff[1], diff[0])) + 90  # perpendicular
    separation = np.linalg.norm(diff)
    ell_width = separation * 0.45
    ell_height = separation * 1.4
    boundary = mpatches.Ellipse(
        midpoint,
        width=ell_width,
        height=ell_height,
        angle=angle_deg,
        fill=False,
        edgecolor=LIGHT,
        linewidth=1.2,
        linestyle="-",
        alpha=0.7,
        zorder=2,
    )
    ax.add_patch(boundary)

    # --- Scatter clouds ---
    ax.scatter(
        pts_before[:, 0],
        pts_before[:, 1],
        color=COLOR_BEFORE,
        s=50,
        zorder=5,
        label="Before (2000–02)",
        edgecolors="white",
        linewidths=0.4,
    )
    ax.scatter(
        pts_after[:, 0],
        pts_after[:, 1],
        color=COLOR_AFTER,
        s=50,
        zorder=5,
        label="After (2009–11)",
        edgecolors="white",
        linewidths=0.4,
    )

    # --- Kernel label near the kernel center ---
    ax.annotate(
        r"$k(x,y) = \exp\!\left(-\dfrac{\|x-y\|^2}{2\sigma^2}\right)$",
        xy=kc,
        xytext=(kc[0] + spread * 0.25, kc[1] + spread * 0.18),
        fontsize=6.5,
        color=COLOR_BEFORE,
        arrowprops=dict(arrowstyle="->", color=COLOR_BEFORE, lw=0.6),
        zorder=6,
    )

    # --- Formula text box ---
    formula = r"$\mathrm{MMD}^2 = \mathbb{E}[k(x,x')] + \mathbb{E}[k(y,y')] - 2\,\mathbb{E}[k(x,y)]$"
    ax.text(
        0.03,
        0.97,
        formula,
        transform=ax.transAxes,
        fontsize=7,
        va="top",
        ha="left",
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=LIGHT, lw=0.5, alpha=0.85),
    )

    # Axes cosmetics
    ax.set_xlabel("PC 1  (idea-space axis 1)", fontsize=8)
    ax.set_ylabel("PC 2  (idea-space axis 2)", fontsize=8)
    ax.set_title(
        "MMD: can a smooth function separate the two clouds?", fontsize=9, color=DARK
    )
    ax.legend(fontsize=7, frameon=False, loc="lower right")

    # Pad axes so ellipse and circles are visible
    margin = spread * 0.35
    xmin, xmax = all_pts[:, 0].min() - margin, all_pts[:, 0].max() + margin
    ymin, ymax = all_pts[:, 1].min() - margin, all_pts[:, 1].max() + margin
    ax.set_xlim(xmin, xmax)
    ax.set_ylim(ymin, ymax)
    ax.set_xticks([])
    ax.set_yticks([])

    fig.tight_layout()
    stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, stem, dpi=DPI)
    plt.close(fig)
    log.info("Done → %s.png", stem)


if __name__ == "__main__":
    sys.exit(main())
