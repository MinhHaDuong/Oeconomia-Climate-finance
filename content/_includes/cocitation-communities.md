## Co-citation Community Detection Across Time Windows

**Script:** `scripts/compare_communities_across_windows.py`

This analysis traces the evolution of co-citation communities in the climate finance literature across four time windows, testing whether the three intellectual traditions posited by the manuscript (environmental economics, development economics, burden-sharing) are empirically detectable as distinct citation lineages.

### Method

For each of four cutoff years (2006, 2014, 2019, 2025), the pipeline:

1. Identifies all references with publication year $\leq$ cutoff that are cited at least once in the corpus.
2. Selects the top 250 most-cited such references.
3. Builds a co-citation graph: two references are linked if they are co-cited by the same source paper *anywhere* in the corpus (not restricted to same-period sources). Edge weight equals the number of co-citing papers.
4. Removes edges with weight $< 3$ and isolates.
5. Applies Louvain community detection (resolution $\gamma = 1.0$, random\_state = 42).
6. Characterizes each community by its top papers (ranked by corpus citation count) and top TF-IDF terms (fitted on available abstracts and titles).

The key design choice is that co-citation links are computed using *all* citing papers in the corpus, not only those published before the cutoff. This gives the co-citation signal between older references the benefit of later scholarship that consolidated intellectual links. The cutoff applies only to the *referenced* papers: it determines which foundational works are included in the network.

### Network statistics

| Window | Cutoff | Nodes | Edges | Communities | Modularity |
|--------|--------|-------|-------|-------------|------------|
| Pre-2007 | $\leq 2006$ | 169 | 1,056 | 18 | 0.18 |
| Pre-2015 | $\leq 2014$ | 232 | 2,918 | 10 | 0.14 |
| Pre-2020 | $\leq 2019$ | 247 | 3,568 | 5 | 0.30 |
| Full | $\leq 2025$ | 250 | 4,298 | 6 | 0.45 |

As the reference pool expands, the network densifies (more edges per node) and community structure first dissolves (modularity dips to 0.14 at pre-2015) then re-crystallizes into a stable, high-modularity configuration (0.45 at full span).

### Community alignment across windows

Communities were aligned across windows using Jaccard similarity on their DOI sets. The table below shows the principal lineages, with community IDs, sizes, and top authors. Only communities with $\geq 5$ members or with a Jaccard link $\geq 0.05$ to a community in another window are shown.

| Tradition | Pre-2007 | Pre-2015 | Pre-2020 | Full |
|-----------|----------|----------|----------|------|
| **Institutions / governance** | C2 (44): DiMaggio, North, Finnemore | C2 (65): Ciplet, Ostrom, Michaelowa | C2 (60): Weikmans, Keohane, Ciplet | C3 (58): Weikmans, Weiler, Keohane |
| **Adaptation / development** | C10 (30): Smit, Adger, Bouwer | mega-C3 (97) | C3 (72): Weiler, Khan, Pickering | C4 (63): Bhandary, Lee, Bracking |
| **Econometrics / panel data** | C0 (32): Arellano, Blundell, Pesaran | C4 (24): Arellano, Blundell, Pesaran | absorbed into C3 (72) | absorbed into C4 (63) |
| **Aid / international agreements** | C4 (11): Alesina, Burnside + C11 (19): Barrett, Carraro | mega-C3 (97) + C1 (15): Keohane, Andonova | C4 (16): Nordhaus, Falkner, Rogelj | absorbed into C3 (58) |
| **Corporate finance / risk** | C6 (4): Fama, Carhart | C6 (11): Matsumura, Jensen, Heinkel | C0 (81): Banga, Battiston | C1 (69): Krueger, Hong, Giglio |
| **Green bonds** | --- | --- | part of C0 (81) | C5 (48): Banga, Flammer, Zhang |
| **Carbon lock-in / transitions** | C1 (5): Unruh, Geels | C5 (6): Unruh, Geels, Newell | absorbed into C0 (81) | absorbed into C1 (69) |
| **Earth system / NBS** | --- | --- | C1 (18): Griscom, Steffen | C2 (7): Griscom, Seddon |

### Jaccard similarity between windows

The strongest Jaccard links between consecutive windows are:

- **Econometrics continuity** (pre-2007 C0 $\to$ pre-2015 C4): $J = 0.436$ --- the most persistent lineage across the first two windows, reflecting the stable core of panel-data econometric methods.
- **Governance continuity** (pre-2015 C2 $\to$ pre-2020 C2): $J = 0.389$ --- the international political economy tradition carries forward with high fidelity, anchored by Keohane, Ciplet, and Weikmans.
- **Pre-2020 to Full stability**: $J = 0.639$ for governance (C2 $\to$ C3), $J = 0.534$ for adaptation (C3 $\to$ C4), $J = 0.376$ for climate risk (C0 $\to$ C1), $J = 0.240$ for green bonds (C0 $\to$ C5). The post-Paris community structure is highly stable.

Full-window DOI turnover between successive periods:

| Comparison | Shared refs | Jaccard |
|------------|------------|---------|
| Pre-2007 vs Pre-2015 | 57 | 0.166 |
| Pre-2007 vs Pre-2020 | 33 | 0.086 |
| Pre-2015 vs Pre-2020 | 120 | 0.334 |
| Pre-2020 vs Full | 179 | 0.563 |

Only 27 of the pre-2007 top-250 references survive into the full-span top-250 (Jaccard = 0.069). The citation base has been almost entirely renewed.

### Cross-reference with semantic clusters

**Script:** `scripts/cross_ref_communities_clusters.py`

To assess whether co-citation communities and embedding-based KMeans clusters (k=6, used in the alluvial analysis) capture the same or complementary structure, we traced which KMeans clusters the *citers* of each pre-2007 co-citation community belong to. Only 2 of 137 community nodes are themselves in the embedding corpus; the indirect mapping via citers yields 831 (citer, community) pairs.

Cramer's V = 0.248 (chi-squared = 204.1, $p < 10^{-32}$, df = 20), indicating a weak-to-moderate but highly significant association. The two classification systems are not independent, but they capture complementary dimensions: co-citation communities trace intellectual lineage (shared foundational references), while embedding clusters capture topical similarity of abstracts. The strongest mapping is pre-2007 Community 3 (Smit, Adger --- adaptation) to KMeans cluster "Climate action and adaptation" (63% of citers).

### Interpretation

The four-window analysis yields three findings for the manuscript's narrative:

1. **Fragmentation before crystallization.** Pre-2007, the co-citation network contains 18 small, distinct communities. Each methodological and intellectual lineage --- econometrics, institutional theory, adaptation science, aid economics, international law, corporate finance --- forms its own citation island. This is consistent with the manuscript's claim that climate finance emerged from multiple disconnected traditions.

2. **Fusion during crystallization, then re-differentiation.** By pre-2015, many of these small communities have merged into a 97-paper mega-community containing adaptation, aid, agreements, and more. Only econometrics and international political economy remain distinct. Modularity drops to its lowest value (0.14). By pre-2020, the field has re-crystallized into 5 well-separated communities ($Q = 0.30$) organized along new lines: climate risk, governance/accounting, adaptation finance, Paris Agreement politics, and earth systems.

3. **Stable post-Paris structure.** The full-span window (6 communities, $Q = 0.45$) is highly similar to the pre-2020 window (Jaccard = 0.563). The main change is that the large pre-2020 green finance cluster (81 papers) splits into climate risk/institutional investors (69) and green bonds proper (48). This late differentiation reflects the rapid growth of green bond scholarship after 2018. A small health/Africa cluster (5 papers) appears as a post-2020 newcomer.

The governance/accountability tradition (DiMaggio $\to$ Keohane $\to$ Weikmans) is the only lineage that persists as a distinct co-citation community across all four windows. The econometrics tradition persists through pre-2015 but then merges with adaptation into a combined empirical-methods cluster. Corporate finance references (Fama, Jensen) are progressively absorbed into the expanding green finance literature.
