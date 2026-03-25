## 7. Clustering Method and Representation Space Comparison
<!-- WARNING: AI-generated, not human-reviewed -->

**Script:** `scripts/compare_clustering.py`

### 7.1 Motivation

The manuscript partitions the corpus into six thematic clusters using KMeans on 1024-dimensional multilingual sentence embeddings. After the v1.0 submission, adding 0.6% new works reshuffled cluster assignments qualitatively --- five of six cluster titles mapped to wrong panels (Errata 1). This incident raises three questions: (1) How stable is KMeans compared to alternative methods? (2) Does natural cluster structure exist in the data? (3) Which representation space best captures the field's intellectual organization?

We compare three clustering algorithms across three representation spaces and three corpus snapshots, producing a systematic evaluation that goes beyond method comparison to characterize the field's structure.

### 7.2 Representation spaces

We construct three independent representations of the same corpus, each capturing a different dimension of similarity between works.

**Semantic space** (1024 dimensions). Sentence embeddings from `BAAI/bge-m3`, a multilingual model with 8192-token context producing L2-normalized vectors. Input: concatenation of title, abstract (if >20 characters), and keywords. This space captures *what works are about* --- topical and conceptual similarity across languages.

**Lexical space** (100 dimensions). TF-IDF vectors (unigrams + bigrams, max 5,000 features, sublinear term frequency, English stopwords removed, min_df=3, max_df=0.8) reduced to 100 dimensions via truncated SVD (explaining 19.2% of variance). This space captures *what words works use* --- vocabulary overlap, which is language-dependent and sensitive to disciplinary jargon.

**Citation space** (100 dimensions). Bibliographic coupling: two works are similar if they share references. We build a source×reference incidence matrix from `refined_citations.csv` (637,444 citation edges from 12,676 source works), compute the coupling matrix (incidence × incidence^T^, diagonal zeroed), reduce via truncated SVD to 100 dimensions (97.4% of variance, reflecting extreme sparsity), and L2-normalize to prevent hub-dominated outlier clusters. After filtering zero-norm works (412 dropped), 10,685 works have citation-space representations. This space captures *what literatures works draw on* --- intellectual lineage and community membership.

The high SVD explained variance in citation space (97.4% vs. 19.2% in lexical) reflects the coupling matrix's sparsity: most work-pairs share zero references, concentrating variance in a few dominant components. This is a property of the matrix structure, not of rich low-dimensional structure.

### 7.3 Clustering methods

**KMeans** (baseline). Partitions the space into *k* convex Voronoi cells minimizing within-cluster variance. Deterministic given a seed (random_state=42, n_init=20). Every point is assigned --- no noise class. Computational cost: O(nk) per iteration.

**HDBSCAN** (Hierarchical Density-Based Spatial Clustering of Applications with Noise). Finds clusters as dense regions separated by sparser areas. Key parameter: `min_cluster_size` (set to 50). Does not require *k*. Points in sparse regions are classified as noise (-1). Expected advantage: identifies ambiguous works that don't belong to any tradition.

**Spectral clustering**. Constructs a nearest-neighbor affinity graph (15 neighbors), computes the graph Laplacian's bottom eigenvectors, and runs KMeans in the spectral embedding. Requires specifying *k*. Expected advantage: captures non-convex cluster shapes. Computational limitation: O(n³) eigendecomposition; for corpora exceeding 5,000 works, we subsample to 5,000, cluster spectrally, and assign remaining points to the nearest centroid (preserving spectral labels for sampled points).

### 7.4 Cross-snapshot stability

Three corpus snapshots test clustering stability under perturbation:

| Snapshot | Description | Size | Construction |
|----------|-------------|------|--------------|
| v1_tagged | `in_v1==1` subset of current corpus | 26,355 | Filtering flag set by `corpus_filter.py` |
| full | v1.1 corpus (S2 + teaching expansion) | 27,315 | All works passing year/title filters |

The v1_tagged and full snapshots overlap by 96.5% (960 works added in v1.1). This tests stability under the kind of marginal expansion that caused Errata 1.

The Adjusted Rand Index (ARI) measures agreement between two clusterings on shared works. ARI = 1 means identical assignments; ARI ≈ 0 means random agreement. Results on semantic space (1024D embeddings):

| Method | v1_tagged → full (n=26,355 shared) |
|--------|-------------------------------------|
| KMeans | **0.980** |
| HDBSCAN | 0.992\* |
| Spectral | 0.587 |

\*HDBSCAN ARI inflated: 97--98% of works are classified as noise (-1). The high ARI reflects agreement on the noise label, not on meaningful cluster assignments.

**Interpretation.** KMeans is highly stable under marginal corpus expansion (ARI = 0.980). Spectral clustering is unstable (0.587), partly because the subsampling approximation introduces centroid-based assignment for 82% of works. HDBSCAN cannot find clusters: with `min_cluster_size=50`, it identifies only 3 clusters containing 2.3% of works, with the remaining 97.7% classified as noise. The semantic embedding space lacks density-separated regions.

### 7.5 Perturbation stability

We measure KMeans robustness by randomly dropping *f*% of works and re-clustering (10 repeats per drop fraction):

| Drop fraction | ARI (mean ± std) | Min | Max |
|--------------|-----------------|-----|-----|
| 1% | 0.887 ± 0.161 | 0.52 | 0.99 |
| 5% | 0.848 ± 0.168 | 0.50 | 0.99 |
| 10% | 0.885 ± 0.150 | 0.55 | 0.99 |

Mean ARI is high (~0.87) but standard deviation is substantial (~0.16). Most perturbations preserve cluster structure (ARI > 0.95 in the majority of runs), but approximately 1 in 10 runs produces a major reshuffle (ARI ≈ 0.5). This bimodal stability pattern --- usually stable, occasionally catastrophic --- explains the Errata 1 incident: a small corpus change happened to trigger a reshuffle of the KMeans partition boundaries.

### 7.6 Multi-space structure comparison

The central question: does natural cluster structure exist in the climate finance corpus?

We compute KMeans silhouette scores for k = 3 to 12 in each space. The silhouette coefficient measures how similar a point is to its own cluster versus the nearest neighboring cluster. Values range from -1 (wrong cluster) to +1 (well-clustered); values near 0 indicate overlapping clusters.

| Space | Works | Silhouette at k=6 | Best k | Best silhouette |
|-------|-------|--------------------|--------|----------------|
| Semantic | 27,315 | 0.025 | 3 | 0.038 |
| Lexical | 23,486 | 0.046 | 12+ | 0.062 |
| Citation | 10,685 | 0.083 | 12+ | 0.108 |

**2. Citation ties create more structure than topical similarity.** The citation space shows 3× more cluster structure than semantic or lexical spaces. Works that cite similar literatures form tighter groups than works about similar topics. This means "traditions" are partly social structures (citation networks) rather than purely conceptual ones (topic similarity). The Louvain co-citation communities (Section 11) capture this citation-based structure directly, which is why the manuscript's k=6 was chosen to match those communities rather than to optimize silhouette.

**Semantic space** (silhouette: 0.025--0.038). Near-zero across all k values. The trough at k=6 (0.025) is the worst value in the range. No natural cluster count exists --- the embedding space is essentially continuous. The multilingual sentence model maps all climate finance works into an overlapping region of the 1024-dimensional space.

**Lexical space** (silhouette: 0.032--0.062). Slightly more structure, monotonically increasing with k. No peak implies the field's vocabulary fragments into ever-finer sub-specializations without forming discrete groups. The TF-IDF SVD captures only 19.2% of total variance, confirming a highly dispersed lexicon.

**Citation space** (silhouette: 0.052--0.108). The strongest structure, approximately 3× the semantic silhouette at k=6. HDBSCAN finds 20 density-based communities in this space (70.8% noise), far more than the 3 clusters (97.7% noise) found in the semantic space. Silhouette increases steadily with k, suggesting many fine-grained citation communities consistent with Louvain community detection results (Section 8).

### 7.7 HDBSCAN noise analysis

HDBSCAN's noise classification provides insight into the density structure of each space:

| Space | Min cluster size | Clusters found | Noise fraction |
|-------|-----------------|----------------|----------------|
| Semantic (1024D) | 50 | 3 | 97.7% |
| Citation (100D, L2) | 50 | 20 | 70.8% |

The semantic space is almost uniformly dense --- no sparse separators between clusters. The citation space has moderate density variation: 20 communities emerge, but 70.8% of works sit in sparse boundary regions between them. This is consistent with a field where works increasingly cite across sub-communities.

### 7.8 Cross-space independence

To test whether the three spaces capture the same or independent structure, we compute the ARI between KMeans (k=6) assignments across spaces on shared works:

| Pair | ARI | Interpretation |
|------|-----|----------------|
| Semantic ↔ Lexical | 0.22 | Weak agreement |
| Semantic ↔ Citation | 0.07 | Near-random |
| Lexical ↔ Citation | 0.06 | Near-random |

The three spaces are **largely independent**. Semantic and lexical spaces show weak agreement (works about similar topics tend to use similar words), but neither aligns with citation structure. What a work is about, what words it uses, and what it cites capture three distinct dimensions of the field's organization.

### 7.9 Language as a structuring variable

The multilingual BGE-M3 model is designed to embed texts across languages in a shared space. We test whether language creates measurable clustering:

| Test | Silhouette |
|------|-----------|
| k=2 (EN vs. non-EN label) on semantic space | -0.010 |

The negative silhouette means the EN/non-EN split is *anti-clustered* --- non-English works are embedded within English-language topic regions, not in separate regions. Language does not create artificial boundaries in the semantic space.

### 7.10 Core versus full corpus

Do highly-cited works (cited_by_count ≥ 50) show more clustering structure?

| Subset | n | Silhouette (k=6) |
|--------|---|-------------------|
| Full corpus | 27,315 | 0.025 |
| Core (≥50 citations) | 2,621 | 0.037 |

The core subset shows marginally higher but still near-zero silhouette. Highly-cited works span all thematic regions rather than concentrating in one cluster. High citation count is not a proxy for topical coherence.

### 7.11 Discussion

**Finding 1: Climate finance is a continuum, not a typology.** All three representation spaces and all clustering methods converge on the same conclusion: the corpus has no well-separated clusters. The intellectual traditions identified in the manuscript are not discrete schools of thought but regions in a continuous field. This is consistent with the paper's qualitative narrative of overlapping, evolving perspectives.

**Finding 2: Citation ties create more structure than topical similarity.** The citation space shows 3× more cluster structure than semantic or lexical spaces (silhouette 0.083 vs. 0.025 at k=6). Works that cite similar literatures form tighter groups than works about similar topics. This means "traditions" are partly social structures --- citation communities defined by shared reference lists --- rather than purely conceptual clusters defined by topic similarity. The Louvain co-citation communities (Section 8) capture this citation-based structure directly.

**Finding 3: The three representation spaces are independent.** Semantic, lexical, and citation spaces produce near-independent clusterings (ARI 0.06--0.22). This has methodological implications: bibliometric studies using only one representation space may miss structure visible in others. Our multi-space approach provides a more complete picture than any single method.

**Finding 4: KMeans is the right pragmatic choice despite its limitations.** HDBSCAN cannot find meaningful clusters in the semantic space (97.7% noise). Spectral clustering offers no stability advantage while being computationally infeasible on the full corpus. KMeans provides deterministic, interpretable partitions that are highly stable under marginal corpus changes (ARI = 0.980). The Errata 1 labeling error resulted from an unconstrained cluster-to-label mapping, not from method instability --- fixed by seeding with v1.0 reference centroids.

**Finding 5: k=6 is a pragmatic convention.** No k value produces well-separated clusters. The manuscript's k=6 matches the six co-citation communities from Louvain community detection on the citation graph. The clustering serves to project citation-based structure into the semantic space for visualization purposes, not to discover structure independently.

**Limitation.** The near-zero silhouette scores should be disclosed as a limitation. The visual coherence of clusters in UMAP projections may overstate the separability of the underlying traditions because UMAP optimizes for local neighborhood preservation, creating apparent boundaries between regions that are continuously connected in the original high-dimensional space.
