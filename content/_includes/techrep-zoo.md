# Part S — Semantic Distribution Methods

The embedding space provides a continuous, high-dimensional representation of meaning.
For each year $t$ and window $w$ we collect two sets of embeddings:
$X_{\text{before}} = \{e_i : t-w \leq \text{year}_i < t\}$ and $X_{\text{after}} = \{e_j : t \leq \text{year}_j < t+w\}$.
A semantic distance method maps $(X_{\text{before}}, X_{\text{after}})$ to a scalar $D \geq 0$,
where $D=0$ means the two samples are drawn from the same distribution.

The four distance-based semantic methods (S1–S4) show the **field convergence** pattern:
early climate finance (1990s) was a loose coalition of three traditions
(finance, development economics, and physical science);
by the 2010s those traditions had merged into a recognisable field
with a shared vocabulary and shared concerns.
The fifth entry, C2ST (embedding), recasts the same two-sample question as a supervised learning task
and serves as a reference-layer sanity check rather than a convergence detector.

For the six stochastic methods (S1–S4, C2ST_embedding, C2ST_lexical), each panel
also shows a faint **replication ribbon** around the line: the trimmed range of
$R$ subsampling replicates expressed in the same Z-score units (μ, σ shared with
the point estimate). The band brackets variability under resampling — a visual
proxy for sampling uncertainty rather than a formal confidence interval.

---

{{< include _includes/zoo/S1_mmd.md >}}

\newpage

---

{{< include _includes/zoo/S2_energy.md >}}

\newpage

---

{{< include _includes/zoo/S3_sliced_wasserstein.md >}}

\newpage

---

{{< include _includes/zoo/S4_frechet.md >}}

\newpage

---

{{< include _includes/zoo/C2ST_embedding.md >}}

\newpage

---

# Part L — Lexical Distribution Methods

Lexical methods operate on TF-IDF representations of abstracts and titles.
A work's TF-IDF vector weights the importance of each vocabulary term by how often it appears in that work
relative to the full corpus.
Unlike embeddings, the TF-IDF space is discrete and interpretable:
discriminating terms can be read directly.

---

{{< include _includes/zoo/L1_js.md >}}

\newpage

---

{{< include _includes/zoo/L2_ntr.md >}}

\newpage

---

{{< include _includes/zoo/L3_term_burst.md >}}

\newpage

---

{{< include _includes/zoo/C2ST_lexical.md >}}

\newpage

---

# Part G — Citation Graph Methods

Citation graph methods represent the corpus as a directed graph
$\mathcal{G} = (V, E)$ where $V$ is the set of works and $(i, j) \in E$ if work $i$ cites work $j$.
These methods compare structural properties of the subgraph before year $t$
with the subgraph after year $t$.
Unlike semantic and lexical methods, they detect changes in *knowledge flow patterns*,
not in the *content* of publications.

The nine graph methods group into three families:

- **Degree topology** (G1 PageRank, G5 preferential attachment, G6 entropy): compare degree distributions.
- **Spectral / global structure** (G2 spectral, G8 betweenness): compare global network geometry.
- **Community / mesoscale** (G3 bibliographic coupling, G4 cross-tradition, G7 disruption, G9 community): compare meso-level organisation.

Only G5 and G6 show a structural break at 2007 in the climate finance corpus;
the remaining graph methods either show the convergence signal or weak/noisy patterns.

---

{{< include _includes/zoo/G1_pagerank.md >}}

\newpage

---

{{< include _includes/zoo/G2_spectral.md >}}

\newpage

---

{{< include _includes/zoo/G3_coupling_age.md >}}

\newpage

---

{{< include _includes/zoo/G4_cross_tradition.md >}}

\newpage

---

{{< include _includes/zoo/G5_pref_attachment.md >}}

\newpage

---

{{< include _includes/zoo/G6_entropy.md >}}

\newpage

---

{{< include _includes/zoo/G7_disruption.md >}}

\newpage

---

{{< include _includes/zoo/G8_betweenness.md >}}

\newpage

---

{{< include _includes/zoo/G9_community.md >}}
