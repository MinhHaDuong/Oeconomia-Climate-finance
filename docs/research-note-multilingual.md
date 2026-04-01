# Whose climate finance? Semantic blind spots across languages and geographies

## Research note — Ha-Duong

### Abstract (250 words)

Bibliometric analyses of climate finance rely predominantly on English-language databases and lexical methods. We argue that this is not merely a coverage gap but a methodological bias: lexical approaches cannot detect thematic differences across languages, and English-only corpora erase both non-Anglophone intellectual traditions and Global South perspectives expressed in English. Multilingual sentence embeddings are a minimum methodological requirement — not because they necessarily change substantive results, but because without them the claim "we mapped the field" is unjustified.

Using a corpus of ~32,000 works with multilingual embeddings (BAAI/bge-m3), a citation graph (~970,000 edges), and author affiliation metadata, we construct a two-axis classification: language (English / non-English) and geography (Global North / Global South, per OECD DAC). This yields four quadrants with distinct epistemic positions. For each, we compute a semantic isolation score — distance to the nearest English-language North neighbors — and extract the distinctive thematic terms of the most isolated works.

We then test three hypotheses. First, non-English works are not randomly distributed across the field's thematic clusters but concentrate in specific traditions (development aid, adaptation), selectively enriching some topics while leaving others unchanged. Second, Global South works — even those written in English — occupy distinct regions of the embedding space, indicating that the North-South divide is epistemic, not merely linguistic. Third, the citation graph is directionally asymmetric: Southern works are cited as empirical cases more than as conceptual frameworks.

The paper's contribution is methodological: it demonstrates what multilingual semantic analysis makes visible that lexical bibliometrics cannot see.

### 1. Problem

Standard scientometric analyses of climate finance use Scopus, Web of Science, or Crossref — databases that index predominantly English-language works. Even when non-English works are included, the analytical methods are typically lexical: keyword co-occurrence, TF-IDF topic models, LDA. These methods cannot compare across languages because they operate on surface vocabulary. A French paper on "finance climat" and an English paper on "climate finance" share no lexical features.

Multilingual sentence embeddings solve this: they place all works in a shared semantic space where thematic proximity is measurable regardless of language. But the case for multilingual embeddings in scientometrics has been made primarily on technical grounds (coverage, precision). We make it on epistemic grounds: without multilingual semantic analysis, we cannot credibly claim to have mapped a field that spans the Global North-South divide.

Climate finance is a particularly revealing test case. The field's object of study — financial flows from North to South — is defined by the very geographic asymmetry that shapes its knowledge production. Who produces knowledge about these flows, in what languages, and through what intellectual frameworks is not a secondary question — it is part of the field's constitution as an economic object.

### 2. Data

The corpus comprises ~32,000 refined works from six sources (OpenAlex, ISTEX, bibCNRS, SciSpace, grey literature, teaching canon). Each work has:

- A multilingual embedding (BAAI/bge-m3, 768 dimensions)
- A position in the citation graph (~970,000 directed edges within the corpus)
- Detected language (via OpenAlex + langdetect)
- Author affiliation country (via OpenAlex, available for ~70-80% of academic works)
- Cluster assignment (k=6) and period assignment

We classify works along two axes:

| | Global North | Global South |
|--|-------------|-------------|
| **English** | Mainstream core (~22K) | Anglophone South (~3K) |
| **Non-English** | European/Japanese traditions (~4K) | Maximally invisible (~1K) |

Counts are estimates; actual distribution to be computed. Works with missing affiliations are analyzed separately. The OECD DAC list defines North/South, which is ironic given the paper's argument but provides a standard, reproducible classification.

The core subset (~2,300 works cited ≥ 50) serves as a robustness check: we expect it to be overwhelmingly English and Northern.

### 3. Method

**Step 1 — Semantic isolation scores.**
For each work, compute cosine distance to its k=10 nearest neighbors in the English-North quadrant (the mainstream). This produces an isolation score per work: how far is this work from the Anglophone mainstream's nearest thematic equivalent?

Aggregate isolation scores by quadrant (EN-North, EN-South, nonEN-North, nonEN-South) and by cluster (6 thematic clusters). Two-way ANOVA or permutation test on quadrant × cluster. The question: is the South-English quadrant closer to or farther from the mainstream than the North-non-English quadrant? If the South is more isolated than non-English Europeans, the divide is geographic, not linguistic.

**Step 2 — Thematic displacement analysis.**
For the top decile of isolated works in each quadrant ("semantic orphans"), extract distinctive terms via TF-IDF on their titles and abstracts. Compare with the TF-IDF signature of their assigned cluster. What topics do the orphans add that the mainstream lacks?

Visualization: heatmap of mean isolation score by quadrant × cluster. UMAP scatter with works colored by isolation score (gradient), English-North in grey.

**Step 3 — Citational directionality.**
For works with author-country metadata, classify each citation edge as:
- N→N (North cites North)
- N→S (North cites South)
- S→N (South cites North)
- S→S (South cites South)

Compute the directional asymmetry ratio: (N→S) / (S→N). If Southern works are cited by the North primarily when they provide case studies (i.e., the citing Northern work is in a different, more "applied" cluster than the cited Southern work), this indicates the South is used as data source, not as intellectual framework.

This is the most contested step. The proxy (cluster difference between citing and cited work) is indirect. We present it as suggestive, not definitive.

**Step 4 — Temporal dynamics.**
Repeat steps 1-3 for each period (pre-2007, 2007-2014, 2015-2024). Does isolation decrease as the field matures (convergence), or does it persist or increase (entrenched asymmetry)? If it decreases for the South-English quadrant but not for non-English works, language barriers persist while geographic barriers weaken — or vice versa.

### 4. What would be genuinely surprising

- **The South-English quadrant is NOT isolated.** Southern scholars writing in English produce work semantically indistinguishable from the Northern mainstream. That would mean the barrier is purely linguistic, not epistemic. The methodological implication: multilingual embeddings are sufficient; no further North-South correction is needed.

- **Orphan topics are random, not systematic.** Non-English isolated works have no coherent thematic pattern — they are scattered outliers, not a suppressed tradition. That would weaken the "blind spots" argument.

- **Citation asymmetry is symmetric.** North cites South and South cites North in equal proportions and similar roles. That would mean the knowledge production hierarchy exists only in coverage, not in intellectual exchange.

Any of these null results is publishable and important: it would mean the English-centrism of bibliometrics is a coverage problem, not an epistemic one, and the fix is inclusion, not methodological overhaul.

### 5. Contribution

1. **Methodological argument.** Multilingual semantic analysis is a minimum requirement for credibly mapping fields that span the North-South divide. This is not because it necessarily changes results, but because without it the claim "we mapped the field" is epistemically unjustified. We provide a replicable protocol (isolation scores, directional citation analysis) for testing this.

2. **Empirical characterization.** A two-axis (language × geography) map of climate finance's epistemic structure, identifying which quadrant × cluster combinations are most isolated from the mainstream.

3. **Methodological critique.** A specific, quantified argument against purely lexical bibliometrics on English-only databases — not as a political statement but as a methodological one: the method cannot see what it claims to map.

### 6. Target journal

Primary: **Quantitative Science Studies** (MIT Press, $750 with ISSI membership). Scope fit: methodological contribution to scientometrics with empirical application. They published Huang & Zhao (2024) on linguistic diversity.

Alternative: **Scientometrics** (Springer, Couperin may cover APC). Broader audience, more empirical tolerance.

If the results are strong enough for the epistemic argument: **Research Evaluation** (OUP) or **Science, Technology, & Human Values** (STS framing).

### 7. Relation to other planned papers

This paper provides the **methodological foundation** for the multilingual corpus design described in the RDJ4HSS data paper (submitted). It answers the question "why bother with non-English sources?" empirically. It is independent of the Oeconomia paper (which uses the same corpus but focuses on periodization and history) and the Ravigné collaboration (which focuses on IPCC selection). The three-lenses paper (text/citation/COP) could cite this for its language-dimension results.
