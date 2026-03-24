## 9. Change-Point Detection in Field Structure
<!-- WARNING: AI-generated, not human-reviewed -->

**Script:** `scripts/compare_clustering.py` (annual silhouette), BIC piecewise-constant model

### 9.1 Motivation

Section 8 identifies a monotonic decline in cluster structure after a peak in the early 2000s. The manuscript uses period breaks at 2007 and 2015. Are these break-points supported by the data? This section applies formal change-point detection to the annual silhouette time series.

### 9.2 Method

We compute KMeans silhouette (k=6) for each individual year (1999--2024) in both semantic and citation spaces. We then fit piecewise-constant models with 0, 1, 2, and 3 change-points and select using the Bayesian Information Criterion (BIC). Lower BIC indicates a better model (balancing fit against complexity). Additionally, we rank candidate break-points by maximum t-statistic for the difference in means before vs. after each year.

### 9.3 Annual silhouette time series

| Year | N | Semantic sil (k=6) | Citation sil (k=6) |
|------|---|--------------------|--------------------|
| 1999 | 74 | 0.074 | --- |
| 2000 | 105 | 0.050 | --- |
| 2001 | 126 | 0.065 | --- |
| 2002 | 148 | 0.050 | --- |
| 2003 | 165 | 0.065 | --- |
| 2004 | 166 | 0.076 | --- |
| 2005 | 250 | 0.068 | --- |
| 2006 | 261 | 0.063 | 0.225 |
| 2007 | 436 | 0.061 | 0.221 |
| 2008 | 539 | 0.052 | 0.171 |
| 2009 | 821 | 0.056 | 0.188 |
| 2010 | 912 | 0.051 | 0.157 |
| 2011 | 920 | 0.050 | 0.153 |
| 2012 | 986 | 0.044 | 0.152 |
| 2013 | 945 | 0.036 | 0.111 |
| 2014 | 924 | 0.036 | 0.118 |
| 2015 | 998 | 0.034 | 0.112 |
| 2016 | 937 | 0.040 | 0.137 |
| 2017 | 937 | 0.038 | 0.136 |
| 2018 | 1,004 | 0.030 | 0.124 |
| 2019 | 1,050 | 0.028 | 0.111 |
| 2020 | 1,609 | 0.026 | 0.078 |
| 2021 | 2,105 | 0.034 | 0.100 |
| 2022 | 2,689 | 0.038 | 0.157 |
| 2023 | 3,899 | 0.034 | 0.079 |
| 2024 | 4,230 | 0.038 | 0.084 |

### 9.4 BIC model selection

| Model | Semantic BIC | Citation BIC |
|-------|-------------|-------------|
| 0 breaks (constant) | -216.96 | -117.72 |
| **1 break** | -250.18 (2011) | -133.56 (2012) |
| **2 breaks** | **-255.61 (2007, 2012)** | -140.20 (2007, 2012) |
| 3 breaks | -255.57 (2002, 2007, 2012) | **-144.05 (2007, 2012, 2022)** |

**Semantic space**: BIC selects 2 breaks at **2007 and 2012**. Adding a third break (at 2002) does not improve the model (ΔBIC = +0.04).

**Citation space**: BIC selects 3 breaks at **2007, 2012, and 2022**. The third break in 2022 captures a citation-space restructuring possibly associated with the Glasgow Financial Alliance (GFANZ, COP26 2021) and the post-COVID ESG boom.

### 9.5 Strongest single break-point

| Space | Strongest break | t-statistic | Mean before | Mean after | Δ |
|-------|----------------|-------------|-------------|-----------|---|
| Semantic | 2012 | 8.93 | 0.060 | 0.035 | +0.025 |
| Citation | 2008 | 12.16 | 0.223 | 0.128 | +0.095 |

The citation space shows the sharpest single break at 2008, immediately after COP-13 Bali (December 2007). The semantic space's sharpest break is at 2012, coinciding with COP-18 Doha and the GCF operationalization.

### 9.6 Discussion

**The 2007 break is robustly supported.** Both spaces include 2007 in their BIC-optimal models. This aligns with the manuscript's first period break and with the Stern Review (2006) / Bali Action Plan (COP-13, 2007), which expanded climate finance from carbon-market economics into a broader field.

**The data suggest 2012, not 2015, as the second break.** Neither space detects 2015 (Paris) as a structural change. Instead, 2012 emerges consistently:

- In the **semantic space**, 2012 marks the sharpest drop in silhouette (from 0.060 before to 0.035 after). By 2012, the field had already become a diffuse continuum.
- In the **citation space**, 2012 separates a period of higher structure (0.152--0.188) from a lower-structure regime (0.111--0.137).

The 2012 break aligns with several institutional developments: the GCF became operational, the Adaptation Fund started direct access, and the Ad Hoc Working Group on the Durban Platform (ADP) began negotiating what became the Paris Agreement. These events restructured the research agenda 3 years before Paris.

**Paris 2015 was an institutional event, not a structural one.** By 2015, the research community had already reorganized. Paris changed what academics *wrote about* (Article 9, transparency, NDCs) but did not change *how they related to each other* (citation patterns, vocabulary, topical proximity).

**The 2022 citation break is tentative.** The citation space detects a possible restructuring in 2022 (silhouette jumps to 0.157 from 0.078--0.100). This may reflect the rapid growth of financial-climate-risk literature following GFANZ (Glasgow, COP26 2021) and the increasing regulatory push (EU taxonomy, SEC climate disclosure). However, citation data for recent years is incomplete (references take time to accumulate), so this break should be treated cautiously.

**Implication for the manuscript.** The three-act periodization (pre-2007, 2007--2015, post-2015) is not the best data-driven partition. A two-act structure (pre-2007 / post-2007) or a three-act structure with different breaks (pre-2007 / 2007--2012 / post-2012) would better match the bibliometric evidence. However, the manuscript's 2015 break can be justified on institutional grounds (Paris Agreement) even though it does not correspond to a structural reorganization of the research community.
