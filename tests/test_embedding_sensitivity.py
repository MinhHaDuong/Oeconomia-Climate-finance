"""Tests for embedding insensitivity analysis (ticket 0036).

Tests:
1. PCA projection preserves break detection on synthetic data with known break
2. Smoke test: run PCA sweep for S2_energy (fastest method) on fixture
3. Smoke test: run JL sweep for S2_energy on fixture (limited runs)
4. Unit tests for helper functions
"""

import os
import subprocess
import sys

import numpy as np
import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
FIXTURES_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "smoke")
ROOT_DIR = os.path.join(os.path.dirname(__file__), "..")

sys.path.insert(0, SCRIPTS_DIR)


def _smoke_env():
    """Environment that redirects pipeline_loaders to fixture data."""
    return {
        **os.environ,
        "CLIMATE_FINANCE_DATA": FIXTURES_DIR,
        "PYTHONHASHSEED": "0",
        "SOURCE_DATE_EPOCH": "0",
    }


def _run_sensitivity(method, projection, output_path, timeout=300):
    """Run compute_embedding_sensitivity.py."""
    result = subprocess.run(
        [
            sys.executable,
            os.path.join(SCRIPTS_DIR, "compute_embedding_sensitivity.py"),
            "--method", method,
            "--projection", projection,
            "--output", str(output_path),
        ],
        env=_smoke_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------

class TestHelpers:
    """Test helper functions in compute_embedding_sensitivity."""

    def test_append_projection_tag_to_default(self):
        from compute_embedding_sensitivity import _append_projection_tag
        df = pd.DataFrame({"hyperparams": ["default"], "value": [1.0]})
        result = _append_projection_tag(df, "pca_64")
        assert result["hyperparams"].iloc[0] == "projection=pca_64"

    def test_append_projection_tag_to_existing(self):
        from compute_embedding_sensitivity import _append_projection_tag
        df = pd.DataFrame({"hyperparams": ["bw=1.0x_median"], "value": [1.0]})
        result = _append_projection_tag(df, "pca_128")
        assert result["hyperparams"].iloc[0] == "bw=1.0x_median;projection=pca_128"

    def test_append_projection_tag_empty_df(self):
        from compute_embedding_sensitivity import _append_projection_tag
        df = pd.DataFrame({"hyperparams": [], "value": []})
        result = _append_projection_tag(df, "original")
        assert len(result) == 0

    def test_make_sensitivity_cfg_overrides_windows(self):
        from compute_embedding_sensitivity import _make_sensitivity_cfg
        cfg = {"divergence": {"windows": [2, 3, 4, 5], "other": "keep"}}
        result = _make_sensitivity_cfg(cfg)
        assert result["divergence"]["windows"] == [3]
        # Original unchanged
        assert cfg["divergence"]["windows"] == [2, 3, 4, 5]

    def test_method_func_registry_covers_all_semantic_methods(self):
        from compute_embedding_sensitivity import METHOD_FUNCS
        expected = {"S1_MMD", "S2_energy", "S3_sliced_wasserstein", "S4_frechet"}
        assert set(METHOD_FUNCS.keys()) == expected


# ---------------------------------------------------------------------------
# PCA projection preserves break on synthetic data
# ---------------------------------------------------------------------------

class TestPCABreakPreservation:
    """Verify that PCA projection preserves a known distributional shift."""

    def test_pca_preserves_shift(self):
        """Two Gaussian clusters with a shift at t=10 should remain
        distinguishable after PCA to d=32."""
        rng = np.random.RandomState(42)
        n_per_group = 50
        d = 1024

        # Before break: centered at 0
        X_before = rng.randn(n_per_group, d) * 1.0
        # After break: shifted mean in first 10 dims
        shift = np.zeros(d)
        shift[:10] = 3.0
        X_after = rng.randn(n_per_group, d) * 1.0 + shift

        # Full-dim energy distance
        import dcor
        full_dist = dcor.energy_distance(X_before, X_after)

        # PCA to d=32
        from sklearn.decomposition import PCA
        pca = PCA(n_components=32, random_state=42)
        combined = np.vstack([X_before, X_after])
        combined_pca = pca.fit_transform(combined)
        X_before_pca = combined_pca[:n_per_group]
        X_after_pca = combined_pca[n_per_group:]

        pca_dist = dcor.energy_distance(X_before_pca, X_after_pca)

        # PCA distance should be positive (shift survives)
        assert pca_dist > 0, "PCA projection lost the distributional shift"
        # The shift should be detectable (not shrunk to noise level)
        # PCA captures variance, so the shifted dimensions should be preserved
        assert pca_dist > full_dist * 0.01, (
            f"PCA distance ({pca_dist:.4f}) too small relative to "
            f"full distance ({full_dist:.4f})"
        )


# ---------------------------------------------------------------------------
# Smoke tests: run dispatcher on fixture data
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSmokePCA:
    """PCA sweep on 100-row smoke fixture."""

    def test_pca_s2_energy(self, tmp_path):
        """S2 energy is the fastest method — use for smoke testing."""
        out = tmp_path / "tab_sens_pca_S2_energy.csv"
        result = _run_sensitivity("S2_energy", "pca", out)
        assert result.returncode == 0, (
            f"PCA sweep failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert out.exists(), "Output CSV not created"

        df = pd.read_csv(out)
        expected_cols = {"year", "channel", "window", "hyperparams", "value"}
        assert expected_cols == set(df.columns)
        assert (df["channel"] == "semantic").all()
        assert len(df) > 0

        # Should have multiple projection tags
        tags = df["hyperparams"].unique()
        has_original = any("original" in str(t) for t in tags)
        has_pca = any("pca_" in str(t) for t in tags)
        assert has_original, f"Missing original baseline. Tags: {tags}"
        assert has_pca, f"Missing PCA projections. Tags: {tags}"

    def test_pca_output_passes_schema(self, tmp_path):
        """Output should conform to DivergenceSchema."""
        out = tmp_path / "tab_sens_pca_S2_energy.csv"
        result = _run_sensitivity("S2_energy", "pca", out)
        assert result.returncode == 0, result.stderr

        from schemas import DivergenceSchema
        df = pd.read_csv(out)
        DivergenceSchema.validate(df)


@pytest.mark.integration
class TestSmokeJL:
    """JL sweep on 100-row smoke fixture.

    JL with 20 runs is slow, but the smoke fixture is small enough.
    """

    def test_jl_s2_energy(self, tmp_path):
        out = tmp_path / "tab_sens_jl_S2_energy.csv"
        result = _run_sensitivity("S2_energy", "jl", out, timeout=600)
        assert result.returncode == 0, (
            f"JL sweep failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert out.exists(), "Output CSV not created"

        df = pd.read_csv(out)
        expected_cols = {"year", "channel", "window", "hyperparams", "value"}
        assert expected_cols == set(df.columns)
        assert (df["channel"] == "semantic").all()
        assert len(df) > 0

        # Should have multiple JL runs
        tags = df["hyperparams"].unique()
        has_jl = any("jl_" in str(t) for t in tags)
        assert has_jl, f"Missing JL projections. Tags: {tags}"

    def test_jl_output_passes_schema(self, tmp_path):
        out = tmp_path / "tab_sens_jl_S2_energy.csv"
        result = _run_sensitivity("S2_energy", "jl", out, timeout=600)
        assert result.returncode == 0, result.stderr

        from schemas import DivergenceSchema
        df = pd.read_csv(out)
        DivergenceSchema.validate(df)


# ---------------------------------------------------------------------------
# Plot script smoke test
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestPlotSmoke:
    """Verify plot script runs without error on PCA sensitivity output."""

    def test_plot_pca(self, tmp_path):
        # First generate data
        csv_out = tmp_path / "tab_sens_pca_S2_energy.csv"
        result = _run_sensitivity("S2_energy", "pca", csv_out)
        assert result.returncode == 0, result.stderr

        # Then plot
        fig_out = tmp_path / "fig_sensitivity.png"
        plot_result = subprocess.run(
            [
                sys.executable,
                os.path.join(SCRIPTS_DIR, "plot_divergence.py"),
                "--palette", "gradient",
                "--output", str(fig_out),
                "--input", str(csv_out),
            ],
            env=_smoke_env(),
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert plot_result.returncode == 0, (
            f"Plot failed:\nstdout: {plot_result.stdout}\n"
            f"stderr: {plot_result.stderr}"
        )
        # Check that the PNG was created (stem + method)
        expected_png = tmp_path / "fig_sensitivity_S2_energy.png"
        assert expected_png.exists(), (
            f"Expected {expected_png} but found: "
            f"{[f.name for f in tmp_path.iterdir()]}"
        )
