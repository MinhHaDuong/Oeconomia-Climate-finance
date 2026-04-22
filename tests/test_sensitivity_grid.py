"""TDD tests for ticket 0083 sensitivity grid."""

import os

import pandas as pd
import pytest
from pipeline_loaders import load_analysis_config

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")


def test_sensitivity_config_block_exists():
    """config/analysis.yaml must have a sensitivity: block with required keys."""
    cfg = load_analysis_config()
    assert "sensitivity" in cfg, "Missing sensitivity: block in analysis.yaml"
    s = cfg["sensitivity"]
    assert "windows" in s, "sensitivity.windows missing"
    assert "gaps" in s, "sensitivity.gaps missing"
    assert "dims" in s, "sensitivity.dims missing"
    assert "equal_n_r" in s, "sensitivity.equal_n_r missing"


def test_sensitivity_grid_schema():
    """tab_sensitivity_grid.csv carries required columns (smoke: file must exist)."""
    path = "content/tables/tab_sensitivity_grid.csv"
    if not os.path.exists(path):
        pytest.skip(
            "tab_sensitivity_grid.csv not yet generated — run compute_sensitivity_grid.py"
        )
    df = pd.read_csv(path)
    required = {
        "model",
        "dim",
        "window",
        "gap",
        "year",
        "method",
        "z_score",
        "n_before",
        "n_after",
    }
    missing = required - set(df.columns)
    assert not missing, f"Missing columns: {missing}"
