## C2ST_lexical — Classifier Two-Sample Test (lexical) {#sec-c2st-lexical}

### Principle

The lexical channel of C2ST applies the same framework as C2ST\_embedding (see @sec-c2st-embedding) but replaces the BAAI/bge-m3 embedding features with TF-IDF vectors.
Everything else — the 5-fold logistic regression, the AUC statistic, the epistemic role as a *reference layer* — is identical.

### Corpus results

![](figures/fig_zoo_C2ST_lexical.png){width=100%}

*Cross-year Z-score for C2ST (lexical), w=2–5.*

**Key values.** The C2ST lexical channel hovers around 0.60–0.67, significantly above chance, for almost all years — confirming that before/after windows are consistently distinguishable. Like its embedding sibling, the AUC time series is flat and noisy: no 2007 peak, no convergence trend. The lexical channel does not add a differential signal beyond the embedding channel on this corpus; both confirm that $\mathrm{AUC} > 0.5$ everywhere, so the distance-based methods are not measuring noise.

### References

Seminal: @lopez_paz_oquab2017 (Lopez-Paz & Oquab 2017, "Revisiting Classifier Two-Sample Tests", *ICLR*).
Recent analogue: @lemos2023sampling (Lemos et al. 2023, "Sampling-Based Accuracy Testing Posterior Estimation for General Inference").
