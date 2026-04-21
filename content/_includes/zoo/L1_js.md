## L1. Jensen-Shannon Divergence (TF-IDF) {#sec-l1}

### Principle

JS divergence compares two probability distributions over a shared vocabulary.
We aggregate the TF-IDF vectors of all works in each window into a "bag of words" distribution,
then measure how much information is needed to encode one distribution using the other as a model.
JS divergence is the symmetrised, bounded version of Kullback-Leibler divergence.

### Definition

$$\text{JS}(P \| Q) = \frac{1}{2} D_{KL}(P \| M) + \frac{1}{2} D_{KL}(Q \| M), \quad M = \frac{P+Q}{2}$$

where $P$ and $Q$ are the normalised mean TF-IDF vectors of the before/after windows,
$D_{KL}(P\|Q) = \sum_i P_i \log(P_i / Q_i)$, and sums run over the vocabulary.
$\text{JS} \in [0, \log 2]$; the square root is a proper metric.

*Script:* `scripts/_divergence_lexical.py`, method `L1`.

### Principle figure

![](figures/schematic_L1_js.png){width=100%}

*JS divergence: mean TF-IDF distributions before vs. after; starred terms have largest |P−Q|.*

### Advantages, biases, limitations

**Advantages.** Interpretable: dominant terms in each distribution are directly readable. Bounded ($\leq \log 2$). No hyperparameter. Consistent with the semantic energy distance on this corpus (same convergence signal).

**Biases.** Vocabulary changes over time (new terms, deprecated terms); TF-IDF weights are computed on the full corpus and re-applied to sub-windows, so rare early terms may dominate early-window distributions. Aggregation to mean TF-IDF discards within-window heterogeneity.

**Limitations.** Ignores word order and semantic similarity (synonyms treated as distinct tokens).

### Corpus results

![](figures/fig_zoo_L1.png){width=100%}

*Cross-year Z-score for L1 (JS-TF-IDF), w=2–5.*

Key values (w=3): peak $Z = +2.7$ at 1998, monotonic decline. Same convergence pattern as S methods.

### References

Seminal: @lin1991divergence (Lin 1991, "Divergence measures based on the Shannon entropy", *IEEE Transactions on Information Theory*).
Recent analogue: @hall2008studying (Hall et al. 2008, "Studying the history of ideas using topic models", EMNLP — JS on bag-of-words for intellectual history, closest to our setting).
