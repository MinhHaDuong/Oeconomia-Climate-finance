## L4. C2ST — Classifier Two-Sample Test (lexical) {#sec-c2st-lexical}

As a meta-check on the lexical distributional methods,
we train a simple classifier to distinguish "before" from "after" papers in the TF-IDF feature space.
If the classifier AUC $> 0.5$ (better than chance),
the two windows are distinguishable by their vocabulary features.

### Principle

C2ST also has an embedding counterpart (see §S5 C2ST (embedding)); the principle is identical, only the feature space differs.

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

For each $(t, w)$ pair, split papers into before/after labels and train a logistic regression with $\ell^2$ regularisation (sklearn default) on the TF-IDF vectors of abstracts and titles.
Measure 5-fold cross-validated AUC $\in [0, 1]$.

$$D_{\text{C2ST}}(t, w) = \mathrm{AUC}(t, w)$$

Reference level: $\mathrm{AUC} = 0.5$ (random classifier).

*Script:* `scripts/_divergence_lexical.py`, method `c2st`.

### Principle figure

![](figures/schematic_C2ST.png){width=100%}

*C2ST principle: a logistic classifier fits a decision boundary in feature space; cross-validated AUC above 0.50 confirms the before/after distributions differ. The same schematic applies to both the embedding and lexical channels — only the feature axes change. Script: `scripts/plot_schematic_C2ST.py`.*

### Advantages, biases, limitations

**Advantages.** No kernel, bandwidth, or bin width to choose.
In the lexical feature space the classifier's learned coefficients are directly interpretable:
they rank TF-IDF terms by their contribution to the before/after split,
giving a built-in attribution story the distance-based detectors lack
(and arguably more transparent than the embedding-channel counterpart, since terms are human-readable).
Variance is estimated cheaply from the cross-validation folds, with no need for a separate null model.

**Biases.** AUC depends on classifier capacity:
a logistic regression captures linear separability only, so C2ST will underestimate differences that are non-linear in the feature space.
The reported variance is dominated by fold sampling rather than by distributional uncertainty, so fold-CV standard deviations are narrower than a full permutation null would produce.
TF-IDF features also inherit a year bias when the corpus vocabulary grows or drifts (new terms enter the field after year $t$), which can inflate AUC even when the underlying topical distribution is stable.

**Limitations.** C2ST does not share the permutation null used by S2, L1, and G9;
its AUC has a different sampling distribution and cannot be fused into the same Z-score scale without rescaling.
We therefore reserve it an epistemic role as a *reference layer*, not a voting layer,
in the companion paper's transition-zone validation:
AUC visibly above 0.5 corroborates the distance-based signals but does not by itself validate a zone.

### Corpus results

![](figures/fig_zoo_C2ST_lexical.png){width=100%}

*Cross-year Z-score for C2ST (lexical), w=2–5.*

**Key values.** The C2ST lexical channel hovers around 0.60–0.67, significantly above chance, for almost all years — confirming that before/after windows are consistently distinguishable. Like its embedding sibling, the AUC time series is flat and noisy: no 2007 peak, no convergence trend. The lexical channel does not add a differential signal beyond the embedding channel on this corpus; both confirm that $\mathrm{AUC} > 0.5$ everywhere, so the distance-based methods are not measuring noise.

### References

Seminal: @lopez_paz_oquab2017 (Lopez-Paz & Oquab 2017, "Revisiting Classifier Two-Sample Tests", *ICLR*).
Recent analogue: @lemos2023sampling (Lemos et al. 2023, "Sampling-Based Accuracy Testing Posterior Estimation for General Inference").
