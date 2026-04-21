"""Schematic figure: S3 Sliced Wasserstein Distance — ELI15 quality.

Shows two small clouds (Before 2000–02, After 2009–11) in 2D PCA space,
with random projection directions and sorted quantile matching shown on
one direction.

Usage::

    uv run python scripts/plot_schematic_S3_sliced_wasserstein.py \\
        --output /tmp/test_S3.png
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

log = get_logger("plot_schematic_S3_sliced_wasserstein")
apply_style()

BEFORE_YEARS = (2000, 2002)
AFTER_YEARS = (2009, 2011)
N_PER_GROUP = 6
SEED = 42

COLOR_BEFORE = "#3A7EC6"  # blue
COLOR_AFTER = "#D94F3D"  # red
N_DIRECTIONS = 2


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

    pts_before = pca.transform(embeddings[sel_before])  # (6, 2)
    pts_after = pca.transform(embeddings[sel_after])  # (6, 2)

    all_pts = np.vstack([pts_before, pts_after])
    centroid = all_pts.mean(axis=0)
    spread = np.ptp(all_pts, axis=0).mean()

    # Two projection directions (unit vectors, fixed angles for clarity)
    angles = [30.0, 110.0]  # degrees
    directions = [
        np.array([np.cos(np.radians(a)), np.sin(np.radians(a))]) for a in angles
    ]

    # --- Build figure ---
    fig, ax = plt.subplots(figsize=(FIGWIDTH, FIGWIDTH * 0.90))

    # Arrow length for projection directions
    arrow_len = spread * 0.60

    for k, (theta, direction) in enumerate(zip(angles, directions)):
        color = LIGHT if k == 1 else MED
        lw = 1.0 if k == 0 else 0.7

        # Draw projection arrow through centroid
        start = centroid - direction * arrow_len
        end = centroid + direction * arrow_len
        ax.annotate(
            "",
            xy=end,
            xytext=start,
            arrowprops=dict(
                arrowstyle="-|>",
                color=color,
                lw=lw,
                mutation_scale=7,
            ),
            zorder=3,
        )

        # Label first direction
        if k == 0:
            label_pos = end + direction * spread * 0.08
            ax.text(
                label_pos[0],
                label_pos[1],
                "random\ndirection θ",
                fontsize=6,
                color=DARK,
                ha="center",
                va="center",
                zorder=5,
            )

    # --- Sorted quantile matching on first direction ---
    theta0 = directions[0]
    perp0 = np.array([-theta0[1], theta0[0]])  # perpendicular for rug offset

    proj_before = pts_before @ theta0  # scalar projections
    proj_after = pts_after @ theta0

    # Sorted order
    sorted_b = np.argsort(proj_before)
    sorted_a = np.argsort(proj_after)

    # Project points onto the direction line (for drawing rug marks)
    rug_offset = spread * 0.06  # perpendicular offset for visibility

    # Draw quantile-matching arrows (sorted rank pairing)
    for rank in range(N_PER_GROUP):
        bi = sorted_b[rank]
        ai = sorted_a[rank]
        # Position along the axis line
        pb_on_line = centroid + proj_before[bi] * theta0
        pa_on_line = centroid + proj_after[ai] * theta0
        # Offset slightly so they don't overlap
        pb_vis = pb_on_line - perp0 * rug_offset
        pa_vis = pa_on_line + perp0 * rug_offset
        ax.annotate(
            "",
            xy=pa_vis,
            xytext=pb_vis,
            arrowprops=dict(
                arrowstyle="-|>",
                color="#888888",
                lw=0.5,
                mutation_scale=4,
                alpha=0.6,
            ),
            zorder=4,
        )

    # Rug marks for each cloud on the first direction
    for bi in range(N_PER_GROUP):
        pb_on_line = centroid + proj_before[bi] * theta0
        mark = pb_on_line - perp0 * rug_offset
        ax.plot(
            [mark[0] - perp0[0] * 0.01, mark[0] + perp0[0] * 0.01],
            [mark[1] - perp0[1] * 0.015, mark[1] + perp0[1] * 0.015],
            color=COLOR_BEFORE,
            lw=1.5,
            zorder=5,
        )
    for ai in range(N_PER_GROUP):
        pa_on_line = centroid + proj_after[ai] * theta0
        mark = pa_on_line + perp0 * rug_offset
        ax.plot(
            [mark[0] - perp0[0] * 0.01, mark[0] + perp0[0] * 0.01],
            [mark[1] - perp0[1] * 0.015, mark[1] + perp0[1] * 0.015],
            color=COLOR_AFTER,
            lw=1.5,
            zorder=5,
        )

    # --- Scatter clouds ---
    ax.scatter(
        pts_before[:, 0],
        pts_before[:, 1],
        color=COLOR_BEFORE,
        s=50,
        zorder=6,
        label="Before (2000–02)",
        edgecolors="white",
        linewidths=0.4,
    )
    ax.scatter(
        pts_after[:, 0],
        pts_after[:, 1],
        color=COLOR_AFTER,
        s=50,
        zorder=6,
        label="After (2009–11)",
        edgecolors="white",
        linewidths=0.4,
    )

    # --- Formula text box ---
    formula = r"$SW = \mathrm{avg}_\theta\; W_1(\mathrm{proj}_\theta P,\; \mathrm{proj}_\theta Q)$"
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
        "Sliced Wasserstein: project → sort → compare → average",
        fontsize=9,
        color=DARK,
    )
    ax.text(
        0.5,
        -0.10,
        "Grey arrows: rank-1 blue matched to rank-1 red, rank-2 to rank-2, …",
        transform=ax.transAxes,
        fontsize=6.5,
        ha="center",
        color=MED,
    )
    ax.legend(fontsize=7, frameon=False, loc="lower right")

    margin = spread * 0.45
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
