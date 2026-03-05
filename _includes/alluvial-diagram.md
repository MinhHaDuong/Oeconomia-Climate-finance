## 5. Alluvial Diagram

**Script:** `scripts/analyze_alluvial.py` (same script as breakpoint detection)

### Period assignment

Papers are assigned to three periods matching the manuscript's three-act structure: 1990--2006, 2007--2014, 2015--2025. Period boundaries are set at [1990, 2007, 2015, 2026).

### Cluster labeling

Cluster labels are derived from abstract TF-IDF distinctiveness rather than noisy keyword metadata:

1. A TF-IDF matrix is fitted on all abstracts (unigrams + bigrams, max_features=8000, sublinear_tf=True, English stopwords, min_df=5, max_df=0.8).
2. For each cluster, the mean TF-IDF vector is compared to the corpus-wide mean. Terms are ranked by distinctiveness (cluster mean minus corpus mean).
3. Domain-generic stopwords are removed (e.g., "climate," "finance," "paper," "study," "countries").
4. The top 3 terms are selected with bigram/unigram deduplication: if all tokens in a candidate term are already covered by previously selected terms (or their stems), the candidate is skipped.

Labels and paper counts are saved to `cluster_labels.json` and `tab2_alluvial.csv`.

### Core share annotations

In full-corpus mode, each alluvial cell is annotated with the share of core papers (cited_by_count >= 50) it contains, showing how the influential core distributes across thematic clusters and periods.
