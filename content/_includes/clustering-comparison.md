## 7. Clustering Method Comparison

**Script:** `scripts/compare_clustering.py`

The manuscript uses KMeans (k=6) on 384-dimensional multilingual sentence embeddings to identify thematic clusters. After the v1.0 submission, we discovered that adding 0.6% new works reshuffled cluster assignments qualitatively (Errata 1: five of six cluster titles mapped to wrong panels). This section evaluates clustering stability systematically by comparing three methods across three corpus snapshots.

### Methods compared

**KMeans** (baseline). Partitions the embedding space into *k* convex Voronoi cells, minimizing within-cluster variance. Requires specifying *k* in advance. Deterministic given a random seed (n_init=20). Every point is assigned to a cluster — no noise class.

**HDBSCAN** (Hierarchical Density-Based Spatial Clustering of Applications with Noise). Finds clusters as dense regions separated by sparser areas. Does not require *k*; the key parameter is `min_cluster_size`. Points in sparse regions are classified as noise (-1). Potentially more stable because it does not force all points into clusters.

**Spectral clustering**. Constructs a nearest-neighbor affinity graph (k=15 neighbors), computes the graph Laplacian's eigenvectors, and clusters in the spectral embedding. Requires specifying *k*. Can capture non-convex cluster shapes that KMeans misses. Note: spectral clustering has O(n³) eigendecomposition cost; for corpora exceeding 5,000 works, we subsample and assign remaining points to the nearest centroid.

### Corpus snapshots

Three snapshots test stability under corpus perturbation:

| Snapshot | Description | Size |
|----------|-------------|------|
| original | v1.0 submission works matched by DOI in current corpus | 18,467 |
| v1_tagged | `in_v1==1` subset of current corpus | 26,355 |
| full | v1.1 corpus (with S2 + teaching expansion) | 27,315 |

The "original" snapshot matches only 18,467 of the 29,875 v1.0 works because matching is by DOI and many works either lack DOIs or have DOIs not present in the current corpus after re-filtering. This makes the original→other comparisons test a larger perturbation than intended.

### Cross-snapshot stability (ARI)

The Adjusted Rand Index (ARI) measures agreement between two clusterings on shared works. ARI = 1 means identical assignments; ARI ≈ 0 means random agreement; ARI < 0 means worse than random.

| Method | original → v1_tagged | original → full | v1_tagged → full |
|--------|---------------------|----------------|-----------------|
| KMeans | 0.678 | 0.674 | **0.980** |
| HDBSCAN | 0.865* | 0.858* | **0.992*** |
| Spectral | 0.666 | 0.774 | 0.587 |

*HDBSCAN caveat: 97–98% of works are classified as noise (-1) across all snapshots (see below). The high ARI reflects agreement on the noise label, not on meaningful cluster assignments. ARI computed on non-noise works only would be substantially lower.

**Reading**: The v1_tagged→full comparison (marginal 3.5% expansion) shows that KMeans is highly stable to small corpus additions (ARI=0.980). The original→other comparisons test a larger perturbation (33% of v1.0 works unmatched) and show moderate stability (ARI≈0.67–0.77). Spectral clustering is unstable across all comparisons, partly due to the subsampling approximation required for computational feasibility.

### Optimal number of clusters

**Silhouette analysis** (KMeans and Spectral, k = 3–12):

| k | KMeans silhouette | Spectral silhouette |
|---|------------------|-------------------|
| 3 | **0.038** | **0.038** |
| 4 | 0.037 | 0.036 |
| 5 | 0.036 | 0.036 |
| 6 | 0.025 | 0.025 |
| 7 | 0.029 | 0.029 |
| 8 | 0.032 | 0.032 |
| 9 | 0.034 | 0.034 |
| 10 | 0.035 | 0.035 |
| 11 | 0.037 | 0.037 |
| 12 | 0.035 | 0.035 |

All silhouette scores are near zero (range: 0.025–0.038), indicating **no natural cluster structure** in the 384-dimensional embedding space. The curve is essentially flat — the optimal k cannot be determined from silhouette alone. The slight peak at k=3 and the slight trough at k=6 suggest that if anything, the manuscript's choice of k=6 captures finer-grained distinctions than the embedding space warrants.

**HDBSCAN parameter sensitivity**: Results from `min_cluster_size` sweep will be reported when available. The default `min_cluster_size=50` produces only 3 clusters with 97.7% noise, indicating the embedding space has no density-separated regions.

![Cross-snapshot clustering stability (Adjusted Rand Index). Higher values indicate more stable assignments across corpus versions.](figures/fig_clustering_ari.png){#fig-clustering-ari width=100%}

![Optimal cluster count analysis. Left: silhouette scores for KMeans and Spectral (k = 3–12). Right: HDBSCAN parameter sensitivity (clusters found vs. noise fraction as min_cluster_size varies).](figures/fig_clustering_optimal_k.png){#fig-clustering-optimal-k width=100%}

### Discussion

The comparison reveals three important findings:

**1. The embedding space has no natural cluster structure.** Silhouette scores near zero across all k values, and HDBSCAN's classification of 97.7% of works as noise, both indicate that the 384-dimensional semantic space does not contain discrete, well-separated groups. Climate finance literature forms a continuous field rather than distinct sub-disciplines. This finding is consistent with the manuscript's qualitative observation that intellectual traditions are fluid and overlapping.

**2. KMeans is the most practical choice despite its limitations.** When clusters are imposed rather than discovered, KMeans provides deterministic, interpretable partitions that are highly stable under marginal corpus perturbation (ARI=0.980 for 3.5% expansion). HDBSCAN cannot find meaningful clusters in this space. Spectral clustering offers no advantage over KMeans in either stability or interpretability, while being computationally prohibitive on large corpora.

**3. The k=6 choice is a pragmatic convention, not a statistical optimum.** The silhouette analysis provides no justification for any particular k. The manuscript's k=6 was chosen to match the six co-citation communities identified by Louvain community detection on the citation graph — a different (and arguably more principled) method for identifying research communities. The clustering serves to project those citation-based communities into the semantic space for visualization, not to discover structure independently.

**Recommendation**: Retain KMeans (k=6) for the manuscript. The Errata 1 labeling error was caused by an insufficiently constrained cluster-to-label mapping, not by KMeans instability. The fix (seeding KMeans with v1.0 reference centroids, implemented in `compute_clusters.py`) provides deterministic label ordering. For future work, the near-zero silhouette scores should be disclosed as a limitation of the thematic clustering.
