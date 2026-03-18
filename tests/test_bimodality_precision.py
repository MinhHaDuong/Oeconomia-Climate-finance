"""Bimodality CSV outputs must use bounded precision for cross-machine reproducibility.

Float columns should carry only scientifically meaningful digits, not 15+ digits
of platform-dependent BLAS noise. Tickets: #203, #205
"""

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))
from utils import BASE_DIR

TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")


def _max_decimal_places(series):
    """Return the max number of decimal places in a float Series."""
    max_dp = 0
    for val in series.dropna():
        s = f"{val:g}"  # compact representation, no trailing zeros
        if "." in s:
            dp = len(s.split(".")[1])
            max_dp = max(max_dp, dp)
    return max_dp


@pytest.mark.skipif(
    not os.path.exists(os.path.join(TABLES_DIR, "tab_bimodality.csv")),
    reason="tab_bimodality.csv not built",
)
class TestBimodalityPrecision:
    """Float columns in bimodality CSVs must not exceed meaningful precision."""

    def test_bic_values_are_integers(self):
        df = pd.read_csv(os.path.join(TABLES_DIR, "tab_bimodality.csv"))
        for col in ["bic_1comp", "bic_2comp", "delta_bic"]:
            vals = df[col].dropna()
            if len(vals) == 0:
                continue
            assert all(v == int(v) for v in vals), (
                f"{col} should be rounded to integers, got: {vals.tolist()}"
            )

    def test_correlations_max_4dp(self):
        df = pd.read_csv(os.path.join(TABLES_DIR, "tab_bimodality.csv"))
        for col in ["embedding_lexical_corr"]:
            dp = _max_decimal_places(df[col])
            assert dp <= 4, f"{col} has {dp} decimal places, expected <= 4"

    def test_variance_max_4dp(self):
        df = pd.read_csv(os.path.join(TABLES_DIR, "tab_bimodality.csv"))
        dp = _max_decimal_places(df["explained_variance"])
        assert dp <= 4, f"explained_variance has {dp} decimal places, expected <= 4"

    def test_axis_detection_precision(self):
        """All float columns in tab_axis_detection.csv must have bounded precision.

        The script writes this file twice: once for embedding PCA (columns
        variance_explained, cosine_with_seed_axis) and once for the combined
        TF-IDF SVD + embedding PCA table (columns explained_variance_ratio,
        corr_with_embedding_axis, etc.). In non-core mode the second write
        overwrites the first, but both must round to avoid cross-machine jitter.
        """
        path = os.path.join(TABLES_DIR, "tab_axis_detection.csv")
        if not os.path.exists(path):
            pytest.skip("tab_axis_detection.csv not built")
        df = pd.read_csv(path)
        # Combined table columns (TF-IDF SVD + embedding PCA)
        for col in ["explained_variance_ratio", "corr_with_embedding_axis",
                     "abs_corr_with_embedding_axis"]:
            if col in df.columns:
                dp = _max_decimal_places(df[col])
                assert dp <= 4, f"{col} has {dp} decimal places, expected <= 4"
        # Embedding PCA table columns (written first, may survive in core mode)
        for col in ["variance_explained", "cosine_with_seed_axis"]:
            if col in df.columns:
                dp = _max_decimal_places(df[col])
                assert dp <= 4, f"{col} has {dp} decimal places, expected <= 4"
        if "delta_bic" in df.columns:
            vals = df["delta_bic"].dropna()
            assert all(v == int(v) for v in vals), (
                f"delta_bic should be integers, got: {vals.tolist()}"
            )

    def test_pole_papers_scores_max_4dp(self):
        path = os.path.join(TABLES_DIR, "tab_pole_papers.csv")
        if not os.path.exists(path):
            pytest.skip("tab_pole_papers.csv not built")
        df = pd.read_csv(path)
        for col in ["axis_score", "lex_score"]:
            if col in df.columns:
                dp = _max_decimal_places(df[col])
                assert dp <= 4, f"{col} has {dp} decimal places, expected <= 4"
