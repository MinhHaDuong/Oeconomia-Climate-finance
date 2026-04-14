## Corpus Filtering

The full filtering pass (`corpus_filter.py --apply`) runs after enrichment (§2) has populated abstracts, citations, and embeddings. It implements a four-phase pipeline applying six flags — three cheap flags that need no external data, and three that depend on enrichment outputs.

### Phase A: Flagging

Six flags are applied to each paper:

1. **Missing metadata:** Papers lacking a title are always flagged. Papers missing only author or year are flagged only if the title also lacks "safe" domain words (a curated list of 30+ terms across English, French, German, Spanish, Chinese, and Japanese).
2. **No abstract + irrelevant title:** Papers with abstracts shorter than 50 characters whose titles lack safe domain words. (Re-evaluated after abstract enrichment — papers that gained abstracts may be unflagged.)
3. **Title blacklist:** Papers whose titles contain noise terms (e.g., "blockchain," "cryptocurrency," "deep learning," "metaverse") but no safe domain words.
4. **Citation isolation:** Papers published in 2019 or earlier that are neither cited by nor citing any other paper in the corpus. Requires `citations.csv` from §2.3.
5. **Semantic outlier:** Papers whose embedding cosine distance from the corpus centroid exceeds mean + 2 standard deviations. Requires `embeddings.npz` from §2.4.
6. **Cross-encoder relevance:** Papers with weak concept-group coverage (fewer than 2 of 4 groups: climate, finance, development, environment) are scored by a cross-encoder reranker model (`BAAI/bge-reranker-v2-m3`, 568M parameters) against the query "climate policy and financial mechanisms." Papers scoring below the calibrated threshold (0.002) are flagged as irrelevant. This replaced an earlier LLM-based classification (Gemini Flash via OpenRouter) for speed, cost, and reproducibility. See §3.1 for calibration details.

| Flag | Prerequisite | Phase available |
|------|-------------|----------------|
| 1. Missing metadata | None | Cheap filter |
| 2. No abstract | None (re-evaluated after abstract enrichment) | Cheap filter |
| 3. Title blacklist | None | Cheap filter |
| 4. Citation isolation | `citations.csv` | Full filter only |
| 5. Semantic outlier | `embeddings.npz` | Full filter only |
| 6. Cross-encoder relevance | Abstracts | Full filter only |

Flag 6 uses a cross-encoder reranker (`BAAI/bge-reranker-v2-m3`, 568M parameters) to score each paper's relevance to "climate policy and financial mechanisms." The model is deterministic, reproducible, and runs locally. The query was selected from 100 candidates (best AUC = 0.766 on weak labels; human validation AUC = 0.818). Threshold 0.002 yields 81% accuracy on a blinded 100-paper sample. See the Annex for full calibration details.

### Phase B: Protection

Papers are protected from removal if they meet any of: cited_by_count >= 50, appear in 2+ sources, are cited within the corpus, or appear in the teaching canon (`from_teaching` flag).

### Phase C: Verification

- **Blacklist validation:** Confirms all noise-term matches in titles are properly caught.
- **LLM audit:** A stratified random sample of 100 papers (stratified by source) is submitted to a generative LLM via litellm (currently `google/gemini-2.5-flash` via OpenRouter). Each paper is classified as relevant or irrelevant to climate finance. Type I error rate (flagged but LLM-relevant) and Type II error rate (unflagged but LLM-irrelevant) are reported.

### Phase D: Filtering

Flagged, non-protected papers are removed.

### Phase E: Deduplication

Enrichment steps can reintroduce duplicates from source JSONs that the merge step had already deduplicated. Two classes of duplicates are addressed:

1. **Grey-literature placeholder DOIs.** Some grey-literature documents share a fake placeholder DOI (e.g., `10.1108/meq.2003.14.4.541.3`). These are detected as normalized DOIs appearing more than once exclusively among `from_grey` records. The DOI field is cleared for these records so they are not collapsed in the next step.

2. **OpenAlex duplicate IDs.** The same paper is occasionally indexed under two different OpenAlex IDs with the same DOI. After clearing placeholder DOIs, records are deduplicated on `doi_norm`, keeping the record with the highest `cited_by_count` (best bibliometric signal). Records without a DOI (NaN `doi_norm`) are excluded from deduplication to avoid incorrectly collapsing distinct works.

An audit trail (`corpus_audit.csv`) records the decision for every paper: `keep`, `remove` (flagged), or `deduped` (dropped by deduplication).

### Phase F: Version provenance

After deduplication, a provenance column (`in_v1`) marks works that were present in the v1.0 submission corpus (git tag `v1.0-submission`). Matching uses normalized DOIs as primary identifiers, with source\_id fallback for works without DOIs. The reference identifier set is stored in `config/v1_identifiers.txt.gz`. This enables exact reproduction of v1 figures and stability checks across corpus versions.

**Result:** The refined corpus contains {{< meta corpus_total >}} papers in `refined_works.csv`.

Venue labels are normalized during filtering: mislabeled report series (e.g., "Climate finance and the USD 100 billion goal"), typos ("MF Policy Paper" → "IMF Policy Paper"), and repository-as-journal entries ("DepositOnce", "Research Online") are reclassified. See the Annex for the full list of venue-cleaning decisions.[^venue]

[^venue]: Venue-cleaning decisions: `Climate finance and the USD 100 billion goal` → report_series; `MF Policy Paper` → IMF Policy Paper (report_series); `DepositOnce` → repository_or_index; `Research Online`-type labels → repository_or_index. These matter for interpretation: institutional channels remain central in the core.
