## Standardisation: cross-year Z-scores {#sec:zscore}

For each (method, window) pair we compute the time series $D(t, w)$ of divergence or distance values.
Within each window $w$, we standardise across years:

$$Z(t, w) = \frac{D(t,w) - \bar{D}(\cdot,w)}{\sigma_D(\cdot,w)}$$

This cross-year $Z$-score measures relative displacement from the temporal mean, not absolute magnitude.
It removes the long-run trend that dominates raw divergence values.
It also makes methods with different units comparable on the same panel.
A value $|Z| \geq 2$ indicates a divergence two standard deviations from the period mean — useful for comparing methods on the same panel, but not a significance threshold when the series is non-stationary (see §\ref{sec:zscore-two-notions} for the formal argument and §\ref{sec:null-model} for the proper permutation test).
