# Climate Finance corpus analysis plan

Ha Duong Minh, 2026-02-26 (v2 — revised after breakpoint results)

## Summary of changes from v1

1. **Three-act periodization** replaces four-section structure. Data shows breaks at 2007 and 2013, nothing at 2021 → merge old sections III and IV.
2. **Figures renumbered**: breakpoints and alluvial are now separate figures (Fig 2, Fig 3). Genealogy becomes Fig 4.
3. **Figure 1 redesigned**: three series on common timeline — economics publications in OpenAlex, "climate" in title in OpenAlex, and climate finance corpus — to show the field emerging *within* economics, not *from* climate science.
4. **New analysis (Fig 5)**: two-communities hypothesis test — bimodality along a well-defined semantic axis (efficiency vs. accountability), both embedding-based and lexical.

---

## Revised article structure (three acts)

The breakpoint analysis detected two robust structural breaks (2007, 2013) and *no* break around 2015 or 2021. The lexical TF-IDF validation confirms that only 2009 produces a wholesale vocabulary reorientation; 2015 and 2021 are thematic inflections within an already-constituted field.

This implies a three-act narrative:

| Section | Period | Data support |
|---|---|---|
| **I. Before climate finance** | 1990–2006 | Formative phase. Sparse literature, pre-Copenhagen vocabulary (CDM, Kyoto, development aid). |
| **II. Crystallization** | 2007–2014 | Two detected breaks bracket a period of rapid emergence. Copenhagen $100bn pledge (2009), GCF creation (2010), Standing Committee on Finance (2011). The field's vocabulary, categories, and intellectual communities form during this period. |
| **III. The established field** | 2015–2025 | No further structural breaks detected. Paris, Glasgow, Baku NCQG — institutional milestones that reanchor but don't restructure the field. Metrisation, contestation, green finance expansion, and NCQG all happen *within* stable intellectual categories. |

The punchier thesis: climate finance crystallized as an economic object around 2009, and everything since — including the fierce $100bn accounting disputes and the $300bn NCQG — has been fought *within* the categories established at that moment.

---

## Figure plan (5 figures)

### Figure 1: The emergence of climate finance in economics (NEW)

**Script**: `scripts/analyze_temporal.py` (rewrite)

**What it shows**: Three time series on a common timeline (1990–2025):

1. **Economics publications in OpenAlex** (by year) — the denominator. Shows the overall growth of the discipline. Query: OpenAlex works with `concept.id` = Economics (level 0), group by year.
2. **Publications with "climate" in title in OpenAlex** (by year) — the broader climate literature within economics. Query: OpenAlex works with concept Economics AND title contains "climate", group by year.
3. **Climate finance publications in our corpus** (by year) — the specific field. From `refined_works.csv` as currently done.

**Why this matters**: The current Fig 1 shows only the corpus bar chart with indexed baselines. The new version makes the argument visually: climate finance doesn't emerge from climate science generally — it emerges as a specific *economic* object after Copenhagen. Series 1 grows linearly. Series 2 grows faster. Series 3 explodes after 2009. The ratio series3/series1 is the economization story.

**Data source**: OpenAlex API queries (two new queries, cached as JSON). The existing `openalex_baselines.json` already has "all science" and "climate change literature" — we replace those with the two economics-specific series. No new dependencies.

**Layout**: Left y-axis = absolute publication counts (log scale or linear). All three series as lines (not bars) to allow comparison. COP events annotated as before. Period bands from the three-act structure in background.

**Output**: `figures/fig1_emergence.{pdf,png}`, `data/catalogs/openalex_economics_baselines.json`

---

### Figure 2: Structural break detection (EXISTING — renumbered, was Fig 2a)

**Script**: `scripts/analyze_alluvial.py` (no change to breakpoint code)

**What it shows**: Z-scored JS divergence time series for w=2,3,4, with detected breakpoints as vertical bands and COP milestones as dashed lines.

**Key result**: Bimodal breaks at 2007 (cosine-supported, 3/3 windows) and 2013 (JS-supported, 3/3 windows). No break near 2015 or 2021. This is the empirical foundation for the three-act periodization.

**Output**: `figures/fig2_breakpoints.{pdf,png}`, `tables/tab2_breakpoints.csv`, `tables/tab2_breakpoint_robustness.csv`

---

### Figure 3: Thematic recomposition (EXISTING — renumbered, was Fig 2b)

**Script**: `scripts/analyze_alluvial.py` (no change to alluvial code)

**What it shows**: Alluvial diagram with data-derived periods. Currently four periods: 1990–2006, 2007–2012, 2013–2014, 2015–2025. This may need adjustment: the 2013–2014 band is very thin (2 years) and could be collapsed.

**Decision needed**: Keep 4 periods in alluvial (showing the brief transition), or collapse to 3 matching the article sections? The 4-period version is more faithful to the data (both breaks are real); the 3-period version is cleaner narratively. Recommendation: keep 4 in the figure but narrate as 3 acts in the text. The thin 2013–2014 band *is* the consolidation moment.

**Output**: `figures/fig3_alluvial.{pdf,png}`, `tables/tab2_alluvial.csv`

Note: rename from fig2_alluvial to fig3_alluvial.

---

### Figure 4: Citation genealogy (EXISTING — renumbered, was Fig 3)

**Script**: `scripts/analyze_genealogy.py` (update period bands to match three-act structure)

**What it shows**: Time-ordered citation DAG of intellectual communities. Same as before but with updated period background bands.

**Output**: `figures/fig4_genealogy.{pdf,png,html}`, `tables/tab3_lineages.csv`

Note: rename from fig3_genealogy to fig4_genealogy.

---

### Figure 5: Testing the two-communities hypothesis (NEW)

**Script**: `scripts/analyze_bimodality.py` (new)

**What the article claims**: Climate finance scholarship is structured around two opposed intellectual communities — an "efficiency" pole (leverage, de-risking, mobilisation, blended finance, green bonds, private sector) and an "accountability" pole (additionality, over-reporting, climate justice, loss and damage, grant-equivalent, equity). This is the central sociological claim. Currently supported only by qualitative reading of the co-citation communities. We need quantitative evidence.

**What it shows**: That the distribution of papers along a well-defined efficiency↔accountability axis is bimodal (two peaks, not one), and that this bimodality is visible in both semantic (embedding) and lexical (word-level) representations.

#### Method A: Embedding-based axis

1. **Define the axis**: Construct two seed vocabularies:
   - Efficiency pole: {"leverage", "de-risking", "mobilisation", "blended finance", "private finance", "green bond", "crowding-in", "bankable", "risk-adjusted return", "financial instrument"}
   - Accountability pole: {"additionality", "over-reporting", "climate justice", "loss and damage", "grant-equivalent", "double counting", "accountability", "equity", "concessional", "ODA"}

2. **Compute pole centroids**: For each pole, find all papers in the corpus whose abstract contains at least 2 terms from that pole's vocabulary. Compute the mean embedding of each pole's papers → `centroid_eff`, `centroid_acc`.

3. **Define axis vector**: `axis = centroid_eff - centroid_acc` (normalized). This is the efficiency↔accountability direction in embedding space.

4. **Project all papers**: For each paper, compute `score = dot(embedding, axis)`. Papers with positive score lean efficiency; negative lean accountability.

5. **Test bimodality**:
   - Hartigan's dip test on the distribution of scores. H0: unimodal. If p < 0.05, reject unimodality.
   - Gaussian Mixture Model (k=2 vs k=1): BIC comparison. If 2-component fits better, bimodality supported.
   - Visual: kernel density estimate of scores, showing two humps.

6. **Temporal evolution**: Plot the score distribution by period (pre-2007, 2007–2014, 2015–2025). Does bimodality emerge, intensify, or flatten over time?

#### Method B: Lexical axis (TF-IDF validation)

Same logic but entirely lexical, as an independent check:

1. Fit TF-IDF on all abstracts (unigrams + bigrams, sublinear TF, English stopwords removed).
2. Compute mean TF-IDF vector for efficiency-pole papers and accountability-pole papers.
3. Define lexical axis as the difference vector. Project all papers onto it.
4. Apply same bimodality tests (dip test, GMM BIC, KDE plot).
5. Report: do the two methods agree on which papers are on which side?

#### Method C: Keyword co-occurrence validation

As a third, simple check: for each paper with abstracts, count how many efficiency-pole keywords appear and how many accountability-pole keywords appear. Plot the 2D scatter (x = efficiency keyword count, y = accountability keyword count). If the field is bimodal, most papers should cluster near one axis or the other (L-shaped or bimodal marginals), not in the center.

**Why three methods**: The embedding axis is the most powerful but least transparent. TF-IDF is transparent but ignores synonymy. Keyword co-occurrence is the simplest and most intuitive. If all three show bimodality, the claim is robust. If only embeddings show it, the effect may be an artifact of the embedding geometry.

**Output**:
- `figures/fig5_bimodality.{pdf,png}` — main figure: KDE of embedding scores, split by period
- `figures/fig5_bimodality_lexical.{pdf,png}` — TF-IDF version (robustness appendix)
- `figures/fig5_bimodality_keywords.{pdf,png}` — keyword scatter (robustness appendix)
- `tables/tab5_bimodality.csv` — dip test p-values, GMM BIC, pole paper counts
- `tables/tab5_pole_papers.csv` — per-paper score and pole assignment

**Dependencies**: numpy, scipy (for KDE), scikit-learn (GMM, TF-IDF), diptest (pip install diptest — small package for Hartigan's dip test; if unavailable, skip dip test and rely on GMM BIC + visual).

**Structure (~250 lines)**:

```python
# Load data + embeddings
# Step 1: Define pole vocabularies, identify pole papers from abstracts
# Step 2: Compute pole centroids in embedding space
# Step 3: Project all papers onto efficiency↔accountability axis
# Step 4: Bimodality tests (dip test, GMM BIC comparison)
# Step 5: KDE plot by period
# Step 6: Repeat with TF-IDF axis (Method B)
# Step 7: Keyword co-occurrence scatter (Method C)
# Step 8: Save tables + figures
```

---

## Robustness appendices (updated)

Carried over from v1, renumbered:

**R1**: Window size sensitivity (w = 2, 3, 4) — already in breakpoint analysis.

**R2**: k sensitivity (k = 4, 5, 6, 7) — `tables/tab2_k_sensitivity.csv`, `figures/fig2_k_sensitivity.{pdf,png}`.

**R3**: Louvain resolution sensitivity (γ = 0.5, 1.0, 1.5, 2.0) — `tables/tab3_louvain_sensitivity.csv`.

**R4**: Lexical TF-IDF validation of 2009 break, with 2015 and 2021 controls — `figures/fig_lexical_tfidf*.{pdf,png}`, `tables/tab2_lexical_tfidf.csv`.

**R5** (new): Bimodality robustness — TF-IDF axis and keyword co-occurrence (Methods B and C from Fig 5).

---

## Script changes summary

| Action | File | Purpose |
|---|---|---|
| **Rewrite** | `scripts/analyze_temporal.py` | New Fig 1: three economics series |
| **Modify** | `scripts/analyze_alluvial.py` | Rename output to fig2/fig3, update period labels |
| **Modify** | `scripts/analyze_genealogy.py` | Rename output to fig4, update period bands |
| **Create** | `scripts/analyze_bimodality.py` | New Fig 5: two-communities test |
| Keep | `scripts/analyze_cocitation.py` | Still needed (generates communities.csv) |
| Keep | `scripts/analyze_embeddings.py` | Still needed (generates embeddings.npy) |

## Output files (updated)

```
figures/fig1_emergence.{pdf,png}           — Three economics series timeline
figures/fig2_breakpoints.{pdf,png}         — Structural break detection
figures/fig3_alluvial.{pdf,png}            — Community flows across periods
figures/fig4_genealogy.{pdf,png,html}      — Citation genealogy
figures/fig5_bimodality.{pdf,png}          — Efficiency↔accountability bimodality
figures/fig5_bimodality_lexical.{pdf,png}  — TF-IDF bimodality (appendix)
figures/fig5_bimodality_keywords.{pdf,png} — Keyword scatter (appendix)
figures/fig_lexical_tfidf*.{pdf,png}       — Lexical validation (appendix, renamed)
figures/fig_k_sensitivity.{pdf,png}        — k-sensitivity (appendix, renamed)

tables/tab1_terms.csv                      — Key concept emergence
tables/tab2_breakpoints.csv                — Yearly divergence metrics
tables/tab2_breakpoint_robustness.csv      — Robust breakpoints
tables/tab2_alluvial.csv                   — Period-community counts
tables/tab2_k_sensitivity.csv              — k-sensitivity JS divergence
tables/tab2_lexical_tfidf.csv              — Lexical validation
tables/tab3_lineages.csv                   — Genealogy lineage assignments
tables/tab3_louvain_sensitivity.csv        — Louvain γ sensitivity
tables/tab5_bimodality.csv                 — Dip test, GMM BIC results
tables/tab5_pole_papers.csv                — Per-paper axis scores
```

## Execution order

```bash
# Prerequisites (already run, outputs cached):
# uv run python scripts/analyze_embeddings.py   → embeddings.npy
# uv run python scripts/analyze_cocitation.py    → communities.csv

# Figure 1 (requires OpenAlex API queries — one-time, cached):
uv run python scripts/analyze_temporal.py

# Figures 2 + 3 (breakpoints + alluvial):
uv run python scripts/analyze_alluvial.py
uv run python scripts/analyze_alluvial.py --robustness

# Figure 4 (genealogy):
uv run python scripts/analyze_genealogy.py

# Figure 5 (bimodality):
uv run python scripts/analyze_bimodality.py
```

## Risks (updated)

| Risk | Mitigation |
|---|---|
| OpenAlex API queries for Fig 1 fail or hit rate limits | Cache results in JSON. Fallback: use existing baselines (all science + climate change) as in v1. |
| Bimodality test shows unimodal distribution | Report as finding: the field is a continuum, not two camps. Revise the "two communities" framing to "spectrum with poles." |
| Efficiency/accountability axis is not the primary axis of variation | Check: compute explained variance of the axis projection. If low, try PCA-derived axes and see if they correlate. |
| Dip test package not available | Rely on GMM BIC + visual KDE. Two methods still sufficient. |
| 2013–2014 period too thin for meaningful alluvial band | Keep in figure (honest), discuss in text as transition moment. |

---

## Previous version notes

The v1 plan, Claude remarks, and ChatGPT remarks are preserved in git history. Key points still valid:
- Methodological novelty claim: endogenous structural break detection via embedding drift. Check Gingras & Mosbah-Natanson, Chavalarias & Cointet before submission.
- z > 1.5 threshold: convention, not theoretically grounded. State this.
- Citation genealogy is not phylogeny. Use "citation DAG stratified by community" in methods text.
