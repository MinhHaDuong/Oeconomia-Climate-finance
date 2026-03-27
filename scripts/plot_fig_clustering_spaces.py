"""Fig: multi-space silhouette comparison (semantic vs lexical vs citation).

Reads:  content/tables/clustering_multi_space.json
Writes: content/figures/fig_clustering_spaces.png (+ .pdf unless --no-pdf)

Bar chart comparing KMeans silhouette scores across three representation
spaces: semantic embeddings (1024D), lexical TF-IDF (→ 100D SVD), and
bibliographic coupling (→ 100D SVD). Used in technical report.

Run compare_clustering.py first to generate the input JSON.
"""

import argparse
import json
import os

import matplotlib.pyplot as plt
import numpy as np
from utils import BASE_DIR, get_logger

log = get_logger("plot_fig_clustering_spaces")

FIGURES_DIR = os.path.join(BASE_DIR, "content", "figures")
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")


def plot_multi_space_figure(space_results, no_pdf=False):
    """Bar chart comparing silhouette scores across representation spaces.

    Reads the multi-space silhouette results (semantic, lexical, citation)
    and produces a grouped bar chart showing silhouette at each k value.
    Output: fig_clustering_spaces.png (and .pdf unless no_pdf).
    """
    os.makedirs(FIGURES_DIR, exist_ok=True)

    if not space_results:
        log.warning("No multi-space results to plot")
        return

    fig, ax = plt.subplots(figsize=(10, 5))

    space_colors = {
        "semantic": "#2196F3",
        "lexical": "#FF9800",
        "citation": "#4CAF50",
    }
    space_labels = {
        "semantic": "Semantic (1024D embeddings)",
        "lexical": "Lexical (TF-IDF → 100D SVD)",
        "citation": "Citation (bib. coupling → 100D SVD)",
    }

    spaces = [s for s in ["semantic", "lexical", "citation"]
              if s in space_results]
    if not spaces:
        log.warning("No recognized spaces in results")
        return

    # All spaces share the same k values
    ks = [r["k"] for r in space_results[spaces[0]]]
    n_k = len(ks)
    n_spaces = len(spaces)
    bar_width = 0.8 / n_spaces
    x = np.arange(n_k)

    for i, space in enumerate(spaces):
        scores = [r["silhouette"] for r in space_results[space]]
        offset = (i - (n_spaces - 1) / 2) * bar_width
        ax.bar(x + offset, scores, bar_width, label=space_labels.get(space, space),
               color=space_colors.get(space, "#999999"), alpha=0.85)

    ax.set_xlabel("Number of clusters (k)", fontsize=11)
    ax.set_ylabel("Silhouette score", fontsize=11)
    ax.set_title("Silhouette scores across representation spaces (KMeans)")
    ax.set_xticks(x)
    ax.set_xticklabels(ks)
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3, axis="y")

    plt.tight_layout()
    png_path = os.path.join(FIGURES_DIR, "fig_clustering_spaces.png")
    fig.savefig(png_path, dpi=150, bbox_inches="tight")
    log.info("Saved multi-space figure → %s", png_path)
    if not no_pdf:
        pdf_path = os.path.join(FIGURES_DIR, "fig_clustering_spaces.pdf")
        fig.savefig(pdf_path, dpi=300, bbox_inches="tight")
        log.info("Saved multi-space figure → %s", pdf_path)
    plt.close()


def main():
    parser = argparse.ArgumentParser(
        description="Plot multi-space silhouette comparison figure"
    )
    parser.add_argument("--no-pdf", action="store_true",
                        help="Skip PDF generation (PNG only)")
    parser.add_argument(
        "--input",
        default=os.path.join(TABLES_DIR, "clustering_multi_space.json"),
        help="Path to clustering_multi_space.json (default: content/tables/)",
    )
    args = parser.parse_args()

    if not os.path.exists(args.input):
        log.error("Input file not found: %s", args.input)
        log.error("Run compare_clustering.py first to generate it.")
        raise SystemExit(1)

    with open(args.input) as f:
        space_results = json.load(f)

    plot_multi_space_figure(space_results, no_pdf=args.no_pdf)
    log.info("Done.")


if __name__ == "__main__":
    main()
