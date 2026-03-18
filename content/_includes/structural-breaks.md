## 5. Structural Break Detection

**Scripts:** `scripts/compute_alluvial.py` + `scripts/plot_fig_breakpoints.py`

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

@fig-breakpoints shows the divergence profiles; @fig-breaks shows the manuscript's simplified two-metric view.

![Structural break detection: JS divergence and cosine distance z-scores by candidate year and window size.](figures/fig_breakpoints.png){#fig-breakpoints width=100%}

![Breakpoints summary (manuscript figure variant).](figures/fig_breaks.png){#fig-breaks width=80%}

### Results: full corpus (N = {{< meta corpus_with_embeddings >}})

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

### Results: core subset (N = {{< meta corpus_core >}}, cited_by_count ≥ {{< meta corpus_core_threshold >}})

The core subset contains only highly-cited papers — the *influential* works that define the field's intellectual structure.

#### Baseline (*k* = 0)

| Year | JS mean z | Cosine mean z | Combined z | Support |
|------|-----------|---------------|------------|---------|
| 2023 | 3.50 | 3.65 | 7.15 | both |

No break is detected in the 2005–2020 range. The only robust signal is at **2023**, driven by extremely high z-scores on both metrics. This is a **boundary artifact**: recent papers (2022–2024) have not yet accumulated enough citations to enter the core subset, creating a composition discontinuity at the edge of the observation window.

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
| Full ({{< meta corpus_with_embeddings >}}) | **2007**, **2013** | **2008**, 2013, 2015 | **2009** |
| Core ({{< meta corpus_core >}}) | 2023* | 2023* | 2023* |

\* Boundary artifact only.
