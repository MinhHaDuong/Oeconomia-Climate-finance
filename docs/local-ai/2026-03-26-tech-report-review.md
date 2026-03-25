# Technical report chapter review — 2026-03-26

AI panel review of `content/_includes/` chapters about corpus structure.
Three independent reviewers checked claims against code and analysis outputs.

## WRONG (contradicts code/data)

### corpus-construction.md
1. **S2 still listed as active source**: Table includes Semantic Scholar row, text says "7 sources",
   SOURCE_PRIORITY includes `semanticscholar`. Reality: S2 disconnected (`dvc.yaml` comment),
   absent from `SOURCE_NAMES` and `SOURCE_PRIORITY` in code. Should be 6 sources.
2. **"1,406 core papers"**: Now 2,648 (stale snapshot from taxonomy design phase).
3. **Teaching canon "15 institutions"**: Now 51 (`teaching_sources.yaml`).
4. **Grey lit raw count 278**: Now 4,882 (World Bank API growth).
5. **Pipeline diagram says "7 sources"**: Should be 6.

### corpus-enrichment.md
6. **ISTEX step described as "API query by DOI"**: Code reads local TEI XML files
   from disk (`enrich_abstracts.py` step 3), no HTTP call.

### corpus-filtering.md
7. **Protection for "2+ teaching syllabi"**: Code uses binary `from_teaching == 1`,
   no syllabus count. Any teaching presence triggers protection.
8. **Citation isolation "before 2020"**: Config says `max_year: 2019` (<=2019),
   technically equivalent but imprecise prose.
9. **LLM audit model "gemma-2-27b-it"**: Now `gemini-2.5-flash` via litellm/OpenRouter.

### embedding-generation.md
10. **Batch size 256**: Code default is 32 (`EMBED_BATCH_SIZE` env var).

### clustering-comparison.md
11. **Citation-space arithmetic inconsistent**: "12,676 sources minus 412 dropped = 10,685"
    — actual: 12,676 - 412 = 12,264 ≠ 10,685. One number is wrong.

### structural-breaks.md
12. **`corpus_with_embeddings` (37,928) used as analysis N**: Actual analysis corpus
    is ~27,509 (after filtering). The meta variable counts the embeddings cache, not
    the analysis subset. Overstates N by ~38%.

## STALE (numbers drifted)

- Full corpus snapshot "27,315 works" → 27,509 (clustering-comparison, structural-breaks)
- Core "2,621 works" → 2,648 (clustering-comparison)
- `tab_corpus_sources.md` multiple cells outdated (OpenAlex, bibCNRS, grey, total)
- TF-IDF SVD variance (19.2%), citation SVD variance (97.4%) — unverifiable without re-run
- HDBSCAN 97.7% noise, 3 clusters — unverifiable
- KMeans/HDBSCAN/Spectral ARI scores — no stored table

## CONFIRMED

- Embedding model BAAI/bge-m3, 1024 dimensions, 8192-token context
- L2-normalized embeddings
- UMAP parameters (n_components=2, n_neighbors=15, min_dist=0.05, cosine, seed=42)
- KMeans k=6, n_init=20, seed=42
- TF-IDF vectorizer parameters (5000 features, sublinear_tf, etc.)
- Spectral clustering subsamples to 5,000
- Four abstract enrichment steps (cross-source, OpenAlex, ISTEX, S2)
- Protection thresholds: cited_by >= 50, source_count >= 2
- Filter flag: semantic outlier > mean + 2 SD

## Action items

- [ ] Fix all 12 WRONG items in the includes
- [ ] Update stale numbers (re-run compute_vars.py or hardcode from fresh data)
- [ ] Decide: should `corpus_with_embeddings` meta var be redefined to mean analysis corpus?
- [ ] The tab_corpus_sources.md needs full regeneration from current data
