## 6. Alluvial Diagram

**Scripts:** `scripts/compute_alluvial.py` + `scripts/plot_fig_alluvial.py`

### Period assignment

Papers are assigned to three periods matching the manuscript's three-act structure: 1990--2006, 2007--2014, 2015--2024. Period boundaries are set at [1990, 2007, 2015, 2025).

### Cluster labeling

Cluster labels are derived from abstract TF-IDF distinctiveness rather than noisy keyword metadata:

1. A TF-IDF matrix is fitted on all abstracts (unigrams + bigrams, max_features=8000, sublinear_tf=True, English stopwords, min_df=5, max_df=0.8).
2. For each cluster, the mean TF-IDF vector is compared to the corpus-wide mean. Terms are ranked by distinctiveness (cluster mean minus corpus mean).
3. Domain-generic stopwords are removed (e.g., "climate," "finance," "paper," "study," "countries").
4. The top 3 terms are selected with bigram/unigram deduplication: if all tokens in a candidate term are already covered by previously selected terms (or their stems), the candidate is skipped.

Labels and paper counts are saved to `cluster_labels.json` and `tab_alluvial.csv`. @fig-lexical-tfidf-2007, @fig-lexical-tfidf-2015, and @fig-lexical-tfidf-2021 show the TF-IDF term distinctiveness for each cluster at three points in time.

![TF-IDF distinctive terms by cluster, 2007.](figures/fig_lexical_tfidf_2007.png){#fig-lexical-tfidf-2007 width=100%}

![TF-IDF distinctive terms by cluster, 2015.](figures/fig_lexical_tfidf_2015.png){#fig-lexical-tfidf-2015 width=100%}

![TF-IDF distinctive terms by cluster, 2021.](figures/fig_lexical_tfidf_2021.png){#fig-lexical-tfidf-2021 width=100%}

### Results

@fig-alluvial shows the full-corpus alluvial diagram; @fig-alluvial-core shows the core subset.

![Alluvial diagram: thematic flows across three periods (full corpus).](figures/fig_alluvial.png){#fig-alluvial width=100%}

![Alluvial diagram: thematic flows across three periods (core subset, cited_by_count >= {{< var corpus_core_threshold >}}).](figures/fig_alluvial_core.png){#fig-alluvial-core width=100%}

### Core share annotations

In full-corpus mode, each alluvial cell is annotated with the share of core papers (cited_by_count >= 50) it contains, showing how the influential core distributes across thematic clusters and periods.
