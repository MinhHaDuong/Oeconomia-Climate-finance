You’re at the point where execution discipline matters more than ideas. Don’t expand scope—**lock positioning, then write a tight paper around what you already have working**.

Below is the **next step package**: a positioning note + outline + a clean Methods core (aligned with your manuscript) + what to do about the literature review.

---

# Positioning note (method paper)

## Research idea

> We propose a **multi-representation framework for detecting and validating structural change in large text corpora**, combining semantic (embeddings), lexical, and citation-network signals under a unified two-sample testing paradigm.

Key constraint:

* works with **unequal, growing samples**
* does **not rely on density estimation**
* produces **both detection and interpretation**

---

## Angle (this is what makes it publishable)

There are many change detection methods. Your angle is:

> **Triangulation across representations + explicit validation logic**

Not just:

* “we use MMD on embeddings”

But:

* **embedding → detects semantic drift**
* **lexical → explains vocabulary change**
* **graph → captures epistemic restructuring**

And crucially:

> **breakpoints are retained only if supported across independent signals**

That’s your novelty.

---

## Relative positioning (important to get right)

### You are NOT:

* a new kernel method paper
* a pure change-point detection paper
* a topic modeling paper

### You ARE:

> a **framework paper at the intersection of NLP, scientometrics, and HET/STS**

Closest neighbors:

* MMD / two-sample testing → you extend to multi-layer + time
* dynamic topic models → you avoid generative assumptions
* scientometric mapping → you add statistical testing

### One-line positioning

> “We contribute a robust, interpretable framework for periodization in text corpora by combining nonparametric distributional tests with multi-layer validation.”

---

# Detailed outline (keep it tight)

## 1. Introduction

* problem: detecting structural change in large text corpora
* limitations of:

  * single-metric approaches
  * embedding-only approaches
* contribution:

  * multi-layer framework
  * unequal sample robustness
  * validation logic

End with:

> “We demonstrate the method on a corpus of ~30,000 works on climate finance.”

---

## 2. Related work (targeted, not exhaustive)

### 2.1 Two-sample testing

* MMD, energy distance

### 2.2 Change-point detection

* classical time series vs high-dimensional data

### 2.3 Text evolution

* dynamic topic models
* embedding drift

### 2.4 Scientometrics

* co-citation, community detection

👉 Position gap:

> no unified framework combining these with statistical validation

---

## 3. Problem formulation

* corpus ( \mathcal{D}_t )
* representations:

  * embeddings ( x )
  * lexical ( w )
  * graph ( G )

### Key sentence:

> The objective is to detect and validate **structural distributional changes across representations**

---

## 4. Method

### 4.1 Temporal segmentation

* sliding / expanding windows
* unequal ( n \neq m )

### 4.2 Embedding layer

* MMD (primary)
* energy (confirmation)
* C2ST (separability)

### 4.3 Lexical layer

* JS divergence
* log-odds terms

### 4.4 Graph layer (be explicit!)

* nodes = papers
* edges = co-citation (or citation, but pick one)
* time rule: **no future edges**

### 4.5 Breakpoint detection

* compute ( S(t) )
* candidate peaks

### 4.6 Validation

* multi-signal agreement
* robustness filters

### 4.7 Statistical design

* permutation null
* effect size normalization

---

## 5. Application: climate finance corpus

* dataset (~30k works)
* show:

  * signals over time
  * breakpoints align with:

    * 2007–2009
    * 2015

(consistent with your main paper )

---

## 6. Interpretation layer

* top discriminative terms
* key documents
* community shifts

---

## 7. Robustness & failure modes

Short but sharp:

* window size
* embedding model
* corpus growth
* citation lag

---

## 8. Discussion

* what method captures / misses
* epistemic status:

> tool for detection + validation, not ground truth generator

---

# Methods section (tight core version)

You already have a long version. For the methods paper, simplify:

## Core principles to emphasize

1. **Nonparametric**
2. **Representation-agnostic**
3. **Unequal sample robustness**
4. **Multi-signal validation**

Keep formulas minimal (MMD only is enough).

---

# Literature review: what to do (important)

Do **NOT** write a long generic review.

Instead:

## Structure it as a gap argument

### Block 1 — Two-sample tests

* strong but:

  * not temporal
  * not multi-representation

### Block 2 — Topic evolution / NLP

* dynamic topic models
* embedding drift
  → lack statistical testing

### Block 3 — Scientometrics

* co-citation mapping
  → descriptive, not inferential

### Your gap:

> no framework combining:

* statistical testing
* multiple representations
* temporal change
* interpretability

That’s enough.

---

# What to do with your codebase (critical step)

You already have the hardest part done.

Now:

## 1. Freeze the pipeline

* no more feature creep
* define:

  * inputs
  * outputs
  * parameters

## 2. Add reproducibility layer

* one script = one figure
* config file (YAML or JSON)
* deterministic seeds

## 3. Generate **3–4 canonical figures**

You only need:

1. Time series of signals (MMD, JS, graph)
2. Breakpoint detection
3. Lexical shifts
4. (optional) community flows

That’s your paper.

---

# Concrete next 7 days plan

## Day 1–2

* write positioning + intro + related work

## Day 3–4

* clean Methods (no bloat)

## Day 5

* generate figures from code

## Day 6

* write application + results

## Day 7

* discussion + polish

---

# Final advice (important)

Don’t try to make this:

* a full theory paper
* a full NLP benchmark paper

Make it:

> a **clean, well-designed method with one strong application**

That’s what gets accepted.

---

If you want next:

* I can draft your **Introduction (publication-ready)**
* or compress your Methods into a **2-page tight version for submission**



Here is a **rewritten, integrated Methods section** that explicitly incorporates **embedding, lexical, and citation layers**, and frames periodization as a **multi-signal breakpoint detection problem**. It is tight, defensible, and aligned with your research goals.

---

# Methods: Multi-layer Detection of Distributional Change and Periodization in Text Corpora

**Date:** 2026-04-15
**Préparé par ChatGPT prompté par Ha-Duong Minh**

## 1. Problem setup

We study the temporal evolution of a corpus of documents ( \mathcal{D} = {d_t} ), each associated with a timestamp. The objective is to:

1. Detect **distributional changes** over time
2. Identify **robust breakpoints (periodization)**
3. Characterize the **nature of these changes**

Each document is represented along three complementary dimensions:

* **Semantic (embedding space):** ( x = \phi(d) \in \mathbb{R}^p )
* **Lexical (term space):** bag-of-words or TF-IDF vector ( w \in \mathbb{R}^V )
* **Citation graph:** node in a directed network ( G = (V,E) )

---

## 2. Temporal segmentation

We define time-indexed subcorpora using sliding or expanding windows:

* ( \mathcal{D}_t^- ): documents before time ( t ) (reference)
* ( \mathcal{D}_t^+ ): documents after time ( t ) (comparison)

Sample sizes vary over time (( n_t \neq m_t )) due to corpus growth.

All methods are designed to be **robust to unequal sample sizes**.

---

## 3. Embedding-based distributional change

### 3.1 Maximum Mean Discrepancy (primary detector)

We compute the squared MMD between embedding samples:

\mathrm{MMD}^2(P,Q)=\mathbb{E}*{x,x'\sim P}[k(x,x')] + \mathbb{E}*{y,y'\sim Q}[k(y,y')] - 2\mathbb{E}_{x\sim P,y\sim Q}[k(x,y)]

* Kernel: multi-scale Gaussian (RBF)
* Estimator: unbiased U-statistic
* Inference: permutation test preserving sample sizes

---

### 3.2 Energy distance (confirmation)

We compute the energy distance between samples, with permutation-based inference.

This provides a complementary, tuning-light measure of distributional difference.

---

### 3.3 Classifier two-sample test (separability)

A classifier is trained to distinguish ( \mathcal{D}_t^- ) from ( \mathcal{D}_t^+ ):

* Model: logistic regression (baseline)
* Metric: cross-validated AUC
* Class imbalance handled via weighting

This evaluates the **practical separability** of the two periods.

---

## 4. Lexical distributional change

### 4.1 Jensen–Shannon divergence

We compute the Jensen–Shannon divergence between term distributions:

[
\mathrm{JS}(P_w, Q_w)
]

where ( P_w ), ( Q_w ) are normalized term frequency distributions.

This captures:

* vocabulary shifts
* changes in rhetorical emphasis

---

### 4.2 Differential term analysis

We identify discriminative terms using:

* log-odds ratio with Dirichlet prior
* or standardized frequency differences

This provides **interpretable drivers of change**.

---

## 5. Citation graph dynamics

### 5.1 Community structure

We detect communities in the citation graph (e.g. Louvain/Leiden) and compute:

* distribution of documents across communities in ( \mathcal{D}_t^- ), ( \mathcal{D}_t^+ )
* divergence between these distributions

---

### 5.2 Structural indicators

We track:

* centrality measures (e.g. in-degree, PageRank)
* cross-community citation flows

This captures **reorganization of intellectual structure**.

---

## 6. Breakpoint detection (periodization)

### 6.1 Time series construction

For each time point ( t ), we compute:

* ( S_{\text{emb}}(t) ): embedding-based statistic (MMD / energy)
* ( S_{\text{lex}}(t) ): lexical divergence (JS)
* ( S_{\text{graph}}(t) ): graph-based divergence

---

### 6.2 Candidate breakpoints

Candidate breakpoints are identified as:

* local maxima in ( S(t) )
* or statistically significant deviations from permutation-based null

---

### 6.3 Multi-signal validation

A breakpoint is considered **robust** if:

* detected in embedding space **and**
* supported by lexical and/or graph signal

This reduces sensitivity to:

* model choice
* sampling variability

---

## 7. Significance and normalization

### 7.1 Permutation-based null

For each statistic:

* labels are permuted within pooled samples
* sample sizes are preserved
* empirical null distributions are computed

---

### 7.2 Standardized effect size

We report:

[
Z(t) = \frac{S(t) - \mathbb{E}*{\text{perm}}[S]}{\mathrm{sd}*{\text{perm}}(S)}
]

This enables comparison across time despite:

* varying sample sizes
* changing corpus variance

---

### 7.3 Subsampling robustness

As a sensitivity analysis:

* larger samples are subsampled to match smaller ones
* statistics are recomputed across repetitions

This verifies that detected changes are not artifacts of sample size.

---

## 8. Interpretation of detected changes

For each validated breakpoint, we report:

* embedding-based discriminative documents
* top differential terms (lexical)
* shifts in citation communities

This enables a **multi-level interpretation**:

* semantic (embedding)
* rhetorical (lexical)
* epistemic (graph)

---

## 9. Summary of methodological framework

| Layer       | Method                             | Role              |
| ----------- | ---------------------------------- | ----------------- |
| Semantic    | MMD, energy, C2ST                  | Detection         |
| Lexical     | JS divergence, term analysis       | Interpretation    |
| Graph       | Community / centrality shifts      | Structural change |
| Integration | Multi-signal breakpoint validation | Periodization     |

---

# Final positioning (what this achieves)

This framework treats periodization as:

> a **multi-dimensional structural change problem**, rather than a single-metric segmentation.

It ensures that identified periods are:

* statistically grounded
* robust to corpus growth
* substantively interpretable

---

If you want the next step, I’ll give you a **compact, reproducible Python pipeline** (aligned with this section, minimal deps, fits your workflow) and a **figure design for the paper (alluvial + breakpoint timeline)**.

