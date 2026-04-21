## S2. Energy Distance {#sec-s2}

### Principle

Energy distance is built on the analogy with gravitational potential energy.
Two samples "attract" themselves (within-group distances) and "repel" each other (between-group distances).
When the two samples come from the same distribution, attraction and repulsion balance exactly.
When they differ, between-group distances are larger on average than within-group distances.

Compared to MMD, energy distance uses Euclidean distance directly rather than a kernel,
so there is no bandwidth to tune.
On high-dimensional embeddings it captures the overall spread of the two clouds
rather than fine local structure.

### Definition

$$E(X, Y) = 2 \, \mathbb{E}\|x - y\| - \mathbb{E}\|x - x'\| - \mathbb{E}\|y - y'\|$$

where $x, x' \overset{iid}{\sim} P$ and $y, y' \overset{iid}{\sim} Q$.
The sample estimator replaces expectations by means over all pairs:

$$\widehat{E}(X, Y) = \frac{2}{nm}\sum_{i,j}\|x_i - y_j\| - \frac{1}{n^2}\sum_{i,i'}\|x_i - x_{i'}\| - \frac{1}{m^2}\sum_{j,j'}\|y_j - y_{j'}\|$$

For our {{< meta emb_dimensions >}}-dimensional embeddings, Euclidean distances are computed in the original space (no projection). Windows are balanced to $\min(|X_{\text{before}}|, |X_{\text{after}}|)$ draws (`equal_n: true`).

*Script:* `scripts/_divergence_semantic.py`, method `energy_distance`.

### Principle figure

![](figures/schematic_S2_energy.png){width=100%}

*Energy distance: cross-group pairwise distances (grey) with representative pair highlighted.*

### Advantages, biases, limitations

**Advantages.** No hyperparameter (no kernel bandwidth). Consistent: $\widehat{E}(X,Y) \to E(P,Q)$ as $n \to \infty$. Equivalent to the Cramér distance for univariate distributions; generalises to arbitrary dimension. Computationally $O(n^2)$ but with a smaller constant than MMD (pure Euclidean distances, no kernel exponentiation).

**Biases.** Grows with embedding dimension $d$ even for equal distributions (the expected pairwise distance in $\mathbb{R}^d$ under a unit Gaussian scales as $\sqrt{d}$). Equal-sample balancing removes growth bias across time; within a given year the raw value should not be compared across corpora of different sizes. With very large samples ($n \gg 10{,}000$) the estimator can saturate: $\sigma_{null} \to 0$, so local permutation $Z$-scores reach 75 or more even when the actual distributional shift is trivial. Cross-year standardisation (this document's default) avoids this saturation.

**Limitations.** Does not decompose by dimension; cannot identify which semantic directions drive the shift. Sensitive to embeddings that are outliers in the high-dimensional space.

### Corpus results

![](figures/fig_zoo_S2_energy.png){width=100%}

*Cross-year Z-score for S2 (Energy Distance), w=2–5. Peak at 1998; monotonic decline through 2005.*

Cross-year $Z$-scores (w=3) show a monotonic decline from $Z = +3.9$ at 1998 to $Z \approx -0.4$ at 2010 (see corpus results figure above).
This is the **field convergence** signature: early climate finance drew on three distant traditions
(finance, development economics, and physical science).
As the field institutionalised — COP3 (1997), Stern Review (2006), post-Bali mechanisms —
new entrants were socialised into a narrower discursive space.
The embedding clouds before and after any given year look increasingly alike.

No peak at 2007 or 2013 is visible in energy distance.
This confirms that the 2007 structural break (G5 and G6, above threshold)
and the suggestive 2013 secondary peak (G6 only, sub-threshold at $Z \approx +1.8$)
are network-topology events, not semantic-content events.

### References

Seminal: @szekely2013 (Székely & Rizzo 2013, "Energy statistics: A class of statistics based on distances between samples", *Journal of Statistical Planning and Inference*).
