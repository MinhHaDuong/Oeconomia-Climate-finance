## 10. UNFCCC Negotiation Architecture and Academic Field Structure
<!-- WARNING: AI-generated, not human-reviewed -->

### The co-production hypothesis

The manuscript argues that climate finance was "invented" --- its categories co-produced by economists and institutions. If true, the organizational structure of UNFCCC negotiations should be reflected in the academic literature's internal organization. This section maps the evolution of negotiating bodies, tracks, and workstreams, then tests whether these diplomatic structures created measurable academic sub-literatures.

### UNFCCC finance architecture: four eras

**Era 1: Single-track finance (1992--2006).** The Convention (1992) embedded "agreed full incremental costs" (Article 4.3) and "new and additional" resources as core financial obligations. The GEF served as the sole operating entity. No dedicated finance body existed; SBI handled guidance. The CDM (Kyoto Protocol Article 12, operational from 2005) generated \$15--24 billion in carbon revenues over 2001--2012, constituting a de facto private finance channel years before that concept entered negotiation language. Academic output was concentrated in carbon market economics (additionality, baselines, CDM methodology) with almost no connection to development economics.

**Era 2: Four-pillar differentiation (2007--2009).** The Bali Action Plan (COP-13, 2007) reorganized negotiations around four explicit pillars: mitigation, adaptation, technology, and finance. This was not rhetorical --- it determined how rooms were organized, which expert groups convened, and which academic communities were invited. Two negotiating tracks (AWG-LCA for Convention-track, AWG-KP for Protocol-track) each had dedicated finance subgroups. The MRV principle ("measurable, reportable, verifiable") was introduced. The Copenhagen Accord (COP-15, 2009) created the \$100 billion pledge, fast-start finance, and proposed the Green Climate Fund --- three institutions that each generated distinct research programmes.

**Era 3: Institutional proliferation (2010--2014).** The Cancún Agreements (COP-16, 2010) created three simultaneous institutions: the Green Climate Fund (equal developed/developing governance), the Standing Committee on Finance (biennial assessments of climate finance flows), and the Long-term Finance workstream (tracking progress toward \$100 billion). COP-17 Durban (2011) added the ADP with two workstreams negotiating what became the Paris Agreement. COP-18 Doha (2012) formalized the LTF workstream and reporting guidelines. By 2012, climate finance negotiations ran on three parallel tracks: ADP finance pillar, LTF workshops, and GCF operationalization.

**Era 4: Implementation and expansion (2015--present).** The Paris Agreement (2015) introduced Article 9 (finance obligations), Article 13 (enhanced transparency), Article 6 (carbon markets), and Article 2.1(c) (aligning all finance flows). The post-Paris agenda expanded to include the loss and damage fund (COP-27 Sharm el-Sheikh 2022, operationalized COP-28 Dubai 2023) and the New Collective Quantified Goal (NCQG, concluded COP-29 Baku 2024 at \$300 billion core, \$1.3 trillion aspirational). Each institution generated corresponding research: GCF evaluation, transparency methodology, Article 6 market design, loss attribution, and NCQG accounting.

### Five academic traditions mapped to negotiating tracks

| Negotiating track | Academic tradition | Institutional intermediaries | Peak period |
|-------------------|-------------------|------|-------------|
| CDM/JI → Article 6 | Carbon market economics | CDM Executive Board, methodology panels | 2005--2012, revival post-2021 |
| Adaptation Fund, LDCF, SCCF | Development/adaptation economics | UNDP, IIED, World Bank development divisions | 2010--present |
| \$100bn → NCQG | Public finance accounting | OECD-DAC, SCF, Oxfam counter-analyses | 2012--present |
| Green bonds, Art. 2.1(c) | Financial economics | World Bank (first green bond 2008), TCFD, FSB | 2016--present |
| WIM, Santiago Network, L\&D Fund | Climate justice / loss attribution | WIM ExCom, attribution science | 2019--present |

### UNFCCC-guided topic classification: results

We classify 27,315 works into eight UNFCCC negotiation tracks using keyword matching on titles, abstracts, and keywords. 21,430 works (78.5%) receive a topic; 5,885 remain unclassified.

| UNFCCC track | Works | Share |
|-------------|-------|-------|
| Development finance | 5,674 | 26.5% |
| CDM/carbon markets | 4,852 | 22.6% |
| Mitigation finance | 4,321 | 20.2% |
| Adaptation | 3,454 | 16.1% |
| Governance | 1,653 | 7.7% |
| Green finance | 993 | 4.6% |
| GCF/funds | 384 | 1.8% |
| Loss and damage | 99 | 0.5% |

**Topic evolution mirrors institutional calendar:**

| Period | CDM | Development | Mitigation | Adaptation | Green fin. | Governance |
|--------|-----|-------------|------------|------------|------------|------------|
| 2000--04 | **70.9%** | 16.4% | 7.6% | 2.7% | 0.2% | 1.9% |
| 2005--09 | **63.2%** | 16.0% | 11.9% | 5.6% | 0.2% | 2.7% |
| 2010--14 | **40.9%** | 23.7% | 16.6% | 10.7% | 0.4% | 4.9% |
| 2015--19 | 19.1% | **26.9%** | 20.9% | 17.5% | 2.2% | 10.0% |
| 2020--24 | 9.1% | **29.4%** | **23.0%** | **19.8%** | **7.7%** | 8.9% |

CDM dominance collapses after Bali 2007. Development, mitigation, and adaptation rise in parallel as their negotiating tracks are formalized. Green finance explodes from 0.4% to 7.7% after Paris Article 2.1(c). Governance grows 5× after the transparency framework is established.

### The anti-clustering test

If UNFCCC categories correspond to natural intellectual boundaries, works within the same category should be closer to each other than to works in other categories. We test this by computing the silhouette score of UNFCCC topic assignments in each representation space:

| Space | Silhouette of UNFCCC topics |
|-------|---------------------------|
| Semantic (1024D embeddings) | **-0.011** |
| Citation (bibliographic coupling) | **-0.010** |
| Lexical (TF-IDF) | **+0.007** |

All three scores are near zero or negative. **The UNFCCC categories are anti-clustered** --- works labelled "CDM" are no more similar to each other than to works labelled "adaptation" or "green finance." The diplomatic room assignments do not correspond to natural topic boundaries in any representation.

The ARI between UNFCCC topics and KMeans (k=6) on semantic embeddings is 0.126 (k=8: 0.128) --- weak but non-trivial agreement, suggesting that while the categorizations are not the same, they share some broad structure.

### Discussion

**The negotiation organized the field, not the other way around.** The topic evolution table (§10.4) shows that academic attention followed institutional creation with a lag of 1--3 years: CDM papers peaked after CDM operational rules were finalized (2005), adaptation papers rose after dedicated funds were created (2001--2010), green finance papers exploded after Article 2.1(c) created demand for "alignment" research (2015). Each negotiating room generated its academic constituency.

**But the categories don't separate.** Despite this institutional co-production, the categories are anti-clustered in the literature's natural structure. A paper about "CDM baseline methodology" is semantically, lexically, and bibliographically close to papers about "adaptation project evaluation" and "green bond verification" --- because they share analytical frameworks (cost-benefit analysis, monitoring protocols, institutional design), vocabulary (developing countries, climate risk, financial flows), and reference lists (IPCC, Stern Review, UNFCCC decisions).

**Implication for the manuscript.** The co-production thesis is supported in its strong form: institutions did not merely label pre-existing categories --- they created categories that the academic community populated. But the categories remain artificial subdivisions of a continuous field. The field's real structure is temporal (pre-2007 tight communities dissolving into a continuum) rather than topical (UNFCCC tracks that overlap completely in conceptual space). The 2007 structural break (Section 9) marks not a change in topics but a change in organization --- from specialized communities to a cross-cutting field.
