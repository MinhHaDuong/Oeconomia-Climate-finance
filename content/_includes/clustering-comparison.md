## 7. Clustering Method Comparison

**Script:** `scripts/compare_clustering.py`

The manuscript uses KMeans (k=6) on 384-dimensional multilingual sentence embeddings to identify thematic clusters. After the v1.0 submission, adding 0.6% new works reshuffled cluster assignments qualitatively (Errata 1: five of six cluster titles mapped to wrong panels). This section evaluates clustering stability systematically by comparing three methods across three corpus snapshots, and tests whether cluster structure exists in the semantic, lexical, or citation representation spaces.

### Methods compared

**KMeans** (baseline). Partitions the embedding space into *k* convex Voronoi cells, minimizing within-cluster variance. Requires specifying *k* in advance. Deterministic given a random seed (n_init=20). Every point is assigned to a cluster — no noise class.

**HDBSCAN** (Hierarchical Density-Based Spatial Clustering of Applications with Noise). Finds clusters as dense regions separated by sparser areas. Does not require *k*; the key parameter is `min_cluster_size`. Points in sparse regions are classified as noise (-1).

**Spectral clustering**. Constructs a nearest-neighbor affinity graph (k=15 neighbors), computes the graph Laplacian's eigenvectors, and clusters in the spectral embedding. Requires specifying *k*. Note: spectral clustering has O(n³) eigendecomposition cost; for corpora exceeding 5,000 works, we subsample and assign remaining points to the nearest centroid.

### Corpus snapshots

Three snapshots test stability under corpus perturbation:

| Snapshot | Description | Size |
|----------|-------------|------|
| original | v1.0 submission works matched by DOI in current corpus | 18,467 |
| v1_tagged | `in_v1==1` subset of current corpus | 26,355 |
| full | v1.1 corpus (with S2 + teaching expansion) | 27,315 |

The "original" snapshot matches only 18,467 of the 29,875 v1.0 works because matching is by DOI and many works either lack DOIs or were removed during re-filtering. This makes the original→other comparisons test a larger perturbation than the 0.6% Errata 1 scenario.

### Cross-snapshot stability (ARI)

The Adjusted Rand Index (ARI) measures agreement between two clusterings on shared works. ARI = 1 means identical assignments; ARI ≈ 0 means random agreement.

| Method | original → v1_tagged | original → full | v1_tagged → full |
|--------|---------------------|----------------|-----------------|
| KMeans | 0.678 | 0.674 | **0.980** |
| HDBSCAN | 0.865\* | 0.858\* | **0.992**\* |
| Spectral | 0.666 | 0.774 | 0.587 |

\*HDBSCAN ARI inflated: 97–98% of works classified as noise (-1) across all snapshots. High ARI reflects agreement on the noise label. HDBSCAN finds only 3 non-noise clusters with min_cluster_size=50 — the semantic embedding space lacks the density separation HDBSCAN requires.

**Reading**: The v1_tagged→full comparison (marginal 3.5% expansion) shows KMeans is highly stable for small additions (ARI=0.980). Spectral is unstable (0.587), partly due to the subsampling approximation. The original→other comparisons show moderate stability (ARI≈0.67) consistent with a ~33% perturbation.

![Cross-snapshot clustering stability (ARI). HDBSCAN values are inflated by noise-class agreement.](figures/fig_clustering_ari.png){#fig-clustering-ari width=100%}

### Perturbation stability

KMeans (k=6) perturbation test: cluster the full corpus, randomly drop *f*% of works, re-cluster, compute ARI (10 repeats).

| Drop fraction | ARI (mean ± std) |
|--------------|-----------------|
| 1% | 0.887 ± 0.161 |
| 5% | 0.848 ± 0.168 |
| 10% | 0.885 ± 0.150 |

Mean ARI is high (~0.87) but standard deviation is substantial (~0.16). This means most perturbations preserve cluster structure, but occasionally assignments reshuffle — consistent with the Errata 1 incident.

![KMeans (k=6) stability under random perturbation.](figures/fig_clustering_perturbation.png){#fig-clustering-perturbation width=100%}

### Multi-space structure comparison

The central question: does natural cluster structure exist in the climate finance corpus? We test three representation spaces using KMeans silhouette scores for k = 3–12.

| Space | Description | Works | Silhouette at k=6 | Range (k=3–12) |
|-------|-------------|-------|--------------------|----------------|
| Semantic | 384D sentence embeddings (MiniLM) | 27,315 | 0.025 | 0.025–0.038 |
| Lexical | TF-IDF (unigrams + bigrams) → 100D SVD | 23,486 | 0.046 | 0.032–0.062 |
| Citation | Bibliographic coupling → 100D SVD, L2 | 10,685 | 0.083 | 0.052–0.108 |

**Semantic space**: Silhouette scores near zero across all k values. No natural cluster structure. The trough at k=6 (0.025) and slight peak at k=3 (0.038) suggest the embedding space is essentially continuous.

**Lexical space**: Slightly higher silhouette, monotonically increasing with k (no optimal k). The TF-IDF SVD captures only 19.2% of variance, indicating a dispersed lexicon. Terms like "climate," "finance," and "carbon" dominate all clusters.

**Citation space**: The strongest structure (3× semantic silhouette at k=6). Bibliographic coupling captures which literatures each work draws on. The 97.4% variance explained by SVD reflects a sparse coupling matrix — most works share few references. After L2 normalization, silhouette increases steadily with k, suggesting many fine-grained citation communities. HDBSCAN finds 20 clusters with 70.8% noise in this space — far more structure than in the semantic space (3 clusters, 97.7% noise).

![Silhouette scores across three representation spaces (KMeans, k = 3–12). Citation space shows the most structure, though all scores remain low (<0.11) indicating no sharply delineated clusters.](figures/fig_clustering_spaces.png){#fig-clustering-spaces width=100%}

### Discussion

**1. Climate finance is a continuum, not a typology.** All three spaces show low silhouette scores (<0.11). There are no well-separated clusters in any representation. The intellectual traditions identified in the manuscript are not discrete schools of thought but regions in a continuous field — a finding consistent with the paper's narrative of overlapping, evolving perspectives.

**2. Citation ties create more structure than topical similarity.** The citation space shows 3× more cluster structure than semantic or lexical spaces. Works that cite similar literatures form tighter groups than works about similar topics. This means "traditions" are partly social structures (citation networks) rather than purely conceptual ones (topic similarity). The Louvain co-citation communities (Section 11) capture this citation-based structure directly, which is why the manuscript's k=6 was chosen to match those communities rather than to optimize silhouette.

**3. KMeans is the right pragmatic choice.** HDBSCAN cannot find meaningful clusters in the semantic space (97.7% noise). Spectral clustering offers no stability advantage while being computationally prohibitive. KMeans provides deterministic, interpretable partitions that are highly stable under small perturbations (ARI=0.980 for 3.5% expansion). The Errata 1 labeling error resulted from an unconstrained cluster-to-label mapping, not from method instability — fixed by seeding with reference centroids.

**4. The k=6 choice is a pragmatic convention, not a statistical optimum.** No k value produces well-separated clusters. The manuscript's k=6 matches the six co-citation communities from Louvain community detection on the citation graph — a more principled community-detection method. The thematic clustering serves to project citation-based structure into the semantic space for visualization.

**Limitation**: The near-zero silhouette scores should be disclosed as a limitation of the thematic clustering in future revisions. The visual coherence of clusters in UMAP projections (Figures 3–4 in the manuscript) may overstate the separability of the underlying traditions.
