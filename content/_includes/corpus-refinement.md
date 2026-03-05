## 2. Corpus Refinement

The refinement script (`scripts/corpus_refine.py`) implements a four-phase pipeline:

### Phase A: Flagging

Five flags are applied to each paper:

1. **Missing metadata:** Papers lacking a title are always flagged. Papers missing only author or year are flagged only if the title also lacks "safe" domain words (a curated list of 30+ terms across English, French, German, Spanish, Chinese, and Japanese).
2. **No abstract + irrelevant title:** Papers with abstracts shorter than 50 characters whose titles lack safe domain words.
3. **Title blacklist:** Papers whose titles contain noise terms (e.g., "blockchain," "cryptocurrency," "deep learning," "metaverse") but no safe domain words.
4. **Citation isolation:** Papers published before 2020 that are neither cited by nor citing any other paper in the corpus (requires `citations.csv`; skipped when stale).
5. **Semantic outlier:** Papers whose embedding cosine distance from the corpus centroid exceeds mean + 2 standard deviations (requires `embeddings.npy`).

An abstract relevance check tests whether at least 2 of 4 concept groups (climate, finance, development, environment) appear in the text.

### Phase B: Protection

Papers are protected from removal if they meet any of: cited_by_count >= 50, appear in 2+ sources, are cited within the corpus, or appear in 2+ teaching syllabi.

### Phase C: Verification

- **Blacklist validation:** Confirms all noise-term matches in titles are properly caught.
- **LLM audit:** A stratified random sample of 50 flagged and 50 unflagged papers is submitted to `google/gemma-2-27b-it` via OpenRouter. Each paper is classified as relevant or irrelevant to climate finance. Type I error rate (flagged but LLM-relevant) and Type II error rate (unflagged but LLM-irrelevant) are reported.

### Phase D: Filtering

Flagged, non-protected papers are removed. An audit trail (`corpus_audit.csv`) records the decision for every paper.

**Result:** The refined corpus contains 22,113 papers in `refined_works.csv`.

### Venue-cleaning decisions

The following venue normalization rules were applied to ensure valid historical inference from venue tables:

- `Climate finance and the USD 100 billion goal` → treated as **report_series** (not journal).
- `MF Policy Paper` → normalized to **IMF Policy Paper**, treated as **report_series**.
- `DepositOnce` → treated as **repository_or_index** (not journal).
- `Research Online`-type labels → treated as **repository_or_index**.

These decisions matter for interpretation: institutional and repository channels remain central in the core, reinforcing the argument that economists and policy institutions (OECD, World Bank, IMF) helped structure the debate through report/working-paper infrastructures, not only journal publication.
