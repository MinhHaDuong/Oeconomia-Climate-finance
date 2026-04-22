"""Tests for zoo bias comparison plot (ticket 0098)."""

import os
import subprocess
import sys

import pandas as pd
import pytest


@pytest.fixture()
def bias_csvs(tmp_path):
    cols = {"year": [2005, 2006, 2007], "window": ["3"] * 3, "hyperparams": [None] * 3}
    df_deb = pd.DataFrame({**cols, "value": [0.10, 0.15, 0.12]})
    df_bias = pd.DataFrame({**cols, "value": [0.20, 0.30, 0.25]})
    p_deb = tmp_path / "tab_div_S2_energy.csv"
    df_deb.to_csv(p_deb, index=False)
    p_bias = tmp_path / "tab_div_biased_S2_energy.csv"
    df_bias.to_csv(p_bias, index=False)
    return str(p_deb), str(p_bias)


def test_plot_zoo_bias_creates_figure(tmp_path, bias_csvs):
    p_deb, p_bias = bias_csvs
    out = str(tmp_path / "fig_zoo_bias_S2_energy.png")
    script = os.path.join(
        os.path.dirname(__file__), "..", "scripts", "plot_zoo_bias_comparison.py"
    )
    result = subprocess.run(
        [
            sys.executable,
            script,
            "--method",
            "S2_energy",
            "--input",
            p_deb,
            "--biased-csv",
            p_bias,
            "--output",
            out,
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, f"Script failed:\n{result.stderr}"
    assert os.path.exists(out), "Output PNG not created"
    assert os.path.getsize(out) > 1000, "Output PNG suspiciously small"
