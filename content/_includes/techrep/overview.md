# Overview

This document surveys the structural break detection methods applied to the climate finance corpus
({{< meta corpus_total >}} works, 1990--2024).
Each method answers the same question in a different vocabulary:
*does the distribution of works written before year $t$ differ from the distribution of works written after $t$?*
We apply a sliding window of $w$ years on each side of the candidate break year.^[Throughout this report we show $w \in \{2, 3, 4\}$. The companion paper reports $w=3$ as the default lead window, with $w \in \{2, 4\}$ as robustness checks.]

Methods are grouped into three layers:

- **Part S — Semantic.** Compare full embedding distributions: each work is a point in the BAAI/bge-m3 embedding space ({{< meta emb_dimensions >}} dimensions). These methods detect distributional shift in *what the field talks about*.
- **Part L — Lexical.** Compare TF-IDF vocabulary distributions. Complementary to semantic methods; more interpretable (discriminating terms are directly readable).
- **Part G — Citation graph.** Compare citation network topology: degree distributions, community structure, centrality. These methods detect changes in *how knowledge flows* rather than *what is said*.
- **C2ST (Classifier two-sample tests).** C2ST\_embedding lives in Part S; C2ST\_lexical lives in Part L. Each asks the same meta-check question — can a classifier distinguish "before" from "after" better than chance? — in its respective feature space.

## Growing-corpus bias and equal-n debiasing

The climate finance corpus grew roughly 15× between 1995 and 2020, so the "after"
window for any anchor year $t$ systematically contains more papers than the "before"
window. This asymmetry introduces two problems.

**Variance imbalance.** For a distance statistic $D$ estimating $d(P_\text{before},
P_\text{after})$, the finite-sample estimator has variance $O(1/n_\text{before} +
1/n_\text{after})$. When $n_\text{after} \gg n_\text{before}$ (early anchor years) or
$n_\text{before} \gg n_\text{after}$ (late anchor years, where indexing lag shrinks
the after window), the estimator variance is dominated by whichever sample is smaller.
The effective precision is limited by the minority window no matter how large the
majority window grows.

**Size-dependent bias.** Many statistics — including energy distance, MMD, and
JS divergence — have non-zero expected value under the null $d = 0$ when
$|1/n_\text{before} - 1/n_\text{after}|$ is large. The bias is not an artefact of a
true shift; it is a finite-sample effect that grows with the size imbalance. Without
correction, the series would show artificially elevated divergence in early and late
years simply because the two windows are unequal in size.

**Equal-$n$ subsampling.** Before computing $D$, we subsample the larger window to
$\min(n_\text{before}, n_\text{after})$ papers, drawn without replacement. This
equalises both the variance contribution and eliminates the size-dependent bias
component. The cost is a power loss proportional to the dropped fraction — largest in
the middle years of the corpus where one window may be several times larger than the
other. To reduce the variance introduced by a single random draw, we use R = 3
median-of-three subsampling (see §Annex): the statistic is the median over three
independent subsample draws at each anchor year.

**Configuration.** Equal-$n$ subsampling is controlled by `divergence.equal_n: true`
in `config/analysis.yaml` (default). It can be disabled at runtime with
`--no-equal-n` to reproduce the biased series and assess the magnitude of the
correction.
