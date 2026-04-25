"""Tests for --null-ci argument in plot_zoo_results.py."""

import argparse
import os
import sys

import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


def _build_method_parser() -> argparse.ArgumentParser:
    """Return the method-level argument parser from plot_zoo_results.

    This mirrors the parser constructed inside main() so we can test its
    help text without running the full script (which requires --output and
    live data).
    """
    import plot_zoo_results

    return plot_zoo_results._build_method_parser()


def test_plot_zoo_results_accepts_null_ci_arg():
    """plot_zoo_results.py must accept --null-ci argument."""
    parser = _build_method_parser()
    help_text = parser.format_help()
    assert "--null-ci" in help_text, "--null-ci argument not found in parser help"


def test_null_ci_defaults_to_none():
    """--null-ci should default to None (optional)."""
    parser = _build_method_parser()
    args = parser.parse_args(["--method", "S2_energy"])
    assert args.null_ci is None


def test_null_ci_accepts_path():
    """--null-ci should accept a path string."""
    parser = _build_method_parser()
    args = parser.parse_args(
        ["--method", "S2_energy", "--null-ci", "/tmp/tab_null_S2_energy.csv"]
    )
    assert args.null_ci == "/tmp/tab_null_S2_energy.csv"


def test_load_null_df_returns_none_when_path_is_none():
    """_load_null_df(None) must return None without raising."""
    import plot_zoo_results

    assert plot_zoo_results._load_null_df(None) is None


def test_load_null_df_returns_none_for_missing_file():
    """_load_null_df with a non-existent path returns None (graceful)."""
    import plot_zoo_results

    assert plot_zoo_results._load_null_df("/nonexistent/path/tab_null.csv") is None


def test_compute_null_z_threshold_adds_column():
    """_compute_null_z_threshold adds z_threshold_upper and z_threshold_lower columns."""
    import plot_zoo_results

    df = pd.DataFrame(
        {
            "year": [2005, 2006, 2007, 2008],
            "window": ["3", "3", "3", "3"],
            "value": [1.0, 2.0, 3.0, 4.0],
            "z_score": [0.5, 1.0, 1.5, 2.0],
        }
    )
    null_df = pd.DataFrame(
        {
            "year": [2005, 2006, 2007, 2008],
            "window": ["3", "3", "3", "3"],
            "null_mean": [1.5, 1.5, 1.5, 1.5],
            "null_std": [0.5, 0.5, 0.5, 0.5],
        }
    )
    result = plot_zoo_results._compute_null_z_threshold(df, null_df)
    assert "z_threshold_upper" in result.columns
    assert "z_threshold_lower" in result.columns
    assert not result["z_threshold_upper"].isna().any()
    assert not result["z_threshold_lower"].isna().any()
    # z_threshold_upper = (null_mean + 1.96*null_std - mu_w) / sigma_w
    mu_w = df["value"].mean()  # window "3" only
    sigma_w = df["value"].std()
    expected_upper = (1.5 + 1.96 * 0.5 - mu_w) / sigma_w
    expected_lower = (1.5 - 1.96 * 0.5 - mu_w) / sigma_w
    assert (
        pytest.approx(result["z_threshold_upper"].iloc[0], rel=1e-6) == expected_upper
    )
    assert (
        pytest.approx(result["z_threshold_lower"].iloc[0], rel=1e-6) == expected_lower
    )
