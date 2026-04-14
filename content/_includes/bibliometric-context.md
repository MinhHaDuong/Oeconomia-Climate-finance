## 11. Bibliometric Context: Positioning in the Literature
<!-- WARNING: AI-generated, not human-reviewed -->

### Prior bibliometric studies of climate finance

Several studies have mapped the climate finance literature bibliometrically. Our study differs from these in scope, methods, and — crucially — in reporting cluster validity.

**Direct climate finance bibliometrics.** Carè and Weber (2023, *Research in International Business and Finance*) analyze 315 papers (2004--2021) using co-word analysis and VOSviewer, identifying 7 clusters and finding the field "not finance-based" — top finance journals are largely absent. Deb (2024, *Journal of Sustainable Finance & Investment*) applies co-citation and bibliographic coupling to 621 Web of Science papers, finding research started meaningfully in 2010 with China, US, and UK dominant. Singhania et al. (2023, *Environmental Science and Pollution Research*) map 657 WoS papers (1995--2020) using CiteSpace. Baran et al. (2024) classify 1,051 Scopus articles into 5 clusters: economic effects, governance, implementation, financing issues, and city-level finance. None of these studies report silhouette scores or cluster validity metrics.

**Topic modeling on adjacent fields.** Alonso-Robisco, Carbó, and Marqués (2024, *Journal of Sustainable Finance & Investment*) apply LDA to 217 ML-for-climate-finance papers, extracting 7 topics (natural hazards, carbon markets, ESG, energy economics, etc.). Reis Maria, Ballini, and Fraga Souza (2023, *Sustainability*) use Structural Topic Modeling on 3,275 RePec articles, finding 3 groups (international/UNFCCC framing, climate risk/green bonds, energy-emissions-economics models) with a temporal shift from international to national framing. This is methodologically the closest to our approach.

**Corpus sizes in context.** Our corpus of ~31,000 works is 10--100× larger than any previous climate finance bibliometric study (315--3,275 papers). This matters: small corpora may produce artificially well-separated clusters by undersampling the boundary-spanning works that create continuity.

### How our approach differs

Our study is, to our knowledge, the first to:

1. **Compare clustering across multiple representation spaces** (semantic embeddings, lexical TF-IDF, bibliographic coupling). Previous bibliometric studies typically use a single representation. The hybrid approach has precedent in general bibliometrics: Yu et al. (2017, *PLoS One*) combine citation and text signals for 7,303 papers, finding optimal weights of α=0.55 (citation) and β=0.45 (text). Our contribution is to compare the spaces rather than fuse them, revealing their independence (ARI 0.06--0.22).

2. **Report silhouette scores.** The near-zero values we find (0.025--0.108) are never reported in the climate finance bibliometric literature, where cluster visualizations (VOSviewer, CiteSpace) are presented without validity metrics. Silhouette analysis is well-established in the topic modeling literature — Mäntylä, Claes, and Farooq (2018, ACM ESEM) show that single-run LDA is "dangerous" and recommend stability metrics including silhouette. Krasnov et al. use silhouette-based cluster quality to select the number of topics rather than perplexity alone.

3. **Test whether UNFCCC categories are natural clusters** (negative silhouette = anti-clustered). No previous study has tested whether the field's conventional categories correspond to empirical structure.

4. **Apply formal change-point detection** to structural properties of the field, as opposed to counting publications over time.

### Contextualizing near-zero silhouette scores

Are near-zero silhouette scores typical or exceptional?

**In bibliometrics.** Bascur, Verberne, van Eck, and Waltman (2024, *Scientometrics*) provide the most relevant benchmark. Analyzing 2.94 million PubMed documents with Leiden clustering on both citation and text networks, they find that **cross-disciplinary and methodological topics cluster poorly** in both networks, while diseases, psychology, and anatomy cluster well. Climate finance — spanning environmental science, economics, political science, and finance — is precisely the kind of boundary-spanning field that resists clean clustering. Our low silhouette scores are consistent with this finding.

**In machine learning.** Rousseeuw (1987) interprets silhouette scores below 0.25 as "no substantial structure." Our semantic-space scores (0.025--0.038) fall far below this threshold.

**In clustering method comparisons.** Šubelj, van Eck, and Waltman (2016, *PLoS One*) compare 30 clustering methods on WoS networks, finding that spectral methods are the least stable (instability ~0.4) and Infomap/map-equation methods perform best. This corroborates our finding that Spectral clustering is the least stable method in our comparison.

**Interpretation.** The near-zero silhouette is not an artifact but a genuine property of the field. It places climate finance among the "boundary-spanning" domains identified by Bascur et al. (2024) that inherently resist bibliometric clustering. This is itself a finding about the field's intellectual structure.

### Methodological contributions

Our multi-space temporal analysis contributes three methodological insights:

**1. Representation space matters more than clustering method.** The choice between KMeans, HDBSCAN, and Spectral matters less than the choice between semantic, lexical, and citation representations (Section 7.8). Yu et al. (2017) show that hybrid citation+text outperforms either alone; we extend this by showing that the spaces are largely independent and capture different structural dimensions.

**2. Silhouette scores should be standard in bibliometrics.** VOSviewer and CiteSpace produce compelling cluster visualizations that always appear well-structured due to force-directed layouts. Reporting silhouette scores alongside visualizations would reveal which clusters are genuine and which are artifacts of the layout algorithm. The Mäntylä et al. (2018) stability framework for LDA should be extended to embedding-based methods.

**3. Temporal silhouette analysis detects structural transitions.** Our change-point detection on annual silhouette series (Section 9) identifies when a field transitions from structured to diffuse — a contribution beyond publication-count trends or keyword-frequency tracking, which are the standard temporal methods in the climate finance bibliometric literature.
