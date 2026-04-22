"""Theory tests for cross-year Z-score bias under non-stationarity.

These tests verify mathematical facts about the cross-year Z-score, not code
behavior. They serve as documentation (the proposition is true) and as
regression guards (the proof algebra stays correct if this file is modified).

See content/_includes/techrep/null-model.md §Two notions of Z-score for the
formal statement and proof.
"""


def test_zscore_inflated_at_trend_extremes():
    """Under linear trend, Z-score is biased at early and late years."""
    import numpy as np

    rng = np.random.default_rng(42)
    T = 30
    b = 0.1  # linear trend
    sigma = 0.05
    D = b * np.arange(T) + rng.normal(0, sigma, T)
    Z = (D - D.mean()) / D.std()
    early_bias = (Z[:5] - (D[:5] - D.mean()) / sigma).mean()
    assert early_bias > 0.5, "Expected positive bias at early years under trend"
