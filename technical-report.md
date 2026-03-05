# Technical Report: Data Analysis Pipeline

Ha Duong Minh, 2026-03-03

This document describes the computational pipeline used to produce the bibliometric analysis in "How Climate Finance Became an Economic Object" (submitted to *Oeconomia*). The pipeline transforms a multi-source literature corpus into five figures and their associated robustness checks. All scripts are in `scripts/`, all generated data in `~/data/projets/Oeconomia-Climate-finance/catalogs/` (configurable via the `CLIMATE_FINANCE_DATA` environment variable), and all outputs in `figures/` and `tables/`.

---

## 1. Corpus Construction

### Sources

The corpus assembles academic and grey literature from seven sources:

| Source | Script | Records | Coverage |
|---|---|---|---|
| OpenAlex | `catalog_openalex.py` | ~11,313 | Broad English-language academic literature |
| OpenAlex (historical) | `catalog_openalex_historical.py` | variable | Pre-2000 and non-English historical works |
| ISTEX | `catalog_istex.py` | 482 | French national archive (full-text JSON) |
| bibCNRS | `catalog_bibcnrs.py` | 242 | Non-English literature (FR, ZH, JA, DE) |
| SciSpace | `catalog_scispsace.py` | 663 | AI-curated thematic corpus |
| Grey literature | `catalog_grey.py` | 213 | OECD, UNFCCC, World Bank, CPI reports |
| Teaching canon | manual | variable | Papers appearing in 2+ syllabi |

### Search strategy

- **OpenAlex:** Cursor-paginated queries using `filter=default.search:"climate finance"` and `filter=default.search:"finance climat"` (captures French variants). Abstracts reconstructed from OpenAlex inverted index format. Polite-pool access with `mailto` header.
- **ISTEX:** Full-text query `"climate finance" OR "finance climat" OR "finance climatique"` on the national archive.
- **bibCNRS:** Title-field searches in French (`"finance climat" OR "finance climatique"`), Chinese (气候融资 OR 气候金融), Japanese (気候金融 OR グリーンファイナンス OR 気候ファイナンス), and German. Manual RIS export.
- **Grey literature:** A curated YAML seed list (16 key policy documents) plus the World Bank Open Knowledge Repository API (query `"climate finance"`, first 200 results).

### Merge and deduplication

The merge script (`scripts/catalog_merge.py`) applies two deduplication passes:

1. **DOI-based deduplication:** DOIs are normalized (lowercased, URL prefix stripped). Records sharing the same DOI are merged using a source priority order: openalex > openalex_historical > scopus > istex > jstor > bibcnrs > scispsace > grey > teaching. The maximum `cited_by_count` across duplicates is retained; other fields use the best non-empty value following source priority.
2. **Title+year deduplication:** Records without DOIs are grouped by normalized title (lowercased, punctuation stripped) and year. Groups are merged using the same priority logic.

A `source_count` field tracks how many sources contributed to each record. The output is `unified_works.csv`.

---

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

---

## 3. Embedding Generation

**Script:** `scripts/analyze_embeddings.py`

**Model:** `paraphrase-multilingual-MiniLM-L12-v2` (sentence-transformers library). This is a 12-layer multilingual BERT producing 384-dimensional vectors, chosen for its ability to place abstracts in English, French, Chinese, Japanese, and German into a shared semantic space.

**Input selection:** Papers from `refined_works.csv` with an abstract longer than 50 characters and a publication year between 1990 and 2025.

**Encoding parameters:**
- Batch size: 256
- Normalization: L2-normalized embeddings
- Runtime: approximately 16 minutes on CPU for ~18,800 abstracts

**Output:** `embeddings.npy` -- a NumPy array of shape (18,798 x 384), cached for reuse by downstream scripts. A size-consistency check ensures the embedding count matches the filtered DataFrame row count.

**Additional outputs:**
- UMAP projection (n_components=2, n_neighbors=15, min_dist=0.05, cosine metric, random_state=42)
- KMeans clustering (k=6, n_init=20, random_state=42) on UMAP coordinates
- Cluster assignments saved to `semantic_clusters.csv`

---

## 4. Structural Break Detection

**Script:** `scripts/analyze_alluvial.py`

This analysis detects endogenous structural breaks in the temporal evolution of the corpus's thematic composition. Rather than imposing external periodizations from COP milestones or policy events, we ask: at what years did the *semantic structure* of climate finance scholarship shift most sharply?

### Clustering

KMeans (k=6, n_init=20, random_state=42) is fitted once on the full embedding space (384 dimensions, no dimensionality reduction). Each paper receives a cluster label. This global fit ensures that thematic categories are consistent across all time windows. The minimum sample size per window is N_MIN=30 for the full corpus, reduced to 20 for the core subset.

### Sliding-window divergence

For each candidate boundary year *y* in [2005, 2023], and for each window half-width *w* in {2, 3, 4}, we compare two adjacent time slices:

- **Before window**: papers with publication year in [*y* − *w*, *y*] (*w* + 1 years)
- **After window**: papers with publication year in [*y* + 1, *y* + 1 + *w*] (*w* + 1 years)

Two complementary metrics quantify the shift:

1. **Jensen-Shannon (JS) divergence** on the cluster proportion vectors. Each window's papers are binned into the 6 clusters, producing a probability distribution over themes. JS divergence measures how much these thematic compositions differ. It is sensitive to *redistribution across clusters* — a shift in which topics dominate.

2. **Cosine distance** between the mean embedding vectors of each window. This captures movement in the continuous semantic space, sensitive to *within-cluster drift* that JS might miss.

Both metrics are z-score normalized across the 19 candidate years (2005–2023) for each window size, making scores comparable across metrics and windows.

### Censored gap variant

An optional censoring parameter *k* (command-line flag `--censor-gap`) shifts the before-window back by *k* years, creating a gap around the candidate boundary:

- **Censored before window**: [*y* − *w* − *k*, *y* − *k*]
- **After window**: [*y* + 1, *y* + 1 + *w*] (unchanged)

With *k* = 0 this is the baseline test. With *k* > 0, the *k* transition years immediately before the boundary are excluded. This guards against the objection that breakpoints are artifacts of gradual blending rather than genuine discontinuities: if the break is real, comparing "clearly before" with "after" should produce an equal or stronger signal.

### Breakpoint detection

Local maxima above z = 1.5 are identified as candidates, subject to the constraint that each candidate must exceed both its neighbours. A breakpoint is **robust** if it appears (within ±1 year tolerance) as a peak in at least 2 of the 3 window sizes. Robust peaks from JS and cosine are then combined. Breakpoints supported by both metrics are flagged "both"; single-metric support is flagged "JS only" or "cosine only."

### Volume confound check

Because the corpus grows rapidly over time, divergence peaks could be driven by uneven sample sizes rather than thematic change. We compute Pearson correlations between each divergence series and the year-over-year growth rate of paper counts. Correlations |*r*| > 0.5 would flag a confounded metric.

### Results: full corpus (N = 18,798)

#### Baseline (*k* = 0)

Two robust breakpoints are detected:

| Year | JS mean z | Cosine mean z | Combined z | Support | Windows |
|------|-----------|---------------|------------|---------|---------|
| 2007 | 0.00 | 2.59 | 2.59 | cosine only | 3 of 3 |
| 2013 | 1.59 | 0.00 | 1.59 | JS only | 3 of 3 |

The 2007 break is driven by cosine distance — a shift in the *semantic centre of mass* of the field, consistent with climate finance emerging as a distinct topic around the Bali Action Plan and the Stern Review's influence. The 2013 break is driven by JS divergence — a *redistribution across clusters*, consistent with the diversification of the field into sub-specialties (green bonds, REDD+, adaptation finance) around the time of the Warsaw International Mechanism.

No break is detected near 2015 (Paris Agreement) or 2021 (Glasgow). The COP milestones that dominate policy narrative do not correspond to discontinuities in the scholarly literature's structure.

**Volume confound check.** All six correlations (JS and cosine × 3 windows) are below the |*r*| > 0.5 threshold (range: *r* = −0.41 to *r* = +0.38, all *p* > 0.08). The breakpoints are not confounded by corpus growth.

#### Censored gap *k* = 1

Removing 1 transition year before each boundary sharpens the picture:

| Year | JS mean z | Cosine mean z | Combined z | Support |
|------|-----------|---------------|------------|---------|
| 2008 | 0.00 | 2.22 | 2.22 | cosine only |
| 2015 | 1.75 | 0.00 | 1.75 | JS only |
| 2013 | 1.73 | 0.00 | 1.73 | JS only |

The cosine break migrates one year forward (2007 → 2008), which is within the ±1 year tolerance and reflects the same underlying transition. The notable addition is **2015** (JS, z = 1.75): with the transition year removed, Paris Agreement effects on thematic redistribution become detectable — but only marginally, and not supported by cosine distance.

#### Censored gap *k* = 2

With a 2-year gap, only one breakpoint survives:

| Year | JS mean z | Cosine mean z | Combined z | Support |
|------|-----------|---------------|------------|---------|
| 2009 | 0.00 | 2.15 | 2.15 | cosine only |

The sole surviving break at **2009** (Copenhagen COP) confirms that the late-2000s semantic shift is the dominant structural feature of the corpus. The 2013 JS break disappears, suggesting it reflects a more gradual thematic redistribution that does not survive the removal of adjacent years. The 2009 result aligns with the thesis that climate finance crystallized as a distinct economic object around the Copenhagen moment.

### Results: core subset (N = 1,176, cited_by_count ≥ 50)

The core subset contains only highly-cited papers — the *influential* works that define the field's intellectual structure.

#### Baseline (*k* = 0)

| Year | JS mean z | Cosine mean z | Combined z | Support |
|------|-----------|---------------|------------|---------|
| 2023 | 3.50 | 3.65 | 7.15 | both |

No break is detected in the 2005–2020 range. The only robust signal is at **2023**, driven by extremely high z-scores on both metrics. This is a **boundary artifact**: recent papers (2022–2025) have not yet accumulated enough citations to enter the core subset, creating a composition discontinuity at the edge of the observation window.

#### Censored gap *k* = 1

| Year | JS mean z | Cosine mean z | Combined z | Support |
|------|-----------|---------------|------------|---------|
| 2023 | 3.54 | 3.68 | 7.22 | both |

Same boundary artifact. Censoring does not resolve it.

#### Censored gap *k* = 2

| Year | JS mean z | Cosine mean z | Combined z | Support |
|------|-----------|---------------|------------|---------|
| 2023 | 3.27 | 3.71 | 6.99 | both |

The 2023 signal weakens slightly but persists. No mid-period break appears.

### Interpretation

The two-sample comparison yields a key finding: **the structural breaks of 2007–2009 are driven by the influx of new, lower-cited scholarship, not by a reorientation of influential works.** The core papers — the field's intellectual backbone — show no thematic discontinuity across the entire 2005–2020 period. The categories through which economists analyse climate finance (carbon markets, green bonds, adaptation, accountability) were established by the mid-2000s; what changed after 2007–2009 was the *volume and breadth* of scholarship working within those categories, not the categories themselves.

The censored-gap analysis reinforces the main breakpoint at **2009** (Copenhagen) as the most robust single-year discontinuity. The 2013 break (baseline) and 2015 break (censored *k* = 1) represent secondary, more gradual thematic redistributions that are sensitive to the exact window specification.

#### Summary

| Corpus | *k* = 0 | *k* = 1 | *k* = 2 |
|--------|---------|---------|---------|
| Full (18,798) | **2007**, **2013** | **2008**, 2013, 2015 | **2009** |
| Core (1,176) | 2023* | 2023* | 2023* |

\* Boundary artifact only.

---

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

---

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

---

## 7. PCA Scatter Plots

**Script:** `scripts/plot_fig45_pca_scatter.py`

This script visualizes how the field's thematic structure evolves over time by plotting individual papers in year × axis-score space.

### Supervised mode (`--supervised`)

Projects all papers onto the efficiency↔accountability seed axis (identical to Section 6's Method A axis). Produces a single-panel scatter plot:
- **X-axis:** publication year (with ±0.3 uniform jitter to reduce overplotting)
- **Y-axis:** seed axis score (positive = efficiency, negative = accountability)
- **Color:** three-period scheme (blue 1990–2006, orange 2007–2014, green 2015–2025)
- **Point size:** proportional to sqrt(cited_by_count / 50)
- **Black line:** yearly median score (smoother)
- **Vertical dashes:** COP events (Rio, Kyoto, Copenhagen, Paris, Glasgow, Baku)
- **Period bands:** light background shading for each period

Recommended with `--core-only` for the paper figure (`fig4_seed_axis_core.png`), showing 1,176 influential papers. The seed axis is bimodal in core (ΔBIC = 112), and the yearly median reveals a drift from the accountability side toward efficiency over time.

### Unsupervised mode (default)

Runs PCA (10 components) on embeddings, tests each PC for bimodality (1- vs 2-component GMM), and plots one panel per PC with ΔBIC > 200. Each PC's poles are labelled using the top 3 TF-IDF terms correlated with positive and negative scores.

On full corpus (18,798 papers), 3 PCs qualify:
| PC | Variance | ΔBIC | (+) pole | (−) pole |
|----|----------|------|----------|----------|
| PC2 | 5.4% | 932 | green, financial, sustainability | carbon, emissions, climate change |
| PC3 | 4.1% | 390 | land, forest, biomass | agreement, paris, finance |
| PC4 | 3.8% | 450 | cdm, clean development | finance, green, financial |

On core (1,176 papers), no PC passes ΔBIC > 200 (max = 46). Unsupervised bimodality requires the full corpus's breadth to emerge.

### Outputs

- `fig4_seed_axis_core.png` -- supervised axis, core papers (paper figure)
- `fig4_pca_scatter.png` -- unsupervised 3-panel, full corpus (appendix)
- `tab4_seed_axis_core.csv` -- seed axis metadata (variance, ΔBIC, pole terms)
- `tab4_pca_components.csv` -- unsupervised PC metadata

---

## 8. Citation Genealogy

**Script:** `scripts/analyze_genealogy.py`

### Backbone selection

Papers from `refined_works.csv` with an abstract longer than 50 characters, a valid year in 1985--2025, and cited_by_count >= 50 form the backbone. Result: approximately 1,128 backbone papers.

### Three-band lineage assignment

Each backbone paper is assigned to one of three bands using two data sources:

1. **KMeans semantic clusters** (from `semantic_clusters.csv`): cluster 2 corresponds to CDM/projects/mechanism literature.
2. **Bimodality axis scores** (from `tab5_pole_papers.csv`): papers with negative axis scores lean accountability; positive scores lean efficiency.

Assignment logic:
- If a paper belongs to KMeans cluster 2 (CDM), it is assigned to **Band 0: CDM / Kyoto heritage**.
- Otherwise, if its bimodality axis score < 0, it is assigned to **Band 1: Accountability pole**.
- Otherwise, it is assigned to **Band 2: Efficiency pole**.

### Citation DAG construction

Internal citation edges are extracted from `citations.csv`: an edge (A -> B) exists when cited paper A and citing paper B are both in the backbone. Edges are deduplicated.

### Layout

- **X-axis:** Publication year (normalized to [0, 1]).
- **Y-axis:** Lineage band. Bands are ordered by median year of their papers (foundational at top). Within each band, papers from the same year are jittered vertically for readability.
- **Node size:** Proportional to the square root of citation count (scaled by sqrt(cited_by_count / 200)).
- **Cross-lineage arcs:** The top 15 cross-lineage citation edges (ranked by combined citation count of source and target) are highlighted with Bezier arcs.

### Outputs

- `fig4_genealogy.{png,pdf}` -- static figure
- `fig4_genealogy.html` -- interactive HTML/SVG version with hover tooltips and DOI click-through
- `tab3_lineages.csv` -- lineage assignments for all backbone papers

---

## 9. Core vs. Full Corpus Analysis

The pipeline implements a two-level analytical design:

### Full corpus (18,798 papers with embeddings)

The broad landscape of "scholarship around climate finance." This includes not only specialized climate finance papers but also adjacent work in environmental economics, green finance, energy policy, and development economics. The full corpus captures the field's periphery and the volume of new entrants over time.

### Core subset (~1,176 papers, cited_by_count >= 50)

The influential intellectual core. These are the papers that have shaped the field's concepts, debates, and categories. The core subset is analyzed separately by passing `--core-only` to `analyze_alluvial.py`.

### Key differences

- **Breakpoints:** The full corpus shows structural breaks at 2007 and 2013. The core subset shows no break in the 2007--2015 range; its only detected break is at 2023 (likely an edge effect). This indicates that structural shifts in the full corpus are driven by the influx of new scholarship, not by changes in the core community's thematic composition.
- **Alluvial:** The core alluvial shows a more stable thematic structure across periods, while the full-corpus alluvial captures the growth of new thematic clusters (e.g., green bonds, ESG).
- **Clustering:** KMeans is re-fitted on core embeddings independently (not inherited from the full corpus), with min_df=3 and N_MIN=20 to accommodate the smaller sample.
- **Bimodality:** The efficiency↔accountability divide is present in both samples but manifests differently. Full corpus: ΔBIC = 1,264 (strong). Core: ΔBIC = 112 (embedding), 1,058 (TF-IDF). The lexical signal is stronger in core because influential papers use more distinctive vocabulary; the embedding signal is weaker because the core is more thematically coherent.
- **Unsupervised PCA bimodality:** Three PCs show bimodality (ΔBIC > 200) in the full corpus; none do in the core (max ΔBIC = 46). The unsupervised discovery of bimodal axes requires the full corpus's breadth. The supervised seed axis remains bimodal in core, confirming that the divide is real but not dominant enough to emerge unsupervised from only 1,176 papers.

### Rationale

The two-level design disentangles two dynamics: (1) the diversification of the broader literature, visible in the full corpus, and (2) the consolidation of the intellectual core, visible in the core subset. Their divergence supports the article's argument that the field's foundational categories crystallized early and have remained stable even as the volume of surrounding literature has grown.

---

## 10. Reproducibility

### Environment setup

```bash
uv sync    # installs all dependencies from pyproject.toml
```

Key packages: pandas, numpy, scikit-learn, scipy, matplotlib, seaborn, sentence-transformers, torch (CPU-only, pinned via `[tool.uv.sources]`), networkx, python-louvain, hdbscan, umap-learn, adjustText, diptest (optional). Python >= 3.10.

### Script execution order

The pipeline has strict data dependencies. Scripts must be run in this order:

```bash
# Stage 1: Corpus construction (requires API access or local data)
uv run python scripts/catalog_istex.py              # parse ISTEX JSON
uv run python scripts/catalog_openalex.py            # query OpenAlex API (~15 min)
uv run python scripts/catalog_openalex_historical.py # historical works
uv run python scripts/catalog_bibcnrs.py             # parse bibCNRS RIS exports
uv run python scripts/catalog_scispsace.py           # parse SciSpace CSVs
uv run python scripts/catalog_grey.py                # World Bank API + YAML seeds

# Stage 2: Merge and refine
uv run python scripts/catalog_merge.py               # → unified_works.csv
uv run python scripts/corpus_refine.py --apply       # → refined_works.csv (22,113)

# Stage 3: Embeddings (slow, ~16 min CPU)
uv run python scripts/analyze_embeddings.py          # → embeddings.npy (18,798 x 384)

# Stage 4: Co-citation (depends on citations.csv from enrich_citations.py)
uv run python scripts/analyze_cocitation.py          # → communities.csv

# Stage 5: Figures (each depends on refined_works.csv + embeddings.npy)
uv run python scripts/plot_fig1_emergence.py         # Fig 1: emergence
uv run python scripts/analyze_alluvial.py            # Figs 2 + 3: breakpoints + alluvial
uv run python scripts/analyze_alluvial.py --core-only   # Figs 2b + 3b: core analysis
uv run python scripts/analyze_bimodality.py          # Fig 5: bimodality (must run before genealogy)
uv run python scripts/analyze_bimodality.py --core-only  # Fig 5 core variant
uv run python scripts/analyze_genealogy.py           # Fig 4: citation genealogy
uv run python scripts/plot_fig45_pca_scatter.py --core-only --supervised  # Fig 4: seed axis scatter (paper)
uv run python scripts/plot_fig45_pca_scatter.py      # Fig 4: unsupervised PCA scatter (appendix)

# Stage 6: Robustness appendices
uv run python scripts/analyze_alluvial.py --robustness   # k-sensitivity (k=4,5,6,7)
uv run python scripts/analyze_alluvial.py --core-only --censor-gap 1  # censored breaks
uv run python scripts/analyze_alluvial.py --core-only --censor-gap 2
uv run python scripts/analyze_alluvial.py --censor-gap 1
uv run python scripts/analyze_alluvial.py --censor-gap 2
uv run python scripts/analyze_genealogy.py --robustness  # Louvain resolution sensitivity
```

### Data dependencies

| Script | Reads | Writes |
|---|---|---|
| `catalog_merge.py` | `*_works.csv` | `unified_works.csv` |
| `corpus_refine.py` | `unified_works.csv`, `citations.csv`*, `embeddings.npy`* | `refined_works.csv`, `corpus_audit.csv` |
| `analyze_embeddings.py` | `refined_works.csv` | `embeddings.npy`, `semantic_clusters.csv` |
| `analyze_alluvial.py` | `refined_works.csv`, `embeddings.npy` | `fig2_breakpoints`, `fig3_alluvial`, `tab2_*.csv`, `cluster_labels.json` |
| `analyze_bimodality.py` | `refined_works.csv`, `embeddings.npy` | `fig5a/5b/5c`, `tab5_bimodality.csv`, `tab5_pole_papers.csv`, `tab5_axis_detection.csv` |
| `analyze_genealogy.py` | `refined_works.csv`, `citations.csv`, `semantic_clusters.csv`, `tab5_pole_papers.csv` | `fig4_genealogy`, `tab3_lineages.csv` |
| `plot_fig45_pca_scatter.py` | `refined_works.csv`, `embeddings.npy` | `fig4_seed_axis_core`, `fig4_pca_scatter`, `tab4_*.csv` |

\* Optional; skipped with `--skip-citation-flag` or when file is absent.

### Data location

All generated data lives outside the repository at `~/data/projets/Oeconomia-Climate-finance/`. This path can be overridden by setting the `CLIMATE_FINANCE_DATA` environment variable. The `scripts/utils.py` module resolves `BASE_DIR` (repository root) and `CATALOGS_DIR` (data/catalogs/) for all scripts.

### Expected runtimes (CPU)

| Step | Time |
|---|---|
| OpenAlex harvest | ~15 min |
| Crossref citation enrichment | ~3--4 hours |
| Embedding generation | ~16 min |
| Breakpoint + alluvial analysis | ~2 min |
| Bimodality analysis | ~1 min |
| Citation genealogy | ~1 min |

### RePEc local mirror

The script `count_repec_econ_cf.py` reads from a local mirror of the RePEc ReDIF archives, providing an independent economics baseline for Figure 1.

```bash
# Mirror setup (several GB, ~30 min)
mkdir -p ~/data/datasets/external/RePEc
rsync -va --delete rsync://rsync.repec.org/RePEc-ReDIF/ ~/data/datasets/external/RePEc/
```

The mirror was last synced 2026-02-26 (~2,334 archive directories). Re-run the same rsync command to update. Override the default path with `REPEC_ROOT` environment variable or `--repec-root` flag.

### Cross-machine reproducibility

Figures that do not involve KMeans clustering (fig1_emergence, fig4_genealogy, fig4_seed_axis_core, figA_1a_robustness) are **byte-identical** across machines when `PYTHONHASHSEED=0` and `SOURCE_DATE_EPOCH=0` are set (the Makefile exports both).

Figures that depend on KMeans (fig2_breakpoints, fig3_alluvial, fig5a_bimodality, and their core variants) may differ across machines. This is because scikit-learn's KMeans delegates to platform-specific BLAS routines (OpenBLAS, MKL, Apple Accelerate), and floating-point summation order in distance computations is not guaranteed across implementations. The resulting cluster assignments can differ at the margin, producing visually similar but not byte-identical figures. Substantive results (breakpoint years, ΔBIC values, period boundaries) are robust to these differences.

### Non-reproducible steps

- ISTEX corpus download (requires institutional access)
- bibCNRS export (requires CNRS Janus credentials, manual browser export)
- Citation enrichment timing may vary due to Crossref index updates
- LLM audit (requires `OPENROUTER_API_KEY`; can be skipped with `--skip-llm`)
- RePEc mirror requires rsync access to `rsync.repec.org`

All scripts support a `--no-pdf` flag to skip PDF generation and produce PNG only.
