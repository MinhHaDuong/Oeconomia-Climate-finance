Excellent—this is exactly the right moment to **convert thinking into an executable program**. Below is a **coherent, production-ready roadmap** that your coding agent can turn into an **epic with tickets**. I’ve removed ambiguity, fixed the epistemic positioning, and made **interfaces, inputs/outputs, and tasks explicit**.

I reference your draft here for continuity , but this version is **fully operationalized**.

---

# ROADMAP — METHOD PAPER + IMPLEMENTATION EPIC

## Title (working)

**Multi-layer Detection and Validation of Structural Change in Text Corpora**

---

# 0. Product definition (what you are building)

## Deliverables

1. **Paper**

   * Methods + application (climate finance corpus)
2. **Reproducible pipeline**

   * deterministic, config-driven
3. **Figure suite (4 canonical outputs)**
4. **Replication package**

---

## Core epistemic stance (must be encoded everywhere)

> The method detects candidate structural changes and provides a framework to **validate and interpret them across multiple representations**. It does **not claim to uniquely discover true periodization**.

This must be reflected in:

* naming (`detect_candidates`, `validate_breakpoints`)
* outputs (scores + evidence, not “final truth”)

---

# 1. System architecture

## Pipeline overview

```
Corpus → Representations → Temporal splits → Metrics → Time series
      → Candidate detection → Validation → Interpretation → Figures
```

---

## Data model

### Document object

```python
Document:
    id: str
    year: int
    text: str
    embedding: np.ndarray  # (p,)
    tokens: Dict[str, int] # or sparse vector
    citations_out: List[str]
```

---

## Core data structures

```python
Corpus: List[Document]

Split:
    before_ids: List[str]
    after_ids: List[str]

MetricsResult:
    t: int
    mmd: float
    energy: float
    auc: float
    js: float
    graph_div: float
    z_scores: Dict[str, float]

Breakpoint:
    t: int
    scores: MetricsResult
    validated: bool
```

---

# 2. Configuration system (MANDATORY)

Single config file:

```yaml
time:
  min_year: 1990
  max_year: 2024
  window_type: expanding   # or sliding
  min_docs: 30

embedding:
  model: sentence-transformer
  normalize: true

mmd:
  kernel: rbf_multiscale
  sigmas: [median, median*2, median/2]

permutation:
  n_perm: 500
  scheme: local_pool   # NOT global

graph:
  type: cocitation
  temporal_rule: no_future_edges

validation:
  min_signals: 2
  min_distance_years: 3
```

---

# 3. Modules (EPIC breakdown)

---

## EPIC 1 — Data preparation

### Ticket 1.1: Corpus ingestion

* input: raw metadata + texts
* output: `Corpus`

### Ticket 1.2: Embedding generation

* deterministic
* cached to disk

### Ticket 1.3: Tokenization

* TF or TF-IDF
* sparse format

### Ticket 1.4: Citation graph construction

* choose: **co-citation**
* rule: only references ≤ t

---

## EPIC 2 — Temporal segmentation

### Ticket 2.1: Split generator

```python
def generate_splits(corpus, config) -> List[Split]
```

Constraints:

* enforce `min_docs`
* handle unequal sizes

---

## EPIC 3 — Metrics computation

### Ticket 3.1: MMD (core)

```python
compute_mmd(X, Y, sigmas) -> float
```

Requirements:

* unbiased estimator
* vectorized

---

### Ticket 3.2: Energy distance

```python
compute_energy(X, Y) -> float
```

---

### Ticket 3.3: C2ST

```python
compute_auc(X, Y) -> float
```

* logistic regression
* class weights balanced
* CV (k=5)

---

### Ticket 3.4: Lexical JS

```python
compute_js(p, q) -> float
```

* normalized distributions
* smoothing required

---

### Ticket 3.5: Graph divergence

```python
compute_graph_div(before_graph, after_graph) -> float
```

Implementation:

* community detection (Louvain)
* compare distributions:

  * KL / JS between community shares

---

## EPIC 4 — Statistical inference

### Ticket 4.1: Permutation test

```python
permutation_test(X, Y, metric_fn)
```

Constraints:

* preserve sample sizes
* shuffle labels within pooled split

---

### Ticket 4.2: Z-score normalization

```python
z = (obs - mean_perm) / std_perm
```

Store per metric.

---

## EPIC 5 — Time series construction

### Ticket 5.1: Compute metrics over all t

```python
compute_time_series(corpus, splits) -> List[MetricsResult]
```

Output:

* dataframe indexed by year

---

## EPIC 6 — Breakpoint detection

### Ticket 6.1: Candidate detection

```python
detect_candidates(series) -> List[int]
```

Rules:

* local maxima
* above threshold (e.g. Z > 2)

---

### Ticket 6.2: Regularization

* enforce minimum distance between breakpoints
* keep strongest peaks

---

## EPIC 7 — Validation layer

### Ticket 7.1: Multi-signal validation

```python
validate_breakpoints(candidates, metrics)
```

Rule:

* ≥2 signals exceed threshold

---

### Ticket 7.2: Subsampling robustness

* downsample larger side
* recompute metrics
* compute variance

---

## EPIC 8 — Interpretation layer

### Ticket 8.1: Discriminative terms

* log-odds ratio
* output: top ± terms

---

### Ticket 8.2: Discriminative documents

* classifier coefficients OR distance
* output: ranked list

---

### Ticket 8.3: Graph interpretation

* dominant communities before/after
* transitions

---

## EPIC 9 — Figures

### Ticket 9.1: Time series plot

* MMD, JS, graph signals

### Ticket 9.2: Breakpoint plot

* peaks + validated breaks

### Ticket 9.3: Lexical shifts

* bar chart

### Ticket 9.4: Community flow (optional)

* alluvial

---

# 4. Methods (paper-ready, tightened)

## Key framing

> We define structural change as a statistically detectable difference between distributions of document representations across time, evaluated across independent representations.

---

## Formal components

### Representations

* ( x \in \mathbb{R}^p ) (embedding)
* ( w \in \mathbb{R}^V ) (lexical)
* ( G ) (graph)

---

### Core statistic

Use MMD as primary detector.

Interpretation:

* nonparametric
* high-dimensional robust
* unequal sample compatible

---

### Multi-layer logic

| Layer     | Function                 |
| --------- | ------------------------ |
| Embedding | detect semantic shift    |
| Lexical   | explain vocabulary       |
| Graph     | detect structural change |

---

### Breakpoint definition

> A breakpoint is a time ( t ) where multiple independent signals indicate a statistically significant distributional shift.

---

### Validation rule

> A breakpoint is retained if at least two signals exceed threshold under permutation-normalized scores.

---

### Null hypothesis

> No difference in distributions between before/after samples at time ( t ), conditional on local sampling.

---

# 5. Literature review (actionable)

## Keep it to 2 pages max

### Section structure

1. Two-sample testing (MMD, energy)
2. Change-point detection
3. Text evolution (DTM, embeddings)
4. Scientometrics

### Final paragraph (critical)

> None of these approaches jointly provide:

* statistical testing
* multi-representation validation
* interpretability

---

# 6. Quality control / failure modes

Must implement:

* minimum sample size filter
* variance explosion warning
* embedding model sensitivity (optional rerun)
* citation lag caveat

---

# 7. Acceptance criteria (for the agent)

Pipeline is done when:

* [ ] deterministic run from config
* [ ] produces all 4 figures
* [ ] outputs table of breakpoints with scores
* [ ] runs on full corpus without manual intervention
* [ ] results stable under subsampling

---

# 8. Final guidance

This is **not**:

* a method zoo
* a benchmark paper

This **is**:

> a **clean, controlled experimental system for detecting and validating structural change**

---

# If you want next step

I can generate:

* a **GitHub repo structure**
* or **exact Python module skeletons**
* or **the Introduction section (journal-ready)**

Just tell me.


=======================


Below is a **publication-ready Methods section**, aligned with your roadmap and precise enough to be directly implemented by your coding agent. It encodes **definitions, assumptions, algorithms, and outputs** without ambiguity.

---

# Methods: Multi-layer Detection and Validation of Structural Change in Text Corpora

**Date:** 2026-04-15
**Préparé par ChatGPT prompté par Ha-Duong Minh**

---

## 1. Objective and scope

We propose a framework to **detect and validate structural changes** in large text corpora over time. The method combines multiple representations—semantic, lexical, and network-based—and applies nonparametric two-sample tests to identify candidate breakpoints.

The method serves two purposes:

1. **Exploratory detection** of candidate change points
2. **Validation and interpretation** of these changes across independent representations

It is not intended to uniquely determine a “true” periodization, but to provide **robust, reproducible evidence of structural change**.

---

## 2. Data and representations

Let ( \mathcal{D} = {d_i}_{i=1}^N ) be a corpus of documents with timestamps ( t_i \in \mathbb{Z} ).

Each document is represented in three spaces:

### 2.1 Semantic representation (embedding space)

Each document is mapped to a vector:

[
x_i = \phi(d_i) \in \mathbb{R}^p
]

where ( \phi ) is a fixed embedding model (e.g., sentence-transformer). Embeddings are L2-normalized.

---

### 2.2 Lexical representation (term space)

Each document is represented as a sparse vector:

[
w_i \in \mathbb{R}^V
]

based on term frequencies or TF-IDF weights. Vocabulary is fixed across the corpus.

---

### 2.3 Citation network representation

We construct a **co-citation graph**:

* Nodes: documents
* Edge weight: number of times two documents are cited together

To avoid temporal leakage, for any time ( t ), the graph includes only documents and citation relations with timestamps ( \le t ).

---

## 3. Temporal segmentation

We define time-indexed splits:

* ( \mathcal{D}_t^- = {d_i : t_i \le t} )
* ( \mathcal{D}_t^+ = {d_i : t_i > t} )

subject to:

* minimum sample size constraint: ( |\mathcal{D}_t^-|, |\mathcal{D}*t^+| \ge n*{\min} )

The corpus is growing over time, so typically ( |\mathcal{D}_t^+| \ge |\mathcal{D}_t^-| ). All methods are designed to be **robust to unequal sample sizes**.

---

## 4. Distributional comparison

For each time ( t ), we compare the distributions of representations in ( \mathcal{D}_t^- ) and ( \mathcal{D}_t^+ ).

---

### 4.1 Maximum Mean Discrepancy (primary statistic)

We compute the squared MMD between embedding samples:

\mathrm{MMD}^2(P,Q)=\mathbb{E}*{x,x'\sim P}[k(x,x')] + \mathbb{E}*{y,y'\sim Q}[k(y,y')] - 2\mathbb{E}_{x\sim P,y\sim Q}[k(x,y)]

* Kernel: multi-scale Gaussian (RBF)
* Bandwidths: derived from quantiles of pairwise distances
* Estimator: unbiased U-statistic

MMD serves as the **primary detector of semantic distributional change**.

---

### 4.2 Energy distance (confirmation)

We compute the energy distance:

[
\mathcal{E}(P,Q) = 2\mathbb{E}|x-y| - \mathbb{E}|x-x'| - \mathbb{E}|y-y'|
]

This provides a complementary, kernel-free measure of distributional difference.

---

### 4.3 Classifier two-sample test (C2ST)

We train a classifier to distinguish ( \mathcal{D}_t^- ) from ( \mathcal{D}_t^+ ):

* Model: logistic regression
* Evaluation: 5-fold cross-validated AUC
* Class imbalance handled via weighting

This measures **practical separability** between the two distributions.

---

### 4.4 Lexical divergence

We compute the Jensen–Shannon divergence between aggregated term distributions:

[
\mathrm{JS}(P_w, Q_w)
]

where ( P_w ), ( Q_w ) are normalized term frequency vectors.

---

### 4.5 Graph-based divergence

We compute structural divergence in the co-citation graph:

1. Detect communities using Louvain clustering
2. Compute distribution of documents across communities in each split
3. Measure divergence between distributions (e.g., Jensen–Shannon)

This captures **reorganization of intellectual structure**.

---

## 5. Statistical inference

### 5.1 Null hypothesis

For each time ( t ):

[
H_0: P_t^- = P_t^+
]

i.e., no distributional difference between before and after samples.

---

### 5.2 Permutation testing

We estimate null distributions via permutation:

1. Pool samples ( \mathcal{D}_t^- \cup \mathcal{D}_t^+ )
2. Randomly shuffle labels while preserving sample sizes
3. Recompute statistic
4. Repeat ( B ) times (typically ( B = 500 ))

---

### 5.3 Standardized effect size

For each statistic ( S ), we compute:

[
Z(t) = \frac{S_{\text{obs}}(t) - \mathbb{E}[S_{\text{perm}}(t)]}{\mathrm{sd}[S_{\text{perm}}(t)]}
]

This allows comparison across time despite varying sample sizes.

---

## 6. Time series construction

For each time point ( t ), we compute:

* ( Z_{\text{MMD}}(t) )
* ( Z_{\text{Energy}}(t) )
* ( Z_{\text{C2ST}}(t) )
* ( Z_{\text{JS}}(t) )
* ( Z_{\text{Graph}}(t) )

This yields a multivariate time series of change signals.

---

## 7. Breakpoint detection

### 7.1 Candidate detection

Candidate breakpoints are identified as:

* local maxima in ( Z_{\text{MMD}}(t) )
* subject to threshold: ( Z > z_{\min} ) (e.g., 2)

---

### 7.2 Regularization

To avoid over-detection:

* enforce minimum temporal separation ( \Delta t ) between breakpoints
* retain highest-scoring candidates within each window

---

## 8. Multi-signal validation

A candidate breakpoint at time ( t ) is considered **validated** if:

* at least ( k ) signals (e.g., ( k = 2 )) exceed threshold
* signals come from independent representations (e.g., embedding + lexical)

This step distinguishes:

* statistical noise (single-signal spikes)
* robust structural changes (multi-signal agreement)

---

## 9. Robustness analysis

### 9.1 Subsampling

To control for unequal sample sizes:

* subsample larger split to match smaller one
* recompute statistics over multiple repetitions

---

### 9.2 Sensitivity checks

We evaluate stability with respect to:

* windowing scheme
* kernel bandwidth
* embedding model (optional)

---

## 10. Interpretation of breakpoints

For each validated breakpoint, we extract:

### 10.1 Discriminative terms

Using log-odds ratio with Dirichlet prior:

* identify terms over-represented in ( \mathcal{D}_t^+ ) vs ( \mathcal{D}_t^- )

---

### 10.2 Discriminative documents

Using classifier weights or distance metrics:

* identify documents most characteristic of each side

---

### 10.3 Structural shifts

From graph analysis:

* dominant communities before/after
* changes in community composition

---

## 11. Output

The method produces:

* time series of standardized change signals
* list of candidate breakpoints
* validated breakpoints with supporting evidence
* interpretability outputs (terms, documents, communities)

---

## 12. Summary

The framework combines:

* **nonparametric detection** (MMD, energy)
* **representation diversity** (embedding, lexical, graph)
* **validation logic** (multi-signal agreement)
* **interpretability outputs**

to provide a **robust and interpretable approach to structural change detection in text corpora**.

---

If you want, next step I can:

* turn this into **Python module skeletons matching each section**, or
* compress this into a **journal-length 1.5–2 page Methods section** depending on your target venue.

=====



