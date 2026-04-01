# The IPCC as category-maker: how assessment reports shaped the field of climate finance

## Research note — Ha-Duong & Ravigné

### Question

Did the IPCC assessment reports merely reflect the emerging scholarship on climate finance, or did they actively shape which definitions, frameworks, and authors became dominant? More specifically: does the timing and selectivity of IPCC citations explain why certain conceptions of climate finance crystallized while others were marginalized?

### Motivation

Climate finance consolidated as a distinct field of economic inquiry between 2007 and 2014. The periodization follows institutional milestones — the Bali Action Plan (2007) and Copenhagen Accord (2009) open the crystallization period, the Paris Agreement (2015) marks the established field — and is visible in the publication volume curve. Embedding-based similarity analysis across the corpus is consistent with this three-act structure. The periodization coincides with IPCC assessment cycles: AR4 (2007), AR5 (2014), AR6 (2022). This raises a question: did the IPCC contribute to the crystallization, or merely document it?

The IPCC occupies a singular position in the science-policy interface. Its assessment reports are not primary research but synthesis — yet being cited in an IPCC report confers visibility, legitimacy, and influence on policy frameworks. If lead authors systematically cite their own work or favor particular research traditions, the IPCC functions not as a mirror but as a lens that bends the field.

### Data

Four citation graphs — one for the field, three for the IPCC — matched by DOI.

| Graph | Source | Nodes | What it captures | Period |
|-------|--------|-------|------------------|--------|
| G₀ | Ha-Duong corpus | ~32K works, ~970K citation edges | Intellectual structure of the field, clustered and periodized | 1990–2025 |
| G₁ | AR4 WG III (2007) | Bibliography of finance chapter(s) | What the IPCC saw at the end of period I (before crystallization) | ≤2006 |
| G₂ | AR5 WG III (2014) | idem | What the IPCC saw at the end of period II (crystallization) | ≤2013 |
| G₃ | AR6 WG III (2022) | idem | What the IPCC saw in period III (established field) | ≤2021 |

G₀ is embedded (SPECTER2), clustered into six intellectual traditions, and periodized along institutional milestones (2007, 2014). The citation graph records which corpus works cite IPCC reports, but not the reverse. G₁–G₃ provide the reverse: which works the IPCC selects from the literature. Joining the four graphs closes the citation loop.

One assessment report per period. The alignment is not designed — it is a consequence of the IPCC assessment cycle roughly coinciding with the field's institutional milestones.

**Ha-Duong** provides G₀ (corpus, clusters, citation graph, embeddings). **Ravigné** provides G₁–G₃ (IPCC bibliographies, lead author metadata, self-citation measures).

### Method

Three phases: matching, corpus extension, and two comparative analyses.

**Phase 0 — Matching and corpus extension.**
Match G₁–G₃ bibliographies against G₀ by DOI. This yields two subsets: (a) matched works — IPCC-selected works already in the corpus, and (b) unmatched references — works cited by the IPCC but absent from G₀. The unmatched references are predominantly grey literature (World Bank, UNFCCC, OECD working papers) that the IPCC considered important enough to cite. Rather than treating low match rates as a problem, we use the unmatched references as a discovery mechanism: they identify grey literature that matters to the IPCC's view of the field. Those with retrievable metadata are added to G₀, extending the corpus precisely in the direction the IPCC points. The match rate itself is a finding: a low rate means the IPCC draws from a literature largely outside the academic corpus, which says something about the field's relationship to policy.

**Analysis 1 — Coverage and blind spots.**
For each ARn, project matched works onto the six clusters. This yields a coverage vector per AR: e.g., AR4 = [15% development aid, 40% carbon markets, 5% adaptation, ...]. Compare coverage vectors across AR4 → AR5 → AR6. Does the IPCC broaden its coverage as the field grows, or does it remain locked into the same traditions? Which clusters are systematically under-represented? A chi-squared test against the null of proportional sampling. Visualization: radar plot, one polygon per AR. The unmatched references from Phase 0 can be embedded and projected onto the same clusters, showing where the IPCC looks *outside* the academic corpus.

**Analysis 2 — Direction of renewal.**
Ravigné has shown that the IPCC renews its references across assessment cycles — this is an institutional mandate given to lead authors. We take this result as given and ask: *in which direction* does renewal occur? For new entrants in each AR (G₂ \ G₁, G₃ \ (G₁ ∪ G₂)), we identify their cluster membership. Does the IPCC discover new intellectual traditions as it renews, or does it refresh within the same ones? If AR5 replaces old carbon market papers with new carbon market papers, renewal is cosmetic. If it brings in adaptation finance or climate risk work that was absent from AR4, the IPCC is broadening its view of the field. We further decompose new entrants into academic (matched in G₀) and grey literature (unmatched), testing whether broadening comes from academic diversification or from the incorporation of new policy sources.

**Synthesis.** Analysis 1 shows *what* the IPCC selects from the field. Analysis 2 shows *where renewal goes* — deeper into the same traditions or across new ones. Together, they test whether the IPCC's mandated renewal translates into genuine intellectual broadening or cosmetic updating within a stable thematic frame.

### Relation to existing work

Studies of IPCC citation patterns have examined geographic bias (Corbera et al. 2016), disciplinary composition (Bjurström and Polk 2011), and self-citation dynamics (Ravigné et al.). Our contribution is to add the *thematic* dimension: not just who or where the IPCC cites, but from which intellectual traditions within a specific field. The embedding-based cluster structure provides a map that prior work lacked.

### Expected contribution

An empirical paper showing patterns in how the IPCC selected from and shaped the climate finance literature across three assessment cycles. We do not claim to demonstrate causation — the analyses are descriptive — but we can characterize the IPCC's thematic coverage, its blind spots, and the direction of its renewal. Three assessment reports aligned with three periods provide a natural comparison. The grey literature extension (Phase 0) is a methodological contribution in its own right: using IPCC bibliographies as a discovery tool for policy-relevant literature that academic databases miss.

### Practical arrangement

Each author contributes their existing pipeline and data. The joint work is the matching step (Phase 0) and the two comparative analyses. Division of labor: Ha-Duong provides G₀ (corpus, clusters, embeddings, citation graph); Ravigné provides G₁–G₃ (IPCC bibliographies, lead author metadata, self-citation analysis). Target: a research article (4,000–5,000 words) for Quantitative Science Studies or Scientometrics.
