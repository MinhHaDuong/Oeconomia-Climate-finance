"""Smoke tests for semantic distributional divergence (S1-S4).

Runs compute_divergence_semantic.py on the smoke fixture and verifies:
- Output CSV exists and has expected columns
- All four methods produce results
- Break detection runs without error
"""

import os
import subprocess
import sys

import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "smoke")


class TestSemanticDivergenceSmoke:
    """End-to-end smoke test on fixture data."""

    @pytest.fixture(autouse=True)
    def setup_output(self, tmp_path):
        self.output_csv = str(tmp_path / "tab_semantic_divergence.csv")
        self.breaks_csv = str(tmp_path / "tab_semantic_divergence_breaks.csv")

    def test_compute_produces_output(self):
        """compute_divergence_semantic.py runs and produces CSV with expected columns."""
        env = os.environ.copy()
        env["CLIMATE_FINANCE_DATA"] = FIXTURES_DIR

        result = subprocess.run(
            [
                sys.executable,
                os.path.join(SCRIPTS_DIR, "compute_divergence_semantic.py"),
                "--output", self.output_csv,
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert result.returncode == 0, (
            f"Script failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

        assert os.path.exists(self.output_csv), "Output CSV not created"
        df = pd.read_csv(self.output_csv)

        # Expected columns
        expected_cols = {"year", "method", "channel", "window", "hyperparams", "value"}
        assert expected_cols.issubset(set(df.columns)), (
            f"Missing columns: {expected_cols - set(df.columns)}"
        )

        # All four methods present
        methods = set(df["method"].unique())
        for m in ["S1_MMD", "S2_energy", "S3_sliced_wasserstein", "S4_frechet"]:
            assert m in methods, f"Method {m} missing from output"

        # Non-empty
        assert len(df) > 0, "Output is empty"

        # Values are numeric and non-negative
        assert df["value"].dtype in ("float64", "float32", "int64")
        assert (df["value"] >= 0).all(), "Negative divergence values found"

    def test_breaks_file_produced(self):
        """Companion _breaks.csv is produced alongside the main output."""
        env = os.environ.copy()
        env["CLIMATE_FINANCE_DATA"] = FIXTURES_DIR

        subprocess.run(
            [
                sys.executable,
                os.path.join(SCRIPTS_DIR, "compute_divergence_semantic.py"),
                "--output", self.output_csv,
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )

        assert os.path.exists(self.breaks_csv), "Breaks CSV not created"
        bdf = pd.read_csv(self.breaks_csv)

        expected_cols = {"method", "channel", "window", "hyperparams", "penalty", "break_years"}
        assert expected_cols.issubset(set(bdf.columns)), (
            f"Missing break columns: {expected_cols - set(bdf.columns)}"
        )

    def test_multiple_windows(self):
        """Multiple window sizes appear in output."""
        env = os.environ.copy()
        env["CLIMATE_FINANCE_DATA"] = FIXTURES_DIR

        subprocess.run(
            [
                sys.executable,
                os.path.join(SCRIPTS_DIR, "compute_divergence_semantic.py"),
                "--output", self.output_csv,
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=300,
        )

        df = pd.read_csv(self.output_csv)
        windows = set(df["window"].unique())
        assert len(windows) >= 2, f"Expected multiple windows, got {windows}"
