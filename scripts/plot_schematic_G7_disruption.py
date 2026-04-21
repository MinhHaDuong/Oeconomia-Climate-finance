"""ELI15 schematic: Disruption Index CD (G7).

Shows the classic concentric-ring diagram from Funk & Owen-Smith (2017):
one focal paper at the centre, reference papers in the inner ring, and
citing papers coloured by type (f/b/c) in the outer ring.

Usage::

    uv run python scripts/plot_schematic_G7_disruption.py \\
        --output /tmp/test_G7.png
"""

import os
import sys

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from pipeline_io import save_figure
from plot_style import DARK, DPI, FIGWIDTH, LIGHT, MED, apply_style
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("plot_schematic_G7_disruption")
apply_style()

# --- Network geometry constants ---
RADIUS_INNER = 0.40  # reference papers ring
RADIUS_OUTER = 1.00  # citing papers ring
N_REFS = 5
N_F = 6  # cite focal only  → disruption ↑
N_B = 5  # cite focal + ≥1 reference → disruption ↓
N_C = 4  # cite references only → disruption ↓

# --- Colours ---
COL_FOCAL = "#F0B429"  # gold / yellow
COL_REF = "#AAAAAA"  # grey
COL_F = "#CC3333"  # red  (disrupting)
COL_B = "#E07830"  # orange (mixed)
COL_C = "#3377BB"  # blue (consolidating)


def _ring_positions(n, radius, angle_offset=0.0):
    """Return (x, y) pairs for n nodes evenly spaced on a ring."""
    angles = np.linspace(0, 2 * np.pi, n, endpoint=False) + angle_offset
    return list(zip(radius * np.cos(angles), radius * np.sin(angles)))


def _draw_arrow(ax, src, dst, color, lw=0.8, mutation_scale=8, linestyle="-"):
    """Draw an arrow from src to dst."""
    ax.annotate(
        "",
        xy=dst,
        xytext=src,
        arrowprops=dict(
            arrowstyle="-|>",
            color=color,
            lw=lw,
            mutation_scale=mutation_scale,
            linestyle=linestyle,
        ),
    )


def _shrink_endpoint(src, dst, shrink=0.08):
    """Move dst inward by shrink units along the src→dst direction."""
    dx, dy = dst[0] - src[0], dst[1] - src[1]
    dist = np.hypot(dx, dy)
    if dist < 1e-9:
        return dst
    return (dst[0] - shrink * dx / dist, dst[1] - shrink * dy / dist)


def main():
    io_args, _ = parse_io_args()
    validate_io(output=io_args.output)

    fig, ax = plt.subplots(figsize=(FIGWIDTH, FIGWIDTH * 0.92))
    ax.set_xlim(-1.4, 1.4)
    ax.set_ylim(-1.4, 1.4)
    ax.set_aspect("equal")
    ax.axis("off")

    focal = (0.0, 0.0)

    # Inner ring: reference papers (evenly spaced)
    ref_positions = _ring_positions(N_REFS, RADIUS_INNER, angle_offset=np.pi / 10)

    # Outer ring: f papers on left arc, b on top arc, c on right arc
    # Divide [0, 2π] into thirds
    f_positions = _ring_positions(N_F, RADIUS_OUTER, angle_offset=np.pi * 0.55)
    b_positions = _ring_positions(N_B, RADIUS_OUTER, angle_offset=-np.pi * 0.10)
    c_positions = _ring_positions(N_C, RADIUS_OUTER, angle_offset=-np.pi * 0.62)

    # --- Draw edges ---
    # F₀ → references (focal cites refs)
    for rp in ref_positions:
        dst = _shrink_endpoint(focal, rp, shrink=0.07)
        _draw_arrow(ax, focal, dst, color="#999999", lw=0.6, mutation_scale=6)

    # f papers → F₀  (cite focal only)
    for fp in f_positions:
        src = _shrink_endpoint(focal, fp, shrink=0.06)
        _draw_arrow(ax, fp, src, color=COL_F, lw=0.7, mutation_scale=7)

    # b papers → F₀
    for bp in b_positions:
        src = _shrink_endpoint(focal, bp, shrink=0.06)
        _draw_arrow(ax, bp, src, color=COL_B, lw=0.7, mutation_scale=7)

    # b papers → closest reference (dashed)
    for i, bp in enumerate(b_positions):
        rp = ref_positions[i % N_REFS]
        dst = _shrink_endpoint(bp, rp, shrink=0.07)
        _draw_arrow(ax, bp, dst, color=COL_B, lw=0.5, mutation_scale=5, linestyle="--")

    # c papers → references only
    for i, cp in enumerate(c_positions):
        rp = ref_positions[(i + 2) % N_REFS]
        dst = _shrink_endpoint(cp, rp, shrink=0.07)
        _draw_arrow(ax, cp, dst, color=COL_C, lw=0.7, mutation_scale=7)

    # --- Draw nodes ---
    node_radius_focal = 0.12
    node_radius_ref = 0.075
    node_radius_outer = 0.065

    # Reference nodes
    for rp in ref_positions:
        ax.add_patch(
            mpatches.Circle(
                rp,
                node_radius_ref,
                facecolor=COL_REF,
                edgecolor=DARK,
                linewidth=0.5,
                zorder=3,
            )
        )
        ax.text(
            rp[0],
            rp[1],
            "ref",
            ha="center",
            va="center",
            fontsize=4.5,
            color="white",
            fontweight="bold",
            zorder=4,
        )

    # f nodes
    for fp in f_positions:
        ax.add_patch(
            mpatches.Circle(
                fp,
                node_radius_outer,
                facecolor=COL_F,
                edgecolor=DARK,
                linewidth=0.5,
                zorder=3,
            )
        )
        ax.text(
            fp[0],
            fp[1],
            "f",
            ha="center",
            va="center",
            fontsize=5,
            color="white",
            fontweight="bold",
            zorder=4,
        )

    # b nodes
    for bp in b_positions:
        ax.add_patch(
            mpatches.Circle(
                bp,
                node_radius_outer,
                facecolor=COL_B,
                edgecolor=DARK,
                linewidth=0.5,
                zorder=3,
            )
        )
        ax.text(
            bp[0],
            bp[1],
            "b",
            ha="center",
            va="center",
            fontsize=5,
            color="white",
            fontweight="bold",
            zorder=4,
        )

    # c nodes
    for cp in c_positions:
        ax.add_patch(
            mpatches.Circle(
                cp,
                node_radius_outer,
                facecolor=COL_C,
                edgecolor=DARK,
                linewidth=0.5,
                zorder=3,
            )
        )
        ax.text(
            cp[0],
            cp[1],
            "c",
            ha="center",
            va="center",
            fontsize=5,
            color="white",
            fontweight="bold",
            zorder=4,
        )

    # Focal node (on top)
    ax.add_patch(
        mpatches.Circle(
            focal,
            node_radius_focal,
            facecolor=COL_FOCAL,
            edgecolor=DARK,
            linewidth=0.8,
            zorder=5,
        )
    )
    ax.text(
        focal[0],
        focal[1] + 0.005,
        "focal\npaper",
        ha="center",
        va="center",
        fontsize=5,
        color=DARK,
        fontweight="bold",
        zorder=6,
    )

    # --- Ring labels ---
    ax.text(
        0.0,
        RADIUS_INNER + node_radius_ref + 0.05,
        "references",
        ha="center",
        va="bottom",
        fontsize=6,
        color=MED,
        style="italic",
    )
    ax.text(
        0.0,
        RADIUS_OUTER + node_radius_outer + 0.06,
        "later papers that cite this network",
        ha="center",
        va="bottom",
        fontsize=6,
        color=MED,
        style="italic",
    )

    # --- Legend ---
    legend_patches = [
        mpatches.Patch(
            facecolor=COL_F,
            edgecolor=DARK,
            linewidth=0.5,
            label=f"f = {N_F}  cite focal only → disruption ↑",
        ),
        mpatches.Patch(
            facecolor=COL_B,
            edgecolor=DARK,
            linewidth=0.5,
            label=f"b = {N_B}  cite both → disruption ↓",
        ),
        mpatches.Patch(
            facecolor=COL_C,
            edgecolor=DARK,
            linewidth=0.5,
            label=f"c = {N_C}  cite refs only → disruption ↓",
        ),
    ]
    ax.legend(
        handles=legend_patches,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.08),
        ncol=1,
        frameon=True,
        fontsize=6,
        framealpha=0.9,
    )

    # --- Formula annotation ---
    cd_val = (N_F - N_B) / (N_F + N_B + N_C)
    formula_text = (
        rf"$CD = \frac{{f - b}}{{f + b + c}}$"
        "\n"
        rf"$= \frac{{{N_F} - {N_B}}}{{{N_F} + {N_B} + {N_C}}} = {cd_val:.3f}$"
        "\n(barely disrupting)"
    )
    ax.text(
        -1.38,
        -1.25,
        formula_text,
        ha="left",
        va="bottom",
        fontsize=6.5,
        color=DARK,
        bbox=dict(boxstyle="round,pad=0.3", fc="#F5F5F5", ec=LIGHT, lw=0.5),
    )

    # --- Titles ---
    ax.set_title(
        "Disruption Index CD: does the paper open a new path or deepen an old one?",
        fontsize=8,
        color=DARK,
        pad=4,
    )
    fig.text(
        0.5,
        0.01,
        "After Funk & Owen-Smith (2017, Fig. 1), Park et al. (2023)",
        ha="center",
        va="bottom",
        fontsize=6.5,
        color=MED,
        style="italic",
    )

    stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, stem, dpi=DPI)
    plt.close(fig)
    log.info("Saved → %s.png", stem)


if __name__ == "__main__":
    sys.exit(main())
