"""Tests for change point detection pipeline.

Tests:
1. Synthetic series: PELT, Dynp, KernelCPD detect a known break
2. Smoke test: run compute_changepoints.py on fixture divergence CSVs
3. Convergence table has expected columns and properties
"""

import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
ROOT_DIR = os.path.join(os.path.dirname(__file__), "..")
TABLES_DIR = os.path.join(ROOT_DIR, "content", "tables")

sys.path.insert(0, SCRIPTS_DIR)


# ---------------------------------------------------------------------------
# Unit tests: detectors on synthetic data
# ---------------------------------------------------------------------------


class TestDetectorsOnSynthetic:
    """Each detector should find a break in a signal with a known mean shift."""

    @pytest.fixture
    def synthetic_series(self):
        """Signal with a mean shift at index 15 (year 2015)."""
        rng = np.random.RandomState(42)
        n = 30
        signal = np.concatenate(
            [
                rng.normal(0, 0.3, 15),
                rng.normal(2, 0.3, 15),
            ]
        )
        years = np.arange(2000, 2000 + n)
        return signal, years

    def test_pelt_finds_break(self, synthetic_series):
        from compute_changepoints import _run_pelt

        signal, years = synthetic_series
        sig = signal.reshape(-1, 1)
        results = _run_pelt(sig, penalties=[3])

        assert len(results) == 1
        params, bkps = results[0]
        assert params == "pen=3"
        # Should detect at least one break near index 15
        assert len(bkps) > 0
        # At least one break within 3 of the true break point
        assert any(abs(b - 15) <= 3 for b in bkps), (
            f"Expected break near 15, got {bkps}"
        )

    def test_dynp_finds_break(self, synthetic_series):
        from compute_changepoints import _run_dynp

        signal, years = synthetic_series
        sig = signal.reshape(-1, 1)
        results = _run_dynp(sig, n_bkps_list=[1])

        assert len(results) == 1
        params, bkps = results[0]
        assert params == "n_bkps=1"
        assert len(bkps) == 1
        # Break should be near index 15
        assert abs(bkps[0] - 15) <= 3, f"Expected break near 15, got {bkps[0]}"

    def test_kernel_cpd_finds_break(self, synthetic_series):
        from compute_changepoints import _run_kernel_cpd

        signal, years = synthetic_series
        sig = signal.reshape(-1, 1)
        results = _run_kernel_cpd(sig, penalties=[3])

        assert len(results) == 1
        params, bkps = results[0]
        assert params == "pen=3"
        assert len(bkps) > 0
        assert any(abs(b - 15) <= 3 for b in bkps), (
            f"Expected break near 15, got {bkps}"
        )

    def test_pelt_multiple_penalties(self, synthetic_series):
        from compute_changepoints import _run_pelt

        signal, _ = synthetic_series
        sig = signal.reshape(-1, 1)
        results = _run_pelt(sig, penalties=[1, 3, 5])

        assert len(results) == 3
        # Higher penalty should find fewer or equal breaks
        _, bkps_pen1 = results[0]
        _, bkps_pen5 = results[2]
        assert len(bkps_pen1) >= len(bkps_pen5)


class TestInterpolateSignal:
    """Test signal interpolation logic."""

    def test_too_few_points_returns_none(self):
        from compute_changepoints import _interpolate_signal

        values = [np.nan, np.nan, 1.0, np.nan, np.nan]
        result = _interpolate_signal(values)
        assert result is None

    def test_sufficient_points_returns_array(self):
        from compute_changepoints import _interpolate_signal

        values = [1.0, np.nan, 3.0, 4.0, 5.0, 6.0]
        result = _interpolate_signal(values)
        assert result is not None
        assert len(result) == 6
        assert np.isclose(result[1], 2.0)  # interpolated

    def test_all_nonnull(self):
        from compute_changepoints import _interpolate_signal

        values = [1.0, 2.0, 3.0, 4.0, 5.0]
        result = _interpolate_signal(values)
        assert result is not None
        np.testing.assert_array_equal(result, values)


# ---------------------------------------------------------------------------
# Integration: compute_breaks on a small DataFrame
# ---------------------------------------------------------------------------


class TestComputeBreaks:
    """Test the full compute_breaks pipeline on a small DataFrame."""

    def test_breaks_output_schema(self):
        from compute_changepoints import compute_breaks

        # Create a simple divergence series with a clear break
        rng = np.random.RandomState(42)
        years = list(range(2005, 2025))
        values = list(rng.normal(1, 0.1, 10)) + list(rng.normal(3, 0.1, 10))

        div_df = pd.DataFrame(
            {
                "method": ["test_method"] * len(years),
                "channel": ["semantic"] * len(years),
                "year": years,
                "window": ["3"] * len(years),
                "hyperparams": [""] * len(years),
                "value": values,
            }
        )

        breaks_df = compute_breaks(div_df, pelt_penalties=[3])

        expected_cols = {
            "method",
            "channel",
            "window",
            "hyperparams",
            "detector",
            "detector_params",
            "break_years",
        }
        assert set(breaks_df.columns) == expected_cols
        assert len(breaks_df) > 0
        assert set(breaks_df["detector"].unique()) == {"pelt", "dynp", "kernel_cpd"}

    def test_skips_sparse_series(self):
        from compute_changepoints import compute_breaks

        # Series with too few non-NaN points
        div_df = pd.DataFrame(
            {
                "method": ["sparse"] * 4,
                "channel": ["semantic"] * 4,
                "year": [2010, 2011, 2012, 2013],
                "window": ["3"] * 4,
                "hyperparams": [""] * 4,
                "value": [1.0, np.nan, np.nan, 2.0],
            }
        )

        breaks_df = compute_breaks(div_df, pelt_penalties=[3])
        # Too few points: should produce empty output
        assert len(breaks_df) == 0


# ---------------------------------------------------------------------------
# Integration: convergence table
# ---------------------------------------------------------------------------


class TestConvergence:
    """Test convergence table computation."""

    def test_convergence_columns(self):
        from compute_changepoints import compute_convergence

        breaks_df = pd.DataFrame(
            {
                "method": ["S1_MMD", "L1", "G1_pagerank"],
                "channel": ["semantic", "lexical", "citation"],
                "window": ["3", "3", "cumulative"],
                "hyperparams": ["", "", ""],
                "detector": ["pelt", "pelt", "pelt"],
                "detector_params": ["pen=3", "pen=3", "pen=3"],
                "break_years": ["2007;2013", "2007", "2013"],
            }
        )

        conv_df = compute_convergence(breaks_df)

        expected_cols = {
            "year",
            "n_semantic",
            "n_lexical",
            "n_citation",
            "n_total",
            "pct_total",
            "methods_detecting",
        }
        assert set(conv_df.columns) == expected_cols
        assert len(conv_df) > 0

    def test_convergence_counts_within_tolerance(self):
        from compute_changepoints import compute_convergence

        breaks_df = pd.DataFrame(
            {
                "method": ["A", "B", "C"],
                "channel": ["semantic", "lexical", "citation"],
                "window": ["3", "3", "3"],
                "hyperparams": ["", "", ""],
                "detector": ["pelt", "pelt", "pelt"],
                "detector_params": ["pen=3", "pen=3", "pen=3"],
                "break_years": ["2007", "2008", "2007"],
            }
        )

        conv_df = compute_convergence(breaks_df)

        # Year 2007 should count method A (exact) and B (within +-1) and C
        row_2007 = conv_df[conv_df["year"] == 2007]
        assert len(row_2007) == 1
        assert row_2007.iloc[0]["n_total"] == 3  # all three within +-1

    def test_empty_breaks(self):
        from compute_changepoints import compute_convergence

        breaks_df = pd.DataFrame(
            {
                "method": ["A"],
                "channel": ["semantic"],
                "window": ["3"],
                "hyperparams": [""],
                "detector": ["pelt"],
                "detector_params": ["pen=3"],
                "break_years": [""],
            }
        )

        conv_df = compute_convergence(breaks_df)
        assert len(conv_df) == 0


# ---------------------------------------------------------------------------
# Smoke test: run on existing divergence CSVs
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestSmoke:
    """Run compute_changepoints.py on available divergence data."""

    @pytest.fixture
    def divergence_csvs(self):
        """Find existing divergence CSVs (new-style or legacy)."""
        import glob

        paths = sorted(glob.glob(os.path.join(TABLES_DIR, "tab_div_*.csv")))
        if not paths:
            paths = sorted(glob.glob(os.path.join(TABLES_DIR, "tab_*_divergence.csv")))
        if not paths:
            pytest.skip("No divergence CSVs available")
        return paths

    def test_smoke_run(self, divergence_csvs, tmp_path):
        """Run the script end-to-end on fixture data."""
        output = str(tmp_path / "tab_changepoints.csv")
        cmd = [
            sys.executable,
            os.path.join(SCRIPTS_DIR, "compute_changepoints.py"),
            "--output",
            output,
            "--input",
        ] + divergence_csvs

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
        )

        assert result.returncode == 0, (
            f"Script failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )

        # Breaks table should exist
        assert os.path.exists(output)
        breaks_df = pd.read_csv(output)
        assert len(breaks_df) > 0

        expected_cols = {
            "method",
            "channel",
            "window",
            "hyperparams",
            "detector",
            "detector_params",
            "break_years",
        }
        assert set(breaks_df.columns) == expected_cols

        # Convergence is now a separate script (compute_convergence.py);
        # verify compute_convergence function works on this output.
        from compute_changepoints import compute_convergence

        conv_df = compute_convergence(breaks_df)
        conv_expected = {
            "year",
            "n_semantic",
            "n_lexical",
            "n_citation",
            "n_total",
            "pct_total",
            "methods_detecting",
        }
        assert set(conv_df.columns) == conv_expected


# ---------------------------------------------------------------------------
# compute_convergence.py CLI smoke test
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestComputeConvergenceScript:
    """Test compute_convergence.py CLI on synthetic changepoints data."""

    def test_convergence_script_smoke(self, tmp_path):
        """Run compute_convergence.py on changepoints output."""
        # Create a synthetic changepoints CSV
        breaks_df = pd.DataFrame(
            {
                "method": ["S1_MMD", "L1", "G1_pagerank", "S2_energy"],
                "channel": ["semantic", "lexical", "citation", "semantic"],
                "window": ["3", "3", "cumulative", "3"],
                "hyperparams": ["", "", "", ""],
                "detector": ["pelt", "pelt", "pelt", "pelt"],
                "detector_params": ["pen=3", "pen=3", "pen=3", "pen=3"],
                "break_years": ["2007;2013", "2007", "2013", "2008"],
            }
        )
        input_path = tmp_path / "tab_changepoints.csv"
        breaks_df.to_csv(input_path, index=False)

        output_path = tmp_path / "tab_convergence.csv"
        result = subprocess.run(
            [
                sys.executable,
                os.path.join(SCRIPTS_DIR, "compute_convergence.py"),
                "--output",
                str(output_path),
                "--input",
                str(input_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"compute_convergence.py failed:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert output_path.exists(), "Convergence CSV not created"
        conv_df = pd.read_csv(output_path)
        expected_cols = {
            "year",
            "n_semantic",
            "n_lexical",
            "n_citation",
            "n_total",
            "pct_total",
            "methods_detecting",
        }
        assert set(conv_df.columns) == expected_cols
        assert len(conv_df) > 0


# ---------------------------------------------------------------------------
# plot_convergence.py smoke test
# ---------------------------------------------------------------------------


@pytest.mark.integration
class TestPlotConvergence:
    """Test plot_convergence.py produces a PNG without error."""

    def test_plot_convergence_smoke(self, tmp_path):
        """plot_convergence.py produces a PNG without error."""
        # Create synthetic divergence + changepoints data
        years = list(range(2005, 2020))

        # Divergence CSV
        div_rows = []
        for method in ["S1_MMD", "L1"]:
            channel = "semantic" if method.startswith("S") else "lexical"
            for y in years:
                div_rows.append(
                    {
                        "year": y,
                        "channel": channel,
                        "window": "3",
                        "hyperparams": "default",
                        "value": float(y - 2005) * 0.1,
                    }
                )
        div_df = pd.DataFrame(div_rows)
        div_path = tmp_path / "tab_div_S1_MMD.csv"
        div_s1 = div_df[div_df["channel"] == "semantic"]
        div_s1.to_csv(div_path, index=False)

        div_l1_path = tmp_path / "tab_div_L1.csv"
        div_l1 = div_df[div_df["channel"] == "lexical"]
        div_l1.to_csv(div_l1_path, index=False)

        # Changepoints CSV
        breaks_df = pd.DataFrame(
            {
                "method": ["S1_MMD", "L1"],
                "channel": ["semantic", "lexical"],
                "window": ["3", "3"],
                "hyperparams": ["default", "default"],
                "detector": ["pelt", "pelt"],
                "detector_params": ["pen=3", "pen=3"],
                "break_years": ["2010", "2010"],
            }
        )
        breaks_path = tmp_path / "tab_changepoints.csv"
        breaks_df.to_csv(breaks_path, index=False)

        # Convergence CSV (sibling file)
        from compute_changepoints import compute_convergence

        conv_df = compute_convergence(breaks_df)
        conv_path = tmp_path / "tab_changepoints_convergence.csv"
        conv_df.to_csv(conv_path, index=False)

        # Run plot
        fig_out = tmp_path / "fig_convergence.png"
        result = subprocess.run(
            [
                sys.executable,
                os.path.join(SCRIPTS_DIR, "plot_convergence.py"),
                "--output",
                str(fig_out),
                "--input",
                str(breaks_path),
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert result.returncode == 0, (
            f"plot_convergence.py failed:\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert fig_out.exists(), (
            f"Expected {fig_out} but found: {[f.name for f in tmp_path.iterdir()]}"
        )
