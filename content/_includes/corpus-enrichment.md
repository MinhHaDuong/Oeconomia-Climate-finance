## Corpus Enrichment

After discovery and merge, the pipeline enriches metadata and computes derived features before full filtering. Each enrichment script writes to its own cache in `enrich_cache/` (persistent, append-only); a final `enrich_join.py` assembles `enriched_works.csv` from the base table and all caches. This allows each enrichment to run independently without triggering others. A cheap pre-filter runs first to avoid wasting API calls on obviously irrelevant records.

### Cheap pre-filter (flags 1–3)

Before enrichment, `corpus_filter.py --apply --cheap` removes papers that fail basic quality checks without needing any external data:

1. **Missing metadata:** No title, or missing author/year with irrelevant title.
2. **No abstract + irrelevant title:** Abstract shorter than 50 characters and title lacks domain-specific safe words.
3. **Title blacklist:** Titles containing noise terms (blockchain, cryptocurrency, deep learning, etc.) without climate/finance safe words.

This step typically removes ~5,000 records, saving downstream enrichment costs. Papers removed here are not submitted for abstract backfill, citation lookup, or embedding generation.

### DOI enrichment

The script `enrich_dois.py` resolves missing DOIs for works that have a title but no DOI. It queries OpenAlex by title (fuzzy match, similarity threshold ≥ 0.85), then falls back to Crossref title search when OpenAlex returns no match. Results are cached in `enrich_cache/doi_resolved.csv` (keyed by source_id). Approximately 27% of corpus works lack DOIs; the Crossref fallback recovers DOIs for works that OpenAlex indexes without one.

### Abstract enrichment

The script `enrich_abstracts.py` backfills missing abstracts through four sources, tried in order:

1. **Cross-source transfer:** If another source catalog has the abstract for the same DOI, copy it.
2. **OpenAlex API:** Query by DOI to retrieve the inverted abstract index.
3. **ISTEX fulltext extraction:** Parse locally downloaded TEI XML files from the ISTEX pool for French national archive abstracts.
4. **Semantic Scholar API:** Query by DOI or title for preprint and working paper abstracts.

Abstracts are needed for embedding generation (§2.4) and LLM relevance scoring (flag 6 in §3).

### Citation enrichment

Citation links are assembled from four sources:

- **Crossref** (`enrich_citations_batch.py`): Batch DOI lookup via the Crossref REST API. Writes to `enrich_cache/crossref_refs.csv` (append-only); resumable via cache-is-data.
- **OpenAlex** (`enrich_citations_openalex.py`): Fills gaps using OpenAlex's `referenced_works` field. Writes to `enrich_cache/openalex_refs.csv`; also skips DOIs already in `openalex_citations.csv` (catalog-stage harvest).
- **GROBID parsing** (`corpus_parse_citations_grobid.py`): Approximately half of Crossref references carry only an unstructured citation string (no structured title, author, or year fields). These are parsed by GROBID, a purpose-built ML model for bibliographic reference parsing, running locally via Podman. Results are cached in `enrich_cache/grobid_parsed.jsonl` (keyed by text hash) and written to `enrich_cache/ref_parsed.csv` with the standard reference schema.
- **Corpus matching** (`corpus_ref_match.py`): Fuzzy-matches GROBID-parsed refs against `refined_works.csv` to discover `ref_doi` for refs that cite corpus works. Uses rapidfuzz `token_sort_ratio` ≥ 85 with year ±1 blocking. Writes to `enrich_cache/ref_matches.csv`.
- **Merge** (`corpus_merge_citations.py`): Concatenates all four caches (Crossref, OpenAlex, GROBID-parsed, corpus-matched) into `citations.csv`, deduplicates on (source_doi, ref_doi) for DOI-bearing refs and on (source_doi, ref_title, ref_first_author, ref_year) for no-DOI refs (books, reports), and excludes sentinels. DVC can safely wipe `citations.csv` — merge regenerates it in seconds.
- **ISTEX** (`catalog_istex.py`): Reference lists (`refBibs`) are extracted during discovery and stored in `istex_refs.csv`.

Quality control (`qa_citations.py`) validates DOI formats, removes self-citations, and reports coverage statistics. The merged `citations.csv` is needed for citation isolation detection (flag 4 in §3).

### Abstract summarization

Approximately 230 records have abstracts exceeding 1,000 whitespace tokens — full introductions, book reviews, or correction notices rather than true abstracts. These degrade embedding quality by injecting noise into the vector space. The script `summarize_abstracts.py` classifies each abstract by length and generates concise (~250-word) summaries via LLM (DeepSeek V3) for oversized records. Summaries are cached in `enrich_cache/abstract_summaries_cache.jsonl` (keyed by DOI) and survive DVC re-runs. The `abstract_status` column tracks provenance: `original` (unchanged), `generated` (LLM summary replaced the original), or `missing` (no abstract available).

### Embedding generation

The script `enrich_embeddings.py` (Phase 1) computes 1024-dimensional sentence embeddings using `BAAI/bge-m3` (8192-token context) on title + abstract + keywords text. Boilerplate abstracts — repository metadata strings (`info:eu-repo/…`), known junk phrases ("International audience", "peer reviewed"), title-as-abstract duplications, and short ALL CAPS fragments — are detected and excluded so that only substantive text enters the embedding. Only papers with non-empty titles (published 1990–2024) are embedded. UMAP projection and KMeans clustering are performed separately in `analyze_embeddings.py` (Phase 2).

Outputs:

- `embeddings.npz`: Compressed embedding cache (vectors, DOI keys, model metadata) — Phase 1.
- `semantic_clusters.csv`: KMeans cluster assignments with UMAP coordinates — Phase 2 (`analyze_embeddings.py`).

Embeddings are needed for semantic outlier detection (flag 5 in §3) and for the alluvial and bimodality analyses. See the Corpus Contents section for UMAP visualizations of the resulting semantic space.
