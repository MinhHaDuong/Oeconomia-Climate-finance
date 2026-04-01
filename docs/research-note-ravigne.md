# The IPCC as category-maker: how assessment reports shaped the field of climate finance

## Research note — Ha-Duong & Ravigné

### Question

Did the IPCC assessment reports merely reflect the emerging scholarship on climate finance, or did they shape which traditions became dominant? Does the timing and selectivity of IPCC citations explain why certain conceptions of climate finance crystallized while others were marginalized?

### Motivation

Climate finance consolidated as a field between 2007 and 2014. Embedding-based break detection on the Ha-Duong corpus identifies structural breaks at 2007 (cosine) and 2013 (Jensen-Shannon), consistent with institutional milestones (Bali Action Plan, Copenhagen Accord, Paris Agreement). These breaks coincide with IPCC assessment cycles: AR4 (2007), AR5 (2014), AR6 (2022). Did the IPCC contribute to the crystallization, or document it?

The IPCC is not primary research but synthesis — yet inclusion in an assessment report confers visibility, legitimacy, and policy influence. If lead authors favor particular traditions, the IPCC functions as a lens that bends the field.

### Data

Four citation graphs, matched by DOI (academic works) and fuzzy title (grey literature).

| Graph | Source | Size | What it captures | Period |
|-------|--------|------|------------------|--------|
| G₀ | Ha-Duong corpus | ~32K works, ~970K edges | Field structure: 6 clusters (k-means on bge-m3 embeddings), 3 periods | 1990–2025 |
| G₁ | AR4 WG III ch. 13 | Bibliography | What the IPCC saw before crystallization | ≤2006 |
| G₂ | AR5 WG III ch. 16 | Bibliography | What the IPCC saw at crystallization's end | ≤2013 |
| G₃ | AR6 WG III ch. 15 | Bibliography | What the IPCC saw in the established field | ≤2021 |

G₀'s citation graph records which corpus works cite IPCC reports; G₁–G₃ provide the reverse. Joining the four graphs closes the citation loop. One AR per period — not by design, but because the IPCC cycle roughly coincides with the field's breaks.

**Ha-Duong** provides G₀. **Ravigné** provides G₁–G₃ (IPCC bibliographies, lead author metadata, self-citation measures).

### Method

**Phase 0 — Matching and corpus extension.**
Match G₁–G₃ against G₀ in two passes: DOI, then fuzzy title for grey literature lacking DOIs. This yields (a) matched works already in the corpus and (b) unmatched references absent from G₀. Climate finance's primary sources — OECD DAC reporting, CPI *Global Landscape* reports, UNFCCC Standing Committee assessments, World Bank documents — are grey literature, so a large unmatched set is expected. The match rate by source type and AR reveals G₀'s academic-database-first blind spot. Unmatched works with retrievable metadata are embedded (bge-m3) and added to G₀, extending the corpus where the IPCC points.

**Institutional context.** IPCC lead authors face three competing mandates, acute for climate finance. They must cite recent results (renewal). Since 2011, following Glaciergate and the InterAcademy Council review, they must justify every non-peer-reviewed citation (Annex 2, IPCC 33rd Session, Abu Dhabi). Yet the field's knowledge base *is* grey literature. The path of least resistance: cite academic papers that themselves cite institutional reports, filtering the field through a proxy layer. The grey-lit share across AR4→AR5→AR6 thus reflects both the field's evolution and this procedural tightening.

**Analysis 1 — Coverage and blind spots.**
Project matched works onto the six clusters. This yields a coverage vector per AR. Compare across AR4→AR5→AR6: does the IPCC broaden its thematic coverage or stay locked in? Chi-squared test against proportional sampling. Embed unmatched references onto the same clusters to show where the IPCC looks outside the academic corpus. Visualization: radar plot, one polygon per AR.

**Analysis 2 — Direction of renewal.**
Ravigné has shown that the IPCC renews references across cycles (institutional mandate). We ask: *in which direction?* For new entrants in each AR (G₂ \ G₁, G₃ \ G₁∪G₂), identify cluster membership. If AR5 replaces old carbon market papers with new ones, renewal is cosmetic. If it brings in adaptation finance or climate risk, the IPCC is broadening. Decompose new entrants into academic (matched) and grey (unmatched) to test whether broadening comes from academic diversification or new policy sources — and whether the post-2011 procedural shift suppresses grey-lit renewal.

**Synthesis.** Analysis 1 shows what the IPCC selects. Analysis 2 shows where renewal goes. Together they test whether mandated renewal translates into intellectual broadening or cosmetic updating within a stable frame.

### Relation to existing work

Studies of IPCC citation patterns have examined geographic bias (Corbera et al. 2016), disciplinary composition (Bjurström and Polk 2011), and self-citation (Ravigné et al.). We add the thematic dimension: not just who or where the IPCC cites, but from which intellectual traditions within a specific field. The embedding-based cluster structure provides a map that prior work lacked. The grey-lit tension (Phase 0 + institutional context) connects to the literature on IPCC governance reform (IAC 2010) in a way that citation studies have not explored for individual subfields.

### Practical arrangement

Each author contributes their existing pipeline. Joint work: matching (Phase 0) and comparative analyses. Ha-Duong: G₀ (corpus, clusters, embeddings, citations). Ravigné: G₁–G₃ (IPCC bibliographies, lead author metadata, self-citation analysis). Target: 4,000–5,000 words for Quantitative Science Studies or Scientometrics.
