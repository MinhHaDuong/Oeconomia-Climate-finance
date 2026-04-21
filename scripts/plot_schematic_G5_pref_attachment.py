"""ELI15 schematic: Preferential Attachment Exponent Divergence (G5).

Shows how the power-law exponent of the in-degree distribution changed between
two windows around 2007. A steeper log-log slope (larger γ) means citations
concentrate more heavily on a small number of hub papers.

Uses real citation data when available; falls back to synthetic data otherwise.

Usage::

    uv run python scripts/plot_schematic_G5_pref_attachment.py \\
        --output /tmp/test_G5.png
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

log = get_logger("plot_schematic_G5_pref_attachment")
apply_style()

# Schematic uses fixed windows — these are display choices, not research params
WINDOW_BEFORE = (2000, 2004)
WINDOW_AFTER = (2007, 2011)


def _load_real_data():
    """Load real citation data; raise FileNotFoundError if unavailable."""
    from pipeline_loaders import load_analysis_corpus, load_refined_citations

    works, _ = load_analysis_corpus(with_embeddings=False)
    citations = load_refined_citations()
    works = works.dropna(subset=["doi"]).copy()

    corpus_dois = set(works["doi"].values)
    doi_to_year = dict(zip(works["doi"], works["year"]))

    mask = citations["source_doi"].isin(corpus_dois) & citations["ref_doi"].isin(
        corpus_dois
    )
    internal = citations.loc[mask, ["source_doi", "ref_doi"]].copy()
    internal["source_year"] = internal["source_doi"].map(doi_to_year)
    return works, internal


def _indegree_distribution(works, internal_edges, year_lo, year_hi):
    """Compute in-degree for papers published in [year_lo, year_hi].

    A paper's in-degree = citations received from papers also in the window.
    """
    window_dois = set(works.loc[works["year"].between(year_lo, year_hi), "doi"].values)
    edge_mask = internal_edges["source_year"].between(year_lo, year_hi)
    edges = internal_edges.loc[edge_mask]

    in_deg = {doi: 0 for doi in window_dois}
    for ref in edges["ref_doi"]:
        if ref in in_deg:
            in_deg[ref] += 1

    return np.array(list(in_deg.values()), dtype=int)


def _synthetic_indegree(n_papers, gamma, rng):
    """Draw in-degrees from a power-law distribution truncated at k>=0."""
    # Use Zipf-like: k ~ (u)^(-1/(gamma-1)) for u ~ Uniform
    min_k = 1
    max_k = n_papers // 4
    ks = np.arange(min_k, max_k + 1, dtype=float)
    weights = ks ** (-gamma)
    weights /= weights.sum()
    counts_pop = (weights * n_papers).astype(int)
    counts_pop = np.maximum(counts_pop, 1)
    degrees = np.repeat(ks.astype(int), counts_pop)
    # Pad zeros for papers with no citations
    n_zeros = max(0, n_papers - len(degrees))
    degrees = np.concatenate([np.zeros(n_zeros, dtype=int), degrees])
    return degrees[:n_papers]


def _powerlaw_fit(degrees):
    """Fit γ via OLS on log(count) ~ -γ log(k) + c for k >= 1.

    Returns (gamma, c, k_vals, count_vals) — only unique k values with count >= 1.
    """
    counts = np.bincount(degrees)
    k_vals = np.where(counts >= 1)[0]
    k_vals = k_vals[k_vals >= 1]  # exclude k=0
    count_vals = counts[k_vals]

    lk = np.log(k_vals.astype(float))
    lc = np.log(count_vals.astype(float))

    # OLS: lc = -gamma * lk + c
    A = np.column_stack([lk, np.ones(len(lk))])
    result, _, _, _ = np.linalg.lstsq(A, lc, rcond=None)
    gamma = -result[0]
    c = result[1]
    return float(gamma), float(c), k_vals, count_vals


def _draw_toy_network(ax):
    """Draw a tiny 'rich get richer' toy network as an inset illustration."""
    # Hub + spokes layout
    hub = np.array([0.5, 0.5])
    n_spokes = 6
    angles = np.linspace(0, 2 * np.pi, n_spokes, endpoint=False)
    spokes = np.column_stack(
        [
            0.5 + 0.38 * np.cos(angles),
            0.5 + 0.38 * np.sin(angles),
        ]
    )
    outlier = np.array([0.5 + 0.18, 0.5 - 0.18])

    # Draw edges from spokes to hub (citations point TO the hub)
    for s in spokes:
        ax.annotate(
            "",
            xy=hub,
            xytext=s,
            arrowprops=dict(arrowstyle="-|>", color=MED, lw=0.8, mutation_scale=7),
        )

    # Extra self-reinforcing arrow (outlier → hub)
    ax.annotate(
        "",
        xy=hub,
        xytext=outlier,
        arrowprops=dict(arrowstyle="-|>", color="#CC4444", lw=1.2, mutation_scale=9),
    )

    # Draw nodes (use facecolor/edgecolor to avoid matplotlib color override warning)
    for s in spokes:
        ax.add_patch(
            mpatches.Circle(
                s,
                0.055,
                facecolor=LIGHT,
                edgecolor=MED,
                linewidth=0.5,
                zorder=3,
            )
        )
    ax.add_patch(
        mpatches.Circle(
            hub,
            0.085,
            facecolor="#4477AA",
            edgecolor=DARK,
            linewidth=0.8,
            zorder=4,
        )
    )
    ax.add_patch(
        mpatches.Circle(
            outlier,
            0.05,
            facecolor=LIGHT,
            edgecolor=MED,
            linewidth=0.5,
            zorder=3,
        )
    )

    ax.text(
        0.5,
        0.5,
        "hub",
        ha="center",
        va="center",
        fontsize=5.5,
        color="white",
        fontweight="bold",
        zorder=5,
    )
    ax.text(
        0.5,
        0.05,
        "most-cited paper attracts more citations",
        ha="center",
        va="bottom",
        fontsize=4.5,
        color=DARK,
        style="italic",
    )

    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.set_aspect("equal")
    ax.axis("off")


def main():
    io_args, _ = parse_io_args()
    validate_io(output=io_args.output)

    # --- Load data ---
    using_real = False
    try:
        works, internal_edges = _load_real_data()
        degrees_before = _indegree_distribution(works, internal_edges, *WINDOW_BEFORE)
        degrees_after = _indegree_distribution(works, internal_edges, *WINDOW_AFTER)
        using_real = True
        log.info("Loaded real citation data.")
    except FileNotFoundError as exc:
        log.warning("Real data unavailable (%s) — using synthetic data.", exc)

    if not using_real:
        # Synthetic: before is flatter (smaller γ), after is steeper (larger γ)
        # Fixed seed — schematic only, not a research parameter
        rng = np.random.default_rng(42)
        degrees_before = _synthetic_indegree(1200, gamma=1.8, rng=rng)
        degrees_after = _synthetic_indegree(1200, gamma=2.4, rng=rng)

    # --- Fit power laws ---
    gamma_before, c_before, k_b, cnt_b = _powerlaw_fit(degrees_before)
    gamma_after, c_after, k_a, cnt_a = _powerlaw_fit(degrees_after)
    delta_gamma = abs(gamma_after - gamma_before)
    log.info(
        "γ_before=%.2f, γ_after=%.2f, Δγ=%.2f", gamma_before, gamma_after, delta_gamma
    )

    # --- Figure layout ---
    fig = plt.figure(figsize=(FIGWIDTH, 4.0))
    # Main axis (log-log scatter) and inset (toy network)
    ax = fig.add_axes([0.11, 0.15, 0.62, 0.72])
    ax_inset = fig.add_axes([0.76, 0.42, 0.22, 0.40])

    # --- Scatter: log-log in-degree distributions ---
    ax.scatter(
        k_b,
        cnt_b,
        marker="s",
        color="#4477AA",
        s=18,
        alpha=0.75,
        label=f"Before {WINDOW_BEFORE[0]}–{WINDOW_BEFORE[1]}",
        zorder=3,
    )
    ax.scatter(
        k_a,
        cnt_a,
        marker="o",
        color="#CC4444",
        s=18,
        alpha=0.75,
        label=f"After {WINDOW_AFTER[0]}–{WINDOW_AFTER[1]}",
        zorder=3,
    )

    # Fitted power-law lines
    k_range = np.array([1, max(k_b.max(), k_a.max())])
    ax.plot(
        k_range,
        np.exp(c_before) * k_range ** (-gamma_before),
        color="#4477AA",
        linewidth=1.2,
        linestyle="--",
        zorder=2,
    )
    ax.plot(
        k_range,
        np.exp(c_after) * k_range ** (-gamma_after),
        color="#CC4444",
        linewidth=1.2,
        linestyle="--",
        zorder=2,
    )

    # Slope annotations
    ax.text(
        0.97,
        0.70,
        rf"$\gamma_{{before}}$ = {gamma_before:.2f}",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=7,
        color="#4477AA",
    )
    ax.text(
        0.97,
        0.60,
        rf"$\gamma_{{after}}$ = {gamma_after:.2f}",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=7,
        color="#CC4444",
    )

    # ΔY annotation
    x_ann = ax.get_xlim()[1] * 0.55 if ax.get_xscale() == "linear" else 1.5
    ax.annotate(
        rf"$\Delta\gamma$ = {delta_gamma:.2f}",
        xy=(0.62, 0.47),
        xycoords="axes fraction",
        xytext=(0.62, 0.30),
        textcoords="axes fraction",
        fontsize=7,
        color=DARK,
        ha="center",
        arrowprops=dict(arrowstyle="-[", color=DARK, lw=0.8),
    )

    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlabel("In-degree  $k$  (citations received)", fontsize=8)
    ax.set_ylabel("Number of papers with in-degree $k$", fontsize=8)
    ax.legend(loc="upper right", frameon=False, fontsize=7)

    # Formula box
    ax.text(
        0.03,
        0.05,
        r"$G5 = |\gamma_{after} - \gamma_{before}|$" + "\n"
        r"$\gamma$ = power-law exponent  (log-log slope)",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=6.5,
        color=DARK,
        bbox=dict(boxstyle="round,pad=0.3", fc="#F5F5F5", ec=LIGHT, lw=0.5),
    )

    src = "synthetic" if not using_real else "real corpus"
    ax.set_title(
        "Preferential Attachment: did the citation hierarchy sharpen in 2007?",
        fontsize=8,
        color=DARK,
        pad=6,
    )
    fig.text(
        0.5,
        0.97,
        "A steeper log-log slope means more concentrated citation to a few hubs."
        f"  [{src} data]",
        ha="center",
        va="top",
        fontsize=6.5,
        color=MED,
        style="italic",
    )

    # --- Toy network inset ---
    _draw_toy_network(ax_inset)

    stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, stem, dpi=DPI)
    plt.close(fig)
    log.info("Saved → %s.png", stem)


if __name__ == "__main__":
    sys.exit(main())
