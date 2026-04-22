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

## Minimum sample requirements per method family {#sec:min-sample}

The pipeline enforces a global floor of `min_papers=30` per window before computing any statistic. The threshold is pragmatic — it avoids degenerate inputs — but its reliability varies by method family. Two methods have higher per-method overrides in `config/analysis.yaml`.

**Semantic (S1--S4).** Energy distance (S2) and MMD (S1) are U-statistics: consistent for $n \geq 2$, with power growing as $O(1/\sqrt{n})$. For a medium effect size ($\delta = 0.5$ mean shift in standard deviation units), power reaches 80\% near $n \approx 30$; the global minimum is adequate. Sliced Wasserstein (S3) converges at the same $O(1/\sqrt{n})$ rate per projection; $n=30$ yields crude but usable trend estimates. Fréchet distance (S4) is the exception: it fits a multivariate Gaussian to each window, which requires $n > d$ for the covariance matrix to be full-rank. With PCA reduction to `max_dim=256`, covariances computed from $n < 300$ papers are rank-deficient or numerically fragile. The pipeline therefore sets `min_papers=300` for S4\_frechet; years with fewer papers in a window are skipped.

**Lexical (L1--L3).** TF-IDF vocabulary distributions are sensitive to vocabulary size and occupancy. At $n=30$, many terms appear only once, inflating JS divergence (L1). Adequate power requires $n \geq 50$; the pipeline emits a low-$n$ warning when `n_min < 50` in a lexical window pair (see `low_n_threshold` in config). The global `min_papers=30` allows computation but the result should be interpreted cautiously. See ticket 0099 for the dimension--sample ratio derivation.

**Citation graph (G1--G9).** Graph methods require a connected subgraph. At $n=30$ with typical citation density ($\bar{k} \approx 5$ in-citations per paper), the mean in-degree is $\bar{k}/n \approx 0.17$, which is above the subcritical threshold for Erdős--Rényi random graphs ($\lambda = 1$ requires $\bar{k} > 1$). In practice, the giant component exists at $n=30$ for this corpus. Community detection (G9) needs at least two non-trivial communities; at $n=30$, the modularity landscape is noisy but not degenerate. The global minimum of 30 is adequate for graph methods.

**C2ST.** With `cv_folds=5`, each fold holds out one-fifth of papers per class. At $n=30$ balanced, the smallest test fold has $30 / (2 \times 5) = 3$ papers — far too few for stable AUC estimation. Reliable AUC requires at least 5--10 papers per test fold, implying $n \geq 50$ (giving $\geq 5$ per class per fold). The pipeline sets `min_papers=50` for C2ST; years below this threshold are skipped.
