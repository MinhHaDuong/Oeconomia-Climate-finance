"""Clustering methods comparison: KMeans vs HDBSCAN vs Spectral.

Orchestrator script: loads corpus snapshots, runs comparison, saves tables,
delegates figure generation to dedicated plot_fig_*.py scripts.

Ticket: #299 (tracking), sub-issues #300–#304.

Three corpus snapshots:
- original: v1.0 submission data (v1_identifiers.txt.gz)
- v1_tagged: in_v1==1 subset of current corpus
- full: v1.1 full corpus

Evaluation:
- Stability: ARI between snapshots and under perturbation
- Optimal k: silhouette sweep (KMeans/Spectral), min_cluster_size sweep (HDBSCAN)
- Interpretability: cluster size distribution, noise fraction

Re-exports all algorithm functions from clustering_methods so tests that
import from compute_clustering_comparison continue to work after the split.
"""

import argparse
import json
import os
import warnings

import numpy as np
import pandas as pd

# Re-export algorithm functions so callers and tests don't need to change
from clustering_methods import (
    build_citation_space,
    build_tfidf_space,
    cluster_hdbscan,
    cluster_kmeans,
    cluster_spectral,
    compute_stability_ari,
    hdbscan_sweep,
    multi_space_silhouette,
    perturbation_stability,
    silhouette_sweep,
    spectral_eigengap,
)
from plot_fig_clustering_comparison import generate_figures
from plot_fig_clustering_spaces import plot_multi_space_figure
from utils import (
    BASE_DIR,
    get_logger,
    load_analysis_config,
    load_analysis_corpus,
)

log = get_logger("compute_clustering_comparison")

warnings.filterwarnings("ignore", category=FutureWarning)

TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
FIGURES_DIR = os.path.join(BASE_DIR, "content", "figures")
os.makedirs(TABLES_DIR, exist_ok=True)
os.makedirs(FIGURES_DIR, exist_ok=True)

V1_IDS_PATH = os.path.join(BASE_DIR, "config", "v1_identifiers.txt.gz")


# ============================================================
# Snapshot loading
# ============================================================


def load_snapshots():
    """Load the three corpus snapshots for comparison.

    Returns dict: {name: (embeddings, row_indices_in_full)} where
    row_indices allows mapping between snapshots.
    """
    import gzip

    df, embeddings = load_analysis_corpus(v1_only=False)
    log.info("Full corpus: %d works", len(df))

    # v1-tagged snapshot
    if "in_v1" not in df.columns:
        raise RuntimeError("in_v1 column missing — re-run corpus_filter.py")
    v1_mask = df["in_v1"] == 1
    v1_idx = np.where(v1_mask.values)[0]
    log.info("v1-tagged snapshot: %d works", len(v1_idx))

    # Original v1.0 snapshot (by DOI matching)
    if os.path.exists(V1_IDS_PATH):
        with gzip.open(V1_IDS_PATH, "rt") as f:
            v1_ids = {line.strip().lower() for line in f}
        doi_lower = df["doi"].fillna("").str.lower()
        orig_mask = doi_lower.isin(v1_ids)
        orig_idx = np.where(orig_mask.values)[0]
        log.info("Original v1.0 snapshot: %d / %d IDs matched",
                 len(orig_idx), len(v1_ids))
    else:
        log.warning("v1_identifiers.txt.gz not found, skipping original snapshot")
        orig_idx = None

    return {
        "full": (embeddings, np.arange(len(df))),
        "v1_tagged": (embeddings[v1_idx], v1_idx),
        "original": (embeddings[orig_idx], orig_idx) if orig_idx is not None else None,
    }


# ============================================================
# Main comparison
# ============================================================


def run_comparison(snapshots, k=6, do_perturbation=True, n_perturbation=10):
    """Run all methods on all snapshots and compute stability metrics."""
    methods = {
        "kmeans": lambda X: cluster_kmeans(X, k=k),
        "hdbscan": lambda X: cluster_hdbscan(X, min_cluster_size=50),
        "spectral": lambda X: cluster_spectral(X, k=k),
    }

    # Step 1: cluster each snapshot with each method
    results = {}
    for snap_name, snap_data in snapshots.items():
        if snap_data is None:
            continue
        X, idx = snap_data
        log.info("=== Snapshot: %s (%d works) ===", snap_name, len(X))
        for method_name, method_fn in methods.items():
            log.info("  Clustering with %s...", method_name)
            labels = method_fn(X)
            n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
            n_noise = int(np.sum(labels == -1)) if -1 in labels else 0
            log.info("    → %d clusters, %d noise points", n_clusters, n_noise)
            results[(snap_name, method_name)] = {
                "labels": labels,
                "indices": idx,
                "n_clusters": n_clusters,
                "n_noise": n_noise,
            }

    # Step 2: cross-snapshot ARI (on shared works)
    ari_table = []
    snapshot_pairs = [
        ("original", "v1_tagged"),
        ("original", "full"),
        ("v1_tagged", "full"),
    ]
    for snap_a, snap_b in snapshot_pairs:
        for method_name in methods:
            key_a = (snap_a, method_name)
            key_b = (snap_b, method_name)
            if key_a not in results or key_b not in results:
                continue
            ra = results[key_a]
            rb = results[key_b]
            # Find shared indices
            shared = np.intersect1d(ra["indices"], rb["indices"])
            if len(shared) < 10:
                continue
            # Map to label positions
            idx_map_a = {v: i for i, v in enumerate(ra["indices"])}
            idx_map_b = {v: i for i, v in enumerate(rb["indices"])}
            pos_a = [idx_map_a[s] for s in shared]
            pos_b = [idx_map_b[s] for s in shared]
            labels_a = ra["labels"][pos_a]
            labels_b = rb["labels"][pos_b]
            ari = compute_stability_ari(labels_a, labels_b)
            log.info("ARI(%s vs %s, %s): %.3f (n=%d shared)",
                     snap_a, snap_b, method_name, ari, len(shared))
            ari_table.append({
                "snapshot_a": snap_a,
                "snapshot_b": snap_b,
                "method": method_name,
                "ari": float(ari),
                "n_shared": len(shared),
            })

    # Step 3: perturbation stability on full corpus
    perturbation_table = []
    if do_perturbation:
        X_full = snapshots["full"][0]
        for method_name in methods:
            log.info("Perturbation stability: %s...", method_name)
            mean_ari, std_ari = perturbation_stability(
                X_full, method=method_name, k=k,
                drop_frac=0.01, n_repeats=n_perturbation,
            )
            log.info("  %s: ARI = %.3f ± %.3f", method_name, mean_ari, std_ari)
            perturbation_table.append({
                "method": method_name,
                "mean_ari": mean_ari,
                "std_ari": std_ari,
                "drop_frac": 0.01,
                "n_repeats": n_perturbation,
            })

    return results, ari_table, perturbation_table


def run_optimal_k(X, k_range=range(3, 13)):
    """Run optimal-k analysis for all methods."""
    log.info("=== Optimal k analysis ===")

    # KMeans silhouette sweep
    log.info("KMeans silhouette sweep (k=%d..%d)...", min(k_range), max(k_range))
    km_sil = silhouette_sweep(X, k_range=k_range)
    for r in km_sil:
        log.info("  k=%d: silhouette=%.3f", r["k"], r["silhouette"])

    # Spectral silhouette sweep
    log.info("Spectral silhouette sweep (k=%d..%d)...", min(k_range), max(k_range))
    sp_sil = spectral_eigengap(X, k_max=max(k_range))
    for r in sp_sil:
        log.info("  k=%d: silhouette=%.3f", r["k"], r["silhouette"])

    # HDBSCAN parameter sweep
    log.info("HDBSCAN min_cluster_size sweep...")
    hdb_sweep = hdbscan_sweep(X, sizes=[10, 20, 50, 100, 200, 500])
    for r in hdb_sweep:
        log.info("  min_cluster_size=%d: %d clusters, %.1f%% noise",
                 r["min_cluster_size"], r["n_clusters"],
                 r["noise_fraction"] * 100)

    return {
        "kmeans_silhouette": km_sil,
        "spectral_silhouette": sp_sil,
        "hdbscan_sweep": hdb_sweep,
    }


# ============================================================
# Output
# ============================================================


def save_results(ari_table, perturbation_table, optimal_k):
    """Save comparison results as CSV and JSON."""
    # ARI cross-snapshot table
    if ari_table:
        df_ari = pd.DataFrame(ari_table)
        path = os.path.join(TABLES_DIR, "tab_clustering_ari.csv")
        df_ari.to_csv(path, index=False)
        log.info("Saved ARI table → %s", path)

    # Perturbation stability table
    if perturbation_table:
        df_pert = pd.DataFrame(perturbation_table)
        path = os.path.join(TABLES_DIR, "tab_clustering_perturbation.csv")
        df_pert.to_csv(path, index=False)
        log.info("Saved perturbation table → %s", path)

    # Optimal k results
    if optimal_k:
        path = os.path.join(TABLES_DIR, "clustering_optimal_k.json")
        with open(path, "w") as f:
            json.dump(optimal_k, f, indent=2)
        log.info("Saved optimal-k results → %s", path)


# ============================================================
# Entry point
# ============================================================


def main():
    parser = argparse.ArgumentParser(
        description="Compare clustering methods across corpus snapshots"
    )
    parser.add_argument("--pdf", action="store_true",
                        help="Also save PDF output")
    parser.add_argument("--no-perturbation", action="store_true",
                        help="Skip perturbation stability (saves time)")
    parser.add_argument("--n-perturbation", type=int, default=10,
                        help="Number of perturbation repeats (default: 10)")
    cfg_k = load_analysis_config()["clustering"]["k"]
    parser.add_argument("--k", type=int, default=cfg_k,
                        help=f"Number of clusters for KMeans/Spectral "
                             f"(default: {cfg_k} from analysis.yaml)")
    parser.add_argument("--k-range", type=str, default="3,12",
                        help="k range for optimal-k sweep (default: 3,12)")
    args = parser.parse_args()

    k_lo, k_hi = [int(x) for x in args.k_range.split(",")]

    # Load snapshots
    snapshots = load_snapshots()

    # Run comparison
    results, ari_table, perturbation_table = run_comparison(
        snapshots, k=args.k,
        do_perturbation=not args.no_perturbation,
        n_perturbation=args.n_perturbation,
    )

    # Run optimal-k analysis on full corpus
    X_full = snapshots["full"][0]
    optimal_k = run_optimal_k(X_full, k_range=range(k_lo, k_hi + 1))

    # Multi-space comparison: semantic vs lexical vs citation
    df_full, _ = load_analysis_corpus(v1_only=False, with_embeddings=False)
    space_results = multi_space_silhouette(
        df_full, X_full, k_range=range(k_lo, k_hi + 1)
    )
    # Save multi-space results
    space_path = os.path.join(TABLES_DIR, "clustering_multi_space.json")
    with open(space_path, "w") as f:
        json.dump(space_results, f, indent=2)
    log.info("Saved multi-space results → %s", space_path)

    # Save results
    save_results(ari_table, perturbation_table, optimal_k)

    # Generate figures — delegates to dedicated plot_fig_*.py scripts
    generate_figures(ari_table, perturbation_table, optimal_k,
                     pdf=args.pdf)
    plot_multi_space_figure(space_results, pdf=args.pdf)

    log.info("Comparison complete.")


if __name__ == "__main__":
    main()
