"""Tests for replication ribbon (ticket 0105).

Tests that compute_crossyear_zscores propagates z_lo/z_hi from subsample
percentiles using the same μ/σ as the main z_score.
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)

from compute_crossyear_zscore import compute_crossyear_zscores


class TestRibbonZscores:
    """Unit tests for z_lo/z_hi derivation in compute_crossyear_zscores."""

    @pytest.fixture()
    def synthetic_div_df(self):
        """Synthetic divergence data for 3 windows, 5 years each."""
        rows = []
        rng = np.random.RandomState(99)
        for w in [2, 3, 4]:
            for y in range(2005, 2010):
                rows.append(
                    {"year": y, "window": str(w), "value": rng.uniform(0.1, 0.9)}
                )
        return pd.DataFrame(rows)

    @pytest.fixture()
    def synthetic_subsample_df(self, synthetic_div_df):
        """Synthetic subsample replicates: R=10 per (year, window)."""
        rows = []
        rng = np.random.RandomState(42)
        for _, row in synthetic_div_df.iterrows():
            y, w, center = int(row["year"]), row["window"], row["value"]
            for r in range(10):
                rows.append(
                    {
                        "method": "S2_energy",
                        "year": y,
                        "window": w,
                        "hyperparams": "",
                        "replicate": r,
                        "value": center + rng.normal(0, 0.05),
                    }
                )
        return pd.DataFrame(rows)

    def test_ribbon_columns_present(self, synthetic_div_df, synthetic_subsample_df):
        """z_lo and z_hi columns must be present when subsample_df is provided."""
        result = compute_crossyear_zscores(
            synthetic_div_df, "S2_energy", subsample_df=synthetic_subsample_df
        )
        assert "z_lo" in result.columns, "missing z_lo"
        assert "z_hi" in result.columns, "missing z_hi"

    def test_ribbon_normalization_consistent(
        self, synthetic_div_df, synthetic_subsample_df
    ):
        """z_lo and z_hi must use the same μ/σ as z_score."""
        result = compute_crossyear_zscores(
            synthetic_div_df, "S2_energy", subsample_df=synthetic_subsample_df
        )
        for w, grp in result.groupby("window"):
            mu = grp["value"].mean()
            sigma = grp["value"].std()
            if sigma == 0:
                continue
            expected_z = (grp["value"] - mu) / sigma
            pd.testing.assert_series_equal(
                grp["z_score"].reset_index(drop=True),
                expected_z.reset_index(drop=True),
                check_names=False,
                atol=1e-6,
            )
            nonnull = grp.dropna(subset=["z_lo", "z_hi"])
            assert len(nonnull) > 0, f"all z_lo/z_hi are null for window={w}"
            for _, row in nonnull.iterrows():
                assert row["z_lo"] <= row["z_hi"], (
                    f"z_lo > z_hi at year={row['year']}, window={w}"
                )

    def test_ribbon_absent_without_subsample(self, synthetic_div_df):
        """Without subsample_df, z_lo and z_hi should be NaN."""
        result = compute_crossyear_zscores(synthetic_div_df, "S2_energy")
        assert "z_lo" in result.columns
        assert "z_hi" in result.columns
        assert result["z_lo"].isna().all()
        assert result["z_hi"].isna().all()

    def test_ribbon_width_nondegenerate(self, synthetic_div_df, synthetic_subsample_df):
        """Ribbon must have nonzero width (some spread expected from replicates)."""
        result = compute_crossyear_zscores(
            synthetic_div_df, "S2_energy", subsample_df=synthetic_subsample_df
        )
        nonnull = result.dropna(subset=["z_lo", "z_hi"])
        widths = nonnull["z_hi"] - nonnull["z_lo"]
        assert widths.mean() > 0.01, f"ribbon too narrow: mean width = {widths.mean()}"

    def test_ribbon_handles_all_nan_subsample_group(self, synthetic_div_df):
        """All-NaN subsample groups must return (NaN, NaN), not IndexError."""
        from compute_crossyear_zscore import _subsample_percentiles

        all_nan = pd.DataFrame(
            [
                {"year": 2005, "window": "2", "value": float("nan")},
                {"year": 2005, "window": "2", "value": float("nan")},
            ]
        )
        result = _subsample_percentiles(all_nan, trim=2)
        assert (2005, "2") in result
        vlo, vhi = result[(2005, "2")]
        assert pd.isna(vlo) and pd.isna(vhi)
