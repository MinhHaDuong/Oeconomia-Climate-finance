## 6. Bimodality Analysis

**Script:** `scripts/analyze_bimodality.py`

This analysis tests whether the corpus is structured around two opposed intellectual communities -- an "efficiency" pole and an "accountability" pole -- using three independent methods.

### Pole vocabularies

**Efficiency terms** (15 terms): leverage, de-risking, mobilisation, mobilization, blended finance, private finance, green bond, crowding-in, bankable, risk-adjusted, financial instrument, de-risk, leveraging, green bonds, private sector.

**Accountability terms** (13 terms): additionality, over-reporting, climate justice, loss and damage, grant-equivalent, double counting, accountability, equity, concessional, oda, grant equivalent, overreporting, climate debt.

### Method A: Embedding-based axis

1. **Pole paper identification:** Papers whose abstract contains at least 2 terms from a pole vocabulary are assigned to that pole. Result: 638 efficiency-pole papers, 279 accountability-pole papers, 19 overlapping.
2. **Centroid computation:** Mean embedding of each pole's papers.
3. **Axis definition:** The difference vector (centroid_eff - centroid_acc), L2-normalized.
4. **Projection:** All 18,798 papers are projected onto this axis (dot product). Scores are median-centered (0 = midpoint). Positive scores indicate efficiency orientation; negative scores indicate accountability orientation.
5. **Explained variance:** The axis explains 3.7% of total embedding variance.

### Bimodality testing

- **Gaussian Mixture Model (GMM):** BIC comparison between 1-component and 2-component models. Result: BIC_1 = -16,910, BIC_2 = -18,174, **DBIC = 1,264** (strong evidence for bimodality; DBIC > 10 is conventionally significant).
- **KDE visualization:** Kernel density estimate with bandwidth 0.15, split by period (1990--2006, 2007--2014, 2015--2025). GMM component overlays shown as dashed grey lines.
- **Per-period bimodality:** DBIC = 22 (1990--2006, n=848), DBIC = -12 (2007--2014, n=4,578; unimodal), DBIC = 864 (2015--2025, n=13,372; strong bimodality). The bimodal structure emerges most clearly in the established-field period.

### Method B: TF-IDF lexical axis

An independent lexical validation using the same logic but on TF-IDF representations (max_features=10,000, unigrams + bigrams, sublinear_tf=True, English stopwords):

1. Mean TF-IDF vectors computed for each pole's papers.
2. Lexical axis = difference of pole means, L2-normalized.
3. All papers projected; scores median-centered.
4. **Lexical DBIC = 8,961** (even stronger bimodality signal).
5. **Embedding--lexical correlation: r = 0.683**, confirming that both representations capture the same underlying structure.

### Method C: Keyword co-occurrence

For each paper, the count of efficiency-pole and accountability-pole keywords in the abstract is computed. A 2D scatter plot (x = efficiency count, y = accountability count) with marginal histograms shows the distribution. If the field is bimodal, most papers cluster near one axis, producing an L-shaped pattern.

### Core subset analysis (`--core-only`)

When run with `--core-only`, the script restricts to papers with cited_by_count >= 50 (~1,176 papers), re-identifies pole papers within the core, and re-computes centroids and projections on core embeddings only. Output files receive a `_core` suffix (e.g., `fig5a_bimodality_core.png`, `tab5b_bimodality_core.csv`).

Core results:
- **Pole papers:** 49 efficiency, 14 accountability (much sparser than full corpus)
- **Embedding ΔBIC = 112** (moderate bimodality, down from 1,264 on full corpus)
- **TF-IDF ΔBIC = 1,058** (strong bimodality persists in lexical space)
- The divide is real in the core but less pronounced in embedding space, consistent with the core being a more thematically coherent population.

### PCA axis detection (Step 7b)

For each embedding PCA component (PC1–PC5), the script computes cosine similarity with the supervised seed axis and tests for bimodality (ΔBIC). It also correlates each PC's scores with TF-IDF features to produce interpretive term labels (top 10 positive and negative terms per PC). Results are saved to `tab5_axis_detection.csv`.

Key findings on full corpus:
- **emb_PC2** (5.4% variance, cosine = 0.557 with seed axis, ΔBIC = 932) most closely aligns with efficiency↔accountability
- **emb_PC4** (3.8%, cosine = −0.598, ΔBIC = 450) captures a CDM/mechanisms ↔ green finance axis
- The efficiency/accountability divide is real but is **not the dominant axis** — it appears at PC2, not PC1

On core:
- **emb_PC4** (cosine = 0.696 with seed axis) aligns most strongly, but max ΔBIC = 46 (no PC passes the 200 threshold for unsupervised bimodality)

### Outputs

- `fig5a_bimodality.png` -- KDE of embedding scores by period (main figure)
- `fig5b_bimodality_lexical.png` -- TF-IDF version (appendix)
- `fig5c_bimodality_keywords.png` -- keyword scatter (appendix)
- `fig5a_bimodality_core.png` -- core KDE (appendix)
- `tab5_bimodality.csv` -- summary statistics (ΔBIC, pole counts, correlation)
- `tab5_pole_papers.csv` -- per-paper axis scores and pole assignments
- `tab5_axis_detection.csv` -- PCA component alignment with seed axis + term labels
- `tab5b_bimodality_core.csv`, `tab5b_axis_detection_core.csv`, `tab5b_pole_papers_core.csv` -- core equivalents
