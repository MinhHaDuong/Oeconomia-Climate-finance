## S4. Fréchet Distance (Gaussian approximation) {#sec-s4}

### Principle

The Fréchet Inception Distance (FID) approximates each embedding cloud by a multivariate Gaussian (fit the empirical mean and covariance), then computes the Fréchet distance between the two fitted Gaussians. This is the approach used to evaluate generative image models. Applied here to text embeddings, it measures whether the two windows look like they could have been drawn from the same Gaussian distribution.

### Definition

$$d_F^2(\mu_1, \Sigma_1, \mu_2, \Sigma_2) = \|\mu_1 - \mu_2\|^2 + \text{tr}\!\left(\Sigma_1 + \Sigma_2 - 2(\Sigma_1\Sigma_2)^{1/2}\right)$$

where $(\mu_k, \Sigma_k)$ are the empirical mean and covariance of each window's embedding matrix, and $(\cdot)^{1/2}$ is the matrix square root (computed via SVD).

*Script:* `scripts/_divergence_semantic.py`, method `frechet`.

### Principle figure

![](figures/schematic_S4_frechet.png){width=100%}

*Fréchet distance: fitted Gaussian ellipses (1σ) with means connected by arrow.*

### Advantages, biases, limitations

**Advantages.** Closed-form; $O(nd^2 + d^3)$, fast even for large $n$. Familiar to ML practitioners.

**Biases.** Assumes Gaussian distributions; real embedding clouds are not Gaussian (they lie on a manifold). Covariance estimation is unstable when $n < d$ (our windows often have $n \sim 200$ and $d = 1024$; we regularise with shrinkage). Fréchet distance is not a metric on arbitrary distributions.

**Limitations.** The Gaussian assumption is the strongest of the four semantic methods.

### Corpus results

![](figures/fig_zoo_S4_frechet.png){width=100%}

*Cross-year Z-score for S4 (Fréchet), w=2–5.*

Key values (w=3): peak $Z = +2.9$ at 1998, monotonic decline. Weaker than S1–S3 due to Gaussian misspecification.

### Sample size note

S4 fits an empirical covariance matrix of dimension $d$ from $n$ embedding vectors. The covariance is full-rank only when $n > d$. With PCA reduction to `max_dim=256`, a window of $n < 300$ papers yields a rank-deficient or numerically fragile covariance. The pipeline therefore sets `min_papers=300` for S4\_frechet in `config/analysis.yaml`; (year, window) pairs with fewer papers are skipped. This is a stricter guard than the global `min_papers=30`.

### References

Seminal: @heusel2017gans (Heusel et al. 2017, "GANs trained by a two time-scale update rule converge to a local Nash equilibrium", NeurIPS).
Recent analogue: @jayasumana2024rethinking (Jayasumana et al. 2024, "Rethinking FID", *CVPR*; critiques FID for image generation and proposes a CLIP-MMD alternative, illustrating the method's dependence on the embedding it uses).
