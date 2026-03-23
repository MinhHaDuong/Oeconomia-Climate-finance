"""Clustering methods comparison: KMeans vs HDBSCAN vs Spectral.

Compares clustering stability across corpus snapshots and methods.
Produces comparison tables for the technical report.

Ticket: #299 (tracking), sub-issues #300–#304.

Three corpus snapshots:
- original: v1.0 submission data (v1_identifiers.txt.gz)
- v1_tagged: in_v1==1 subset of current corpus
- full: v1.1 full corpus

Evaluation:
- Stability: ARI between snapshots and under perturbation
- Optimal k: silhouette sweep (KMeans/Spectral), min_cluster_size sweep (HDBSCAN)
- Interpretability: cluster size distribution, noise fraction
"""

import argparse
import json
import os
import warnings

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score, silhouette_score

from utils import (
    BASE_DIR,
    CATALOGS_DIR,
    REFINED_EMBEDDINGS_PATH,
    REFINED_WORKS_PATH,
    get_logger,
    load_analysis_config,
    load_analysis_corpus,
)

log = get_logger("compare_clustering")

warnings.filterwarnings("ignore", category=FutureWarning)

TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
FIGURES_DIR = os.path.join(BASE_DIR, "content", "figures")
os.makedirs(TABLES_DIR, exist_ok=True)
os.makedirs(FIGURES_DIR, exist_ok=True)

V1_IDS_PATH = os.path.join(BASE_DIR, "config", "v1_identifiers.txt.gz")
V1_CENTROIDS_PATH = os.path.join(BASE_DIR, "config", "v1_cluster_centroids.npy")


# ============================================================
# Clustering method implementations
# ============================================================


def cluster_kmeans(X, k=6, random_state=42, init="k-means++"):
    """KMeans clustering. Returns integer labels [0, k)."""
    from sklearn.cluster import KMeans

    km = KMeans(n_clusters=k, random_state=random_state, n_init=20, init=init)
    return km.fit_predict(X)


def cluster_hdbscan(X, min_cluster_size=50, min_samples=None):
    """HDBSCAN density-based clustering. Returns labels with -1 for noise."""
    import hdbscan

    clusterer = hdbscan.HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric="euclidean",
        core_dist_n_jobs=1,
    )
    return clusterer.fit_predict(X)


def cluster_spectral(X, k=6, random_state=42, max_n=5000):
    """Spectral clustering on nearest-neighbor affinity graph.

    When len(X) > max_n, subsample to max_n works (eigendecomposition is
    O(n³), infeasible on >10K works with 384D input). Remaining points
    are assigned to nearest cluster centroid.
    """
    from sklearn.cluster import SpectralClustering
    from sklearn.metrics import pairwise_distances_argmin_min

    n = len(X)
    if n <= max_n:
        sc = SpectralClustering(
            n_clusters=k,
            random_state=random_state,
            affinity="nearest_neighbors",
            n_neighbors=min(15, n - 1),
            n_jobs=1,
        )
        return sc.fit_predict(X)

    # Subsample + assign remaining via nearest centroid
    rng = np.random.RandomState(random_state)
    sample_idx = rng.choice(n, max_n, replace=False)
    X_sample = X[sample_idx]

    sc = SpectralClustering(
        n_clusters=k,
        random_state=random_state,
        affinity="nearest_neighbors",
        n_neighbors=15,
        n_jobs=1,
    )
    sample_labels = sc.fit_predict(X_sample)

    # Compute centroids from sample, assign all points
    centroids = np.array([X_sample[sample_labels == c].mean(axis=0)
                          for c in range(k)])
    all_labels, _ = pairwise_distances_argmin_min(X, centroids)
    return all_labels


# ============================================================
# Stability metrics
# ============================================================


def compute_stability_ari(labels_a, labels_b):
    """Adjusted Rand Index between two label assignments."""
    return adjusted_rand_score(labels_a, labels_b)


def perturbation_stability(X, method="kmeans", k=6, drop_frac=0.01,
                           n_repeats=10, random_state=42,
                           min_cluster_size=50):
    """Measure clustering stability under random perturbation.

    Clusters full data, then repeatedly drops drop_frac of points,
    re-clusters, and computes ARI on the remaining points.

    Returns (mean_ari, std_ari).
    """
    rng = np.random.RandomState(random_state)
    n = len(X)
    n_drop = max(1, int(n * drop_frac))

    # Reference clustering on full data
    if method == "kmeans":
        ref_labels = cluster_kmeans(X, k=k, random_state=random_state)
    elif method == "hdbscan":
        ref_labels = cluster_hdbscan(X, min_cluster_size=min_cluster_size)
    elif method == "spectral":
        ref_labels = cluster_spectral(X, k=k, random_state=random_state)
    else:
        raise ValueError(f"Unknown method: {method}")

    aris = []
    for i in range(n_repeats):
        drop_idx = set(rng.choice(n, n_drop, replace=False))
        keep_idx = np.array([j for j in range(n) if j not in drop_idx])
        X_sub = X[keep_idx]

        if method == "kmeans":
            sub_labels = cluster_kmeans(X_sub, k=k, random_state=random_state + i + 1)
        elif method == "hdbscan":
            sub_labels = cluster_hdbscan(X_sub, min_cluster_size=min_cluster_size)
        elif method == "spectral":
            sub_labels = cluster_spectral(X_sub, k=k, random_state=random_state + i + 1)

        ari = compute_stability_ari(ref_labels[keep_idx], sub_labels)
        aris.append(ari)

    return float(np.mean(aris)), float(np.std(aris))


# ============================================================
# Optimal k / parameter analysis
# ============================================================


def silhouette_sweep(X, k_range=range(3, 13), random_state=42):
    """Compute silhouette scores for KMeans across k values."""
    results = []
    for k in k_range:
        labels = cluster_kmeans(X, k=k, random_state=random_state)
        score = silhouette_score(X, labels, sample_size=min(5000, len(X)),
                                 random_state=random_state)
        results.append({"k": k, "silhouette": float(score)})
    return results


def hdbscan_sweep(X, sizes=None):
    """Sweep HDBSCAN min_cluster_size and report results."""
    if sizes is None:
        sizes = [10, 20, 50, 100, 200]
    results = []
    for mcs in sizes:
        labels = cluster_hdbscan(X, min_cluster_size=mcs)
        n_clusters = len(set(labels)) - (1 if -1 in labels else 0)
        noise_frac = float(np.sum(labels == -1)) / len(labels)
        results.append({
            "min_cluster_size": mcs,
            "n_clusters": n_clusters,
            "noise_fraction": noise_frac,
        })
    return results


def spectral_eigengap(X, k_max=12, random_state=42):
    """Estimate optimal k for Spectral clustering via silhouette."""
    return silhouette_sweep(X, k_range=range(2, k_max + 1),
                            random_state=random_state)


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


def generate_figures(ari_table, perturbation_table, optimal_k):
    """Generate comparison figures for the technical report."""
    import matplotlib.pyplot as plt

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
        path = os.path.join(FIGURES_DIR, "fig_clustering_ari.pdf")
        fig.savefig(path, dpi=300, bbox_inches="tight")
        fig.savefig(path.replace(".pdf", ".png"), dpi=150, bbox_inches="tight")
        plt.close()
        log.info("Saved ARI heatmap → %s", path)

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
        path = os.path.join(FIGURES_DIR, "fig_clustering_perturbation.pdf")
        fig.savefig(path, dpi=300, bbox_inches="tight")
        fig.savefig(path.replace(".pdf", ".png"), dpi=150, bbox_inches="tight")
        plt.close()
        log.info("Saved perturbation chart → %s", path)

    # Figure 3: Silhouette scores
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
        path = os.path.join(FIGURES_DIR, "fig_clustering_optimal_k.pdf")
        fig.savefig(path, dpi=300, bbox_inches="tight")
        fig.savefig(path.replace(".pdf", ".png"), dpi=150, bbox_inches="tight")
        plt.close()
        log.info("Saved optimal-k figure → %s", path)


# ============================================================
# Multi-space representations
# ============================================================


def build_tfidf_space(df, max_features=5000):
    """Build TF-IDF representation from abstracts.

    Returns (X_tfidf, valid_idx) where X_tfidf is a dense matrix and
    valid_idx maps rows back to df positions.
    """
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.decomposition import TruncatedSVD

    abstracts = df["abstract"].fillna("")
    has_abstract = abstracts.str.len() > 20
    valid_idx = np.where(has_abstract.values)[0]
    texts = abstracts.iloc[valid_idx].tolist()
    log.info("TF-IDF space: %d works with abstracts (of %d total)",
             len(valid_idx), len(df))

    vectorizer = TfidfVectorizer(
        max_features=max_features, sublinear_tf=True,
        stop_words="english", min_df=3, max_df=0.8,
        ngram_range=(1, 2),
    )
    X_tfidf = vectorizer.fit_transform(texts)

    # Reduce to 100D via SVD for clustering (sparse TF-IDF is high-dim)
    n_components = min(100, X_tfidf.shape[1] - 1, len(valid_idx) - 1)
    svd = TruncatedSVD(n_components=n_components, random_state=42)
    X_reduced = svd.fit_transform(X_tfidf)
    explained = svd.explained_variance_ratio_.sum()
    log.info("TF-IDF SVD: 100 components explain %.1f%% of variance", explained * 100)
    return X_reduced, valid_idx


def build_citation_space(df, citations_path=None):
    """Build bibliographic coupling matrix from citation data.

    Two works are coupled if they share references. Returns (X_coupling,
    valid_idx) where X_coupling is SVD-reduced and valid_idx maps to df.
    """
    from scipy.sparse import csr_matrix
    from sklearn.decomposition import TruncatedSVD

    if citations_path is None:
        citations_path = os.path.join(CATALOGS_DIR, "refined_citations.csv")
    if not os.path.exists(citations_path):
        log.warning("No citations file at %s, skipping citation space",
                     citations_path)
        return None, None

    cit = pd.read_csv(citations_path, usecols=["source_doi", "ref_doi"])
    cit = cit.dropna(subset=["source_doi", "ref_doi"])
    cit["source_doi"] = cit["source_doi"].str.lower()
    cit["ref_doi"] = cit["ref_doi"].str.lower()

    # Map corpus DOIs to indices
    doi_lower = df["doi"].fillna("").str.lower()
    corpus_dois = set(doi_lower)
    # Only keep citations from corpus works
    cit = cit[cit["source_doi"].isin(corpus_dois)]

    # Build source→ref incidence matrix
    sources = cit["source_doi"].unique()
    source_to_idx = {d: i for i, d in enumerate(sources)}
    refs = cit["ref_doi"].unique()
    ref_to_idx = {d: i for i, d in enumerate(refs)}

    rows = [source_to_idx[d] for d in cit["source_doi"]]
    cols = [ref_to_idx[d] for d in cit["ref_doi"]]
    data = np.ones(len(rows))
    incidence = csr_matrix((data, (rows, cols)),
                           shape=(len(sources), len(refs)))

    # Bibliographic coupling = incidence @ incidence.T
    coupling = incidence @ incidence.T
    coupling.setdiag(0)  # no self-coupling
    log.info("Bibliographic coupling: %d sources, %d refs, %d non-zero entries",
             len(sources), len(refs), coupling.nnz)

    # SVD reduction
    n_components = min(100, len(sources) - 1)
    svd = TruncatedSVD(n_components=n_components, random_state=42)
    X_coupling = svd.fit_transform(coupling)
    explained = svd.explained_variance_ratio_.sum()
    log.info("Citation SVD: %d components explain %.1f%% of variance",
             n_components, explained * 100)

    # L2 normalize to prevent hub-dominated outlier clusters
    norms = np.linalg.norm(X_coupling, axis=1, keepdims=True)
    non_zero = norms.flatten() > 1e-10
    X_coupling = np.where(norms > 1e-10, X_coupling / norms, 0)

    # Map back to df indices — keep only non-zero-norm works
    doi_to_df_idx = {d: i for i, d in enumerate(doi_lower)}
    all_valid = [doi_to_df_idx[d] for d in sources if d in doi_to_df_idx]
    source_order = [source_to_idx[doi_lower.iloc[i]]
                    for i in all_valid if doi_lower.iloc[i] in source_to_idx]
    X_coupling = X_coupling[source_order]
    keep = non_zero[source_order]
    valid_idx = np.array(all_valid)[keep]
    X_coupling = X_coupling[keep]

    log.info("Citation space: %d works with coupling data "
             "(%d dropped: zero coupling)", len(valid_idx),
             len(all_valid) - len(valid_idx))
    return X_coupling, valid_idx


def multi_space_silhouette(df, embeddings, k_range=range(3, 13)):
    """Compare silhouette across semantic, lexical, and citation spaces."""
    results = {}

    # Semantic space (already have embeddings)
    log.info("=== Multi-space silhouette comparison ===")
    log.info("--- Semantic space (384D embeddings) ---")
    results["semantic"] = silhouette_sweep(embeddings, k_range=k_range)
    for r in results["semantic"]:
        log.info("  k=%d: silhouette=%.4f", r["k"], r["silhouette"])

    # Lexical space (TF-IDF)
    log.info("--- Lexical space (TF-IDF → 100D SVD) ---")
    X_tfidf, tfidf_idx = build_tfidf_space(df)
    results["lexical"] = silhouette_sweep(X_tfidf, k_range=k_range)
    for r in results["lexical"]:
        log.info("  k=%d: silhouette=%.4f", r["k"], r["silhouette"])

    # Citation space (bibliographic coupling)
    log.info("--- Citation space (bibliographic coupling → 100D SVD) ---")
    X_cit, cit_idx = build_citation_space(df)
    if X_cit is not None:
        results["citation"] = silhouette_sweep(X_cit, k_range=k_range)
        for r in results["citation"]:
            log.info("  k=%d: silhouette=%.4f", r["k"], r["silhouette"])
    else:
        log.warning("Citation space not available")

    return results


# ============================================================
# Entry point
# ============================================================


def main():
    parser = argparse.ArgumentParser(
        description="Compare clustering methods across corpus snapshots"
    )
    parser.add_argument("--no-pdf", action="store_true",
                        help="Skip figure generation")
    parser.add_argument("--no-perturbation", action="store_true",
                        help="Skip perturbation stability (saves time)")
    parser.add_argument("--n-perturbation", type=int, default=10,
                        help="Number of perturbation repeats (default: 10)")
    parser.add_argument("--k", type=int, default=6,
                        help="Number of clusters for KMeans/Spectral (default: 6)")
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

    # Generate figures
    if not args.no_pdf:
        generate_figures(ari_table, perturbation_table, optimal_k)

    log.info("Comparison complete.")


if __name__ == "__main__":
    main()
