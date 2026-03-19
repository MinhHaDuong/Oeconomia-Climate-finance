"""Generate DVC pipeline DAG figure from dvc.yaml.

Reads the pipeline definition and renders a directed acyclic graph
showing stage dependencies. Output: content/figures/fig_dag.png
"""

import os

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import yaml

from plot_style import FIGWIDTH, DPI, DARK, MED, LIGHT, FILL, RCPARAMS
from utils import get_logger

log = get_logger("plot_fig_dag")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── Load pipeline ──────────────────────────────────────────

def load_dag():
    """Parse dvc.yaml and return {stage: [upstream_stages]}."""
    dvc_path = os.path.join(BASE_DIR, "dvc.yaml")
    with open(dvc_path) as f:
        dvc = yaml.safe_load(f)

    stages = dvc["stages"]

    # Build output → stage mapping
    out_to_stage = {}
    for name, spec in stages.items():
        for out in spec.get("outs", []):
            out_to_stage[out] = name

    # Build adjacency: stage → list of upstream stages
    deps = {}
    for name, spec in stages.items():
        upstream = set()
        for dep in spec.get("deps", []):
            if dep in out_to_stage and out_to_stage[dep] != name:
                upstream.add(out_to_stage[dep])
        deps[name] = sorted(upstream)

    return deps


# ── Layout ──────────────────────────────────────────────────

# Manual layout: (x, y) positions for each stage.
# x = column (pipeline phase), y = row (parallel stages spread vertically).
POSITIONS = {
    "catalog_bibcnrs":  (0, 4),
    "catalog_istex":    (0, 3),
    "catalog_openalex": (0, 2),
    "catalog_grey":     (0, 1),
    "catalog_teaching": (0, 0),
    "catalog_merge":    (1.8, 2),
    "enrich":           (3.3, 2),
    "extend":           (4.8, 2),
    "filter":           (6.3, 2),
    "align":            (7.8, 2),
}

# Short display names
LABELS = {
    "catalog_bibcnrs":  "bibCNRS",
    "catalog_istex":    "ISTEX",
    "catalog_openalex": "OpenAlex",
    "catalog_grey":     "Grey lit.",
    "catalog_teaching": "Teaching",
    "catalog_merge":    "Merge",
    "enrich":           "Enrich",
    "extend":           "Extend",
    "filter":           "Filter",
    "align":            "Align",
}

# Phase groupings for background shading
PHASES = [
    ("Discovery", [-0.8, 0.8], [-0.7, 4.7]),
    ("Merge",     [1.1, 2.5],  [1.3, 2.7]),
    ("Enrich",    [2.6, 4.0],  [1.3, 2.7]),
    ("Refine",    [4.1, 7.0],  [1.3, 2.7]),
    ("Align",     [7.1, 8.5],  [1.3, 2.7]),
]


def draw_dag(deps):
    """Render the DAG as a matplotlib figure."""
    matplotlib.rcParams.update(RCPARAMS)

    fig, ax = plt.subplots(figsize=(FIGWIDTH * 1.5, FIGWIDTH * 0.55))

    # Phase background bands
    for label, (x0, x1), (y0, y1) in PHASES:
        rect = mpatches.FancyBboxPatch(
            (x0, y0), x1 - x0, y1 - y0,
            boxstyle="round,pad=0.1", facecolor=FILL, edgecolor="none",
            alpha=0.5, zorder=0)
        ax.add_patch(rect)
        ax.text((x0 + x1) / 2, y1 + 0.15, label,
                ha="center", va="bottom", fontsize=7, fontstyle="italic",
                color=MED)

    # Edges
    for stage, upstreams in deps.items():
        if stage not in POSITIONS:
            continue
        x1, y1 = POSITIONS[stage]
        for up in upstreams:
            if up not in POSITIONS:
                continue
            x0, y0 = POSITIONS[up]
            ax.annotate("", xy=(x1 - 0.15, y1), xytext=(x0 + 0.15, y0),
                        arrowprops=dict(arrowstyle="-|>", color=MED,
                                        lw=0.8, shrinkA=2, shrinkB=2),
                        zorder=1)

    # Nodes
    for stage, (x, y) in POSITIONS.items():
        label = LABELS.get(stage, stage)
        bbox = dict(boxstyle="round,pad=0.3", facecolor="white",
                    edgecolor=DARK, linewidth=0.8)
        ax.text(x, y, label, ha="center", va="center",
                fontsize=7, fontweight="bold", color=DARK,
                bbox=bbox, zorder=2)

    # Scispsace annotation (hand-curated input to merge)
    ax.text(1.8, 0.8, "SciSpace\n(manual)", ha="center", va="top",
            fontsize=6, fontstyle="italic", color=MED)
    ax.annotate("", xy=(1.8, 1.35), xytext=(1.8, 0.85),
                arrowprops=dict(arrowstyle="-|>", color=LIGHT,
                                lw=0.6, linestyle="--"),
                zorder=1)

    # Output annotations on right
    ax.text(7.8 + 0.6, 2.6, "refined_works.csv\nrefined_embeddings.npz\nrefined_citations.csv",
            ha="left", va="center", fontsize=5.5, color=MED, fontstyle="italic")

    ax.set_xlim(-1.3, 10.5)
    ax.set_ylim(-1.0, 5.3)
    ax.set_aspect("equal")
    ax.axis("off")

    out_path = os.path.join(BASE_DIR, "content", "figures", "fig_dag.png")
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight",
                facecolor="white", pad_inches=0.1)
    log.info("Saved %s", out_path)
    plt.close(fig)


if __name__ == "__main__":
    deps = load_dag()
    draw_dag(deps)
