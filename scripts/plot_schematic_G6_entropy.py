"""ELI15 schematic: Citation Degree Entropy Divergence (G6).

Shows how the Shannon entropy of the in-degree distribution changed between two
windows around 2007. Low entropy means a few hub papers hoard most citations;
high entropy means citations are spread across many papers.

Uses real citation data when available; falls back to synthetic data otherwise.

Usage::

    uv run python scripts/plot_schematic_G6_entropy.py \\
        --output /tmp/test_G6.png
"""

import os
import sys

import matplotlib.pyplot as plt
import numpy as np
from pipeline_io import save_figure
from plot_style import DARK, DPI, FIGWIDTH, LIGHT, MED, apply_style
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("plot_schematic_G6_entropy")
apply_style()

# Schematic uses fixed windows — display choices, not research params
WINDOW_BEFORE = (2000, 2004)
WINDOW_AFTER = (2007, 2011)
# Tail bin: degrees >= this are lumped as "6+"
TAIL_BIN = 6


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


def _indegree_degrees(works, internal_edges, year_lo, year_hi):
    """Return array of in-degrees for papers published in [year_lo, year_hi]."""
    window_dois = set(works.loc[works["year"].between(year_lo, year_hi), "doi"].values)
    edge_mask = internal_edges["source_year"].between(year_lo, year_hi)
    edges = internal_edges.loc[edge_mask]

    in_deg = {doi: 0 for doi in window_dois}
    for ref in edges["ref_doi"]:
        if ref in in_deg:
            in_deg[ref] += 1

    return np.array(list(in_deg.values()), dtype=int)


def _degree_bars(degrees):
    """Compute bar heights for k = 0, 1, …, TAIL_BIN-1, TAIL_BIN+ as fractions."""
    n = len(degrees)
    bars = np.zeros(TAIL_BIN + 1)  # indices 0..TAIL_BIN; last = "TAIL_BIN+"
    for d in degrees:
        idx = min(d, TAIL_BIN)
        bars[idx] += 1
    bars = bars / n  # normalise to fractions
    return bars


def _shannon_entropy(fracs):
    """Shannon entropy in bits from an array of probabilities (ignoring zeros)."""
    p = fracs[fracs > 0]
    return float(-np.sum(p * np.log2(p)))


def _synthetic_degrees(n_papers, gamma, rng):
    """Draw in-degrees from a power-law-like distribution."""
    min_k = 1
    max_k = n_papers // 4
    ks = np.arange(min_k, max_k + 1, dtype=float)
    weights = ks ** (-gamma)
    weights /= weights.sum()
    counts_pop = (weights * n_papers * 0.4).astype(int)
    counts_pop = np.maximum(counts_pop, 1)
    cited = np.repeat(ks.astype(int), counts_pop)
    n_zeros = max(0, n_papers - len(cited))
    degrees = np.concatenate([np.zeros(n_zeros, dtype=int), cited])
    return degrees[:n_papers]


def main():
    io_args, _ = parse_io_args()
    validate_io(output=io_args.output)

    # --- Load data ---
    using_real = False
    try:
        works, internal_edges = _load_real_data()
        degrees_before = _indegree_degrees(works, internal_edges, *WINDOW_BEFORE)
        degrees_after = _indegree_degrees(works, internal_edges, *WINDOW_AFTER)
        using_real = True
        log.info("Loaded real citation data.")
    except FileNotFoundError as exc:
        log.warning("Real data unavailable (%s) — using synthetic data.", exc)

    if not using_real:
        # Synthetic: "before" is more uniform (smaller γ), "after" is more concentrated
        # Fixed seed — schematic only, not a research parameter
        rng = np.random.default_rng(42)
        degrees_before = _synthetic_degrees(1200, gamma=1.8, rng=rng)
        degrees_after = _synthetic_degrees(1200, gamma=2.6, rng=rng)

    bars_before = _degree_bars(degrees_before)
    bars_after = _degree_bars(degrees_after)
    H_before = _shannon_entropy(bars_before)
    H_after = _shannon_entropy(bars_after)
    G6 = abs(H_after - H_before)
    log.info("H_before=%.3f bits, H_after=%.3f bits, G6=%.3f", H_before, H_after, G6)

    # --- Figure ---
    fig, (ax_b, ax_mid, ax_a) = plt.subplots(
        1,
        3,
        figsize=(FIGWIDTH, 3.6),
        gridspec_kw={"width_ratios": [5, 1, 5]},
    )

    x_labels = [str(k) for k in range(TAIL_BIN)] + [f"{TAIL_BIN}+"]
    x = np.arange(len(x_labels))

    y_max = max(bars_before.max(), bars_after.max()) * 1.18

    # Left bar chart — before
    ax_b.bar(x, bars_before, color="#4477AA", width=0.7, alpha=0.85, zorder=2)
    ax_b.set_xticks(x)
    ax_b.set_xticklabels(x_labels, fontsize=7)
    ax_b.set_ylim(0, y_max)
    ax_b.set_xlabel("In-degree $k$", fontsize=7)
    ax_b.set_ylabel("Fraction of papers", fontsize=7)
    ax_b.set_title(
        f"Before\n{WINDOW_BEFORE[0]}–{WINDOW_BEFORE[1]}", fontsize=8, color="#4477AA"
    )
    ax_b.text(
        0.95,
        0.95,
        f"$H$ = {H_before:.2f} bits",
        transform=ax_b.transAxes,
        ha="right",
        va="top",
        fontsize=7.5,
        color="#4477AA",
        bbox=dict(boxstyle="round,pad=0.2", fc="#EEF3FA", ec="#4477AA", lw=0.5),
    )

    # Right bar chart — after
    ax_a.bar(x, bars_after, color="#CC4444", width=0.7, alpha=0.85, zorder=2)
    ax_a.set_xticks(x)
    ax_a.set_xticklabels(x_labels, fontsize=7)
    ax_a.set_ylim(0, y_max)
    ax_a.set_xlabel("In-degree $k$", fontsize=7)
    ax_a.set_ylabel("")
    ax_a.yaxis.set_ticklabels([])
    ax_a.set_title(
        f"After\n{WINDOW_AFTER[0]}–{WINDOW_AFTER[1]}", fontsize=8, color="#CC4444"
    )
    ax_a.text(
        0.95,
        0.95,
        f"$H$ = {H_after:.2f} bits",
        transform=ax_a.transAxes,
        ha="right",
        va="top",
        fontsize=7.5,
        color="#CC4444",
        bbox=dict(boxstyle="round,pad=0.2", fc="#FAEEEE", ec="#CC4444", lw=0.5),
    )

    # Middle column: G6 arrow + formula
    ax_mid.axis("off")
    ax_mid.annotate(
        "",
        xy=(0.5, 0.62),
        xycoords="axes fraction",
        xytext=(0.5, 0.38),
        textcoords="axes fraction",
        arrowprops=dict(arrowstyle="<->", color=DARK, lw=1.2),
    )
    ax_mid.text(
        0.5,
        0.50,
        f"$G6$\n= {G6:.2f}",
        ha="center",
        va="center",
        fontsize=7,
        color=DARK,
        transform=ax_mid.transAxes,
    )

    # Formula box at bottom of the middle column
    formula = (
        r"$H = -\sum p_k \log_2 p_k$" + "\n"
        r"$G6 = |H_{after} - H_{before}|$"
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

    # Overall title and subtitle
    src = "synthetic" if not using_real else "real corpus"
    fig.suptitle(
        "Entropy Divergence: did citations become more (or less) concentrated?",
        fontsize=8.5,
        color=DARK,
        y=0.99,
    )
    fig.text(
        0.5,
        0.93,
        "Low entropy = a few mega-hubs; high entropy = spread across many papers."
        f"  G6 peaks at 2007 — citation concentration changed.  [{src} data]",
        ha="center",
        va="top",
        fontsize=6.5,
        color=MED,
        style="italic",
    )

    fig.tight_layout(rect=[0, 0.09, 1, 0.92])

    stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, stem, dpi=DPI)
    plt.close(fig)
    log.info("Saved → %s.png", stem)


if __name__ == "__main__":
    sys.exit(main())
