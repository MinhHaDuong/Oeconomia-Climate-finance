## 11. Citation Graph: Coverage and Quality

**Scripts:** `scripts/enrich_citations_batch.py` (Crossref), `scripts/enrich_citations_openalex.py` (OpenAlex), `scripts/qc_citations.py` (verification)

**Data:** `content/tables/qc_citations_report.json`

### Coverage

The citation graph was built by querying Crossref and OpenAlex for every DOI in `refined_works.csv`. Of {{< var cite_total_dois >}} unique corpus DOIs, {{< var cite_fetched_dois >}} ({{< var cite_coverage_pct >}}%) appear as source papers in `citations.csv`, contributing {{< var cite_total_rows >}} reference rows of which {{< var cite_doi_ref_rows >}} ({{< var cite_doi_ref_pct >}}%) carry a resolved reference DOI. OpenAlex complemented the {{< var cite_crossref_rows >}} rows from Crossref.

| Metric | Value |
|--------|-------|
| Corpus DOIs | {{< var cite_total_dois >}} |
| DOIs with citation data | {{< var cite_fetched_dois >}} ({{< var cite_coverage_pct >}}%) |
| Total reference rows | {{< var cite_total_rows >}} |
| Rows with resolved ref DOI | {{< var cite_doi_ref_rows >}} ({{< var cite_doi_ref_pct >}}%) |
| Crossref-sourced rows | {{< var cite_crossref_rows >}} |

Coverage varies by period:

{{< include _includes/tab_citation_coverage.md >}}

The remaining {{< var cite_never_fetched >}} never-fetched DOIs belong to publishers — preprint servers, small journals, regional outlets — that neither deposit reference metadata to Crossref nor appear in OpenAlex with resolved references. This is a genuine structural ceiling; no further improvement is expected without full-text PDF access.

### Quality verification

A stratified random sample of 30 source DOIs was re-fetched from Crossref and compared entry-by-entry with our stored data (seed 42, verification date: 2026-03-12).

| Metric | Value |
|--------|-------|
| Papers sampled | 30 (29 found in Crossref) |
| Aggregate precision (our DOI refs found in Crossref) | **0.648** |
| Aggregate recall (Crossref DOI refs we captured) | **1.000** |
| Mean per-paper precision | **0.661** |
| Mean per-paper recall | **1.000** |
| Papers with phantom references | 19 / 29 |
| Papers with missing references | 0 / 29 |

Recall is perfect: every reference DOI that Crossref reports is present in our stored data. Precision against Crossref is 0.65 because OpenAlex contributes additional resolved DOI references that Crossref does not list — these are not false positives but references resolved through OpenAlex's own metadata. For the 10 papers whose references come exclusively from Crossref, precision is 1.0. The 19 papers flagged as having "phantom" references are those where OpenAlex adds DOI refs beyond what Crossref reports; manual inspection confirms these are valid references.

### Alternative source evaluation

Prior to adding the OpenAlex enrichment pass, the Crossref-only coverage stood at 47%. Three alternatives were evaluated on a random sample of never-fetched DOIs:

| Source | Found in index | With refs | Mean refs/paper | Actual new links |
|--------|---------------|-----------|-----------------|-----------------|
| **Crossref** | 27 / 30 | 1 / 30 | 0.3 | ~0 |
| **OpenAlex** `referenced_works` | 20 / 20 | 9 / 20 | 23 | **+237,918** (implemented) |
| **Semantic Scholar** | 3 / 10 | 2 / 10 | 80 | not implemented\* |
| **PDF / GROBID** | n/a | n/a | — | not implemented |

\* Semantic Scholar coverage is low for grey literature, non-English, and small-journal content typical in this corpus; its free tier requires an API key for sustained use.

OpenAlex was the highest-leverage option because: (a) 100% of tested never-fetched DOIs were found in the index, (b) 45% had `referenced_works` lists, and (c) references are pre-resolved to OpenAlex IDs which map cleanly to DOIs. The `enrich_citations_openalex.py` script queries in two phases — batch-fetching source works, then batch-resolving referenced OpenAlex IDs — and appended 237,918 new citation rows to `citations.csv`, raising overall coverage from 47% to 78%.
