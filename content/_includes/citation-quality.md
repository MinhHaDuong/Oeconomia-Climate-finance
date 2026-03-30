## 12. Citation Graph: Coverage and Quality

**Scripts:** `scripts/enrich_citations_batch.py` (Crossref), `scripts/enrich_citations_openalex.py` (OpenAlex), `scripts/corpus_parse_citations_grobid.py` (GROBID parsing), `scripts/corpus_ref_match.py` (fuzzy corpus matching), `scripts/corpus_merge_citations.py` (merge caches → citations.csv), `scripts/qa_citations.py` (verification)

**Data:** `content/tables/qa_citations_report.json`

### Coverage

The citation graph was built by querying Crossref and OpenAlex for every DOI in `refined_works.csv`. Of {{< meta cite_total_dois >}} unique corpus DOIs, {{< meta cite_fetched_dois >}} ({{< meta cite_coverage_pct >}}%) appear as source papers in `citations.csv`, contributing {{< meta cite_total_rows >}} reference rows of which {{< meta cite_doi_ref_rows >}} ({{< meta cite_doi_ref_pct >}}%) carry a resolved reference DOI. OpenAlex complemented the {{< meta cite_crossref_rows >}} rows from Crossref.

| Metric | Value |
|--------|-------|
| Corpus DOIs | {{< meta cite_total_dois >}} |
| DOIs with citation data | {{< meta cite_fetched_dois >}} ({{< meta cite_coverage_pct >}}%) |
| Total reference rows | {{< meta cite_total_rows >}} |
| Rows with resolved ref DOI | {{< meta cite_doi_ref_rows >}} ({{< meta cite_doi_ref_pct >}}%) |
| Crossref-sourced rows | {{< meta cite_crossref_rows >}} |

Coverage varies by period:

{{< include tables/tab_citation_coverage.md >}}

The remaining {{< meta cite_never_fetched >}} never-fetched DOIs belong to publishers — preprint servers, small journals, regional outlets — that neither deposit reference metadata to Crossref nor appear in OpenAlex with resolved references. This is a genuine structural ceiling; no further improvement is expected without full-text PDF access.

### Unstructured references

Of the reference rows in `refined_citations.csv`, 60% carry a resolved DOI, 17% have a title but no DOI, and 23% (~189,000 rows) contain only a raw Crossref `unstructured` string — a free-text citation that neither Crossref nor OpenAlex could parse into structured fields. OpenAlex's `referenced_works` endpoint already resolves most Crossref references using fuzzy title and author matching at scale; these 189,000 rows are the residual that OpenAlex could not match either, typically grey literature, institutional reports, and working papers outside its corpus.

### Quality verification

Two statistical tests verify the citation graph against Crossref as independent ground truth (seed 42, n=300 per test, verification date: 2026-03-26).

**Test A — Accuracy (are our links real?)**
A random sample of 300 individual (source_doi, ref_doi) links from `citations.csv` was checked against Crossref metadata: does Crossref list this reference for this source paper?

| Metric | Value |
|--------|-------|
| Links sampled | 300 |
| Confirmed by Crossref | 297 / 300 |
| **Accuracy** | **99.0%**, 95% CI [97.1%, 99.7%] |

The 3 unconfirmed links are OpenAlex additions — references resolved through OpenAlex's own metadata that Crossref does not list. These are not false positives but references from an additional source.

**Test B — Completeness (are links missing?)**
A random sample of 300 source DOIs was re-fetched from Crossref. For each, all Crossref reference DOIs were compared against our stored data.

| Metric | Value |
|--------|-------|
| Source DOIs sampled | 300 (285 with Crossref DOI refs) |
| Crossref ref DOIs checked | 11,780 |
| **Completeness** | **100.0%**, 95% CI [99.97%, 100%] |

Every reference DOI that Crossref reports is present in our data. The 15 source DOIs without Crossref DOI references are papers whose publishers deposit no structured reference metadata.

**Sample size justification.** At n=300, the Wilson confidence interval for a proportion near 1.0 has width ≤ ±2 percentage points. Each test requires ~150 seconds of Crossref API calls at 0.15s polite rate limiting.

### Alternative source evaluation

Prior to adding the OpenAlex enrichment pass, the Crossref-only coverage stood at 47%. Three alternatives were evaluated on a random sample of never-fetched DOIs:

| Source | Found in index | With refs | Mean refs/paper | Actual new links |
|--------|---------------|-----------|-----------------|-----------------|
| **Crossref** | 27 / 30 | 1 / 30 | 0.3 | ~0 |
| **OpenAlex** `referenced_works` | 20 / 20 | 9 / 20 | 23 | **+237,918** (implemented) |
| **Semantic Scholar** | 3 / 10 | 2 / 10 | 80 | not implemented\* |
| **PDF / GROBID** | n/a | n/a | — | not implemented |

\* Semantic Scholar coverage is low for grey literature, non-English, and small-journal content typical in this corpus; its free tier requires an API key for sustained use.

OpenAlex was the highest-leverage option because: (a) 100% of tested never-fetched DOIs were found in the index, (b) 45% had `referenced_works` lists, and (c) references are pre-resolved to OpenAlex IDs which map cleanly to DOIs. The `enrich_citations_openalex.py` script fetches referenced works and resolves OpenAlex IDs to DOIs in interleaved waves, appending to `enrich_cache/openalex_refs.csv`. The merge step (`corpus_merge_citations.py`) then combines both source caches into `citations.csv`. OpenAlex contributed 237,918 citation rows, raising overall coverage from 47% to 78%.
