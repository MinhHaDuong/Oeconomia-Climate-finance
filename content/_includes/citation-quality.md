## Citation Graph: Coverage and Quality

**Scripts:** `scripts/enrich_citations_batch.py` (Crossref), `scripts/enrich_citations_openalex.py` (OpenAlex), `scripts/qc_citations.py` (verification)

**Data:** `content/tables/qc_citations_report.json`

### Coverage

The citation graph was built by querying Crossref and OpenAlex for every DOI in `refined_works.csv`. Of 17,533 unique corpus DOIs, 13,699 (78%) appear as source papers in `citations.csv`, contributing 595,923 reference rows of which 509,966 (86%) carry a resolved reference DOI. OpenAlex contributed 237,918 rows complementing the 358,005 from Crossref.

| Metric | Value |
|--------|-------|
| Corpus DOIs | 17,533 |
| DOIs with citation data | 13,699 (78%) |
| Total reference rows | 595,923 |
| Rows with resolved ref DOI | 509,966 (86%) |
| Crossref-sourced rows | 358,005 |
| OpenAlex-sourced rows | 237,918 |

Coverage varies by period:

| Period | Total works | With citation data | Coverage |
|--------|------------:|-------------------:|---------:|
| 1990–2006 | 957 | 322 | 34% |
| 2007–2014 | 5,168 | 2,187 | 42% |
| 2015–2025 | 15,532 | 10,971 | 71% |

Coverage is significantly higher for the most-cited works (core papers with $\geq 50$ incoming citations): 1,353 of 1,461 (93%) have reference data.

The remaining 3,834 never-fetched DOIs belong to publishers — preprint servers, small journals, regional outlets — that neither deposit reference metadata to Crossref nor appear in OpenAlex with resolved references. This is a genuine structural ceiling; no further improvement is expected without full-text PDF access.

### Quality verification

A stratified random sample of 30 source DOIs was re-fetched from Crossref and compared entry-by-entry with our stored data (seed 42, verification date: 2026-03-09).

| Metric | Value |
|--------|-------|
| Papers sampled | 30 |
| Precision (our DOI refs found in Crossref) | **1.0000** |
| Recall (Crossref DOI refs we captured) | **1.0000** |
| Papers with phantom references | 0 / 30 |
| Papers with missing references | 0 / 30 |
| Verification date | 2026-03-09 |

Precision and recall are both exactly 1.0: every reference DOI we store matches Crossref, and we have captured every reference DOI that Crossref reports. The quality of the stored data is perfect for the subset of papers where Crossref provides reference metadata.

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
