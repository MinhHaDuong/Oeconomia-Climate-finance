## 3. Embedding Generation

**Script:** `scripts/analyze_embeddings.py`

**Model:** `paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers library). This is a 12-layer multilingual BERT producing 384-dimensional vectors, chosen for its ability to place abstracts in English, French, Chinese, Japanese, and German into a shared semantic space.

**Input selection:** Papers from `refined_works.csv` with an abstract longer than 50 characters and a publication year between 1990 and 2025.

**Encoding parameters:**
- Batch size: 256
- Normalization: L2-normalized embeddings
- Runtime: approximately 16 minutes on CPU for ~18,800 abstracts

**Output:** `embeddings.npy` -- a NumPy array of shape (18,798 x 384), cached for reuse by downstream scripts. A size-consistency check ensures the embedding count matches the filtered DataFrame row count.

**Additional outputs:**
- UMAP projection (n_components=2, n_neighbors=15, min_dist=0.05, cosine metric, random_state=42)
- KMeans clustering (k=6, n_init=20, random_state=42) on UMAP coordinates
- Cluster assignments saved to `semantic_clusters.csv`
