## 3. Corpus Refinement

The full refinement pass (`corpus_refine.py --apply`) runs after enrichment (§2) has populated abstracts, citations, and embeddings. It implements a four-phase pipeline applying six flags — three cheap flags that need no external data, and three that depend on enrichment outputs.

### Phase A: Flagging

Six flags are applied to each paper:

1. **Missing metadata:** Papers lacking a title are always flagged. Papers missing only author or year are flagged only if the title also lacks "safe" domain words (a curated list of 30+ terms across English, French, German, Spanish, Chinese, and Japanese).
2. **No abstract + irrelevant title:** Papers with abstracts shorter than 50 characters whose titles lack safe domain words. (Re-evaluated after abstract enrichment — papers that gained abstracts may be unflagged.)
3. **Title blacklist:** Papers whose titles contain noise terms (e.g., "blockchain," "cryptocurrency," "deep learning," "metaverse") but no safe domain words.
4. **Citation isolation:** Papers published before 2020 that are neither cited by nor citing any other paper in the corpus. Requires `citations.csv` from §2.3.
5. **Semantic outlier:** Papers whose embedding cosine distance from the corpus centroid exceeds mean + 2 standard deviations. Requires `embeddings.npz` from §2.4.
6. **Cross-encoder relevance:** Papers with weak concept-group coverage (fewer than 2 of 4 groups: climate, finance, development, environment) are scored by a cross-encoder reranker model (`BAAI/bge-reranker-v2-m3`, 568M parameters) against the query "climate policy and financial mechanisms." Papers scoring below the calibrated threshold (0.002) are flagged as irrelevant. This replaced an earlier LLM-based classification (Gemini Flash via OpenRouter) for speed, cost, and reproducibility. See §3.1 for calibration details.

| Flag | Prerequisite | Phase available |
|------|-------------|----------------|
| 1. Missing metadata | None | Cheap filter |
| 2. No abstract | None (re-evaluated after abstract enrichment) | Cheap filter |
| 3. Title blacklist | None | Cheap filter |
| 4. Citation isolation | `citations.csv` | Full refine only |
| 5. Semantic outlier | `embeddings.npz` | Full refine only |
| 6. Cross-encoder relevance | Abstracts | Full refine only |

### 3.1 Cross-encoder calibration {#sec-reranker-calibration}

Flag 6 uses a cross-encoder reranker rather than a generative LLM to classify papers as relevant or irrelevant. Cross-encoders score a (query, document) pair by jointly encoding both through a transformer, producing a single relevance score. This is deterministic, reproducible, and runs locally on CPU without API costs.

**Model.** We use `BAAI/bge-reranker-v2-m3` (568M parameters, multilingual), loaded via the `sentence-transformers` `CrossEncoder` class. The model scores each candidate paper's title and abstract against a query string, producing a continuous relevance score. Scores are cached per DOI so that threshold adjustments do not require re-scoring.

**Query optimization.** The query string determines what the cross-encoder considers "relevant." Rather than choosing a query by hand, we searched systematically across 100 candidate queries generated from:

- 5 domain templates (e.g., "history of economic thought on climate finance," "climate finance measurement and accounting")
- 5 topic templates (e.g., "climate policy and financial mechanisms," "carbon markets and environmental finance")
- 4 syntactic variations per template (bare, with "Relevance for" prefix, with appended subtopics)
- 66 two-term combinations drawn from 12 core terms (climate finance, carbon market, green bond, adaptation finance, etc.)
- 3 hand-crafted scholarly queries

Each candidate query was evaluated on a stratified sample of 200 papers (100 positive, 100 negative) drawn from weak labels, ranked by AUC (area under the ROC curve, computed via Mann-Whitney U statistic).

**Weak labels.** To avoid circular validation against LLM outputs, we built weak labels from independent corpus signals:

- *Positive set* (~2,356 papers): papers appearing in teaching syllabi, cited 50+ times (`cited_by_count`), or discovered by 3+ independent sources (`source_count`).
- *Negative set* (~1,174 papers): papers flagged by Flags 1--3 (missing metadata, no abstract with irrelevant title, or title blacklist match), excluding any overlap with the positive set.

**Results.** The best query was "climate policy and financial mechanisms" (AUC = 0.766). The top 5 queries clustered tightly (AUC 0.75--0.77), suggesting the model's discriminative power is stable across reasonable query formulations. The bottom queries involved narrow institutional terms ("UNFCCC, Paris Agreement," AUC = 0.53), confirming that overly specific queries lose generality.

**Threshold selection.** Using the best query, all 3,530 labeled papers were scored. Score distributions are compressed near zero (positive mean = 0.032, negative mean = 0.006). An initial threshold of 0.0049 was selected via Youden's J on weak labels. This was then validated and adjusted through human-in-the-loop review.

**Human validation.** A stratified sample of 100 papers (20 per score quintile) was presented in randomized order, blinded to scores and metadata, for human labeling against the criterion: "Is this paper relevant to the history of economic thought on climate finance?" The AUC against human labels was 0.818, higher than the 0.766 against weak labels, confirming the reranker's discriminative power. The proportion of human-relevant papers increased monotonically across score quintiles (10%, 15%, 20%, 60%, 80%), showing a clear signal. However, the initial threshold of 0.0049 fell in a zone where 60% of papers were human-relevant, indicating excessive removal. The threshold was adjusted to 0.002, yielding 81% accuracy (precision = 74%, recall = 76%) on the human-labeled sample. At this threshold, strata 1--3 (scores below 0.002, where 85% of papers are irrelevant) are removed, while strata 4--5 (where 60--80% are relevant) are retained.

**Comparison with LLM backend.** The cross-encoder replaces the previous Gemini Flash (OpenRouter) / Qwen 32B (Ollama) backend. Advantages: deterministic output, no API dependency, ~5 minutes on 24 CPU threads vs. ~15 minutes with rate-limited API calls, zero marginal cost. The continuous score also enables threshold tuning without re-running the model.

### Phase B: Protection

Papers are protected from removal if they meet any of: cited_by_count >= 50, appear in 2+ sources, are cited within the corpus, or appear in 2+ teaching syllabi.

### Phase C: Verification

- **Blacklist validation:** Confirms all noise-term matches in titles are properly caught.
- **LLM audit:** A stratified random sample of 50 flagged and 50 unflagged papers is submitted to `google/gemma-2-27b-it` via OpenRouter. Each paper is classified as relevant or irrelevant to climate finance. Type I error rate (flagged but LLM-relevant) and Type II error rate (unflagged but LLM-irrelevant) are reported.

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

### Venue-cleaning decisions

The following venue normalization rules were applied to ensure valid historical inference from venue tables:

- `Climate finance and the USD 100 billion goal` → treated as **report_series** (not journal).
- `MF Policy Paper` → normalized to **IMF Policy Paper**, treated as **report_series**.
- `DepositOnce` → treated as **repository_or_index** (not journal).
- `Research Online`-type labels → treated as **repository_or_index**.

These decisions matter for interpretation: institutional and repository channels remain central in the core, reinforcing the argument that economists and policy institutions (OECD, World Bank, IMF) helped structure the debate through report/working-paper infrastructures, not only journal publication.
