# Literature review: structural break detection in scientific corpora

Date: 2026-04-14
Context: ticket 0026 (periodization paper)

## 1. The dominant paradigm: CiteSpace and burst detection

The standard bibliometric tool for detecting "turning points" in scientific
literature is CiteSpace (Chen 2006). It combines Kleinberg's (2003) burst
detection algorithm on terms and cited references with Freeman's (1979)
betweenness centrality to identify pivot papers bridging communities.

CiteSpace does not perform formal statistical change point detection. It
identifies emerging terms and articles and visualizes them on time-zone maps.
The choice of time slices is manual, and the output is exploratory rather
than inferential. The method has been applied to hundreds of fields over
two decades and remains the most widely used approach.

- Chen, C. (2006). CiteSpace II: Detecting and visualizing emerging trends
  and transient patterns in scientific literature. *JASIST*, 57(3), 359-377.
  https://doi.org/10.1002/asi.20317
- Kleinberg, J. (2003). Bursty and hierarchical structure in streams. *KDD*.
  https://doi.org/10.1145/775047.775061

## 2. Phylomemetic patterns (Chavalarias & Cointet 2013)

Phylomemetic reconstruction models the evolution of scientific fields as
lineage relationships between term co-occurrence clusters across time slices.
It identifies regularities: emergence, branching, merging, decline. The
approach is bottom-up and does not require fixing a global number of clusters,
but relies on local clustering of term pairs at each time step.

Phylomemies describe evolution qualitatively rather than testing for abrupt
structural breaks. The lifecycle model (cohesion increase after emergence,
renewal through branching/merging, decay when density drops) is a descriptive
framework, not a statistical test.

- Chavalarias, D. & Cointet, J.-P. (2013). Phylomemetic patterns in science
  evolution: The rise and fall of scientific fields. *PLOS ONE*, 8(2), e54847.
  https://doi.org/10.1371/journal.pone.0054847

## 3. Dynamic Topic Models (Blei & Lafferty 2006)

DTMs extend LDA by allowing topic distributions to evolve over time via a
Gaussian random walk on the natural parameters. Widely used, but two
limitations for break detection:

1. The number of topics k must be fixed a priori (the arbitrary-k problem
   that motivates our continuous approach).
2. The Gaussian chain assumes smooth evolution, making DTMs poorly suited
   for detecting *abrupt* structural breaks.

Modern successors include BERTrend (2024), which uses neural embeddings and
HDBSCAN for dynamic topic detection, and ATEM (2024), which combines dynamic
topic modeling with dynamic graph embeddings. Both remain in the topic-based
paradigm with implicit cluster counts.

- Blei, D. M. & Lafferty, J. D. (2006). Dynamic Topic Models. *ICML*.
  https://doi.org/10.1145/1143844.1143859
- BERTrend (2024). Neural topic modeling for emerging trends detection.
  https://arxiv.org/abs/2411.05930
- ATEM (2024). A topic evolution model for the detection of emerging topics
  in scientific archives. *ECIR 2024*.
  https://doi.org/10.1007/978-3-031-53472-0_28

## 4. Semantic changepoint detection (Kurchaninova & Koltcov 2021)

The most direct precedent for our distributional approach. They compute
document embeddings per time window, calculate semantic drift as the cosine
distance between consecutive centroids:

    delta_t = 1 - cos(c_t, c_{t-1})

and apply changepoint detection to the resulting time series.

**Limitation:** the centroid cosine is a single scalar summary of two
distributions. It captures mean shift but not changes in dispersion,
multimodality, or tail behavior. Our methods S1-S4 (MMD, energy distance,
sliced Wasserstein, Frechet) are full distributional tests that detect
any change in the embedding distribution, not just centroid displacement.

- Kurchaninova, E. & Koltcov, S. (2021). Semantic changepoint detection
  for finding potentially novel research publications. *Front. Res. Metr.
  Anal.*, 6, 684050.
  https://doi.org/10.3389/frma.2021.684050

## 5. Embedding approaches for topic evolution (Niu et al. 2023)

Models research topics as multidimensional vectors (Doc2Vec or
sentence-transformers), measures inter-topic distances over time. Their
similarity metric is more stable than Jaccard and outperforms alternatives,
but the analysis remains centroid-based: it compares mean vectors, not
distributions.

- Niu, J. et al. (2023). An embedding approach for analyzing the evolution
  of research topics with a case study on computer science subdomains.
  *Scientometrics*, 128(3), 1567-1594.
  https://doi.org/10.1007/s11192-023-04642-4

## 6. Novelty / Transience / Resonance (Barron et al. 2018)

A well-established framework for measuring innovation dynamics in text
corpora. For each document:

- Novelty = KL(doc || past): divergence from previous discourse
- Transience = KL(doc || future): divergence from subsequent discourse
- Resonance = Novelty - Transience: new patterns that persist

Aggregated per year, novelty peaks signal moments of disruption while
resonance identifies lasting structural changes.

Applied successfully to:
- French Revolution debates (Barron et al. 2018)
- Brazilian economics research (Ribeiro et al. 2022)
- Rap music lyrics (USF 2023)
- Chinese diaspora media (2024)

The framework uses topic model outputs (LDA) as the distributional
representation, making it complementary to embedding-based methods.

- Barron, A. T. J. et al. (2018). Individuals, institutions, and innovation
  in the debates of the French Revolution. *PNAS*, 115(18), 4607-4612.
  https://doi.org/10.1073/pnas.1717729115

## 7. Distributional distance methods from ML/statistics

These methods are well established in their home fields but have **not been
applied to bibliometric corpora**. This is the main methodological gap our
work would fill.

### 7.1 MMD — Maximum Mean Discrepancy (Gretton et al. 2012)

Kernel-based two-sample test. Compares distributions by embedding them in
a reproducing kernel Hilbert space (RKHS). Consistent against all
alternatives when using a characteristic kernel. Quadratic time in sample
size (subsampling or linear-time approximations available).

- Gretton, A. et al. (2012). A kernel two-sample test. *JMLR*, 13, 723-773.

### 7.2 Energy distance (Szekely & Rizzo 2004, 2013)

Distribution-free two-sample test based on pairwise Euclidean distances
between points from two samples. No kernel to choose. Consistent against
all alternatives with finite first moments. Mathematically related to MMD
with the energy kernel (Sejdinovic et al. 2013).

- Szekely, G. J. & Rizzo, M. L. (2004). Testing for equal distributions
  in high dimension. *InterStat*, 5.
- Szekely, G. J. & Rizzo, M. L. (2013). Energy statistics: A class of
  statistics based on distances. *J. Stat. Plan. Inf.*, 143(8), 1249-1272.

### 7.3 Sliced Wasserstein distance (Bonneel et al. 2015)

Approximates optimal transport cost by averaging 1D Wasserstein distances
over random projections. Scalable to high dimensions (embeddings are
1024-dim in our case). Captures geometric structure that MMD may smooth
over.

- Bonneel, N. et al. (2015). Sliced and Radon Wasserstein barycenters of
  measures. *JMIV*, 51(1), 22-45.

### 7.4 Frechet distance / FID (Dowson & Landau 1982)

Models each sample as a multivariate Gaussian (mean + covariance), computes
the Frechet distance between them. Popularized as FID for evaluating
generative models (Heusel et al. 2017). Parametric assumption is a
limitation but keeps computation fast.

- Dowson, D. C. & Landau, B. V. (1982). The Frechet distance between
  multivariate normal distributions. *JMVA*, 12, 450-455.

### 7.5 WATCH: Wasserstein change point detection (Li & Yu 2022)

The first dedicated algorithm for change point detection using Wasserstein
distance in high-dimensional data. Models the current distribution and
monitors behavior over time using a threshold-ratio approach. Designed for
IoT/traffic data, never applied to scientific corpora.

- Li, K. & Yu, S. (2022). WATCH: Wasserstein change point detection for
  high-dimensional time series data. *IEEE Int. Conf. Big Data*.
  https://arxiv.org/abs/2201.07125

### 7.6 MMDEW: MMD on exponential windows

Online change detection combining MMD with exponential windows for
polylogarithmic runtime and logarithmic memory. Suited to streaming
settings where the corpus grows over time.

- Cobb, A. D. et al. (2022). Maximum Mean Discrepancy on exponential
  windows for online change detection. https://arxiv.org/abs/2205.12706

## 8. Diachronic word embeddings (Hamilton et al. 2016)

Train word2vec models per time period, align via orthogonal Procrustes
transformation, measure the residual rotation. Established two "laws" of
semantic change: frequency correlates with slower change, polysemy with
faster change.

This is our method S5. Well established in computational linguistics but
rarely applied in bibliometrics where the focus is on document-level rather
than word-level analysis.

- Hamilton, W. L. et al. (2016). Diachronic word embeddings reveal
  statistical laws of semantic change. *ACL*.
  https://doi.org/10.18653/v1/P16-1141

## 9. Disruption index (Funk & Owen-Smith 2017; Wu et al. 2019)

The CD index measures whether a paper consolidates the existing paradigm
(its citants also cite its references) or disrupts it (its citants ignore
the prior literature). Defined as:

    CD_i = (n_i - n_j) / (n_i + n_j + n_k)

where n_i = papers citing i but not i's references, n_j = papers citing
both, n_k = papers citing i's references but not i.

Wu et al. (2019) in *Nature* showed that papers and patents are becoming
less disruptive over time across all fields. Aggregated per year, mean CD
is a continuous indicator of structural disruption vs. consolidation — no
clustering required.

- Funk, R. J. & Owen-Smith, J. (2017). A dynamic network measure of
  technological change. *Management Science*, 63(3), 791-817.
- Wu, L. et al. (2019). Large teams develop and small teams disrupt science
  and technology. *Nature*, 566, 378-382.
  https://doi.org/10.1038/s41586-019-0941-9

## 10. Citation network temporal dynamics

### 10.1 PageRank volatility

PageRank (Brin & Page 1998) is well established in bibliometrics (Ding
2009). The temporal extension — measuring rank displacement between
consecutive time slices — is less common but methodologically
straightforward. Bras-Amoros et al. (2023) show PageRank values are
field-dependent, making within-field temporal analysis (our G1) the natural
use case.

- Ding, Y. (2009). Applying weighted PageRank to author citation networks.
  *JASIST*, 60(11), 2229-2243.
- Bras-Amoros, M. et al. (2023). The field-dependent nature of PageRank
  values in citation networks. *Scientometrics*, 128, 387-406.

### 10.2 Betweenness centrality dynamics (Chen 2006)

CiteSpace uses betweenness centrality to identify pivot papers, but
typically at the individual paper level. Aggregating betweenness statistics
(mean, max, or Gini coefficient) per time slice produces a continuous
indicator of structural bridging in the citation network.

- Freeman, L. C. (1979). Centrality in social networks: Conceptual
  clarification. *Social Networks*, 1, 215-239.
- Chen, C. (2006). CiteSpace II. *JASIST*, 57(3), 359-377.

### 10.3 Temporal representations of citations (He & Chen 2018)

Represents the changing citation contexts of publications across time
periods as sequences of vectors. Quantifies how much the role of a
publication changed and interprets the nature of the change.

- He, J. & Chen, C. (2018). Temporal representations of citations for
  understanding the changing roles of scientific publications. *Front. Res.
  Metr. Anal.*, 3, 27.
  https://doi.org/10.3389/frma.2018.00027

### 10.4 Normalized impact and discovery periods (Bol et al. 2024)

Network-based normalized impact measure that identifies successful periods
of scientific discovery across disciplines. Shows that Cell Biology lost
and regained its breakthrough capacity over decades — a regime shift
detectable through citation network indicators.

- Bol, T. et al. (2024). A network-based normalized impact measure reveals
  successful periods of scientific discovery across disciplines. *PNAS*,
  121(1), e2309378120.
  https://doi.org/10.1073/pnas.2309378120

## 11. Change point detection methods (meta-layer)

### 11.1 PELT (Killick et al. 2012)

Pruned Exact Linear Time method for detecting multiple changepoints. Uses
a penalized cost function (BIC, MBIC, or Hannan-Quinn). Does not require
fixing the number of changepoints — the penalty controls model complexity.
The standard choice for offline multiple changepoint detection.

- Killick, R. et al. (2012). Optimal detection of changepoints with a linear
  computational cost. *JASA*, 107(500), 1590-1598.

### 11.2 BOCPD — Bayesian Online Change Point Detection (Adams & MacKay 2007)

Bayesian approach that maintains a posterior distribution over the current
"run length" (time since the last changepoint). Outputs a probability of
change at each time point rather than a binary decision. Natural for
streaming data but applicable offline. Does not require fixing the number
of changepoints.

- Adams, R. P. & MacKay, D. J. C. (2007). Bayesian online changepoint
  detection. https://arxiv.org/abs/0710.3742

### 11.3 Kernel CPD (Harchaoui et al. 2009)

CUSUM-style test statistic based on MMD. Detects changepoints in
multivariate distributions without parametric assumptions. Can be applied
directly to embedding time series without first reducing to scalar
divergence measures.

- Harchaoui, Z. et al. (2009). Kernel change-point analysis. *NIPS*, 22.

## 12. Gap analysis: what our panel contributes

| What exists in bibliometrics | What is missing |
|------------------------------|-----------------|
| Burst detection (per-term, CiteSpace) | Full distributional two-sample tests on embedding distributions |
| Cosine between centroids (Kurchaninova 2021) | MMD, energy distance, Wasserstein — sensitive to dispersion, multimodality, tails |
| Dynamic Topic Models (fixed k) | Cluster-free continuous divergence measures |
| PageRank at individual paper level | PageRank volatility as time series |
| Disruption index per paper | Disruption index aggregated as temporal regime indicator |
| Betweenness centrality per paper (CiteSpace) | Betweenness dynamics as time series |
| Heuristic visual segmentation | Principled change point detection (PELT, BOCPD, kernel CPD) |

The core contribution: bringing rigorous two-sample testing from
ML/statistics into bibliometric temporal analysis, combined with established
bibliometric indicators recast as continuous time series, and applying
principled change point detection to the resulting multi-channel signal.

Convergence across independent channels (semantic, lexical, citation) is
the robustness criterion. A break detected by only one channel may be a
method artifact; a break detected by all three is a genuine structural
change in the field.
