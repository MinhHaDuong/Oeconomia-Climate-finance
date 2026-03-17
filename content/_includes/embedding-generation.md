## 3. Embedding Generation

**Script:** `scripts/analyze_embeddings.py`

**Model:** `paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers library). This is a 12-layer multilingual BERT producing 384-dimensional vectors, chosen for its ability to place texts in English, French, Chinese, Japanese, and German into a shared semantic space.

**Input selection:** Papers from `refined_works.csv` with a non-empty title and a publication year between 1990 and 2024. For each work, the embedded text concatenates title, abstract (if longer than 20 characters), and keywords (if available).

**Encoding parameters:**
- Batch size: 256
- Normalization: L2-normalized embeddings
- Runtime: approximately 16 minutes on CPU for a full corpus (~{{< var corpus_total_approx >}} works); incremental runs encode only new additions

**Output:** `embeddings.npz` -- a compressed NumPy archive containing the embedding vectors (N x 384), DOI/source_id keys for each row, model name, and text field specification. The keyed cache enables incremental updates: only works absent from the cache are encoded. A change in model name or text fields triggers a full recompute.

**Additional outputs:**
- UMAP projection (n_components=2, n_neighbors=15, min_dist=0.05, cosine metric, random_state=42)
- KMeans clustering (k=6, n_init=20, random_state=42) on UMAP coordinates
- Cluster assignments saved to `semantic_clusters.csv`
