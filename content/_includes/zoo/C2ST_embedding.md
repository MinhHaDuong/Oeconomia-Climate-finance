## S5. C2ST — Classifier Two-Sample Test (embedding) {#sec-c2st-embedding}

As a meta-check on the distributional-shift methods,
we train a simple classifier to distinguish "before" from "after" papers in the BAAI/bge-m3 embedding space.
If the classifier AUC $> 0.5$ (better than chance),
the two windows are distinguishable by their embedding features.

### Principle

C2ST also has a lexical counterpart (see §L4 C2ST (lexical)); the principle is identical, only the feature space differs.

C2ST recasts the two-sample problem as a supervised learning task [@lopez_paz_oquab2017]:
if a simple classifier can predict whether a paper belongs to the before- or after-window
better than chance, the two distributions must differ.
The test statistic is the cross-validated classifier AUC; the null is $\mathrm{AUC} = 0.5$.

This differs from the distance-based detectors (S1–S4, L1, G9) in a crucial way.
MMD, energy distance, sliced Wasserstein, and JS divergence all compare the two empirical distributions *directly* through a chosen geometry (kernel, Euclidean distance, projection, bin counts).
C2ST instead lets a classifier *fit its own decision boundary* in feature space —
the geometry of comparison is learned, not prescribed.
It answers "are they separable?" rather than "how far apart are they?".

### Definition

For each $(t, w)$ pair, split papers into before/after labels and train a logistic regression with $\ell^2$ regularisation (sklearn default) on the BAAI/bge-m3 embedding vectors.
Measure 5-fold cross-validated AUC $\in [0, 1]$.

$$D_{\text{C2ST}}(t, w) = \mathrm{AUC}(t, w)$$

Reference level: $\mathrm{AUC} = 0.5$ (random classifier).

*Script:* `scripts/_divergence_semantic.py`, method `c2st`.

### Principle figure

![](figures/schematic_C2ST.png){width=100%}

*C2ST principle: a logistic classifier fits a decision boundary in PCA-projected embedding space; cross-validated AUC above 0.50 confirms the before/after distributions differ. Script: `scripts/plot_schematic_C2ST.py`.*

### Advantages, biases, limitations

**Advantages.** No kernel or bandwidth to choose, unlike MMD; no projection direction to sample, unlike sliced Wasserstein.
The classifier's learned coefficients are directly interpretable — they rank embedding dimensions by their contribution to the before/after split, giving a built-in attribution story the distance-based detectors lack.
Variance is estimated cheaply from the cross-validation folds, with no need for a separate null model.

**Biases.** AUC depends on classifier capacity:
a logistic regression captures linear separability only, so C2ST will underestimate differences that are non-linear in the feature space.
The reported variance is dominated by fold sampling rather than by distributional uncertainty, so fold-CV standard deviations are narrower than a full permutation null would produce.

**Limitations.** C2ST does not share the permutation null used by S2, L1, and G9;
its AUC has a different sampling distribution and cannot be fused into the same Z-score scale without rescaling.
We therefore reserve it an epistemic role as a *reference layer*, not a voting layer,
in the companion paper's transition-zone validation:
AUC visibly above 0.5 corroborates the distance-based signals but does not by itself validate a zone.

### Corpus results

![](figures/fig_zoo_C2ST_embedding.png){width=100%}

*Cross-year Z-score for C2ST (embedding), w=2–5.*

**Key values.** The C2ST embedding channel hovers around 0.60–0.67, significantly above chance, for almost all years — confirming that before/after windows are consistently distinguishable. However, the AUC time series is flat and noisy: no 2007 peak, no convergence trend. C2ST is a less sensitive detector than the distributional methods for this corpus. Its primary use here is as a sanity check: the fact that $\mathrm{AUC} > 0.5$ everywhere confirms that our methods are not measuring noise.

### Sample size note

With `cv_folds=5`, each fold holds out one-fifth of each class. At $n=30$ balanced papers, the smallest test fold contains only 3 papers per class — too few for stable AUC estimation. Reliable folds require at least 5 test papers per class, giving $n \geq 50$. The pipeline sets `min_papers=50` for C2ST in `config/analysis.yaml`; (year, window) pairs below this threshold are skipped. AUC estimates near the boundary ($n \approx 50$) carry higher variance than those at typical window sizes ($n \approx 200$).

### References

Seminal: @lopez_paz_oquab2017 (Lopez-Paz & Oquab 2017, "Revisiting Classifier Two-Sample Tests", *ICLR*).
Recent analogue: @lemos2023sampling (Lemos et al. 2023, "Sampling-Based Accuracy Testing Posterior Estimation for General Inference").
