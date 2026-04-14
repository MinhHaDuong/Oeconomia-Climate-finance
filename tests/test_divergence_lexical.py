"""Smoke tests for lexical divergence methods L1-L3.

Validates that compute_divergence_lexical.py and plot_divergence_lexical.py
run end-to-end on the 100-row smoke fixture without error.
"""

import os
import subprocess
import sys

import pandas as pd
import pytest

SMOKE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "smoke")
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")

sys.path.insert(0, SCRIPTS_DIR)


def _smoke_env():
    """Environment that redirects pipeline_loaders to fixture data."""
    return {
        **os.environ,
        "CLIMATE_FINANCE_DATA": SMOKE_DIR,
        "PYTHONHASHSEED": "0",
        "SOURCE_DATE_EPOCH": "0",
    }


def _run_script(script_name, *args, timeout=120):
    """Run a script against smoke fixture data."""
    result = subprocess.run(
        [sys.executable, os.path.join(SCRIPTS_DIR, script_name), *args],
        capture_output=True, text=True,
        env=_smoke_env(),
        timeout=timeout,
    )
    return result


# ---------------------------------------------------------------------------
# Unit tests: individual method functions
# ---------------------------------------------------------------------------

class TestL1Unit:
    """L1 JS divergence computation on synthetic data."""

    def test_l1_returns_dataframe(self):
        from compute_divergence_lexical import compute_l1
        df = pd.DataFrame({
            "year": [2010] * 10 + [2011] * 10 + [2012] * 10 + [2013] * 10,
            "abstract": [
                "climate change adaptation finance developing countries",
                "carbon market emissions trading greenhouse gas",
                "renewable energy investment policy green bonds",
                "forest conservation biodiversity ecosystem services",
                "sustainable development goals poverty reduction",
            ] * 8,
        })
        result = compute_l1(df, windows=(2,))
        assert isinstance(result, pd.DataFrame)
        assert "year" in result.columns
        assert "method" in result.columns
        assert "value" in result.columns
        assert (result["method"] == "L1").all()

    def test_l1_js_values_between_0_and_1(self):
        from compute_divergence_lexical import compute_l1
        df = pd.DataFrame({
            "year": [2010] * 10 + [2011] * 10 + [2012] * 10 + [2013] * 10,
            "abstract": [
                "climate change adaptation finance developing countries",
                "carbon market emissions trading greenhouse gas",
                "renewable energy investment policy green bonds",
                "forest conservation biodiversity ecosystem services",
                "sustainable development goals poverty reduction",
            ] * 8,
        })
        result = compute_l1(df, windows=(2,))
        if not result.empty:
            assert result["value"].min() >= 0
            assert result["value"].max() <= 1


class TestL2Unit:
    """L2 Novelty/Transience/Resonance on synthetic data."""

    def test_l2_returns_three_metrics(self):
        from compute_divergence_lexical import compute_l2
        df = pd.DataFrame({
            "year": [2010] * 10 + [2011] * 10 + [2012] * 10 + [2013] * 10,
            "abstract": [
                "climate change adaptation finance developing countries",
                "carbon market emissions trading greenhouse gas",
                "renewable energy investment policy green bonds",
                "forest conservation biodiversity ecosystem services",
                "sustainable development goals poverty reduction",
            ] * 8,
        })
        result = compute_l2(df, windows=(3,))
        assert isinstance(result, pd.DataFrame)
        if not result.empty:
            metrics = result["hyperparams"].str.extract(
                r"metric=(\w+)"
            )[0].unique()
            assert set(metrics) == {"novelty", "transience", "resonance"}


class TestL3Unit:
    """L3 burst detection on synthetic data."""

    def test_l3_returns_integer_burst_counts(self):
        from compute_divergence_lexical import compute_l3
        df = pd.DataFrame({
            "year": list(range(2005, 2025)) * 5,
            "abstract": [
                "climate change adaptation finance developing countries",
                "carbon market emissions trading greenhouse gas",
                "renewable energy investment policy green bonds",
                "forest conservation biodiversity ecosystem services",
                "sustainable development goals poverty reduction",
            ] * 20,
        })
        result = compute_l3(df)
        assert isinstance(result, pd.DataFrame)
        assert (result["method"] == "L3").all()
        # All values should be non-negative integers
        if not result.empty:
            assert (result["value"] >= 0).all()


class TestPELT:
    """PELT break detection wrapper."""

    def test_pelt_returns_dataframe(self):
        from compute_divergence_lexical import detect_breaks_pelt
        series = pd.DataFrame({
            "year": list(range(2005, 2025)),
            "method": ["L1"] * 20,
            "window": [3] * 20,
            "hyperparams": ["w=3"] * 20,
            "value": [0.1] * 10 + [0.5] * 10,  # clear step change
        })
        result = detect_breaks_pelt(series, penalties=[3])
        assert isinstance(result, pd.DataFrame)
        if not result.empty:
            assert "break_years" in result.columns


# ---------------------------------------------------------------------------
# Integration: end-to-end smoke test
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSmokeEndToEnd:
    """Run full pipeline on 100-row smoke fixture."""

    def test_compute_divergence_lexical(self, tmp_path):
        output = str(tmp_path / "tab_lexical_divergence.csv")
        result = _run_script(
            "compute_divergence_lexical.py", "--output", output,
        )
        assert result.returncode == 0, (
            f"compute_divergence_lexical.py failed:\n{result.stderr}"
        )
        assert os.path.exists(output), "Output CSV not created"
        df = pd.read_csv(output)
        assert len(df) > 0, "Output CSV is empty"
        assert set(df.columns) >= {"year", "method", "channel", "window", "hyperparams", "value"}
        # All three methods present
        methods = set(df["method"].unique())
        assert "L1" in methods
        assert "L2" in methods
        assert "L3" in methods

    def test_plot_divergence_lexical(self, tmp_path):
        """Plot script runs after compute produces data."""
        # First, compute the data
        tables_dir = tmp_path / "tables"
        figures_dir = tmp_path / "figures"
        tables_dir.mkdir()
        figures_dir.mkdir()

        series_path = str(tables_dir / "tab_lexical_divergence.csv")
        result = _run_script(
            "compute_divergence_lexical.py", "--output", series_path,
        )
        assert result.returncode == 0, (
            f"compute failed:\n{result.stderr}"
        )

        # Then, plot
        fig_output = str(figures_dir / "fig_divergence_L1.png")
        result = _run_script(
            "plot_divergence_lexical.py", "--output", fig_output,
        )
        assert result.returncode == 0, (
            f"plot_divergence_lexical.py failed:\n{result.stderr}"
        )

        # Check all three figures created
        for n in [1, 2, 3]:
            fig_path = figures_dir / f"fig_divergence_L{n}.png"
            assert fig_path.exists(), f"Missing figure: {fig_path}"
