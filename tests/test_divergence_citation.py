"""Smoke tests for citation graph divergence scripts.

Validates that compute_divergence_citation.py and plot_divergence_citation.py
run end-to-end on the 100-row smoke fixture.

The smoke fixture has zero internal citation edges (all ref_dois point outside
the corpus), so graph-based methods (G1, G2, G4, G5, G6, G8) produce NaN.
G3 (age shift) and G7 (disruption proxy) produce valid values.
"""

import os
import subprocess
import sys
import tempfile

import numpy as np
import pandas as pd
import pytest

SMOKE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "smoke")
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
ROOT_DIR = os.path.join(os.path.dirname(__file__), "..")


def _run(cmd, env=None):
    """Run a command and return CompletedProcess, raising on failure."""
    full_env = os.environ.copy()
    full_env["CLIMATE_FINANCE_DATA"] = SMOKE_DIR
    if env:
        full_env.update(env)
    return subprocess.run(
        cmd, capture_output=True, text=True, cwd=ROOT_DIR, env=full_env,
        timeout=120,
    )


class TestComputeDivergenceCitation:
    """compute_divergence_citation.py on smoke fixture."""

    @pytest.fixture(autouse=True)
    def _tmpdir(self, tmp_path):
        self.tmp = tmp_path

    def test_runs_without_error(self):
        out = self.tmp / "tab_citation_divergence.csv"
        result = _run([
            sys.executable, os.path.join(SCRIPTS_DIR, "compute_divergence_citation.py"),
            "--output", str(out),
        ])
        assert result.returncode == 0, result.stderr

    def test_output_has_expected_columns(self):
        out = self.tmp / "tab_citation_divergence.csv"
        _run([
            sys.executable, os.path.join(SCRIPTS_DIR, "compute_divergence_citation.py"),
            "--output", str(out),
        ])
        df = pd.read_csv(out)
        assert set(df.columns) == {"year", "method", "window", "hyperparams", "value"}

    def test_all_eight_methods_present(self):
        out = self.tmp / "tab_citation_divergence.csv"
        _run([
            sys.executable, os.path.join(SCRIPTS_DIR, "compute_divergence_citation.py"),
            "--output", str(out),
        ])
        df = pd.read_csv(out)
        methods = sorted(df["method"].unique())
        assert len(methods) == 8
        for i, prefix in enumerate(["G1", "G2", "G3", "G4", "G5", "G6", "G7", "G8"], 1):
            assert any(m.startswith(prefix) for m in methods), f"Missing {prefix}"

    def test_g3_has_valid_values(self):
        """G3 (age shift) uses ref_year, should produce values even without internal edges."""
        out = self.tmp / "tab_citation_divergence.csv"
        _run([
            sys.executable, os.path.join(SCRIPTS_DIR, "compute_divergence_citation.py"),
            "--output", str(out),
        ])
        df = pd.read_csv(out)
        g3 = df[df["method"] == "G3_age_shift"]
        valid = g3["value"].dropna()
        assert len(valid) >= 5, f"G3 should have >= 5 valid values, got {len(valid)}"

    def test_breaks_file_created(self):
        out = self.tmp / "tab_citation_divergence.csv"
        _run([
            sys.executable, os.path.join(SCRIPTS_DIR, "compute_divergence_citation.py"),
            "--output", str(out),
        ])
        breaks_path = self.tmp / "tab_citation_divergence_breaks.csv"
        assert breaks_path.exists(), "Breaks CSV not created"
        df_br = pd.read_csv(breaks_path)
        assert "method" in df_br.columns
        assert "penalty" in df_br.columns
        assert "breakpoints" in df_br.columns
        # 8 methods x 3 penalties = 24 rows
        assert len(df_br) == 24


class TestPlotDivergenceCitation:
    """plot_divergence_citation.py on smoke fixture."""

    @pytest.fixture(autouse=True)
    def _setup(self, tmp_path):
        self.tmp = tmp_path
        # First compute the data
        self.series_path = self.tmp / "tab_citation_divergence.csv"
        self.breaks_path = self.tmp / "tab_citation_divergence_breaks.csv"
        _run([
            sys.executable, os.path.join(SCRIPTS_DIR, "compute_divergence_citation.py"),
            "--output", str(self.series_path),
        ])

    def test_generates_eight_figures(self):
        fig_dir = self.tmp / "figures"
        fig_dir.mkdir()
        out = fig_dir / "fig_divergence_G1.png"
        result = _run([
            sys.executable, os.path.join(SCRIPTS_DIR, "plot_divergence_citation.py"),
            "--output", str(out),
            "--input", str(self.series_path), str(self.breaks_path),
        ])
        assert result.returncode == 0, result.stderr
        for i in range(1, 9):
            fig_path = fig_dir / f"fig_divergence_G{i}.png"
            assert fig_path.exists(), f"Missing figure: fig_divergence_G{i}.png"
            assert fig_path.stat().st_size > 1000, f"Figure G{i} too small"

    def test_figures_with_data_are_larger(self):
        """G3 and G7 have data; their figures should be larger than placeholders."""
        fig_dir = self.tmp / "figures"
        fig_dir.mkdir()
        out = fig_dir / "fig_divergence_G1.png"
        _run([
            sys.executable, os.path.join(SCRIPTS_DIR, "plot_divergence_citation.py"),
            "--output", str(out),
            "--input", str(self.series_path), str(self.breaks_path),
        ])
        # G3 and G7 have actual data curves
        g3_size = (fig_dir / "fig_divergence_G3.png").stat().st_size
        g1_size = (fig_dir / "fig_divergence_G1.png").stat().st_size
        assert g3_size > g1_size, "G3 (with data) should be larger than G1 (placeholder)"
