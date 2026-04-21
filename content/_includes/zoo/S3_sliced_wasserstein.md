## S3. Sliced Wasserstein Distance {#sec-s3}

### Principle

The Wasserstein (earth-mover) distance is theoretically appealing for comparing distributions in high dimensions, but computing the exact optimal transport plan is $O(n^3)$ and impractical for large corpora. Sliced Wasserstein projects both distributions onto many random 1-D directions, computes the exact Wasserstein distance on each 1-D slice (closed-form: the difference between sorted quantiles), and averages. The result is a consistent approximation that runs in $O(n \log n \cdot K)$ time for $K$ slices.

### Definition

$$\text{SW}_2^2(P, Q) = \int_{\mathbb{S}^{d-1}} W_2^2(\theta_\# P, \theta_\# Q)\, d\sigma(\theta)$$

where $\theta_\# P$ denotes the push-forward of $P$ through the projection $x \mapsto \langle \theta, x\rangle$,
$W_2$ is the 2-Wasserstein distance, and $\sigma$ is the uniform measure on the unit sphere.
Sample estimate: average over $K=200$ random unit directions, computing $W_2$ as the $\ell^2$ distance between sorted projected samples.

*Script:* `scripts/_divergence_semantic.py`, method `sliced_wasserstein`.

### Principle figure

![](figures/schematic_S3_sliced_wasserstein.png){width=100%}

*Sliced Wasserstein: random projection directions with sorted quantile matching.*

### Advantages, biases, limitations

**Advantages.** Metrically consistent approximation of optimal transport. No hyperparameter. Scales to $n \sim 10^4$ embeddings in seconds. Invariant to the global mean of each set (only the shape differs, not the location, after centering).

**Biases.** Random projections introduce Monte Carlo variance; mitigated by $K=200$. Approximation quality degrades when the signal lives in a low-dimensional subspace (all the action is on a few directions; random projections miss most of them).

**Limitations.** Shares the convergence-not-break limitation with S1 and S2 on the climate finance corpus.

### Corpus results

![](figures/fig_zoo_S3_sliced_wasserstein.png){width=100%}

*Cross-year Z-score for S3 (Sliced Wasserstein), w=2–5.*

Key values (w=3): peak $Z = +3.4$ at 1998, monotonic decline. Pattern identical to S2.

### References

Seminal: @bonneel2015sliced (Bonneel et al. 2015, "Sliced and Radon Wasserstein Barycenters of Measures"). Recent analogue: @kolouri2019generalized (Kolouri et al. 2019, "Generalized Sliced Wasserstein Distances", *NeurIPS*).
