## 2. Corpus Enrichment

After discovery and merge, the pipeline enriches metadata and computes derived features before full refinement. A cheap pre-filter runs first to avoid wasting API calls on obviously irrelevant records.

### Cheap pre-filter (flags 1–3)

Before enrichment, `corpus_refine.py --apply --cheap` removes papers that fail basic quality checks without needing any external data:

1. **Missing metadata:** No title, or missing author/year with irrelevant title.
2. **No abstract + irrelevant title:** Abstract shorter than 50 characters and title lacks domain-specific safe words.
3. **Title blacklist:** Titles containing noise terms (blockchain, cryptocurrency, deep learning, etc.) without climate/finance safe words.

This step typically removes ~5,000 records, saving downstream enrichment costs. Papers removed here are not submitted for abstract backfill, citation lookup, or embedding generation.

### Abstract enrichment

The script `enrich_abstracts.py` backfills missing abstracts through four sources, tried in order:

1. **Cross-source transfer:** If another source catalog has the abstract for the same DOI, copy it.
2. **OpenAlex API:** Query by DOI to retrieve the inverted abstract index.
3. **ISTEX API:** Query by DOI for French national archive abstracts.
4. **Semantic Scholar API:** Query by DOI or title for preprint and working paper abstracts.

Abstracts are needed for embedding generation (§2.4) and LLM relevance scoring (flag 6 in §3).

### Citation enrichment

Citation links are assembled from three sources:

- **Crossref** (`enrich_citations_batch.py`): Batch DOI lookup via the Crossref REST API. Resumable; only fetches DOIs not already in `citations.csv`.
- **OpenAlex** (`enrich_citations_openalex.py`): Fills gaps using OpenAlex's `referenced_works` field. Also incorporates citation links extracted during the OpenAlex catalog build (`openalex_citations.csv`).
- **ISTEX** (`catalog_istex.py`): Reference lists (`refBibs`) are extracted during discovery and stored in `istex_refs.csv`.

Quality control (`qc_citations.py`) validates DOI formats, removes self-citations, and reports coverage statistics. The merged `citations.csv` is needed for citation isolation detection (flag 4 in §3).

### Embedding generation

The script `analyze_embeddings.py` computes 384-dimensional sentence embeddings using a multilingual MiniLM model (`paraphrase-multilingual-MiniLM-L12-v2`) on title + abstract text. Only papers with abstracts of at least 50 characters (published 1990–2025) are embedded.

Outputs:

- `embeddings.npz`: Compressed embedding cache (vectors, DOI keys, model metadata).
- `semantic_clusters.csv`: Cluster assignments from HDBSCAN, with UMAP coordinates for visualization.

Embeddings are needed for semantic outlier detection (flag 5 in §3) and for the alluvial and bimodality analyses.
