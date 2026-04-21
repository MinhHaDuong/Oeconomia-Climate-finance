"""ELI15 schematic: Betweenness Centrality (G8).

Three panels show star, ring, and chain topologies with node size and
colour proportional to betweenness centrality.  Based on Freeman (1977,
Fig. 2).

Usage::

    uv run python scripts/plot_schematic_G8_betweenness.py \\
        --output /tmp/test_G8.png
"""

import os
import sys

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from matplotlib.cm import ScalarMappable
from matplotlib.colors import Normalize
from pipeline_io import save_figure
from plot_style import DARK, DPI, FIGWIDTH, LIGHT, MED, apply_style
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("plot_schematic_G8_betweenness")
apply_style()

N_NODES = 7


def _linear_layout(G):
    """Lay out a path graph as a horizontal line."""
    return {i: (i / (N_NODES - 1), 0.5) for i in G.nodes()}


def _star_layout(G):
    """Hub at centre, leaves in a circle."""
    hub = 0
    leaves = [n for n in G.nodes() if n != hub]
    angles = np.linspace(0, 2 * np.pi, len(leaves), endpoint=False)
    pos = {hub: (0.5, 0.5)}
    for leaf, angle in zip(leaves, angles):
        pos[leaf] = (0.5 + 0.42 * np.cos(angle), 0.5 + 0.42 * np.sin(angle))
    return pos


def _draw_panel(ax, G, pos, bc, title):
    """Draw one topology panel."""
    bc_vals = np.array([bc[n] for n in G.nodes()])
    cmap = plt.colormaps["Greys"]
    norm = Normalize(vmin=0.0, vmax=max(bc_vals.max(), 0.01))

    node_sizes = 200 + 1500 * bc_vals
    node_colors = [cmap(norm(bc[n])) for n in G.nodes()]

    nx.draw_networkx_edges(G, pos, ax=ax, edge_color=MED, width=0.8, arrows=False)
    nx.draw_networkx_nodes(
        G,
        pos,
        ax=ax,
        node_size=node_sizes,
        node_color=node_colors,
        edgecolors=DARK,
        linewidths=0.5,
    )
    # Labels: betweenness rounded to 2 decimal places
    labels = {n: f"{bc[n]:.2f}" for n in G.nodes()}
    nx.draw_networkx_labels(
        G, pos, labels=labels, ax=ax, font_size=4.5, font_color=DARK
    )

    ax.set_title(title, fontsize=7.5, color=DARK, pad=4)
    ax.set_xlim(-0.05, 1.05)
    ax.set_ylim(0.0, 1.0)
    ax.set_aspect("equal")
    ax.axis("off")


def main():
    io_args, _ = parse_io_args()
    validate_io(output=io_args.output)

    # --- Build graphs ---
    G_star = nx.star_graph(N_NODES - 1)  # 7 nodes: hub 0 + leaves 1-6
    G_ring = nx.cycle_graph(N_NODES)
    G_chain = nx.path_graph(N_NODES)

    # --- Layouts ---
    pos_star = _star_layout(G_star)
    pos_ring = nx.circular_layout(G_ring, center=(0.5, 0.5), scale=0.42)
    pos_chain = _linear_layout(G_chain)

    # --- Betweenness centrality ---
    bc_star = nx.betweenness_centrality(G_star, normalized=True)
    bc_ring = nx.betweenness_centrality(G_ring, normalized=True)
    bc_chain = nx.betweenness_centrality(G_chain, normalized=True)

    # --- Figure: 3 side-by-side panels ---
    fig, axes = plt.subplots(1, 3, figsize=(FIGWIDTH, 2.6))

    _draw_panel(axes[0], G_star, pos_star, bc_star, "Star\n(hub controls all)")
    _draw_panel(axes[1], G_ring, pos_ring, bc_ring, "Ring\n(everyone equal)")
    _draw_panel(axes[2], G_chain, pos_chain, bc_chain, "Chain\n(middle is gatekeeper)")

    # --- Colourbar (shared) ---
    sm = ScalarMappable(cmap=plt.colormaps["Greys"], norm=Normalize(vmin=0, vmax=1))
    sm.set_array([])
    cbar = fig.colorbar(
        sm, ax=axes, orientation="horizontal", fraction=0.04, pad=0.18, aspect=40
    )
    cbar.set_label("Betweenness centrality (normalised)", fontsize=6.5)
    cbar.ax.tick_params(labelsize=6)

    # --- Titles ---
    fig.suptitle(
        "Betweenness Centrality: who controls the flow of information?",
        fontsize=8,
        color=DARK,
        y=1.01,
    )
    fig.text(
        0.5,
        0.96,
        "Node size ∝ betweenness.  After Freeman (1977, Fig. 2)",
        ha="center",
        va="top",
        fontsize=6.5,
        color=MED,
        style="italic",
    )

    # --- Formula text box below panels ---
    fig.text(
        0.5,
        -0.02,
        r"$G8 = |\overline{BC}_{after} - \overline{BC}_{before}|$"
        "     G8 measures whether authority became more or less"
        " concentrated in broker papers.",
        ha="center",
        va="top",
        fontsize=6,
        color=DARK,
        bbox=dict(boxstyle="round,pad=0.3", fc="#F5F5F5", ec=LIGHT, lw=0.5),
    )

    plt.tight_layout(rect=[0, 0.0, 1, 0.95])

    stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, stem, dpi=DPI)
    plt.close(fig)
    log.info("Saved → %s.png", stem)


if __name__ == "__main__":
    sys.exit(main())
