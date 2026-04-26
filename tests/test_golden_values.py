"""Golden value regression tests for the divergence pipeline.

Compares fresh runs of all 15 divergence methods against committed golden
CSVs in tests/fixtures/smoke/golden/. Any change in output values (beyond
ATOL=1e-6) is a regression.

These tests catch silent changes in:
  - Numeric libraries (scipy, dcor, ot, numpy)
  - Our metric implementations
  - Data loading / alignment logic
"""

import os
import sys

import numpy as np
import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "smoke")
GOLDEN_DIR = os.path.join(FIXTURES_DIR, "golden")

sys.path.insert(0, SCRIPTS_DIR)
from compute_divergence import METHODS

ALL_METHODS = sorted(METHODS.keys())

# Tolerance for value regression check. Golden files are padme (GPU) outputs.
# Padme S3 is deterministic run-to-run (diff = 0.0); 1e-6 is sufficient.
# CPU environments deviate by ~1e-3 from GPU goldens — these tests are
# intentionally padme-only (@pytest.mark.slow). See ticket 0123 for investigation.
ATOL = 1e-6

from conftest import run_compute as _run_compute


@pytest.mark.slow
class TestGoldenValues:
    """Compare fresh computation against committed golden CSVs."""

    @pytest.mark.parametrize("method", ALL_METHODS)
    def test_method_matches_golden(self, method, tmp_path):
        golden_path = os.path.join(GOLDEN_DIR, f"tab_div_{method}.csv")
        if not os.path.exists(golden_path):
            pytest.skip(f"Golden CSV not found: {golden_path}")

        golden = pd.read_csv(golden_path)

        # Fresh run
        out = tmp_path / f"tab_div_{method}.csv"
        result = _run_compute(method, out)
        assert result.returncode == 0, (
            f"{method} failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

        fresh = pd.read_csv(out)

        # Same shape
        assert fresh.shape == golden.shape, (
            f"{method}: shape mismatch — golden {golden.shape}, fresh {fresh.shape}"
        )

        # Same non-numeric columns (fill NaN before str comparison)
        for col in ["year", "channel", "window", "hyperparams"]:
            if col in golden.columns:
                pd.testing.assert_series_equal(
                    fresh[col].fillna("").astype(str).reset_index(drop=True),
                    golden[col].fillna("").astype(str).reset_index(drop=True),
                    check_names=False,
                    obj=f"{method}.{col}",
                )

        # Numeric values match within tolerance
        golden_vals = golden["value"].values.astype(float)
        fresh_vals = fresh["value"].values.astype(float)

        # Handle NaN positions
        golden_nan = np.isnan(golden_vals)
        fresh_nan = np.isnan(fresh_vals)
        np.testing.assert_array_equal(
            golden_nan,
            fresh_nan,
            err_msg=f"{method}: NaN positions differ",
        )

        # Compare non-NaN values
        mask = ~golden_nan
        if mask.any():
            np.testing.assert_allclose(
                fresh_vals[mask],
                golden_vals[mask],
                atol=ATOL,
                err_msg=f"{method}: value column regression",
            )
