"""Tests for --null-ci argument in plot_zoo_results.py."""

import argparse
import os
import sys

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
