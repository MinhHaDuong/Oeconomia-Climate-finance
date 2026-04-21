## Permutation null model

For each (method, year, window) cell, we assess statistical significance via a permutation test.
Under the null hypothesis of label exchangeability, before- and after-period papers are pooled and
relabelled $B = 500$ times; the observed divergence statistic is then standardised against this
null distribution to yield a $Z$-score (see §\ref{sec:zscore}).
Three complementary strategies make the $B = 500 \times \text{cells}$ computation tractable:
(i) **GPU-batched permutations** for $S_2$ energy distance and $S_1$ MMD: the pairwise
distance or kernel matrix is precomputed once on GPU; all $B$ permutation statistics reduce to
a single matrix multiplication, converting $O(B n^2)$ computation to $O(n^2)$ setup plus $O(B n)$
batched aggregation;
(ii) **precomputed TF-IDF** for $L_1$: the vectoriser runs once per window, and permutations
reshuffle row indices into the sparse matrix, eliminating $B$ redundant transform calls; and
(iii) **CPU parallelism** via joblib across (year, window) pairs for $G_2$ spectral gap and
$G_9$ community JS divergence, with a configurable `--n-jobs` flag (default: all cores).
End-to-end runtime on an NVIDIA RTX A4000 drops from approximately three hours to seven minutes
for the full null-model sweep.
