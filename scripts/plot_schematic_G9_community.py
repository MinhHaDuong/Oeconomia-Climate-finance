"""ELI15 schematic: Louvain Community JS Divergence (G9).

Shows how the community structure of the citation graph changed between two
periods. JS divergence between community-share vectors quantifies the shift.

Uses entirely synthetic data (two stochastic-block-model graphs) for clarity
and reproducibility — real community detection is expensive and non-deterministic.

Usage::

    uv run python scripts/plot_schematic_G9_community.py \\
        --output /tmp/test_G9.png
"""

import os
import sys

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from pipeline_io import save_figure
from plot_style import DARK, DPI, FIGWIDTH, LIGHT, MED, apply_style
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("plot_schematic_G9_community")
apply_style()

# Fixed seed — schematic only, not a research parameter
_SEED = 42

# Community colours (accessible palette)
_COMM_COLORS = ["#4477AA", "#CC4444", "#44AA77"]
_COMM_LABELS = ["A", "B", "C"]


def _make_sbm_graph(sizes, p_in, p_out, seed):
    """Build a stochastic block model graph with given community sizes."""
    rng = np.random.default_rng(seed)
    nodes_per_comm = []
    start = 0
    for s in sizes:
        nodes_per_comm.append(list(range(start, start + s)))
        start += s
    n = sum(sizes)
    G = nx.DiGraph()
    G.add_nodes_from(range(n))
    for i in range(n):
        ci = next(k for k, members in enumerate(nodes_per_comm) if i in members)
        for j in range(n):
            if i == j:
                continue
            cj = next(k for k, members in enumerate(nodes_per_comm) if j in members)
            p = p_in if ci == cj else p_out
            if rng.random() < p:
                G.add_edge(i, j)
    # Store community membership as node attribute
    for k, members in enumerate(nodes_per_comm):
        for node in members:
            G.nodes[node]["community"] = k
    return G, nodes_per_comm


def _detect_communities(G, seed):
    """Run Louvain community detection. Falls back to node attribute if unavailable."""
    try:
        # NetworkX 3.x built-in
        from networkx.algorithms.community import louvain_communities

        comms = louvain_communities(G.to_undirected(), seed=seed)
        # Map node -> community index
        node_comm = {}
        for k, members in enumerate(comms):
            for node in members:
                node_comm[node] = k
        return node_comm, len(comms)
    except (ImportError, AttributeError):
        pass

    try:
        import community as community_louvain  # python-louvain

        partition = community_louvain.best_partition(
            G.to_undirected(), random_state=seed
        )
        n_comms = max(partition.values()) + 1
        return partition, n_comms
    except ImportError:
        pass

    # Fallback: use ground-truth community labels stored as node attributes
    log.warning(
        "No Louvain implementation found — using ground-truth partition as fallback."
    )
    node_comm = {n: G.nodes[n]["community"] for n in G.nodes()}
    n_comms = len(set(node_comm.values()))
    return node_comm, n_comms


def _community_shares(node_comm, n_nodes, n_comms):
    """Fraction of nodes in each community (vector of length n_comms)."""
    counts = np.zeros(n_comms)
    for c in node_comm.values():
        if c < n_comms:
            counts[c] += 1
    total = counts.sum()
    return counts / total if total > 0 else counts


def _js_divergence(p, q):
    """Jensen-Shannon divergence between two probability vectors."""
    p = np.asarray(p, dtype=float)
    q = np.asarray(q, dtype=float)
    # Pad shorter vector with zeros
    n = max(len(p), len(q))
    p = np.pad(p, (0, n - len(p)))
    q = np.pad(q, (0, n - len(q)))
    m = 0.5 * (p + q)

    # Use clipping to avoid log(0)
    def _kl(a, b):
        mask = (a > 0) & (b > 0)
        return np.sum(a[mask] * np.log2(a[mask] / b[mask]))

    return 0.5 * _kl(p, m) + 0.5 * _kl(q, m)


def _draw_graph(ax, G, node_comm, n_comms, title, seed):
    """Draw force-directed graph coloured by community."""
    pos = nx.spring_layout(G.to_undirected(), seed=seed, k=0.6)

    # Map detected community indices → display colours (cycle if >3)
    comm_color_map = {c: _COMM_COLORS[c % len(_COMM_COLORS)] for c in range(n_comms)}
    node_colors = [comm_color_map[node_comm[n]] for n in G.nodes()]

    nx.draw_networkx_nodes(
        G,
        pos,
        ax=ax,
        node_color=node_colors,
        node_size=140,
        alpha=0.9,
    )
    nx.draw_networkx_edges(
        G,
        pos,
        ax=ax,
        edge_color=LIGHT,
        arrows=True,
        arrowstyle="-|>",
        arrowsize=8,
        width=0.5,
        alpha=0.6,
    )
    ax.set_title(title, fontsize=8, color=DARK)
    ax.axis("off")


def _draw_stacked_bar(ax, shares, n_comms, title):
    """Draw a stacked bar showing community shares."""
    bottom = 0.0
    for k in range(n_comms):
        s = shares[k] if k < len(shares) else 0.0
        color = _COMM_COLORS[k % len(_COMM_COLORS)]
        ax.bar(
            0,
            s,
            bottom=bottom,
            width=0.6,
            color=color,
            alpha=0.85,
            zorder=2,
        )
        if s > 0.06:
            ax.text(
                0,
                bottom + s / 2,
                f"Comm {_COMM_LABELS[k % len(_COMM_LABELS)]}\n{s:.0%}",
                ha="center",
                va="center",
                fontsize=6,
                color="white",
                fontweight="bold",
            )
        bottom += s
    ax.set_xlim(-0.5, 0.5)
    ax.set_ylim(0, 1)
    ax.set_title(title, fontsize=7.5, color=DARK)
    ax.set_xticks([])
    ax.set_ylabel("Share of nodes", fontsize=7)
    ax.yaxis.set_tick_params(labelsize=6)


def main():
    io_args, _ = parse_io_args()
    validate_io(output=io_args.output)

    # --- Build synthetic graphs ---
    # "Before": three roughly equal communities (stable, balanced structure)
    sizes_before = [7, 6, 7]
    G_before, _ = _make_sbm_graph(sizes_before, p_in=0.45, p_out=0.05, seed=_SEED)

    # "After": community membership shifts — community B absorbs part of C
    # (simulate reorg by changing block sizes)
    sizes_after = [6, 11, 3]
    G_after, _ = _make_sbm_graph(sizes_after, p_in=0.50, p_out=0.04, seed=_SEED + 7)

    # Detect communities
    node_comm_b, n_comms_b = _detect_communities(G_before, seed=_SEED)
    node_comm_a, n_comms_a = _detect_communities(G_after, seed=_SEED)
    n_comms = max(n_comms_b, n_comms_a, 3)

    shares_before = _community_shares(node_comm_b, len(G_before), n_comms)
    shares_after = _community_shares(node_comm_a, len(G_after), n_comms)
    js = _js_divergence(shares_before, shares_after)
    log.info(
        "shares_before=%s, shares_after=%s, JS=%.4f",
        np.round(shares_before, 3),
        np.round(shares_after, 3),
        js,
    )

    # --- Figure layout ---
    # Row 0: two graphs | Row 1: two stacked bars + JS arrow
    fig = plt.figure(figsize=(FIGWIDTH, 4.4))
    gs = fig.add_gridspec(
        2,
        5,
        height_ratios=[2.2, 1.4],
        width_ratios=[4, 0.5, 1, 0.5, 4],
        hspace=0.15,
        wspace=0.05,
    )

    ax_gb = fig.add_subplot(gs[0, 0])  # graph before
    ax_ga = fig.add_subplot(gs[0, 4])  # graph after
    ax_bb = fig.add_subplot(gs[1, 0])  # bar before
    ax_arr = fig.add_subplot(gs[1, 1:4])  # arrow + JS label
    ax_ba = fig.add_subplot(gs[1, 4])  # bar after

    # Graphs
    _draw_graph(
        ax_gb,
        G_before,
        node_comm_b,
        n_comms,
        f"Before 2007\n({len(G_before)} nodes)",
        seed=_SEED,
    )
    _draw_graph(
        ax_ga,
        G_after,
        node_comm_a,
        n_comms,
        f"After 2007\n({len(G_after)} nodes)",
        seed=_SEED + 7,
    )

    # Stacked bars
    _draw_stacked_bar(ax_bb, shares_before, n_comms, "Community shares\nbefore")
    _draw_stacked_bar(ax_ba, shares_after, n_comms, "Community shares\nafter")

    # Arrow + JS annotation
    ax_arr.axis("off")
    ax_arr.annotate(
        "",
        xy=(0.85, 0.5),
        xycoords="axes fraction",
        xytext=(0.15, 0.5),
        textcoords="axes fraction",
        arrowprops=dict(arrowstyle="<->", color=DARK, lw=1.4),
    )
    ax_arr.text(
        0.5,
        0.55,
        f"JS = {js:.3f}",
        ha="center",
        va="bottom",
        fontsize=7.5,
        color=DARK,
        transform=ax_arr.transAxes,
        fontweight="bold",
    )
    ax_arr.text(
        0.5,
        0.30,
        "G9",
        ha="center",
        va="top",
        fontsize=9,
        color=DARK,
        transform=ax_arr.transAxes,
    )

    # Formula box
    formula = (
        r"$G9 = JS(q_{before},\, q_{after})$" + "\n"
        r"$q_k$ = fraction of nodes in community $k$"
    )
    fig.text(
        0.5,
        0.005,
        formula,
        ha="center",
        va="bottom",
        fontsize=6.5,
        color=DARK,
        bbox=dict(boxstyle="round,pad=0.3", fc="#F5F5F5", ec=LIGHT, lw=0.5),
    )

    fig.suptitle(
        "Community Divergence: did citation clusters reorganise?",
        fontsize=8.5,
        color=DARK,
        y=0.995,
    )
    fig.text(
        0.5,
        0.955,
        "JS between community-share vectors — before vs. after window.  [synthetic data]",
        ha="center",
        va="top",
        fontsize=6.5,
        color=MED,
        style="italic",
    )

    fig.tight_layout(rect=[0, 0.08, 1, 0.95], w_pad=0.2, h_pad=0.5)

    stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, stem, dpi=DPI)
    plt.close(fig)
    log.info("Saved → %s.png", stem)


if __name__ == "__main__":
    sys.exit(main())
