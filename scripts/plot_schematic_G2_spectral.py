"""ELI15 schematic: Spectral Gap (G2).

Shows the eigengap heuristic for the normalised graph Laplacian in two
citation-network windows (before / after 2007).  The position of the
largest gap between consecutive eigenvalues indicates the number of
natural communities (Von Luxburg 2007, Fig. 4).

Usage::

    uv run python scripts/plot_schematic_G2_spectral.py \\
        --output /tmp/test_G2.png
"""

import os
import sys

import matplotlib.pyplot as plt
import numpy as np
from pipeline_io import save_figure
from plot_style import DARK, DPI, FIGWIDTH, FILL, LIGHT, MED, apply_style
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("plot_schematic_G2_spectral")
apply_style()

# Schematic windows — display choices, not research params
WINDOW_BEFORE = (2000, 2004)
WINDOW_AFTER = (2007, 2011)

# Synthetic fallback eigenvalues (spec-defined)
SYNTHETIC_BEFORE = [0, 0, 0.01, 0.8, 0.9, 1.0, 1.1, 1.1, 1.2, 1.3]
SYNTHETIC_AFTER = [0, 0.01, 0.7, 0.8, 0.9, 1.0, 1.1, 1.2, 1.3, 1.4]


def _build_adjacency(works, internal_edges, year_lo, year_hi):
    """Build a sparse adjacency matrix for papers published in [year_lo, year_hi]."""
    import scipy.sparse as sp

    window_dois = list(
        works.loc[works["year"].between(year_lo, year_hi), "doi"].dropna().unique()
    )
    doi_idx = {doi: i for i, doi in enumerate(window_dois)}
    n = len(window_dois)
    if n < 20:
        raise ValueError(f"Too few nodes ({n}) in window {year_lo}-{year_hi}")

    edge_mask = internal_edges["source_year"].between(year_lo, year_hi)
    edges = internal_edges.loc[edge_mask]

    rows, cols = [], []
    for _, row in edges.iterrows():
        s, r = row["source_doi"], row["ref_doi"]
        if s in doi_idx and r in doi_idx:
            rows.append(doi_idx[s])
            cols.append(doi_idx[r])
            rows.append(doi_idx[r])  # symmetrise
            cols.append(doi_idx[s])

    data = np.ones(len(rows), dtype=np.float32)
    A = sp.csr_matrix((data, (rows, cols)), shape=(n, n))
    return A


def _smallest_eigenvalues(A, k=10):
    """Return the k smallest eigenvalues of the normalised Laplacian."""
    import scipy.sparse.csgraph as csgraph

    # Extract largest connected component
    n_comp, labels = csgraph.connected_components(A, directed=False)
    if n_comp > 1:
        largest = np.bincount(labels).argmax()
        mask = labels == largest
        A = A[mask][:, mask]
        log.info("Restricted to largest component: %d nodes", A.shape[0])

    L = csgraph.laplacian(A, normed=True)
    n = L.shape[0]

    if n <= k + 2:
        raise ValueError(f"Graph too small ({n} nodes) for {k} eigenvalues")

    try:
        # Shift-invert mode: fast for smallest eigenvalues
        from scipy.sparse.linalg import eigsh

        vals, _ = eigsh(L, k=k, sigma=0.0, which="LM")
        return np.sort(np.real(vals))
    except Exception as exc:
        log.warning("eigsh failed (%s) — falling back to dense solver", exc)
        L_dense = L.toarray() if hasattr(L, "toarray") else np.array(L)
        vals = np.linalg.eigvalsh(L_dense)
        return vals[:k]


def _load_real_eigenvalues():
    """Attempt to load real data and compute eigenvalues; raise on any failure."""
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

    A_before = _build_adjacency(works, internal, *WINDOW_BEFORE)
    A_after = _build_adjacency(works, internal, *WINDOW_AFTER)

    eigs_before = _smallest_eigenvalues(A_before)
    eigs_after = _smallest_eigenvalues(A_after)
    return eigs_before, eigs_after


def _eigengap_index(eigs):
    """Return (gap_index, gap_size) for the largest gap between consecutive eigs."""
    gaps = np.diff(eigs)
    idx = int(np.argmax(gaps))  # 0-based gap index → cluster count = idx+1
    return idx, float(gaps[idx])


def _draw_panel(ax, eigs, label, color, window_label):
    """Draw eigenvalue scatter and shade the eigengap."""
    indices = np.arange(1, len(eigs) + 1)
    gap_idx, gap_size = _eigengap_index(eigs)
    k_clusters = gap_idx + 1  # number of near-zero eigenvalues

    # Bar chart
    ax.bar(indices, eigs, color=color, alpha=0.6, width=0.55, zorder=2)
    ax.scatter(indices, eigs, color=color, s=28, zorder=3)

    # Shade eigengap region
    ax.axvspan(
        gap_idx + 1.5, gap_idx + 2.5, color=FILL, alpha=0.9, zorder=1, label="eigengap"
    )

    # Horizontal bracket at the gap
    y_mid = (eigs[gap_idx] + eigs[gap_idx + 1]) / 2
    ax.annotate(
        "",
        xy=(gap_idx + 2, eigs[gap_idx + 1]),
        xytext=(gap_idx + 2, eigs[gap_idx]),
        arrowprops=dict(arrowstyle="<->", color=DARK, lw=0.8),
    )
    ax.text(
        gap_idx + 2.25,
        y_mid,
        f"eigengap\nat k = {k_clusters}",
        va="center",
        ha="left",
        fontsize=6,
        color=DARK,
    )

    ax.set_xlabel("Eigenvalue index", fontsize=7)
    ax.set_ylabel(r"$\lambda_i$  (Laplacian eigenvalue)", fontsize=7)
    ax.set_xticks(indices)
    ax.set_title(
        f"{window_label[0]}–{window_label[1]}\n({label})",
        fontsize=7.5,
        color=DARK,
        pad=3,
    )
    ax.set_xlim(0.3, len(eigs) + 1.0)
    ax.set_ylim(-0.05, max(eigs) * 1.15)
    return k_clusters, gap_size


def main():
    io_args, _ = parse_io_args()
    validate_io(output=io_args.output)

    using_real = False
    try:
        eigs_before, eigs_after = _load_real_eigenvalues()
        using_real = True
        log.info("Loaded real citation data for spectral computation.")
    except Exception as exc:
        log.warning("Real data unavailable (%s) — using synthetic eigenvalues.", exc)
        eigs_before = np.array(SYNTHETIC_BEFORE, dtype=float)
        eigs_after = np.array(SYNTHETIC_AFTER, dtype=float)

    gap_before_idx, gap_before_size = _eigengap_index(eigs_before)
    gap_after_idx, gap_after_size = _eigengap_index(eigs_after)
    g2 = abs(gap_after_size - gap_before_size)
    log.info(
        "eigengap before: k=%d (gap=%.3f), after: k=%d (gap=%.3f), G2=%.3f",
        gap_before_idx + 1,
        gap_before_size,
        gap_after_idx + 1,
        gap_after_size,
        g2,
    )

    fig, (ax_b, ax_a) = plt.subplots(1, 2, figsize=(FIGWIDTH, 3.0), sharey=False)
    plt.subplots_adjust(left=0.10, right=0.97, top=0.85, bottom=0.18, wspace=0.38)

    _draw_panel(ax_b, eigs_before, "before", "#4477AA", WINDOW_BEFORE)
    _draw_panel(ax_a, eigs_after, "after", "#CC4444", WINDOW_AFTER)

    # G2 formula box
    src = "synthetic" if not using_real else "real corpus"
    fig.text(
        0.5,
        0.01,
        rf"$G2 = |gap_{{after}} - gap_{{before}}| = {g2:.3f}$"
        f"   [{src} data]",
        ha="center",
        va="bottom",
        fontsize=6.5,
        color=DARK,
        bbox=dict(boxstyle="round,pad=0.3", fc="#F5F5F5", ec=LIGHT, lw=0.5),
    )

    fig.suptitle(
        "Spectral Gap: how many clusters does the citation network have?",
        fontsize=8,
        color=DARK,
        y=0.98,
    )
    fig.text(
        0.5,
        0.93,
        "Eigengap at index k → k natural communities (Von Luxburg 2007, Fig. 4)",
        ha="center",
        va="top",
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
