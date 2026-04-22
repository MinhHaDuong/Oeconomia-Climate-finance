## Two notions of Z-score {#sec:zscore-two-notions}

Two distinct Z-scores appear in this analysis. The *cross-year Z-score* $Z(t,w)$
(§\ref{sec:zscore}) standardises each method's divergence series across years within
a window. The *permutation Z-score* $Z_\text{perm}(t,w)$ (this section) standardises
the observed statistic against its null distribution from random permutations of paper
labels. They answer different questions: the cross-year Z-score measures relative
displacement from the period mean; the permutation Z-score measures evidence against
the null hypothesis of exchangeability. Only the latter is a valid significance test.

::: {.callout-note}
**Proposition.** If the divergence series $D(t,w)$ has a non-constant trend, then
$|Z(t,w)| \geq z_\alpha$ does not imply $p \leq \alpha$.

**Model.** Let $D(t,w) = \mu(t) + \varepsilon(t,w)$ where $\mu(t)$ is a slowly-varying
trend and $\varepsilon(t,w) \sim \text{i.i.d.}(0,\sigma_\varepsilon^2)$.
Under $H_0$ (no structural break), the cross-year Z-score is:

$$Z(t,w) = \frac{\mu(t) - \bar{\mu} + \varepsilon(t,w)}{S(w)}$$

where $\bar{\mu} = T^{-1}\sum_t \mu(t)$ and $S^2(w) \approx \text{Var}_t(\mu) + \sigma_\varepsilon^2$.
The bias term $[\mu(t) - \bar{\mu}]/S(w)$ is non-zero whenever $t$ is not at the
temporal mean of $\mu$. For a monotone decreasing trend (convergence: homogenising field), early years have
$\mu(t) > \bar{\mu}$ (Z inflated, false positives) and late years have $\mu(t) < \bar{\mu}$
(Z deflated, false negatives). The empirical distribution of $Z$ under $H_0$ mirrors
the shape of $\mu$, not $N(0,1)$.

**Quantified distortion for a linear trend** $\mu(t) = a + bt$ with $b \neq 0$:
the bias at year $t_0$ is

$$\text{Bias}(t_0) = \frac{b(t_0 - \bar{t})}{\sqrt{b^2 \text{Var}_t(t) + \sigma_\varepsilon^2}}$$

At high signal-to-noise ($b^2 T^2 \gg \sigma_\varepsilon^2$) this simplifies to
$(t_0 - \bar{t})\sqrt{12}/T$. For $T=30$ years ($t_0-\bar{t} = 14.5$ at the first year),
the bias magnitude is $14.5\sqrt{12}/30 \approx 1.67$ (the large-$T$ limit is
$\sqrt{3} \approx 1.73$): a threshold $|Z| \geq 2$ then requires an anomaly
of only $0.33\,S$ at $t_\text{min}$ but $3.67\,S$ at $t_\text{max}$ — an
asymmetric test that is neither conservative nor liberal but *structurally distorted*.

Use the permutation CI band (below) to assess significance; use the cross-year Z only
for cross-method comparability.

**Empirical check.** For the $S_2$ energy distance series ($n=90$ year–window pairs),
the Spearman rank correlation between $|Z_\text{cross}|$ and $-\log_{10}(p_\text{perm})$
is $\rho = -0.25$ ($p = 0.018$) — *negative*, confirming that large cross-year Z-scores
cluster at early years where trend inflation is highest, not where the permutation test
finds the strongest evidence. The two rankings diverge by design. $\square$
:::

## Permutation null model {#sec:null-model}

For each (method, year, window) cell, we assess statistical significance via a permutation test.
Under the null hypothesis of exchangeability (before- and after-period papers are drawn from the same distribution), they are pooled and randomly permuted $B = 500$ times; the observed divergence statistic is then standardised against this
null distribution to yield a $Z$-score (see §\ref{sec:zscore}).
Three complementary strategies make the 500-permutation sweep across all cells tractable:
(i) **GPU-batched permutations** for $S_2$ energy distance and $S_1$ MMD: the pairwise
distance or kernel matrix is precomputed once on GPU; all $B$ permutation statistics are then
evaluated in a single batched matrix operation, replacing $B$ sequential \texttt{cdist} calls
with one \texttt{cdist} plus one GPU matmul, exploiting hardware-level parallelism;
(ii) **precomputed TF-IDF** for $L_1$: the vectoriser runs once per window, and permutations
reshuffle row indices into the sparse matrix, eliminating $B$ redundant transform calls; and
(iii) **CPU parallelism** via joblib across (year, window) pairs for $G_2$ spectral gap and
$G_9$ community JS divergence, with a configurable `--n-jobs` flag (default: all cores).
End-to-end runtime on an NVIDIA RTX A4000 is approximately 2--3 minutes at default parallelism
($\texttt{--n-jobs}=-1$, 24 cores), measured 2026-04-21.
