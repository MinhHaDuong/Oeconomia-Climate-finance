## Embedding Generation

**Scripts:** `scripts/enrich_embeddings.py` (Phase 1: encoding), `scripts/analyze_embeddings.py` (Phase 2: UMAP + clustering)

**Model:** `BAAI/bge-m3` (sentence-transformers library). This multilingual model produces 1024-dimensional vectors with an 8192-token context window, chosen for its ability to place texts in English, French, Chinese, Japanese, and German into a shared semantic space without truncation of typical abstracts.

**Input selection:** Papers from `refined_works.csv` with a non-empty title and a publication year between 1990 and 2024. For each work, the embedded text concatenates title, abstract (if longer than 20 characters), and keywords (if available).

**Encoding parameters:**
- Batch size: 32 (configurable via `EMBED_BATCH_SIZE` environment variable)
- Normalization: L2-normalized embeddings
- Runtime: approximately 16 minutes on CPU for a full corpus (~{{< meta corpus_total_approx >}} works); incremental runs encode only new additions

**Output:** `embeddings.npz` -- a compressed NumPy archive containing the embedding vectors (N x 1024), DOI/source_id keys for each row, model name, and text field specification. The incremental cache is stored separately in `enrich_cache/embeddings_cache.npz` so that DVC re-runs (which delete stage outputs) do not destroy already-computed vectors. Only works absent from the cache or whose text content has changed are re-encoded. A change in model name or text fields triggers a full recompute.

**Phase 2 analysis** (`analyze_embeddings.py`, Makefile target):

- UMAP projection (n_components=2, n_neighbors=15, min_dist=0.05, cosine metric, random_state=42)
- KMeans clustering (k=6, n_init=20, random_state=42) on UMAP coordinates
- Cluster assignments saved to `semantic_clusters.csv`
