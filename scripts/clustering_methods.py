"""Clustering algorithm implementations and stability metrics.

Pure algorithmic module — no I/O, no plotting. All functions operate
on numpy arrays and return numpy arrays or plain dicts.

Extracted from compute_clustering_comparison.py (ticket #430) to separate
algorithms from orchestration. This module is a library (no __main__
guard), importable from compute_clustering_comparison.py and tests.

Methods:
- KMeans (sklearn): fast, deterministic, sensitive to k
- HDBSCAN (hdbscan): density-based, auto-detects noise, k-free
- Spectral (sklearn): affinity-based, subsampled for large corpora

Space builders:
- build_tfidf_space: abstracts → TF-IDF → 100D SVD
- build_citation_space: citation edges → bib. coupling → 100D SVD

Stability metrics:
- compute_stability_ari: ARI between two label assignments
- perturbation_stability: mean/std ARI under random 1% drops
- silhouette_sweep: silhouette at each k for KMeans
- hdbscan_sweep: cluster count + noise fraction by min_cluster_size
- spectral_eigengap: silhouette sweep for Spectral
- multi_space_silhouette: compare silhouette across spaces

"""

import os

import numpy as np
from sklearn.metrics import adjusted_rand_score, silhouette_score
from utils import CATALOGS_DIR, get_logger

log = get_logger("clustering_methods")


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
    from sklearn.cluster import HDBSCAN

    clusterer = HDBSCAN(
        min_cluster_size=min_cluster_size,
        min_samples=min_samples,
        metric="euclidean",
        n_jobs=1,
    )
    return clusterer.fit_predict(X)


def cluster_spectral(X, k=6, random_state=42, max_n=5000):
    """Spectral clustering on nearest-neighbor affinity graph.

    When len(X) > max_n, subsample to max_n works (eigendecomposition is
    O(n³), infeasible on >10K works with 1024D input). Remaining points
    are assigned to nearest cluster centroid.
    """
    import warnings

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
        # Well-separated clusters produce a block-diagonal affinity matrix
        # (disconnected graph). Spectral clustering handles this correctly —
        # each connected component maps to one cluster.
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore",
                                    message="Graph is not fully connected",
                                    category=UserWarning)
            return sc.fit_predict(X)

    # Subsample + assign out-of-sample via nearest centroid
    rng = np.random.RandomState(random_state)
    sample_idx = rng.choice(n, max_n, replace=False)
    sample_set = set(sample_idx)
    X_sample = X[sample_idx]

    sc = SpectralClustering(
        n_clusters=k,
        random_state=random_state,
        affinity="nearest_neighbors",
        n_neighbors=15,
        n_jobs=1,
    )
    sample_labels = sc.fit_predict(X_sample)

    # Compute centroids, assign only out-of-sample points
    centroids = np.array([X_sample[sample_labels == c].mean(axis=0)
                          for c in range(k)])
    oos_idx = np.array([i for i in range(n) if i not in sample_set])
    oos_labels, _ = pairwise_distances_argmin_min(X[oos_idx], centroids)

    all_labels = np.empty(n, dtype=int)
    # Preserve spectral labels for sampled points
    for pos, orig_i in enumerate(sample_idx):
        all_labels[orig_i] = sample_labels[pos]
    # Assign nearest-centroid labels for out-of-sample
    for pos, orig_i in enumerate(oos_idx):
        all_labels[orig_i] = oos_labels[pos]
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
# Multi-space representation builders
# ============================================================


def build_tfidf_space(df, max_features=5000):
    """Build TF-IDF representation from abstracts.

    Returns (X_tfidf, valid_idx) where X_tfidf is a dense matrix and
    valid_idx maps rows back to df positions.
    """
    from sklearn.decomposition import TruncatedSVD
    from sklearn.feature_extraction.text import TfidfVectorizer

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
    import pandas as pd
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

    # Map corpus DOIs to indices (exclude empty strings)
    doi_lower = df["doi"].fillna("").str.lower()
    doi_to_df_idx = {}
    for i, d in enumerate(doi_lower):
        if d:  # skip empty DOIs
            doi_to_df_idx[d] = i
    corpus_dois = set(doi_to_df_idx.keys())
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
    log.info("Citation SVD: %d components explain %.1f%% of variance "
             "(high value reflects matrix sparsity, not rich structure)",
             n_components, explained * 100)

    # L2 normalize to prevent hub-dominated outlier clusters
    norms = np.linalg.norm(X_coupling, axis=1, keepdims=True)
    non_zero = norms.flatten() > 1e-10

    # Map sources → df indices, filter to non-zero-norm works.
    # sources[i] ↔ X_coupling[i] ↔ non_zero[i] — all aligned by source_to_idx.
    df_indices = []
    source_positions = []
    for i, doi in enumerate(sources):
        if doi in doi_to_df_idx and non_zero[i]:
            df_indices.append(doi_to_df_idx[doi])
            source_positions.append(i)

    valid_idx = np.array(df_indices)
    X_out = X_coupling[source_positions]
    # Normalize the selected rows
    out_norms = np.linalg.norm(X_out, axis=1, keepdims=True)
    X_out = X_out / out_norms  # safe: we filtered non_zero above

    n_dropped = len(sources) - len(valid_idx)
    log.info("Citation space: %d works with coupling data "
             "(%d dropped: zero coupling or no DOI match)",
             len(valid_idx), n_dropped)
    return X_out, valid_idx


def multi_space_silhouette(df, embeddings, k_range=range(3, 13)):
    """Compare silhouette across semantic, lexical, and citation spaces."""
    results = {}

    # Semantic space (already have embeddings)
    log.info("=== Multi-space silhouette comparison ===")
    log.info("--- Semantic space (1024D embeddings) ---")
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
