"""ELI15 schematic: Cross-Tradition Citation Flow (G4).

Visualises citation flows between three intellectual traditions
(Finance, Development Economics, Physical Science) as a node-and-arrow
diagram.  Based on Börner (2010) and Klavans & Boyack (2017).

Uses real corpus when available (keyword-based tradition assignment);
falls back to hand-tuned synthetic flow matrix.

Usage::

    uv run python scripts/plot_schematic_G4_cross_tradition.py \\
        --output /tmp/test_G4.png
"""

import os
import sys

import matplotlib.patches as mpatches
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import FancyArrowPatch
from pipeline_io import save_figure
from plot_style import DARK, DPI, FIGWIDTH, LIGHT, MED, apply_style
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("plot_schematic_G4_cross_tradition")
apply_style()

# --- Tradition definitions ---
TRADITIONS = ["Finance", "Development", "Physical\nScience"]
TRAD_COLORS = ["#3377BB", "#449944", "#CC3333"]

# Keyword sets for tradition assignment (title + abstract matching)
_FINANCE_KW = {
    "green bond",
    "investment",
    "risk",
    "financial",
    "finance",
    "market",
    "fund",
    "asset",
    "bank",
    "portfolio",
    "capital",
}
_DEVELOP_KW = {
    "development",
    "aid",
    "poverty",
    "developing",
    "emerging",
    "south",
    "world bank",
    "oda",
    "donor",
    "recipient",
    "adaptation fund",
}
_PHYSICAL_KW = {
    "carbon",
    "emission",
    "temperature",
    "climate model",
    "mitigation",
    "renewable",
    "energy transition",
    "greenhouse",
    "radiative",
    "atmospheric",
}

# Synthetic fallback flow matrix (F→F, F→D, F→P, D→F, ...) — hand-tuned
# Rows = citer tradition, cols = cited tradition
SYNTHETIC_FLOWS = np.array(
    [
        [480, 60, 40],  # Finance cites: Finance (480), Dev (60), Phys (40)
        [55, 320, 80],  # Development cites
        [35, 45, 410],  # Physical cites
    ],
    dtype=float,
)

# Triangle node positions (unit circle, apex at top)
_ANGLES = [np.pi / 2, np.pi / 2 + 2 * np.pi / 3, np.pi / 2 + 4 * np.pi / 3]
NODE_R = 0.62
NODE_POS = [(NODE_R * np.cos(a), NODE_R * np.sin(a)) for a in _ANGLES]


def _classify_text(text):
    """Return 0=Finance, 1=Development, 2=Physical, or -1=unknown."""
    if not isinstance(text, str):
        return -1
    t = text.lower()
    scores = [
        sum(1 for kw in _FINANCE_KW if kw in t),
        sum(1 for kw in _DEVELOP_KW if kw in t),
        sum(1 for kw in _PHYSICAL_KW if kw in t),
    ]
    best = int(np.argmax(scores))
    return best if scores[best] > 0 else -1


def _load_real_flows():
    """Build 3×3 flow matrix from real corpus; raise on failure."""
    from pipeline_loaders import load_analysis_corpus, load_refined_citations

    works, _ = load_analysis_corpus(with_embeddings=False)
    citations = load_refined_citations()

    # Build combined text column for classification
    text_col = works["title"].fillna("") + " " + works.get("abstract", "").fillna("")
    works = works.copy()
    works["tradition"] = text_col.apply(_classify_text)

    classified = works[works["tradition"] >= 0]
    if len(classified) < 200:
        raise ValueError(f"Too few classified works ({len(classified)})")

    doi_trad = dict(zip(classified["doi"], classified["tradition"]))

    mask = citations["source_doi"].isin(doi_trad) & citations["ref_doi"].isin(doi_trad)
    internal = citations.loc[mask, ["source_doi", "ref_doi"]]

    flows = np.zeros((3, 3), dtype=float)
    for _, row in internal.iterrows():
        s_trad = doi_trad[row["source_doi"]]
        r_trad = doi_trad[row["ref_doi"]]
        flows[s_trad, r_trad] += 1

    total = flows.sum()
    if total < 100:
        raise ValueError(f"Too few classified citation edges ({total:.0f})")

    log.info("Real flows (citer→cited):\n%s", flows.astype(int))
    return flows


def _curved_arrow(ax, src, dst, width, color, self_loop=False, rad=0.35):
    """Draw a curved arrow from src to dst with width proportional to flow."""
    if self_loop:
        # Draw a small circular arc as a self-loop above the node
        cx, cy = src
        theta = np.linspace(0.2 * np.pi, 1.8 * np.pi, 60)
        r = 0.13 + 0.06 * (width / 5.0)
        xs = cx + r * np.cos(theta)
        ys = cy + r * np.sin(theta) + 0.18
        lw = max(0.6, min(width * 0.5, 5.0))
        ax.plot(xs, ys, color=color, lw=lw, solid_capstyle="round", zorder=2)
        # Arrowhead at end of arc
        ax.annotate(
            "",
            xy=(xs[-1], ys[-1]),
            xytext=(xs[-2], ys[-2]),
            arrowprops=dict(arrowstyle="-|>", color=color, lw=lw, mutation_scale=8),
        )
        return

    lw = max(0.6, min(width * 0.5, 6.0))
    patch = FancyArrowPatch(
        src,
        dst,
        connectionstyle=f"arc3,rad={rad}",
        arrowstyle=f"-|>,head_width={max(0.02, width * 0.012)},head_length={max(0.03, width * 0.018)}",
        color=color,
        linewidth=lw,
        zorder=2,
    )
    ax.add_patch(patch)


def _draw_diagram(ax, flows, using_real):
    """Draw the 3-tradition flow diagram."""
    total = flows.sum()
    c_cross = flows.sum() - np.trace(flows)
    c_within = np.trace(flows)
    g4 = c_cross / total if total > 0 else 0.0

    # --- Draw arrows ---
    max_flow = flows.max()
    for i in range(3):
        for j in range(3):
            f = flows[i, j]
            if f < 1:
                continue
            width = 1.0 + 8.0 * (f / max_flow)
            src = NODE_POS[i]
            dst = NODE_POS[j]
            if i == j:
                _curved_arrow(ax, src, dst, width, TRAD_COLORS[i], self_loop=True)
            else:
                # Alternate curvature direction to avoid overlap
                rad = 0.25 if (i + j) % 2 == 0 else -0.25
                _curved_arrow(ax, src, dst, width, TRAD_COLORS[i], rad=rad)

    # --- Flow volume labels on cross-tradition arrows ---
    for i in range(3):
        for j in range(3):
            if i == j:
                continue
            f = flows[i, j]
            if f < 10:
                continue
            mx = (NODE_POS[i][0] + NODE_POS[j][0]) / 2
            my = (NODE_POS[i][1] + NODE_POS[j][1]) / 2
            # Offset perpendicular to the arrow
            dx = NODE_POS[j][1] - NODE_POS[i][1]
            dy = NODE_POS[i][0] - NODE_POS[j][0]
            norm = np.hypot(dx, dy) + 1e-9
            offset = 0.10 if (i + j) % 2 == 0 else -0.10
            ax.text(
                mx + offset * dx / norm,
                my + offset * dy / norm,
                f"{f:.0f}",
                ha="center",
                va="center",
                fontsize=5.5,
                color=DARK,
                zorder=5,
            )

    # --- Draw node circles ---
    node_r_display = 0.155
    for i, (pos, name, col) in enumerate(zip(NODE_POS, TRADITIONS, TRAD_COLORS)):
        ax.add_patch(
            mpatches.Circle(
                pos,
                node_r_display,
                facecolor=col,
                edgecolor=DARK,
                linewidth=0.7,
                alpha=0.85,
                zorder=3,
            )
        )
        ax.text(
            pos[0],
            pos[1],
            name,
            ha="center",
            va="center",
            fontsize=6,
            color="white",
            fontweight="bold",
            zorder=4,
            multialignment="center",
        )

    # --- G4 annotation ---
    src_label = "synthetic" if not using_real else "real corpus"
    ax.text(
        0.5,
        -0.95,
        rf"$G4 = C_{{cross}} / (C_{{cross}} + C_{{within}})$"
        f" = {g4:.1%}\nArrow width = citation volume  [{src_label} data]",
        ha="center",
        va="bottom",
        fontsize=6.5,
        color=DARK,
        transform=ax.transData,
        bbox=dict(boxstyle="round,pad=0.3", fc="#F5F5F5", ec=LIGHT, lw=0.5),
    )

    ax.set_xlim(-1.05, 1.05)
    ax.set_ylim(-1.05, 1.05)
    ax.set_aspect("equal")
    ax.axis("off")


def main():
    io_args, _ = parse_io_args()
    validate_io(output=io_args.output)

    using_real = False
    try:
        flows = _load_real_flows()
        using_real = True
        log.info("Using real corpus flows.")
    except Exception as exc:
        log.warning("Real data unavailable (%s) — using synthetic flows.", exc)
        flows = SYNTHETIC_FLOWS.copy()

    fig, ax = plt.subplots(figsize=(FIGWIDTH, FIGWIDTH * 0.95))
    plt.subplots_adjust(left=0.02, right=0.98, top=0.90, bottom=0.12)

    _draw_diagram(ax, flows, using_real)

    ax.set_title(
        "Cross-Tradition Citation Flow: how interconnected are the sub-fields?",
        fontsize=8,
        color=DARK,
        pad=6,
    )
    fig.text(
        0.5,
        0.01,
        "Arrow width = citation volume (Börner 2010, Klavans & Boyack 2017)",
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
