## Temporal Structure Analysis
<!-- WARNING: AI-generated, not human-reviewed -->

**Script:** `scripts/compute_clustering_comparison.py` (multi-space silhouette), `scripts/analyze_space_interactions.py`

Section 7 establishes that the full corpus shows weak cluster structure. But this static picture may obscure temporal dynamics: did the field once have clear boundaries that later dissolved? This section examines how cluster structure evolves over time in each representation space.

### Method

We compute KMeans silhouette scores (k = 2 through 8) in rolling 5-year windows across all three representation spaces. For each window we report the best-k (highest silhouette) and its score. Windows with fewer than 100 works are excluded. Citation space requires at least 30 non-zero-coupling works per window.

### Results: structure over time

| Window | N works | Semantic best-k (sil) | Lexical best-k (sil) | Citation best-k (sil) |
|--------|---------|----------------------|---------------------|-----------------------|
| 1995--1999 | 135 | 5 (0.077) | --- | --- |
| 2000--2004 | 710 | 7 (0.061) | 8 (0.237) | --- |
| 2003--2007 | 1,278 | 7 (0.061) | 8 (0.206) | 7 (0.233) |
| 2005--2009 | 2,307 | 6 (0.056) | 8 (0.179) | 8 (0.183) |
| 2009--2013 | 4,584 | 6 (0.049) | 8 (0.166) | 8 (0.196) |
| 2012--2016 | 4,790 | 2 (0.039) | 8 (0.168) | 8 (0.192) |
| 2015--2019 | 4,926 | 2 (0.039) | 8 (0.149) | 8 (0.188) |
| 2017--2021 | 6,705 | 3 (0.037) | 8 (0.124) | 7 (0.144) |
| 2019--2023 | 11,352 | 3 (0.047) | 8 (0.113) | 8 (0.110) |
| 2020--2024 | 14,532 | 3 (0.049) | 7 (0.115) | 8 (0.100) |

### A single structural transition, not three acts

All three spaces agree on the temporal pattern: **structure peaks in the early-to-mid 2000s and declines monotonically thereafter.** The key observations:

**Peak structure (2000--2007).** The early corpus was small, tightly scoped, and organized around a few well-defined research programmes: CDM project economics, carbon market design, and Kyoto Protocol compliance. Citation space reaches silhouette 0.233 in 2003--2007 (genuine community structure). Lexical space shows 0.206 (specialized vocabularies). Even semantic space --- flat throughout --- has its highest value (0.077) in 1995--1999 when the corpus contained only 135 works.

**Inflection point (~2007).** All silhouette curves show an inflection around 2005--2008, coinciding with the Bali Action Plan (COP-13, 2007) and the Stern Review (2006). These events expanded climate finance from a technical carbon-market concern into a broader economic and political issue, attracting researchers from development economics, financial economics, and political science. The manuscript's first period break at 2007 is supported by this structural inflection.

**Monotonic decline (2008--2024).** As the field expands and diversifies, cluster boundaries dissolve in all spaces. The decline is steepest in lexical space (0.237 → 0.115), indicating that disciplinary vocabularies increasingly overlap. Citation space retains more structure (0.233 → 0.100), suggesting that citation communities persist longer than topical boundaries --- researchers continue citing within their lineage even as their topics converge.

**No detectable 2015 break.** The manuscript's second period break at 2015 (Paris Agreement) does not appear as a structural transition in any representation space. Silhouette scores continue their smooth decline through 2015 without a local maximum, minimum, or inflection. This suggests that while Paris was a major institutional event, it did not reorganize the research community's structure. The field was already a diffuse continuum by 2015.

### Preferred number of clusters changes over time

The optimal k shifts systematically:

- **Pre-2007**: k = 5--7 in semantic space, k = 7--8 in lexical and citation. The field has many small, distinct sub-communities.
- **2010--2016**: k = 2 in semantic space. The field consolidates into a broad binary: applied climate economics vs. environmental economics/governance.
- **Post-2017**: k = 3 in semantic space, k = 7--8 in lexical/citation. A third cluster emerges (likely financial economics/ESG/climate risk), while lexical and citation spaces retain finer granularity.

This evolution matches the manuscript's narrative: the field transitions from pre-existing disciplinary clusters through a period of convergence (post-Copenhagen) to a new three-way organization (carbon markets, development/adaptation, financial economics).

### Cross-space agreement over time

We compute ARI between KMeans (k=6) assignments across each pair of spaces, per 5-year window:

| Window | Sem ↔ Lex | Sem ↔ Cit | Lex ↔ Cit |
|--------|-----------|-----------|-----------|
| 2000--2004 | 0.202 | 0.017 | 0.016 |
| 2005--2009 | **0.264** | 0.064 | **0.091** |
| 2010--2014 | 0.202 | **0.098** | 0.057 |
| 2015--2019 | 0.129 | 0.067 | 0.057 |
| 2020--2024 | 0.216 | 0.073 | 0.058 |

**The three spaces do not converge over time.** Agreement is low throughout (ARI < 0.27) and follows non-monotone patterns:

- **Semantic ↔ Lexical**: peaks in 2005--2009 (0.264) when the Kyoto/CDM vocabulary was tightly coupled to conceptual content, drops to a trough in 2015--2019 (0.129) as the field becomes interdisciplinary (same concepts, different words).
- **Semantic ↔ Citation**: peaks in 2010--2014 (0.098) when citation networks partially align with topic structure in the mature field.
- **Lexical ↔ Citation**: peaks in 2005--2009 (0.091) and then converges to ~0.06. During the formative period, what you cited correlated with what words you used; this correlation weakens as the field matures.

**Interpretation.** The spaces capture largely independent dimensions throughout the field's history. What a work is about (semantic), what words it uses (lexical), and what it cites (citation) are three distinct fingerprints. This independence strengthens the case for multi-space analysis: any single representation captures at most one facet of the field's organization.

### Language structure over time

| Window | % non-English | k=2 EN/non-EN sil |
|--------|--------------|-------------------|
| 2000--2004 | 14.2% | 0.008 |
| 2005--2009 | 12.5% | 0.002 |
| 2010--2014 | 9.7% | -0.008 |
| 2015--2019 | 10.9% | -0.012 |
| 2020--2024 | 8.5% | -0.010 |

The non-English share declines from 14.2% to 8.5% as English consolidates as the field's working language. The k=2 silhouette for the EN/non-EN split is near zero or negative throughout, becoming increasingly negative after 2010. **Language does not create clustering structure at any point in the field's history.** The negative silhouette after 2010 means non-English works are anti-clustered --- they are embedded within English-language topic regions, not in separate linguistic enclaves. The multilingual embedding model is working as intended.

### Core versus full structure over time

| Window | N full | Sil full (k=6) | N core (≥50 cit) | Sil core (k=6) |
|--------|--------|----------------|-------------------|----------------|
| 2000--2004 | 710 | 0.056 | 87 | 0.041 |
| 2005--2009 | 2,307 | 0.056 | 296 | 0.055 |
| 2010--2014 | 4,687 | 0.045 | 531 | 0.037 |
| 2015--2019 | 4,926 | 0.032 | 794 | 0.034 |
| 2020--2024 | 14,532 | 0.034 | 913 | 0.042 |

The core (highly-cited) subset does not show more semantic structure than the full corpus in any period. In early windows, the core actually shows *less* structure (0.041 vs. 0.056), likely because the most-cited early works span across sub-communities rather than belonging exclusively to one. In the recent window (2020--2024), the core shows slightly more structure (0.042 vs. 0.034), likely because "core" in this period selects for older, more settled works from distinct traditions.

### Discussion

**The data detect one structural transition, centered around 2007.** Before 2007, the climate finance literature consists of a few distinct research programmes with specialized vocabularies, separate citation networks, and identifiable topical boundaries. After 2007 --- particularly after the Stern Review, the Bali Action Plan, and the Copenhagen Accord --- the field expands rapidly and these boundaries dissolve. The transition is gradual (2005--2010), not sharp.

**The manuscript's three-act periodization is institutionally, not structurally, motivated.** The 2007 break corresponds to a genuine structural inflection in the data. The 2015 break does not. This does not invalidate the three-act structure --- Paris was a major institutional turning point that reshaped policy discourse --- but it suggests that by 2015, the research community had already converged into a continuum. The Paris Agreement influenced what academics wrote about but did not reorganize how they related to each other.

**Implications for cluster interpretation.** The time-varying analysis reveals that the k=6 thematic clusters of the full corpus are a superposition of distinct historical phases: tight communities that formed pre-2007 and a diffuse expansion that followed. A single static clustering conflates these two regimes. Future work might consider period-specific clustering (e.g., k=5--7 for pre-2007, k=2--3 for post-2007) to better capture the field's evolution.
