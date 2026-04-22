## Permutation null model

For each (method, year, window) cell, we assess statistical significance via a permutation test.
Under the null hypothesis of label exchangeability, before- and after-period papers are pooled and
randomly permuted $B = 500$ times; the observed divergence statistic is then standardised against this
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
