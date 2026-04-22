## S1. Maximum Mean Discrepancy (MMD) {#sec-s1}

### Principle

MMD measures the distance between two distributions by comparing their means in a rich feature space (a reproducing kernel Hilbert space, RKHS). Intuitively: if you can find *any* smooth function that has a different average value over the two samples, the distributions differ. The kernel trick lets you do this without explicitly computing the feature map.

### Definition

$$\widehat{\text{MMD}}^2(X, Y) = \frac{1}{n^2}\sum_{i,j} k(x_i, x_j) - \frac{2}{nm}\sum_{i,j} k(x_i, y_j) + \frac{1}{m^2}\sum_{i,j} k(y_i, y_j)$$

where $k(\cdot,\cdot)$ is a radial basis function kernel $k(x,y) = \exp(-\|x-y\|^2 / (2\sigma^2))$ with bandwidth $\sigma$ set to the median pairwise distance (median heuristic).

*Script:* `scripts/_divergence_semantic.py`, method `mmd_rbf`.

### Principle figure

![](figures/schematic_S1_mmd.png){width=100%}

*MMD principle: two embedding clouds with kernel witness function.*

### Advantages, biases, limitations

**Advantages.** MMD is a proper metric between distributions; $\widehat{\text{MMD}}^2 = 0$ iff the distributions are identical (under a characteristic kernel). Unbiased estimator exists. Well-studied theoretical properties [@gretton2012].

**Biases.** The median-heuristic bandwidth is data-driven; it changes as the corpus grows, making raw values non-comparable across windows of different sizes. The `equal_n: true` flag (random subsampling to equal-sized windows) mitigates growth bias. Quadratic computation ($O(n^2)$) limits scalability; we use biased estimator with batching for $n > 2000$.

**Limitations.** Sensitive to outlier embeddings. Bandwidth choice is a free parameter. Does not identify *which* dimensions drive the shift.

### Corpus results

![](figures/fig_zoo_S1_MMD.png){width=100%}

*Cross-year Z-score for S1 (MMD), w=2–5. Peak at 1998 (field heterogeneity); monotonic decline.*

Key values (w=3): peak $Z = +3.2$ at 1998, monotonic decline to $Z \approx -0.4$ by 2010.

### References

Seminal: @gretton2012 (JMLR 13:723–773, 2012). Recent analogue: @hulkund2022interpretable (optimal transport applied to interpretable distribution-shift detection; the closest machine-learning setting to cross-window corpus comparison).

::: {.callout-note}
All zoo results use the equal-n debiased estimator; see the bias comparison figure for the magnitude of the correction.
:::
