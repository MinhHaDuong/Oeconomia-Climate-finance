# Whose climate finance? Semantic blind spots across languages and geographies

## Research note — Ha-Duong

---

## Framing

### Topic

The epistemic structure of climate finance scholarship across languages and geographies, measured through multilingual sentence embeddings and citation analysis.

### Angle

This is not a "we should include more languages" paper. It is a **methodological argument**: lexical bibliometrics (keyword co-occurrence, LDA, TF-IDF topic models) cannot compare across languages because they operate on surface vocabulary. A French paper on "finance climat" and an English paper on "climate finance" share no lexical features. Multilingual sentence embeddings are therefore a *minimum methodological requirement* for credibly mapping any field that spans the North-South divide — and climate finance is defined by that divide.

The twist: the language axis and the geography axis are not the same thing. Global South scholars writing in English may still occupy distinct regions of the embedding space. If so, the barrier is epistemic (different questions, different framings, different objects of study), not merely linguistic. The two-axis design (language × geography) disentangles these.

### Narrative arc

1. **Setup.** Existing bibliometric studies of climate finance (Carè & Weber 2023, Shang & Jin 2023, Maria et al. 2023) use English-only databases and lexical methods. They cannot see across languages. They claim to map "the field" but map only its Anglophone core.

2. **Instrument.** We use multilingual sentence embeddings (bge-m3) that place 31,700 works in 8+ languages into a shared semantic space. This lets us *measure* what lexical methods cannot: thematic proximity across languages.

3. **Diagnostic.** We construct a 2×2 classification (English/non-English × North/South) and compute semantic isolation scores — how far is each work from the nearest Anglophone-Northern equivalent? The isolation score is a continuous measure of "invisibility to the mainstream."

4. **Findings.** Three empirical tests: (a) non-English works concentrate in specific clusters, not randomly distributed — they selectively enrich some traditions while leaving others unchanged; (b) Global South works in English are still semantically distinct from the Northern mainstream — the divide is geographic, not just linguistic; (c) citation flows are directionally asymmetric — the South is cited as empirical case, not as conceptual framework.

5. **Implication.** The methodological fix is not just "include more languages" but "use methods that can see across them." Multilingual embeddings are necessary. Citation directionality analysis reveals what inclusion alone does not.

### Key results (expected)

From corpus v1.1.1 (~31,000 refined works):

- **Language distribution**: 93.1% English, 1.8% Portuguese, 1.3% German, 1.3% Spanish, 1.1% French, <1% each for Chinese, Japanese, Indonesian, Turkish, Korean, Russian. Non-English works: ~2,100 in semantic clusters.
- **Cluster concentration**: Portuguese works cluster disproportionately in cluster 2 (3.6% vs 1.8% corpus-wide) — visible as a dense pocket in the UMAP at (x≈8–10, y≈10–12). German overrepresented in cluster 3 (2.0% vs 1.3%). Non-random distribution.
- **Global South**: ~2,000 works (6.5%) match Global South affiliation keywords. Expected to be unevenly distributed across clusters and languages.
- **Core subset**: The ~2,650 most-cited papers are expected to be overwhelmingly English and Northern — the citation threshold itself is a filter that reproduces the hierarchy.
- **Citation graph**: 843K edges. Language-stratified citation analysis not yet computed — this is the new analysis.

### Empirical proof strategy

| Hypothesis | Test | Evidence for | Evidence against |
|-----------|------|-------------|-----------------|
| H1: Non-English works cluster non-randomly | χ² or Fisher's exact on language × cluster contingency table | Significant departure from independence; specific clusters enriched | Uniform distribution across clusters |
| H2: South-English ≠ North-English in embedding space | Mean isolation score comparison (permutation test) | South-English isolation > North-English isolation | No significant difference |
| H3: Citation asymmetry N↔S | Directional ratio (N→S)/(S→N), stratified by cluster distance | Ratio ≪ 1; South cited cross-cluster (as case study) | Ratio ≈ 1; symmetric exchange |
| H4: Isolation changes over time | Per-period isolation scores | Monotonic trend (convergence or entrenchment) | No temporal pattern |
| H5: Well-cited non-English works are less isolated | Isolation score vs. citation count (non-English subset) | Negative correlation (integration rewarded) | No correlation (isolation independent of impact) |

Any null result is publishable: it would mean English-centrism is a coverage problem, not an epistemic one, and the fix is inclusion, not methodological overhaul.

### Robustness and limitations (methodological)

- **Isolation score k-sensitivity**: Report results for k ∈ {5, 10, 20}. If H2 conclusions change with k, the finding is hyperparameter-dependent.
- **Alternative South definitions**: Sensitivity analysis with OECD DAC (primary), UN LDC list (strictest), World Bank income groups (gradient). Report whether qualitative pattern persists.
- **Co-authorship edge case**: Mixed-affiliation papers (North + South co-authors) classified as South by default. Sensitivity: also report with "lead geography" (first author affiliation) classification.
- **Missing affiliations (~20-30%)**: Run H1–H3 on (a) complete data only, (b) missing imputed as North, (c) missing imputed as South. Report range of conclusions.
- **Embedding model confound**: bge-m3 is trained on web text, which overrepresents Anglophone academic writing. EN-South isolation may partly reflect training data imbalance, not epistemic difference. Acknowledged as limitation; resolving requires retraining experiment beyond scope.
- **Multiple comparisons**: H1 (contingency table) uses FDR correction on cell-level tests. H2–H3 are confirmatory (stated a priori); H4–H5 are exploratory and flagged as such. Report effect sizes (Cohen's d) alongside p-values.
- **Citation directionality**: The cross-cluster citation proxy for "South as data source" is indirect. Requires manual validation on a stratified sample (~300 citations) to calibrate. Present as suggestive pending validation.

### Outlet

Diamond OA preferred. Candidates to investigate:

- **Quantitative Science Studies** (MIT Press) — diamond OA, good scope fit for methodology + empirical application. Published Huang & Zhao (2024) on linguistic diversity.
- **Research Evaluation** (OUP) — if the epistemic argument is strong enough.
- **Science, Technology, & Human Values** — STS framing.

Journal selection requires verification (URLs, actual OA model, scope fit) before committing.

Target length: 6,000–8,000 words. QSS has no explicit word limit; typical articles run 8,000–12,000.

---

## Structured abstract (250 words)

Bibliometric analyses of climate finance rely predominantly on English-language databases and lexical methods. We argue that this creates not merely a coverage gap but a methodological blind spot: lexical approaches cannot detect thematic differences across languages, and English-only corpora erase both non-Anglophone intellectual traditions and Global South perspectives expressed in English. Multilingual sentence embeddings are a minimum methodological requirement — not because they necessarily change substantive results, but because without them the claim "we mapped the field" is unjustified.

Using a corpus of ~32,000 works with multilingual embeddings (BAAI/bge-m3), a citation graph (~970,000 edges), and author affiliation metadata, we construct a two-axis classification: language (English / non-English) and geography (Global North / Global South, per OECD DAC). This yields four quadrants with distinct epistemic positions. For each, we compute a semantic isolation score — distance to the nearest English-language North neighbors — and extract the distinctive thematic terms of the most isolated works.

We test three hypotheses. First, non-English works concentrate in specific thematic clusters (development aid, adaptation), selectively enriching some traditions while leaving others unchanged. Second, Global South works — even those written in English — occupy distinct regions of the embedding space, indicating that the North-South divide is epistemic, not merely linguistic. Third, the citation graph is directionally asymmetric: Southern works are cited as empirical cases more than as conceptual frameworks.

The paper's contribution is empirical: using multilingual sentence embeddings, we document the geographic and epistemic structure of climate finance scholarship and show that this structure is invisible to monolingual lexical methods.

---

## Tables and figures

### Tables

| ID | Title | Content | Data source |
|----|-------|---------|-------------|
| T1 | Corpus composition by language | Row per language (en, pt, de, es, fr, zh, ja, other), columns: N works, % of corpus, N in core subset, % of core | `refined_works.csv` + `semantic_clusters.csv` |
| T2 | Four-quadrant classification | 2×2 table (EN/nonEN × North/South): N works, % with embeddings, % with citations, mean cited_by_count | `refined_works.csv` + `is_global_south()` |
| T3 | Language × cluster contingency | 6 clusters × 8 languages, cell = count, with χ² test statistic and p-value. Highlights cells with standardized residual > 2 | `semantic_clusters.csv` |
| T4 | Isolation scores by quadrant | 4 quadrants × summary stats (mean, median, SD, p10, p90 of isolation score), plus permutation test p-values for pairwise comparisons | Computed (new) |
| T5 | Orphan topics by quadrant | Top-10 distinctive TF-IDF terms for the most isolated decile in each quadrant, compared to their assigned cluster's signature | Computed (new) |
| T6 | Citation directionality | 4-cell flow table (N→N, N→S, S→N, S→S): raw counts, row-normalized %, expected under independence, and asymmetry ratio | `refined_citations.csv` + affiliation data |
| T7 | Temporal isolation trends | Mean isolation score per quadrant × period (pre-2007, 2007–2014, 2015–2024), with trend test | Computed (new) |

### Figures

| ID | Title | Type | What it shows |
|----|-------|------|--------------|
| F1 | Semantic map by language | UMAP scatter | All works; English in grey (α=0.2), non-English highlighted by language. **Already exists**: `fig_semantic_lang.png`. Adapt for publication quality. |
| F2 | Semantic map by quadrant | UMAP scatter | Same projection, colored by 4 quadrants (EN-N grey, EN-S blue, nonEN-N orange, nonEN-S red). Shows geographic vs linguistic separation. |
| F3 | Isolation score distributions | Violin + strip plot | One violin per quadrant, showing full distribution of isolation scores. Horizontal lines at medians. Key comparison: EN-South vs nonEN-North. |
| F4 | Isolation heatmap | Heatmap (4 quadrants × 6 clusters) | Mean isolation score per cell. Color gradient from low (integrated) to high (isolated). Reveals which quadrant × cluster combinations are most invisible. |
| F5 | Citation flow diagram | Sankey or alluvial | Directed citation flows between quadrants: width proportional to citation count. Asymmetry visible as unequal band widths. |
| F6 | Temporal isolation trends | Line plot | Mean isolation score per quadrant across 3 periods. Convergence = lines approach; entrenchment = lines diverge or stay flat. |
| F7 | Orphan topic wordclouds | 2×2 panel of wordclouds | Distinctive terms of the most isolated decile in each quadrant. Visual summary of what each tradition contributes that the mainstream lacks. |

---

## Detailed outline

### 1. Introduction (~1,000 words)

**1.1 The problem: monolingual mapping of a multilingual field**
- Climate finance spans the North-South divide by definition (Article 4.3 UNFCCC, Article 9 Paris Agreement). The object of study — financial flows from developed to developing countries — is constituted by the same geographic asymmetry that shapes knowledge production about it.
- Existing bibliometric studies (Carè & Weber 2023; Shang & Jin 2023; Maria et al. 2023) use Scopus or WoS (English-dominant), keyword co-occurrence or LDA (lexical, monolingual). They map the Anglophone core and call it "the field."
- This is not a complaint about coverage. It is a methodological claim: lexical methods *cannot* compare across languages. They are structurally incapable of detecting whether a French-language tradition on aide publique au développement and an English-language literature on ODA cover the same ground.

**1.2 Multilingual embeddings as minimum requirement**
- Sentence-transformer embeddings (BAAI/bge-m3) place documents in a shared semantic space regardless of language. Thematic proximity becomes measurable across languages.
- The case for multilingual embeddings has been made on technical grounds (coverage, precision). We make it on epistemic grounds: without cross-lingual comparison, the claim "we mapped the field" is unjustified for any field that spans languages.
- This is a testable claim. If multilingual analysis reveals nothing that monolingual analysis misses, the technical case collapses and English-only bibliometrics is adequate. We test it.

**1.3 Two axes, not one**
- Language (English / non-English) and geography (Global North / Global South) are correlated but distinct. Southern scholars often write in English; European scholars write in national languages. The 2×2 design disentangles linguistic from epistemic barriers.
- Preview of findings and roadmap.

### 2. Related work (~1,500 words)

**2.1 Language bias in scientometrics**
- The English dominance of bibliometric databases is well documented (van Leeuwen et al. 2001; Archambault et al. 2006; Mongeon & Paul-Hus 2016). But the argument has been about *coverage* (what's indexed) rather than *method* (what the tools can see).
- Huang & Zhao (2024, QSS) on linguistic diversity in science: closest precedent for our methodological argument.
- Amano et al. (2023, PLoS Biology) on language barriers in conservation science: systematic evidence that non-English evidence is ignored, with quantified consequences for policy.

**2.2 North-South knowledge production in climate**
- Corbera et al. (2016): geographic and disciplinary bias in IPCC AR5 authorship and citations. The IPCC reproduces the North-South hierarchy in its citation practices.
- Karlsson et al. (2007): North-South participation in environmental research. Structural asymmetry in who produces knowledge about whose climate.
- Bjurström & Polk (2011): disciplinary composition of IPCC citations. Frame for thinking about what "representative" citation means.
- Roberts & Parks (2007): climate justice framing — the political economy of who defines climate finance categories.

**2.3 Multilingual NLP in bibliometrics**
- Multilingual sentence-transformers: technical background. BAAI/bge-m3 (Chen et al. 2024): 111 languages, 8192-token context, state-of-the-art on MTEB.
- Applications in scientometrics remain rare. Most embedding-based bibliometrics uses English-only models (SPECTER, SciBERT). Constantino et al. (2025) used English embeddings for physics — a field with minimal language diversity. Our case requires multilingual capacity by design.
- Existing multilingual scientometrics: mostly counting (how many papers per language) rather than analyzing (what do they say differently).

**2.4 Climate finance bibliometrics**
- Carè & Weber (2023): VOSviewer, 7 clusters, English-only Scopus corpus. Finding: field insufficiently grounded in financial theory. Cannot see non-English traditions.
- Shang & Jin (2023): co-authorship networks, keyword analysis, Scopus. Finding: field started ~2010, dominated by environmental science. No language analysis.
- Maria et al. (2023): STM + network analysis. Only study to use a topic model, but monolingual.
- Common limitation: all three periodize exogenously and analyze monolingually. None tests whether non-English literatures add thematic content or just duplicate the English mainstream.

### 3. Data (~800 words)

**3.1 Corpus**
- ~32,000 refined works from 6 sources (OpenAlex, Semantic Scholar, ISTEX, bibCNRS, SciSpace, grey literature, teaching canon). Cross-reference the companion data descriptor.
- Language distribution: 93.1% English, 7% non-English across 15+ detected languages. [Table T1]
- Multilingual embeddings: BAAI/bge-m3, 1024 dimensions, normalized. All works with titles embedded regardless of language.
- Citation graph: ~970,000 directed edges within the corpus.

**3.2 Two-axis classification**
- Language axis: English vs. non-English, via OpenAlex metadata + langdetect fallback.
- Geography axis: Global North vs. Global South, via author affiliation country. Classification per OECD DAC recipient list. Works with mixed affiliations (North + South co-authors) classified as South if any Southern affiliation present.
- Four quadrants: EN-North (mainstream core), EN-South (Anglophone South), nonEN-North (European/Japanese traditions), nonEN-South (maximally invisible). [Table T2]
- Missing data: ~4% without language tag, ~20-30% without affiliation. Analyzed separately; excluded from quadrant analyses but included in aggregate statistics.

**3.3 Cluster structure**
- K-means clustering (k=6) on bge-m3 embeddings, from the Oeconomia paper. Cluster labels via TF-IDF distinctiveness. [Table T3 cross-references]
- Core subset: ~2,650 works cited ≥ 50 times. Expected to be overwhelmingly EN-North.

### 4. Method (~1,500 words)

**4.1 Semantic isolation scores**
- For each work *w*, compute cosine distance to its k=10 nearest neighbors among EN-North works. Mean distance = isolation score *I(w)*. Report for k ∈ {5, 10, 20} to verify robustness.
- Interpretation: *I(w)* measures semantic distance from the Anglophone mainstream — how far *w* is from the nearest thematic equivalent. High isolation does not imply "worse," only "different."
- Aggregate by quadrant and cluster. Two-way permutation test (quadrant × cluster interaction). [Table T4, Figure F3]
- Key comparison: mean *I*(EN-South) vs mean *I*(nonEN-North). If EN-South > nonEN-North, the divide is geographic; if nonEN-North > EN-South, it is linguistic. Report full distributions (violin plots), not just means — bimodal distributions would indicate mixed populations within quadrants.
- Caveat: EN-South isolation may partly reflect embedding model training bias (bge-m3 trained on Anglophone-dominant web text), not only epistemic difference. Acknowledged, not resolvable without retraining experiment.

**4.2 Thematic displacement analysis**
- For the top decile of isolated works ("semantic orphans") in each quadrant: extract distinctive TF-IDF terms from titles and abstracts.
- Compare with the TF-IDF signature of the orphans' assigned cluster. The difference = what the orphans add that the cluster mainstream lacks. [Table T5, Figure F7]
- This step makes the isolation score interpretable: not just "how far" but "in what direction."

**4.3 Citational directionality**
- Classify each citation edge by geography of citing and cited author: N→N, N→S, S→N, S→S. Compute directional asymmetry ratio: (N→S) / (S→N). [Table T6, Figure F5]
- Conditional on cluster: when the North cites the South, is the cited work in the same cluster (intellectual peer) or a different cluster (empirical case study)? Cross-cluster citation ratio as proxy for "South as data source."
- Limitations: proxy is indirect; affiliation data incomplete; co-authored papers complicate directionality. Present as suggestive, not definitive.

**4.4 Temporal dynamics**
- Repeat 4.1–4.3 for three periods: pre-2007, 2007–2014, 2015–2024. [Table T7, Figure F6]
- Convergence hypothesis: isolation decreases as the field matures and becomes more international.
- Entrenchment hypothesis: isolation persists or increases as Northern frameworks solidify.
- Differential dynamics: isolation may decrease on one axis (language) but not the other (geography), or vice versa. The two-axis design is essential to see this.

### 5. Results (~2,000 words)

**5.1 Non-random linguistic clustering** [H1]
- Contingency table results. Which clusters are enriched by which languages?
- Portuguese concentration in cluster 2 (visible in UMAP). German in cluster 3. Interpretation: these are not random scatters but thematic traditions (Brazilian development economics, German Energiewende literature).

**5.2 The geography of isolation** [H2]
- Isolation score distributions by quadrant. The key comparison: EN-South vs nonEN-North.
- If the result supports the epistemic hypothesis: Southern scholars writing in English still produce semantically distinct work. The barrier is not language access but intellectual framing.
- Orphan topics: what distinctive themes do the isolated works contribute?

**5.3 Citational asymmetry** [H3]
- Flow table and asymmetry ratio.
- Conditional analysis: does the North cite the South within the same tradition (peer) or across traditions (case study)?
- Cautious interpretation given data limitations. The cross-cluster proxy requires manual validation (~300 stratified citations coded as framework/case/method/other) before causal claims are warranted. Without validation, report the pattern as descriptive.
- Decompose by entry period: if asymmetry disappears for post-2015 works, it is a cohort effect (North entered first), not a structural dependency.

**5.4 Temporal dynamics** [H4]
- Three-period trends. Convergence, divergence, or stability?
- Differential by axis: language barriers vs geographic barriers may evolve at different rates.

**5.5 Isolation and impact** [H5, exploratory]
- For non-English works: scatter plot of isolation score vs. log(cited_by_count). Spearman correlation.
- If negative: well-cited non-English works are more integrated into the mainstream. Integration is rewarded.
- If uncorrelated: impact is independent of semantic proximity to the mainstream. The field can absorb distant contributions — or ignore them regardless.

**5.6 The core as filter**
- Core subset (~2,650, cited ≥ 50): language and geography composition. Expected finding: the citation threshold reproduces the hierarchy. The "most important" papers are overwhelmingly EN-North, by construction.

### 6. Discussion (~1,000 words)

**6.1 What multilingual analysis reveals**
- Synthesis: the three findings (clustering, isolation, citation asymmetry) tell a coherent story about epistemic structure, or they don't. If they do: the field has blind spots that are invisible to monolingual methods. If they don't (null results): monolingual methods are adequate and the fix is simply better indexing.

**6.2 Methodological implications for scientometrics**
- Multilingual embeddings as standard practice for fields at the science-policy interface (climate, health, development). Not optional; not a luxury.
- The isolation score as a replicable diagnostic: applicable to any corpus with multilingual embeddings and geographic metadata.
- Citation directionality as a complement to citation counting: who cites whom *in what role* matters more than how often.

**6.3 The irony of classification**
- We use the OECD DAC list to define North/South — the same institution whose classification of climate finance flows is the object of the field's contestation. The paper's method reproduces the categories it critiques. This is not a bug; it is a feature that should be acknowledged.

**6.4 Limitations**
- Affiliation data incomplete (~20-30% missing). Global South classification via keyword matching on affiliations, not institutional authority lookup. Sensitivity analysis with imputation bounds (see Robustness section).
- Embedding model choice: bge-m3 is state-of-the-art but trained primarily on web text, which overrepresents Anglophone academic writing. EN-South isolation may partly reflect training data imbalance. Resolving this requires a retraining experiment beyond scope.
- The 2×2 classification is crude. "Global South" conflates China, Brazil, Kenya, and Bangladesh. "Non-English" conflates French, Chinese, and Portuguese. Sensitivity analysis with alternative definitions (OECD DAC, UN LDC, World Bank income groups) tests whether qualitative patterns persist.
- Citation graph captures only within-corpus edges. Works citing non-corpus literature (especially grey literature in non-English languages) are invisible.
- Citation directionality proxy (cross-cluster = case study) is indirect and requires manual validation before causal interpretation.

### 7. Conclusion (~500 words)

- Restate the methodological argument: multilingual semantic analysis is necessary, not sufficient, for credibly mapping fields that span the North-South divide.
- Restate empirical findings (or null results, which are equally informative).
- Implications for future bibliometric studies of climate finance and other science-policy fields.
- Connection to the Oeconomia paper's argument: climate finance was constructed as an economic object primarily by Northern economists writing in English. This paper provides the methodological evidence for what that construction excludes.

---

## Key literature (seeds for literature review)

### Language bias in scientometrics

- **Amano, T., et al. (2023).** "The manifold costs of being a non-native English speaker in science." *PLoS Biology*, 21(7), e3002184. — Systematic evidence that language barriers exclude non-English research from global science. Quantifies the cost. Our paper provides a method to *detect* these exclusions in a specific field.

- **Huang, Y., & Zhao, S. (2024).** [Linguistic diversity in science — title TBC]. *Quantitative Science Studies*. — Published in our target journal. Closest methodological precedent. **TO FIND: exact reference.** [Not in main.bib — needs adding.]

- **Mongeon, P., & Paul-Hus, A. (2016).** "The journal coverage of Web of Science and Scopus: A comparative analysis." *Scientometrics*, 106(1), 213–228. — Quantifies English-language bias in major databases. Background for our "coverage is not the only problem" argument.

- **van Leeuwen, T. N., et al. (2001).** "Limits to the measurement of university research performance in international rankings." *Scientometrics*, 51(3), 659–671. — Early documentation of language bias in citation indices. Historical anchor.

- **Archambault, É., et al. (2006).** "Benchmarking scientific output in the social sciences and humanities: The limits of existing databases." *Scientometrics*, 68(3), 329–349. — SSH-specific database limitations. Relevant because climate finance is interdisciplinary with strong SSH component.

### North-South knowledge production in climate

- **Corbera, E., et al. (2016).** "Patterns of authorship in the IPCC Working Group III report." *Nature Climate Change*, 6, 94–99. DOI: 10.1038/nclimate2782. — Geographic bias in IPCC authorship. Our citation directionality analysis extends this from authorship to citation practice. [Not in main.bib — needs adding.]

- **Karlsson, S., et al. (2007).** "The role of science in global environmental governance." *Global Environmental Change*, 17, 1–2. — North-South asymmetry in environmental research production. Structural framing.

- **Bjurström, A., & Polk, M. (2011).** "Physical and economic bias in climate change research: A scientometric study of IPCC Third Assessment Report." *Climatic Change*, 108, 1–22. — Disciplinary bias in IPCC citations. [Already in main.bib.]

- **Roberts, J. T., & Parks, B. C. (2007).** *A Climate of Injustice: Global Inequality, North-South Politics, and Climate Policy.* MIT Press. — Political economy of climate justice. Frames the North-South divide as constitutive, not incidental.

### Multilingual NLP and embeddings

- **Chen, J., et al. (2024).** "M3-Embedding: Multi-Linguality, Multi-Functionality, Multi-Granularity Text Embeddings Through Self-Knowledge Distillation." *arXiv:2402.03216*. — The bge-m3 model paper. Technical reference for our embedding method.

- **Cohan, A., et al. (2020).** "SPECTER: Document-Level Representation Learning Using Citation-Informed Transformers." *ACL 2020*, 2270–2282. DOI: 10.18653/v1/2020.acl-main.207. — English-only document embeddings. We contrast: SPECTER cannot do what we need because it is monolingual. [Already in main.bib.]

- **Constantino, S. M., et al. (2025).** "Representing the Disciplinary Structure of Physics: A Comparative Evaluation of Graph and Text Embedding Methods." *QSS*. DOI: 10.1162/qss_a_00349. — Closest methodological peer. Physics has minimal language diversity; our case demands multilingual capacity. [Already in main.bib.]

- **Puccetti, G., et al. (2023).** "Semantic and Relational Spaces in Science of Science." *Scientometrics*, 128, 5553–5586. DOI: 10.1007/s11192-021-03984-1. — Text vs. graph embeddings comparison. [Already in main.bib.]

### Climate finance bibliometrics (the papers we critique)

- **Carè, R., & Weber, O. (2023).** "How Much Finance Is in Climate Finance?" *Research in International Business and Finance*, 64, 101886. DOI: 10.1016/j.ribaf.2023.101886. — VOSviewer, 7 clusters, English-only Scopus. Our primary foil: they map the Anglophone core and call it "the field." [Already in main.bib.]

- **Shang, Q., & Jin, X. (2023).** "A Bibliometric Analysis on Climate Finance." *ESPR*, 30(57), 119711–119732. DOI: 10.1007/s11356-023-31006-5. — Co-authorship networks, keyword analysis, Scopus. No language analysis. [Already in main.bib.]

- **Maria, M. R., et al. (2023).** "Evolution of Green Finance: A Bibliometric Analysis through Complex Networks and Machine Learning." *Sustainability*, 15(2), 967. DOI: 10.3390/su15020967. — Only existing study using a topic model. Monolingual. [Already in main.bib.]

### STS and epistemic framing (if targeting STS outlet)

- **Espeland, W. N., & Stevens, M. L. (1998).** "Commensuration as a Social Process." *Annual Review of Sociology*, 24, 313–343. DOI: 10.1146/annurev.soc.24.1.313. — Measurement as category-making. Embeddings as commensuration device. [Already in main.bib.]

- **Roberts, J. T., & Weikmans, R. (2017).** "Postface: Fragmentation, Failing Trust and Enduring Tensions over What Counts as Climate Finance." *INEA*, 17(1), 129–137. DOI: 10.1007/s10784-016-9347-4. — The politics of "what counts" — directly relevant to our argument about whose knowledge counts. [Already in main.bib.]

### Bibliography status

| Reference | In main.bib? | Action needed |
|-----------|-------------|---------------|
| Amano et al. 2023 | No | Add |
| Huang & Zhao 2024 | No | Find exact reference + add |
| Mongeon & Paul-Hus 2016 | No | Add |
| van Leeuwen et al. 2001 | No | Add |
| Archambault et al. 2006 | No | Add |
| Corbera et al. 2016 | No | Add |
| Karlsson et al. 2007 | No | Add |
| Roberts & Parks 2007 | No | Add |
| Chen et al. 2024 (bge-m3) | No | Add |
| Bjurström & Polk 2011 | Check | Verify |
| All others | Yes | — |

---

## Relation to other planned papers

- **Oeconomia paper** (submitted): provides the historical narrative and periodization. This paper provides the methodological foundation for why the corpus needed to be multilingual. The Oeconomia paper's argument — climate finance was constructed primarily by Northern economists — is supported empirically here.
- **Data paper** (RDJ4HSS, submitted): describes the corpus for reuse. This paper answers "why bother with non-English sources?" empirically. The data paper asserts multilingual design as a feature; this paper demonstrates its necessity.
- **Companion methods paper** (draft): focuses on temporal break detection and bimodality. Independent of language/geography analysis. Could cite this paper's isolation score as additional validation of the embedding space's utility.
- **Field structure paper** (`research-note-field-structure.md`): three-lens comparison (text/citation/COP). Could incorporate language as a fourth dimension, but the scope would expand too much. Better as separate papers that cross-reference.
- **Ravigné collaboration** (`research-note-ravigne.md`): IPCC selection bias. Complementary: we study what the field produces across languages; they study what the IPCC selects from that production.
