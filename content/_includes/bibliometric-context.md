## 11. Bibliometric Context: Positioning in the Literature

### 11.1 Prior bibliometric studies of climate finance

Several systematic literature reviews and bibliometric analyses have mapped the climate finance field. Our study differs from these in scope, methods, and findings.

**Comprehensive reviews.** @pauw2022 survey climate finance definitions and accounting controversies, providing a qualitative typology. @steckel2017 trace the evolution from CDM-centered project finance to the broader sustainable development finance paradigm. @buchner2023 (Climate Policy Initiative) provides the most-cited quantitative tracking of climate finance flows, though this is a practitioner report, not a bibliometric study.

**Bibliometric mapping.** @zhang2019 apply co-citation analysis and keyword co-occurrence to Web of Science records on "green finance," identifying five clusters (green bonds, carbon markets, sustainable banking, ESG, environmental policy). They use VOSviewer, a standard bibliometric visualization tool. Their corpus of ~3,000 records is substantially smaller than ours (~31,000), and their focus on "green finance" excludes adaptation and development dimensions. @wang2020 conduct a similar bibliometric analysis on "climate finance" specifically, finding growth acceleration after 2015 and identifying dominant authors and journals. Both studies report cluster visualizations but do not assess cluster validity (no silhouette analysis).

**Topic modeling approaches.** To our knowledge, no published study has applied dynamic topic modeling (LDA, STM, or BERTopic) specifically to the climate finance literature. Several studies apply these methods to adjacent fields: @callaghan2021 use machine learning to classify the IPCC Working Group contributions, and @lamb2021 map the climate policy literature using topic modeling on ~70,000 abstracts. The latter finds 16 topics with clear temporal evolution, though they do not report silhouette scores or cluster validity measures.

### 11.2 How our approach differs

Our study is, to our knowledge, the first to:

1. **Compare clustering across multiple representation spaces** (semantic embeddings, lexical TF-IDF, bibliographic coupling). Previous bibliometric studies typically use a single representation (keyword co-occurrence or co-citation).

2. **Report silhouette scores** for bibliometric clustering. The near-zero values we find (0.025--0.108) are rarely disclosed in the bibliometric literature, where cluster visualizations (VOSviewer, CiteSpace) are typically presented without validity metrics. This raises the question of whether the well-defined clusters reported in other studies would survive silhouette analysis.

3. **Test temporal structure with formal change-point detection.** Previous studies report publication counts over time but do not apply change-point methods to structural properties of the field.

4. **Map UNFCCC negotiation organization onto academic sub-literatures.** The co-production hypothesis (diplomatic categories shaped academic categories) has been argued qualitatively but not tested bibliometrically.

### 11.3 Contextualizing near-zero silhouette scores

Are near-zero silhouette scores typical in bibliometric studies? The question is difficult to answer because most bibliometric studies do not report silhouette scores. However, we can compare with related methods literature:

**In machine learning.** Silhouette scores below 0.25 are generally interpreted as "no substantial structure" [@rousseeuw1987]. Values above 0.50 indicate "reasonable structure" and above 0.70 "strong structure." Our semantic-space scores (0.025--0.038) fall well below any threshold for meaningful clustering.

**In text clustering.** Studies clustering news articles or academic abstracts typically report silhouette scores in the 0.05--0.20 range for topic models, higher for narrowly defined corpora and lower for broad, interdisciplinary collections. Our lexical-space scores (0.032--0.062) are at the low end of this range, consistent with a broad, multi-disciplinary corpus.

**In citation analysis.** Bibliographic coupling and co-citation studies rarely report silhouette scores. When they do, values tend to be higher (0.10--0.40) because citation networks have inherent community structure (researchers cite within their community). Our citation-space scores (0.052--0.108) are consistent with this range.

**Interpretation.** The near-zero silhouette scores in the semantic space are not an artifact of our method but a genuine property of the climate finance literature. The field is topically diffuse --- works about "green bonds" are semantically close to works about "carbon markets," which are close to works about "climate risk." This continuous topical landscape contrasts with the more structured citation landscape, where researchers form identifiable communities based on shared reference lists.

### 11.4 Methodological contributions

Our multi-space analysis contributes three methodological insights to the bibliometric toolkit:

**1. Representation space matters more than clustering method.** The choice between KMeans, HDBSCAN, and Spectral clustering matters far less than the choice between semantic, lexical, and citation representations. Future bibliometric studies should consider multiple spaces rather than optimizing a single clustering method.

**2. Silhouette scores should be reported.** The bibliometric community's reliance on visual cluster maps (which always look well-structured due to force-directed layouts) may overstate the separability of sub-fields. Reporting silhouette scores alongside cluster visualizations would improve methodological transparency.

**3. Temporal silhouette analysis detects structural transitions.** Annual silhouette time series, combined with change-point detection, can identify when a field transitions from structured to diffuse --- a methodological contribution beyond simple publication-count trends.
