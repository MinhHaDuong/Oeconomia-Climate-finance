"""Schematic figure: PageRank Distribution Divergence.

Illustrates how JS divergence on PageRank histograms captures shifts in
citation authority between two time windows.

Uses real citation data: edges where the *source* paper was published in
2000–2004 (before) or 2005–2009 (after crystallisation).

An inset toy graph (5-node) illustrates the PageRank concept.

Usage::

    uv run python scripts/plot_schematic_G1_pagerank.py \\
        --output content/figures/schematic_G1_pagerank.png
"""

import os
import sys

import matplotlib.pyplot as plt
import networkx as nx
import numpy as np
from pipeline_io import save_figure
from pipeline_loaders import load_analysis_corpus, load_refined_citations
from plot_style import DARK, DPI, FIGWIDTH, FILL, LIGHT, MED, apply_style
from scipy.special import rel_entr
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("plot_schematic_G1_pagerank")
apply_style()

# --------------------------------------------------------------------------- #
# Configuration                                                                #
# --------------------------------------------------------------------------- #
BEFORE_YEARS = (2000, 2004)
AFTER_YEARS = (2005, 2009)
N_BINS = 30  # histogram bins (log-spaced)
ALPHA_PR = 0.85  # PageRank damping factor


def _build_graph(cit_df, works_df, year_range: tuple[int, int]) -> nx.DiGraph:
    """Build DiGraph for papers whose source is published in year_range."""
    lo, hi = year_range
    dois_in_range = set(
        works_df.loc[(works_df["year"] >= lo) & (works_df["year"] <= hi), "doi"]
        .dropna()
        .str.lower()
    )
    sub = cit_df[cit_df["source_doi"].str.lower().isin(dois_in_range)]
    G = nx.DiGraph()
    for _, row in sub.iterrows():
        src = str(row["source_doi"]).lower()
        tgt = str(row["ref_doi"]).lower() if row.get("ref_doi") else None
        if src and tgt and tgt != "nan":
            G.add_edge(src, tgt)
    log.info(
        "%d–%d graph: %d nodes, %d edges",
        lo,
        hi,
        G.number_of_nodes(),
        G.number_of_edges(),
    )
    return G


def _pagerank_array(G: nx.DiGraph) -> np.ndarray:
    if G.number_of_nodes() == 0:
        return np.array([])
    pr = nx.pagerank(G, alpha=ALPHA_PR, max_iter=200, tol=1e-6)
    return np.array(list(pr.values()))


def _js_hist(pr_a: np.ndarray, pr_b: np.ndarray, n_bins: int = N_BINS):
    """Compute JS divergence between two PageRank distributions via histograms."""
    if len(pr_a) == 0 or len(pr_b) == 0:
        return np.array([]), np.array([]), np.array([]), 0.0

    combined = np.concatenate([pr_a, pr_b])
    lo = combined.min()
    hi = combined.max()
    eps = 1e-12
    bins = np.linspace(np.log10(lo + eps), np.log10(hi + eps), n_bins + 1)
    bins = 10**bins

    h_a, _ = np.histogram(pr_a, bins=bins, density=False)
    h_b, _ = np.histogram(pr_b, bins=bins, density=False)

    # Normalise
    p = h_a / h_a.sum() if h_a.sum() > 0 else h_a.astype(float)
    q = h_b / h_b.sum() if h_b.sum() > 0 else h_b.astype(float)
    m = 0.5 * (p + q)

    kl_pm = np.sum(rel_entr(p, np.where(m > 0, m, 1)))
    kl_qm = np.sum(rel_entr(q, np.where(m > 0, m, 1)))
    js = 0.5 * (kl_pm + kl_qm)

    bin_centres = 0.5 * (bins[:-1] + bins[1:])
    return bin_centres, p, q, float(js)


def _draw_toy_graph(ax):
    """Draw a 5-node toy citation graph illustrating PageRank in an inset."""
    G = nx.DiGraph()
    # Hub H receives citations from many nodes; hub gets high PR
    edges = [
        ("A", "H"),
        ("B", "H"),
        ("C", "H"),
        ("D", "H"),
        ("A", "B"),
        ("B", "C"),
    ]
    G.add_edges_from(edges)
    pr = nx.pagerank(G, alpha=0.85)

    pos = {
        "H": (0.5, 0.5),
        "A": (0.1, 0.85),
        "B": (0.1, 0.15),
        "C": (0.5, 0.05),
        "D": (0.9, 0.5),
    }
    node_sizes = [pr[n] * 8000 for n in G.nodes()]
    node_colors = [DARK if n == "H" else LIGHT for n in G.nodes()]

    nx.draw_networkx_edges(
        G,
        pos,
        ax=ax,
        edge_color=MED,
        arrows=True,
        arrowsize=8,
        arrowstyle="-|>",
        width=0.6,
        connectionstyle="arc3,rad=0.1",
    )
    nx.draw_networkx_nodes(
        G,
        pos,
        ax=ax,
        node_size=node_sizes,
        node_color=node_colors,
        alpha=0.85,
    )
    nx.draw_networkx_labels(
        G,
        pos,
        ax=ax,
        labels={n: n for n in G.nodes()},
        font_size=6,
        font_color="white" if True else DARK,
    )
    ax.set_title(
        "PageRank:\nH cited by all\n→ highest PR", fontsize=5.5, color=DARK, pad=2
    )
    ax.axis("off")


def main() -> None:
    io_args, _extra = parse_io_args()
    validate_io(output=io_args.output)

    log.info("Loading corpus …")
    df, _ = load_analysis_corpus(with_embeddings=False)
    cit_df = load_refined_citations()

    G_before = _build_graph(cit_df, df, BEFORE_YEARS)
    G_after = _build_graph(cit_df, df, AFTER_YEARS)

    pr_before = _pagerank_array(G_before)
    pr_after = _pagerank_array(G_after)

    bin_centres, p_hist, q_hist, js = _js_hist(pr_before, pr_after)

    log.info(
        "PageRank arrays: before=%d nodes, after=%d nodes",
        len(pr_before),
        len(pr_after),
    )
    log.info("JS divergence on PR histograms: %.4f", js)

    # --------------------------------------------------------------------- #
    # Plot                                                                   #
    # --------------------------------------------------------------------- #
    fig = plt.figure(figsize=(FIGWIDTH, 3.4))

    # Main axes (log-log histogram)
    ax_main = fig.add_axes([0.12, 0.18, 0.72, 0.70])

    if len(bin_centres) > 0:
        ax_main.fill_between(
            bin_centres,
            p_hist,
            alpha=0.45,
            color="#4477AA",
            step="mid",
            label=f"Before ({BEFORE_YEARS[0]}–{BEFORE_YEARS[1]})",
        )
        ax_main.fill_between(
            bin_centres,
            q_hist,
            alpha=0.45,
            color="#CC4444",
            step="mid",
            label=f"After ({AFTER_YEARS[0]}–{AFTER_YEARS[1]})",
        )
        ax_main.step(bin_centres, p_hist, color="#4477AA", lw=0.8, where="mid")
        ax_main.step(bin_centres, q_hist, color="#CC4444", lw=0.8, where="mid")

        ax_main.set_xscale("log")

        # Shade area of disagreement (where distributions differ most)
        p_arr = np.array(p_hist)
        q_arr = np.array(q_hist)
        disagreement = np.abs(p_arr - q_arr)
        top3 = np.argsort(disagreement)[-3:]
        for i in top3:
            ax_main.axvspan(
                bin_centres[i] * 0.85,
                bin_centres[i] * 1.15,
                color=FILL,
                alpha=0.6,
                zorder=0,
            )

        ax_main.set_xlabel("PageRank score (log scale)")
        ax_main.set_ylabel("Fraction of nodes")

    ax_main.set_title(
        "PageRank Divergence: do citations point to different authorities?",
        fontsize=9,
        color=DARK,
    )
    ax_main.legend(
        loc="upper right",
        fontsize=6.5,
        frameon=True,
        framealpha=0.9,
        edgecolor=LIGHT,
        title=f"G1 = JS(hist(PR_before), hist(PR_after)) = {js:.3f}",
        title_fontsize=6.5,
    )
    ax_main.text(
        0.01,
        0.99,
        "Shaded bands: JS = ½KL(P‖M) + ½KL(Q‖M)",
        transform=ax_main.transAxes,
        ha="left",
        va="top",
        fontsize=6,
        color=MED,
        style="italic",
    )

    # Inset: toy graph
    ax_inset = fig.add_axes([0.82, 0.45, 0.16, 0.45])
    _draw_toy_graph(ax_inset)

    stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, stem, dpi=DPI)
    plt.close(fig)
    log.info("Saved schematic_G1_pagerank to %s.png", stem)


if __name__ == "__main__":
    sys.exit(main())
