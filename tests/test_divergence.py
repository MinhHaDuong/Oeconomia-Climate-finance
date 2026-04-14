"""Tests for the refactored divergence pipeline.

Tests:
1. DivergenceSchema validation
2. Smoke test: run compute_divergence.py --method for each method type
3. Module function availability checks
"""

import os
import subprocess
import sys

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


def _run_compute(method, output_path, timeout=300):
    """Run compute_divergence.py --method M --output P."""
    result = subprocess.run(
        [
            sys.executable,
            os.path.join(SCRIPTS_DIR, "compute_divergence.py"),
            "--method", method,
            "--output", str(output_path),
        ],
        env=_smoke_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )
    return result


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------

class TestDivergenceSchema:
    """DivergenceSchema validation."""

    def test_valid_dataframe_passes(self):
        from schemas import DivergenceSchema
        df = pd.DataFrame({
            "year": [2010, 2011],
            "channel": ["semantic", "semantic"],
            "window": ["3", "3"],
            "hyperparams": ["default", "default"],
            "value": [0.5, 0.6],
        })
        DivergenceSchema.validate(df)

    def test_extra_column_rejected(self):
        from schemas import DivergenceSchema
        df = pd.DataFrame({
            "year": [2010],
            "channel": ["semantic"],
            "window": ["3"],
            "hyperparams": ["default"],
            "value": [0.5],
            "extra": ["oops"],
        })
        with pytest.raises(Exception):
            DivergenceSchema.validate(df)

    def test_bad_channel_rejected(self):
        from schemas import DivergenceSchema
        df = pd.DataFrame({
            "year": [2010],
            "channel": ["unknown"],
            "window": ["3"],
            "hyperparams": ["default"],
            "value": [0.5],
        })
        with pytest.raises(Exception):
            DivergenceSchema.validate(df)

    def test_nullable_value_accepted(self):
        import numpy as np
        from schemas import DivergenceSchema
        df = pd.DataFrame({
            "year": [2010],
            "channel": ["citation"],
            "window": ["cumulative"],
            "hyperparams": [""],
            "value": [np.nan],
        })
        DivergenceSchema.validate(df)

    def test_coercion_works(self):
        """String year and float value should be coerced."""
        from schemas import DivergenceSchema
        df = pd.DataFrame({
            "year": ["2010"],
            "channel": ["lexical"],
            "window": ["3"],
            "hyperparams": ["w=3"],
            "value": ["0.5"],
        })
        validated = DivergenceSchema.validate(df)
        assert validated["year"].dtype in (int, "int64")


# ---------------------------------------------------------------------------
# Module function availability
# ---------------------------------------------------------------------------

class TestModuleFunctions:
    """Verify each private module exposes the expected functions."""

    def test_semantic_module_has_all_functions(self):
        import _divergence_semantic as mod
        for fn in ["compute_s1_mmd", "compute_s2_energy",
                    "compute_s3_wasserstein", "compute_s4_frechet",
                    "load_semantic_data"]:
            assert hasattr(mod, fn), f"Missing: {fn}"
            assert callable(getattr(mod, fn)), f"Not callable: {fn}"

    def test_lexical_module_has_all_functions(self):
        import _divergence_lexical as mod
        for fn in ["compute_l1_js", "compute_l2_novelty",
                    "compute_l3_bursts", "load_lexical_data"]:
            assert hasattr(mod, fn), f"Missing: {fn}"
            assert callable(getattr(mod, fn)), f"Not callable: {fn}"

    def test_citation_module_has_all_functions(self):
        import _divergence_citation as mod
        for fn in ["compute_g1_pagerank", "compute_g2_spectral",
                    "compute_g3_age_shift", "compute_g4_cross_trad",
                    "compute_g5_pa_exponent", "compute_g6_entropy",
                    "compute_g7_disruption", "compute_g8_betweenness",
                    "load_citation_data"]:
            assert hasattr(mod, fn), f"Missing: {fn}"
            assert callable(getattr(mod, fn)), f"Not callable: {fn}"

    def test_dispatcher_registry_complete(self):
        from compute_divergence import METHODS
        assert len(METHODS) == 15
        # Verify all three channels present
        channels = {v[2] for v in METHODS.values()}
        assert channels == {"semantic", "lexical", "citation"}


# ---------------------------------------------------------------------------
# Smoke tests: run dispatcher on fixture data
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSmokeSemantic:
    """Semantic methods on 100-row fixture."""

    @pytest.mark.parametrize("method", [
        "S1_MMD", "S2_energy", "S3_sliced_wasserstein", "S4_frechet",
    ])
    def test_compute_method(self, method, tmp_path):
        out = tmp_path / f"tab_div_{method}.csv"
        result = _run_compute(method, out)
        assert result.returncode == 0, (
            f"{method} failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert out.exists(), f"Output CSV not created for {method}"
        df = pd.read_csv(out)
        assert {"year", "channel", "window", "hyperparams", "value"} == set(df.columns)
        assert (df["channel"] == "semantic").all()
        assert len(df) > 0


@pytest.mark.integration
class TestSmokeLexical:
    """Lexical methods on 100-row fixture."""

    @pytest.mark.parametrize("method", ["L1", "L2", "L3"])
    def test_compute_method(self, method, tmp_path):
        out = tmp_path / f"tab_div_{method}.csv"
        result = _run_compute(method, out)
        assert result.returncode == 0, (
            f"{method} failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert out.exists(), f"Output CSV not created for {method}"
        df = pd.read_csv(out)
        assert {"year", "channel", "window", "hyperparams", "value"} == set(df.columns)
        assert (df["channel"] == "lexical").all()
        assert len(df) > 0


@pytest.mark.integration
class TestSmokeCitation:
    """Citation methods on 100-row fixture."""

    @pytest.mark.parametrize("method", [
        "G1_pagerank", "G2_spectral", "G3_coupling_age", "G4_cross_tradition",
        "G5_pref_attachment", "G6_entropy", "G7_disruption", "G8_betweenness",
    ])
    def test_compute_method(self, method, tmp_path):
        out = tmp_path / f"tab_div_{method}.csv"
        result = _run_compute(method, out)
        assert result.returncode == 0, (
            f"{method} failed:\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
        assert out.exists(), f"Output CSV not created for {method}"
        df = pd.read_csv(out)
        assert {"year", "channel", "window", "hyperparams", "value"} == set(df.columns)
        assert (df["channel"] == "citation").all()
        assert len(df) > 0

    def test_g3_has_valid_values(self, tmp_path):
        """G3 (age shift) uses ref_year, should produce values even without internal edges."""
        out = tmp_path / "tab_div_G3_coupling_age.csv"
        _run_compute("G3_coupling_age", out)
        df = pd.read_csv(out)
        valid = df["value"].dropna()
        assert len(valid) >= 5, f"G3 should have >= 5 valid values, got {len(valid)}"


# ---------------------------------------------------------------------------
# Schema validation on smoke output
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestSchemaValidationOnOutput:
    """Verify that actual smoke outputs pass DivergenceSchema."""

    def test_s2_output_passes_schema(self, tmp_path):
        out = tmp_path / "tab_div_S2_energy.csv"
        result = _run_compute("S2_energy", out)
        assert result.returncode == 0, result.stderr

        from schemas import DivergenceSchema
        df = pd.read_csv(out)
        DivergenceSchema.validate(df)

    def test_l1_output_passes_schema(self, tmp_path):
        out = tmp_path / "tab_div_L1.csv"
        result = _run_compute("L1", out)
        assert result.returncode == 0, result.stderr

        from schemas import DivergenceSchema
        df = pd.read_csv(out)
        DivergenceSchema.validate(df)

    def test_g3_output_passes_schema(self, tmp_path):
        out = tmp_path / "tab_div_G3_coupling_age.csv"
        result = _run_compute("G3_coupling_age", out)
        assert result.returncode == 0, result.stderr

        from schemas import DivergenceSchema
        df = pd.read_csv(out)
        DivergenceSchema.validate(df)
