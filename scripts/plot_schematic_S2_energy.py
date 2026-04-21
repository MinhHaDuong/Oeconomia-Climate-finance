"""Schematic figure: S2 Energy Distance — ELI15 quality.

Shows two small clouds (Before 2000–02, After 2009–11) in 2D PCA space,
with all 25 cross-cloud lines in grey, a highlighted representative pair,
and within-group dashed connectors.

Usage::

    uv run python scripts/plot_schematic_S2_energy.py \\
        --output /tmp/test_S2.png
"""

import os
import sys

import matplotlib.pyplot as plt
import numpy as np
from pipeline_io import save_figure
from pipeline_loaders import load_analysis_corpus
from plot_style import DARK, DPI, FIGWIDTH, LIGHT, MED, apply_style
from script_io_args import parse_io_args, validate_io
from sklearn.decomposition import PCA
from utils import get_logger

log = get_logger("plot_schematic_S2_energy")
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

    pts_before = pca.transform(embeddings[sel_before])  # (5, 2)
    pts_after = pca.transform(embeddings[sel_after])  # (5, 2)

    all_pts = np.vstack([pts_before, pts_after])

    # --- Build figure ---
    fig, ax = plt.subplots(figsize=(FIGWIDTH, FIGWIDTH * 0.85))

    # --- Within-group connectors (dashed, very light) ---
    for i in range(N_PER_GROUP):
        for j in range(i + 1, N_PER_GROUP):
            ax.plot(
                [pts_before[i, 0], pts_before[j, 0]],
                [pts_before[i, 1], pts_before[j, 1]],
                color=COLOR_BEFORE,
                linewidth=0.4,
                linestyle="--",
                alpha=0.20,
                zorder=1,
            )
            ax.plot(
                [pts_after[i, 0], pts_after[j, 0]],
                [pts_after[i, 1], pts_after[j, 1]],
                color=COLOR_AFTER,
                linewidth=0.4,
                linestyle="--",
                alpha=0.20,
                zorder=1,
            )

    # --- All 25 cross-cloud lines in thin grey ---
    for i in range(N_PER_GROUP):
        for j in range(N_PER_GROUP):
            ax.plot(
                [pts_before[i, 0], pts_after[j, 0]],
                [pts_before[i, 1], pts_after[j, 1]],
                color=LIGHT,
                linewidth=0.5,
                alpha=0.30,
                zorder=2,
            )

    # --- Representative pair: lowest PC2 in each cloud ---
    rep_b_idx = np.argmin(pts_before[:, 1])
    rep_a_idx = np.argmin(pts_after[:, 1])
    rb = pts_before[rep_b_idx]
    ra = pts_after[rep_a_idx]

    ax.plot(
        [rb[0], ra[0]],
        [rb[1], ra[1]],
        color=DARK,
        linewidth=1.8,
        zorder=4,
    )

    # Label at midpoint of the black line
    mid = (rb + ra) / 2.0
    spread = np.ptp(all_pts, axis=0).mean()
    ax.annotate(
        r"$d_{ij} = \|x_i - y_j\|$",
        xy=mid,
        xytext=(mid[0] + spread * 0.20, mid[1] + spread * 0.15),
        fontsize=7,
        color=DARK,
        arrowprops=dict(arrowstyle="->", color=DARK, lw=0.7),
        zorder=6,
    )

    # --- Scatter clouds ---
    ax.scatter(
        pts_before[:, 0],
        pts_before[:, 1],
        color=COLOR_BEFORE,
        s=55,
        zorder=5,
        label="Before (2000–02)",
        edgecolors="white",
        linewidths=0.4,
    )
    ax.scatter(
        pts_after[:, 0],
        pts_after[:, 1],
        color=COLOR_AFTER,
        s=55,
        zorder=5,
        label="After (2009–11)",
        edgecolors="white",
        linewidths=0.4,
    )

    # Mark representative points with a ring
    ax.scatter(
        [rb[0]],
        [rb[1]],
        s=120,
        facecolors="none",
        edgecolors=DARK,
        linewidths=1.2,
        zorder=6,
    )
    ax.scatter(
        [ra[0]],
        [ra[1]],
        s=120,
        facecolors="none",
        edgecolors=DARK,
        linewidths=1.2,
        zorder=6,
    )

    # --- Formula text box (upper left) ---
    formula = (
        r"$E = 2\langle d_{\rm cross}\rangle - \langle d_{\rm blue}\rangle"
        r" - \langle d_{\rm red}\rangle$"
    )
    ax.text(
        0.03,
        0.97,
        formula,
        transform=ax.transAxes,
        fontsize=7.5,
        va="top",
        ha="left",
        bbox=dict(boxstyle="round,pad=0.3", fc="white", ec=LIGHT, lw=0.5, alpha=0.88),
    )

    ax.set_xlabel("PC 1  (idea-space axis 1)", fontsize=8)
    ax.set_ylabel("PC 2  (idea-space axis 2)", fontsize=8)
    ax.set_title(
        "Energy Distance: how far apart are the two clouds?",
        fontsize=9,
        color=DARK,
    )
    ax.text(
        0.5,
        -0.10,
        "Large E → the two windows' papers live far apart in idea-space",
        transform=ax.transAxes,
        fontsize=7,
        ha="center",
        color=MED,
    )
    ax.legend(fontsize=7, frameon=False, loc="lower right")

    margin = spread * 0.35
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
