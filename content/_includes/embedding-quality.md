## Embedding Quality Validation

**Script:** `scripts/qa_embeddings.py` (seed=42, no API calls)

To verify that the embedding vectors capture semantic content rather than noise, we compared cosine similarity within and between the six KMeans clusters. Sampling 200 random pairs from each condition, mean within-cluster similarity (0.550, 95% CI [0.538, 0.561]) exceeds mean between-cluster similarity (0.511, 95% CI [0.501, 0.520]) with a medium effect size (Cohen's *d* = 0.51, Mann--Whitney *U* = 25,452, *p* = 1.2 x 10^-6^). A spot-check of the five nearest neighbours for ten landmark works (e.g., the Stern Review, IPCC Synthesis Report, green bond surveys) confirms that neighbours are topically coherent. These results provide evidence that the BGE-M3 embeddings encode meaningful disciplinary proximity, supporting their use for clustering and semantic mapping.
