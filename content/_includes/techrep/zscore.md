## Standardisation: cross-year Z-scores {#sec:zscore}

For each (method, window) pair we compute the time series $D(t, w)$ of divergence or distance values.
Within each window $w$, we standardise across years:

$$Z(t, w) = \frac{D(t,w) - \bar{D}(\cdot,w)}{\sigma_D(\cdot,w)}$$

This cross-year $Z$-score measures relative displacement from the temporal mean, not absolute magnitude.
It removes the long-run trend that dominates raw divergence values
and makes methods with different units comparable on the same panel.
A value $|Z| \geq 2$ indicates an unusually large (or small) divergence relative to the period average.
