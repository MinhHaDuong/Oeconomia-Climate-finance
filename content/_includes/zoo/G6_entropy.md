## G6. Citation Degree Entropy {#sec-g6}

### Principle

Shannon entropy of the in-degree distribution measures how concentrated or dispersed citations are.
A low-entropy distribution has a few mega-hubs receiving most citations (a hierarchical, consensus field).
A high-entropy distribution spreads citations across many works (a pluralistic, exploratory field).
A structural break at 2007 would appear as a sudden change in entropy —
the field may have consolidated around a new set of authoritative texts (entropy decrease)
or opened up to new voices (entropy increase).

### Definition

Normalise the in-degree histogram of the window subgraph to obtain $p_k = (\text{count of papers with degree } k) / n$.

$$H(t, w) = -\sum_k p_k \log_2 p_k$$

$$D_{\text{G6}}(t, w) = |H_{\text{after}} - H_{\text{before}}|$$

*Script:* `scripts/_citation_methods.py`, `G6_entropy`.

### Principle figure

![](figures/schematic_G6_entropy.png){width=100%}

*Entropy divergence: before/after in-degree histograms with H annotated on each panel.*

### Advantages, biases, limitations

**Advantages.** Intuitive. Sensitive to the full shape of the degree distribution, not just the tail. Requires no distributional assumption.

**Biases.** Entropy depends on the number of distinct degree values, which grows with network size; equal-window balancing (`equal_n: true`) mitigates but does not eliminate this. Absolute difference loses sign (can't tell whether consolidation or dispersal dominates).

**Limitations.** Correlated with G5: both respond to changes in the degree distribution. A joint measure (e.g., JS between degree histograms) would be cleaner but is not yet implemented.

### Corpus results

![](figures/fig_zoo_G6_entropy.png){width=100%}

*Cross-year Z-score for G6 (degree entropy), w=2–5. **Peak at 2007** confirms G5 finding.*

**Key result:** Cross-year $Z$-scores (w=3) peak at **2007** ($Z = +2.46$), confirming the G5 finding.
Entropy peaked again around 2013 ($Z \approx +1.8$).
Combined with G5, this constitutes the main evidence for the 2007 structural break being a citation-topology event.

### References

Seminal: @shannon1948mathematical (Shannon 1948, "A Mathematical Theory of Communication").
Recent analogue: @leydesdorff_rafols2011indicators (Leydesdorff & Rafols 2011, "Indicators of the Interdisciplinarity of Journals: Diversity, Centrality, and Citations", *Journal of Informetrics*; uses Shannon entropy on citation vectors to assess interdisciplinarity).
