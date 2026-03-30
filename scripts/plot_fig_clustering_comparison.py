"""Fig: clustering method comparison — ARI heatmaps and silhouette curves.

Reads:  content/tables/tab_clustering_ari.csv
        content/tables/tab_clustering_perturbation.csv
        content/tables/clustering_optimal_k.json
Writes: content/figures/fig_clustering_ari.png
        content/figures/fig_clustering_perturbation.png
        content/figures/fig_clustering_optimal_k.png
        (+.pdf variants with --pdf)

Three figures in one script because they share data from a single
comparison run (compare_clustering.py) and always appear together in
the technical report. Separated from compare_clustering.py so figures
can be regenerated without re-running the full comparison.

Run compare_clustering.py first to generate the input tables.
"""

import argparse
import json
import os

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from utils import BASE_DIR, get_logger

log = get_logger("plot_fig_clustering_comparison")

FIGURES_DIR = os.path.join(BASE_DIR, "content", "figures")
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")


def _save(fig, stem, pdf=False):
    """Save PNG always; PDF when pdf=True."""
    os.makedirs(FIGURES_DIR, exist_ok=True)
    png_path = os.path.join(FIGURES_DIR, f"{stem}.png")
    fig.savefig(png_path, dpi=150, bbox_inches="tight")
    log.info("Saved %s → %s", stem, png_path)
    if pdf:
        pdf_path = os.path.join(FIGURES_DIR, f"{stem}.pdf")
        fig.savefig(pdf_path, dpi=300, bbox_inches="tight")
        log.info("Saved %s → %s", stem, pdf_path)


def generate_figures(ari_table, perturbation_table, optimal_k, pdf=False):
    """Generate comparison figures for the technical report.

    Always produces PNG. Also saves PDF when pdf=True.

    Three figures:
    1. ARI heatmap (method × snapshot pair)
    2. Perturbation stability bar chart
    3. Silhouette scores + HDBSCAN sweep
    """
    # Figure 1: ARI heatmap (method × snapshot pair)
    if ari_table:
        df_ari = pd.DataFrame(ari_table)
        pivot = df_ari.pivot_table(
            index="method",
            columns=df_ari["snapshot_a"] + " → " + df_ari["snapshot_b"],
            values="ari",
        )
        fig, ax = plt.subplots(figsize=(8, 4))
        im = ax.imshow(pivot.values, cmap="RdYlGn", vmin=0, vmax=1, aspect="auto")
        ax.set_xticks(range(len(pivot.columns)))
        ax.set_xticklabels(pivot.columns, rotation=30, ha="right", fontsize=9)
        ax.set_yticks(range(len(pivot.index)))
        ax.set_yticklabels(pivot.index, fontsize=10)
        for i in range(len(pivot.index)):
            for j in range(len(pivot.columns)):
                val = pivot.values[i, j]
                if not np.isnan(val):
                    ax.text(j, i, f"{val:.2f}", ha="center", va="center",
                            fontsize=11, fontweight="bold")
        plt.colorbar(im, ax=ax, label="Adjusted Rand Index")
        ax.set_title("Cross-snapshot clustering stability (ARI)")
        plt.tight_layout()
        _save(fig, "fig_clustering_ari", pdf=pdf)
        plt.close()

    # Figure 2: Perturbation stability bar chart
    if perturbation_table:
        df_pert = pd.DataFrame(perturbation_table)
        fig, ax = plt.subplots(figsize=(6, 4))
        x = range(len(df_pert))
        ax.bar(x, df_pert["mean_ari"], yerr=df_pert["std_ari"],
               capsize=5, color=["#2196F3", "#FF9800", "#4CAF50"][:len(df_pert)])
        ax.set_xticks(x)
        ax.set_xticklabels(df_pert["method"], fontsize=11)
        ax.set_ylabel("ARI (1% perturbation)")
        ax.set_ylim(0, 1.05)
        ax.set_title("Clustering stability under 1% random perturbation")
        for i, row in df_pert.iterrows():
            ax.text(i, row["mean_ari"] + row["std_ari"] + 0.02,
                    f"{row['mean_ari']:.3f}±{row['std_ari']:.3f}",
                    ha="center", fontsize=9)
        plt.tight_layout()
        _save(fig, "fig_clustering_perturbation", pdf=pdf)
        plt.close()

    # Figure 3: Silhouette scores + HDBSCAN sweep
    if optimal_k:
        fig, axes = plt.subplots(1, 2, figsize=(12, 5))

        # KMeans + Spectral silhouette
        ax = axes[0]
        for method_key, label, color in [
            ("kmeans_silhouette", "KMeans", "#2196F3"),
            ("spectral_silhouette", "Spectral", "#4CAF50"),
        ]:
            if method_key in optimal_k:
                data = optimal_k[method_key]
                ks = [r["k"] for r in data]
                scores = [r["silhouette"] for r in data]
                ax.plot(ks, scores, "o-", label=label, color=color, linewidth=2)
        ax.set_xlabel("Number of clusters (k)")
        ax.set_ylabel("Silhouette score")
        ax.set_title("Silhouette analysis")
        ax.legend()
        ax.grid(True, alpha=0.3)

        # HDBSCAN sweep
        ax = axes[1]
        if "hdbscan_sweep" in optimal_k:
            data = optimal_k["hdbscan_sweep"]
            sizes = [r["min_cluster_size"] for r in data]
            n_clusters = [r["n_clusters"] for r in data]
            noise = [r["noise_fraction"] * 100 for r in data]
            ax.plot(sizes, n_clusters, "o-", color="#FF9800", label="# clusters",
                    linewidth=2)
            ax2 = ax.twinx()
            ax2.plot(sizes, noise, "s--", color="#F44336", label="% noise",
                     linewidth=1.5, alpha=0.7)
            ax.set_xlabel("min_cluster_size")
            ax.set_ylabel("Number of clusters", color="#FF9800")
            ax2.set_ylabel("Noise fraction (%)", color="#F44336")
            ax.set_title("HDBSCAN parameter sensitivity")
            lines1, labels1 = ax.get_legend_handles_labels()
            lines2, labels2 = ax2.get_legend_handles_labels()
            ax.legend(lines1 + lines2, labels1 + labels2, loc="upper right")
            ax.grid(True, alpha=0.3)

        plt.tight_layout()
        _save(fig, "fig_clustering_optimal_k", pdf=pdf)
        plt.close()


def main():
    parser = argparse.ArgumentParser(
        description="Plot clustering comparison figures (ARI, perturbation, silhouette)"
    )
    parser.add_argument("--pdf", action="store_true",
                        help="Also save PDF")
    parser.add_argument(
        "--ari",
        default=os.path.join(TABLES_DIR, "tab_clustering_ari.csv"),
        help="Path to ARI table CSV",
    )
    parser.add_argument(
        "--perturbation",
        default=os.path.join(TABLES_DIR, "tab_clustering_perturbation.csv"),
        help="Path to perturbation stability CSV",
    )
    parser.add_argument(
        "--optimal-k",
        default=os.path.join(TABLES_DIR, "clustering_optimal_k.json"),
        help="Path to optimal-k JSON",
    )
    args = parser.parse_args()

    ari_table = None
    perturbation_table = None
    optimal_k = None

    if os.path.exists(args.ari):
        ari_table = pd.read_csv(args.ari).to_dict("records")
        log.info("Loaded ARI table: %d rows", len(ari_table))
    else:
        log.warning("ARI table not found: %s (skipping fig_clustering_ari)", args.ari)

    if os.path.exists(args.perturbation):
        perturbation_table = pd.read_csv(args.perturbation).to_dict("records")
        log.info("Loaded perturbation table: %d rows", len(perturbation_table))
    else:
        log.warning("Perturbation table not found: %s (skipping)", args.perturbation)

    if os.path.exists(args.optimal_k):
        with open(args.optimal_k) as f:
            optimal_k = json.load(f)
        log.info("Loaded optimal-k results")
    else:
        log.warning("Optimal-k JSON not found: %s (skipping)", args.optimal_k)

    if ari_table is None and perturbation_table is None and optimal_k is None:
        log.error("No input data found. Run compare_clustering.py first.")
        raise SystemExit(1)

    generate_figures(ari_table, perturbation_table, optimal_k, pdf=args.pdf)
    log.info("Done.")


if __name__ == "__main__":
    main()
