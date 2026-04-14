## Metadata Accuracy

**Script:** `scripts/qa_metadata.py`

**Data:** `content/tables/qa_metadata_report.json`

A stratified random sample of 100 works with DOIs was drawn from `refined_works.csv` (seed 42) and independently verified against the Crossref API. Of the 100 sampled DOIs, 96 were found in Crossref (4 returned 404, typically grey literature or small publishers). Title accuracy was assessed by fuzzy string matching (difflib.SequenceMatcher, threshold 0.85): 95 of 96 titles matched, yielding a proportion of 0.990 (95% Wilson CI: [0.943, 0.998]). The single mismatch was a multi-chapter OECD report where the DOI resolved to a different chapter than the one indexed. Publication year matched exactly in 84 of 96 cases (0.875, CI: [0.794, 0.927]); the 12 discrepancies were all off-by-one, reflecting the difference between online-first and print publication dates. When allowing a one-year tolerance, year agreement was 96/96 (1.000, CI: [0.962, 1.000]). DOI resolution (HTTP HEAD to doi.org) succeeded for 21 of 30 tested DOIs (0.700, CI: [0.521, 0.833]); failures were concentrated among grey literature DOIs from repositories that do not maintain persistent resolution.

For the 8,602 works without DOIs (28% of the corpus), a separate sample of 30 was searched by title in OpenAlex. Of these, 24 returned a high-confidence title match (similarity > 0.85), with 23 of 24 year values also matching exactly. The remaining 6 could not be found via title search, consistent with their provenance from grey literature sources not indexed by OpenAlex.

| Metric | n | Proportion | 95% Wilson CI |
|--------|---|-----------|---------------|
| Title match (fuzzy, > 0.85) | 96 | 0.990 | [0.943, 0.998] |
| Year exact match | 96 | 0.875 | [0.794, 0.927] |
| Year within 1 year | 96 | 1.000 | [0.962, 1.000] |
| DOI resolves | 30 | 0.700 | [0.521, 0.833] |
