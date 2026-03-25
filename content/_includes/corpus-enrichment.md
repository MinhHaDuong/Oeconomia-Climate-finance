## 2. Corpus Enrichment

After discovery and merge, the pipeline enriches metadata and computes derived features before full filtering. A cheap pre-filter runs first to avoid wasting API calls on obviously irrelevant records.

### Cheap pre-filter (flags 1–3)

Before enrichment, `corpus_filter.py --apply --cheap` removes papers that fail basic quality checks without needing any external data:

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

- **Crossref** (`enrich_citations_batch.py`): Batch DOI lookup via the Crossref REST API. Writes to `enrich_cache/crossref_refs.csv` (append-only); resumable via cache-is-data.
- **OpenAlex** (`enrich_citations_openalex.py`): Fills gaps using OpenAlex's `referenced_works` field. Writes to `enrich_cache/openalex_refs.csv`; also skips DOIs already in `openalex_citations.csv` (catalog-stage harvest).
- **Merge** (`merge_citations.py`): Concatenates both caches into `citations.csv`, deduplicates on (source_doi, ref_doi), and excludes sentinels. DVC can safely wipe `citations.csv` — merge regenerates it in seconds.
- **ISTEX** (`catalog_istex.py`): Reference lists (`refBibs`) are extracted during discovery and stored in `istex_refs.csv`.

Quality control (`qa_citations.py`) validates DOI formats, removes self-citations, and reports coverage statistics. The merged `citations.csv` is needed for citation isolation detection (flag 4 in §3).

### Embedding generation

The script `enrich_embeddings.py` (Phase 1) computes 1024-dimensional sentence embeddings using `BAAI/bge-m3` (8192-token context) on title + abstract + keywords text. Boilerplate abstracts — repository metadata strings (`info:eu-repo/…`), known junk phrases ("International audience", "peer reviewed"), title-as-abstract duplications, and short ALL CAPS fragments — are detected and excluded so that only substantive text enters the embedding. Only papers with non-empty titles (published 1990–2024) are embedded. UMAP projection and KMeans clustering are performed separately in `analyze_embeddings.py` (Phase 2).

Outputs:

- `embeddings.npz`: Compressed embedding cache (vectors, DOI keys, model metadata) — Phase 1.
- `semantic_clusters.csv`: KMeans cluster assignments with UMAP coordinates — Phase 2 (`analyze_embeddings.py`).

Embeddings are needed for semantic outlier detection (flag 5 in §3) and for the alluvial and bimodality analyses. @fig-semantic shows the resulting 2D UMAP projection colored by KMeans cluster; @fig-semantic-period shows the same projection by publication period; @fig-semantic-lang shows it by language ({{< meta lang_english_pct >}}% English).

![UMAP semantic map of the corpus, colored by cluster.](figures/fig_semantic.png){#fig-semantic width=100%}

![UMAP semantic map, colored by publication period.](figures/fig_semantic_period.png){#fig-semantic-period width=100%}

![UMAP semantic map, colored by language.](figures/fig_semantic_lang.png){#fig-semantic-lang width=100%}
