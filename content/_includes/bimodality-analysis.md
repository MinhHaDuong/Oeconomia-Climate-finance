## 7. Bimodality Analysis

**Script:** `scripts/analyze_bimodality.py`

This analysis tests whether the corpus is structured around two opposed intellectual communities -- an "efficiency" pole and an "accountability" pole -- using three independent methods.

### Pole vocabularies

**Efficiency terms** (15 terms): leverage, de-risking, mobilisation, mobilization, blended finance, private finance, green bond, crowding-in, bankable, risk-adjusted, financial instrument, de-risk, leveraging, green bonds, private sector.

**Accountability terms** (13 terms): additionality, over-reporting, climate justice, loss and damage, grant-equivalent, double counting, accountability, equity, concessional, oda, grant equivalent, overreporting, climate debt.

### Method A: Embedding-based axis

1. **Pole paper identification:** Papers whose abstract contains at least 2 terms from a pole vocabulary are assigned to that pole. Result: {{< var bim_n_efficiency >}} efficiency-pole papers, {{< var bim_n_accountability >}} accountability-pole papers, {{< var bim_n_overlap >}} overlapping.
2. **Centroid computation:** Mean embedding of each pole's papers.
3. **Axis definition:** The difference vector (centroid_eff - centroid_acc), L2-normalized.
4. **Projection:** All {{< var corpus_with_embeddings >}} papers are projected onto this axis (dot product). Scores are median-centered (0 = midpoint). Positive scores indicate efficiency orientation; negative scores indicate accountability orientation.
5. **Explained variance:** The axis explains {{< var bim_var_pct >}}% of total embedding variance.

### Bimodality testing

- **Gaussian Mixture Model (GMM):** BIC comparison between 1-component and 2-component models. Result: BIC_1 = {{< var bim_bic1 >}}, BIC_2 = {{< var bim_bic2 >}}, **ΔBIC = {{< var bim_dbic_embedding >}}** (strong evidence for bimodality; ΔBIC > 10 is conventionally significant).
- **KDE visualization:** Kernel density estimate with bandwidth 0.15, split by period (1990--2006, 2007--2014, 2015--2024). GMM component overlays shown as dashed grey lines. @fig-kde shows the overall KDE of embedding scores.
- **Per-period bimodality:** ΔBIC = {{< var bim_dbic_pre2007 >}} (1990--2006, n={{< var bim_n_pre2007 >}}), ΔBIC = {{< var bim_dbic_2007_2014 >}} (2007--2014, n={{< var bim_n_2007_2014 >}}; unimodal), ΔBIC = {{< var bim_dbic_post2015 >}} (2015--2024, n={{< var bim_n_post2015 >}}; strong bimodality). The bimodal structure emerges most clearly in the established-field period.

![KDE of embedding axis scores with GMM component overlay.](figures/fig_kde.png){#fig-kde width=100%}

### Method B: TF-IDF lexical axis

An independent lexical validation using the same logic but on TF-IDF representations (max_features=10,000, unigrams + bigrams, sublinear_tf=True, English stopwords):

1. Mean TF-IDF vectors computed for each pole's papers.
2. Lexical axis = difference of pole means, L2-normalized.
3. All papers projected; scores median-centered.
4. **Lexical ΔBIC = {{< var bim_dbic_tfidf >}}** (even stronger bimodality signal).
5. **Embedding--lexical correlation: r = {{< var bim_corr >}}**, confirming that both representations capture the same underlying structure.

### Method C: Keyword co-occurrence

For each paper, the count of efficiency-pole and accountability-pole keywords in the abstract is computed. A 2D scatter plot (x = efficiency count, y = accountability count) with marginal histograms shows the distribution. If the field is bimodal, most papers cluster near one axis, producing an L-shaped pattern.

### Core subset analysis (`--core-only`)

When run with `--core-only`, the script restricts to papers with cited_by_count >= {{< var corpus_core_threshold >}} (~{{< var corpus_core >}} papers), re-identifies pole papers within the core, and re-computes centroids and projections on core embeddings only. Output files receive a `_core` suffix (e.g., `fig_bimodality_core.png`, `tab_bimodality_core.csv`).

Core results:
- **Pole papers:** {{< var bim_core_n_efficiency >}} efficiency, {{< var bim_core_n_accountability >}} accountability (much sparser than full corpus)
- **Embedding ΔBIC = {{< var bim_core_dbic_embedding >}}** (moderate bimodality, down from {{< var bim_dbic_embedding >}} on full corpus)
- **TF-IDF ΔBIC = {{< var bim_core_dbic_tfidf >}}** (strong bimodality persists in lexical space)
- The divide is real in the core but less pronounced in embedding space, consistent with the core being a more thematically coherent population.

### PCA axis detection (Step 7b)

For each embedding PCA component (PC1–PC5), the script computes cosine similarity with the supervised seed axis and tests for bimodality (ΔBIC). It also correlates each PC's scores with TF-IDF features to produce interpretive term labels (top 10 positive and negative terms per PC). Results are saved to `tab_axis_detection.csv`.

Key findings on full corpus:
- **emb_PC2** ({{< var pca_emb_pc2_var_pct >}}% variance, cosine = {{< var pca_emb_pc2_cosine >}} with seed axis, ΔBIC = {{< var pca_emb_pc2_dbic >}}) most closely aligns with efficiency↔accountability
- **emb_PC4** ({{< var pca_emb_pc4_var_pct >}}%, cosine = {{< var pca_emb_pc4_cosine >}}, ΔBIC = {{< var pca_emb_pc4_dbic >}}) captures a CDM/mechanisms ↔ green finance axis
- The efficiency/accountability divide is real but is **not the dominant axis** — it appears at PC2, not PC1

On core:
- **emb_PC4** (cosine = 0.696 with seed axis) aligns most strongly, but max ΔBIC = 46 (no PC passes the 200 threshold for unsupervised bimodality)

### Figures

![KDE of embedding axis scores by period, full corpus.](figures/fig_bimodality.png){#fig-bimodality width=100%}

![TF-IDF lexical axis scores by period.](figures/fig_bimodality_lexical.png){#fig-bimodality-lexical width=100%}

![Keyword co-occurrence scatter: efficiency vs. accountability term counts.](figures/fig_bimodality_keywords.png){#fig-bimodality-keywords width=100%}

![KDE of embedding axis scores, core subset.](figures/fig_bimodality_core.png){#fig-bimodality-core width=100%}

![TF-IDF lexical axis scores, core subset.](figures/fig_bimodality_lexical_core.png){#fig-bimodality-lexical-core width=100%}

![Keyword co-occurrence scatter, core subset.](figures/fig_bimodality_keywords_core.png){#fig-bimodality-keywords-core width=100%}

### Data outputs

- `tab_bimodality.csv` -- summary statistics (ΔBIC, pole counts, correlation)
- `tab_pole_papers.csv` -- per-paper axis scores and pole assignments
- `tab_axis_detection.csv` -- PCA component alignment with seed axis + term labels
- `tab_bimodality_core.csv`, `tab_axis_detection_core.csv`, `tab_pole_papers_core.csv` -- core equivalents
