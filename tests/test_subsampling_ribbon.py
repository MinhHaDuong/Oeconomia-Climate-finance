"""Tests for the subsampling-variance ribbon (ticket 0084).

Three red tests that define the expected behaviour before implementation:
1. Smoke: compute_divergence_subsampled.py produces R rows per (year, window).
2. Bracket: z_trim_lo ≤ z_median ≤ z_trim_hi in the export summary.
3. RNG independence: subsampling stream and permutation stream are uncorrelated.
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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _smoke_env():
    return {
        **os.environ,
        "CLIMATE_FINANCE_DATA": FIXTURES_DIR,
        "PYTHONHASHSEED": "0",
        "SOURCE_DATE_EPOCH": "0",
    }


def _run_subsampled(method, div_csv, output_path, r=None, timeout=300):
    cmd = [
        sys.executable,
        os.path.join(SCRIPTS_DIR, "compute_divergence_subsampled.py"),
        "--method",
        method,
        "--div-csv",
        str(div_csv),
        "--output",
        str(output_path),
    ]
    if r is not None:
        cmd += ["--r", str(r)]
    return subprocess.run(
        cmd,
        env=_smoke_env(),
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def _make_synthetic_subsample_df(R=5, z_lo=-1.0, z_hi=1.0):
    """Build a synthetic subsample CSV as export_divergence_summary would read."""
    rows = []
    rng = np.random.RandomState(7)
    for year in [2010, 2011]:
        base = rng.uniform(0.3, 0.7)
        for rep in range(R):
            rows.append(
                {
                    "method": "S2_energy",
                    "year": year,
                    "window": "3",
                    "hyperparams": "",
                    "replicate": rep,
                    "value": base + rng.uniform(-0.1, 0.1),
                }
            )
    return pd.DataFrame(rows)


def _make_synthetic_null_df():
    return pd.DataFrame(
        {
            "year": [2010, 2011],
            "window": ["3", "3"],
            "observed": [0.55, 0.65],
            "null_mean": [0.30, 0.35],
            "null_std": [0.10, 0.12],
            "z_score": [2.5, 2.5],
            "p_value": [0.01, 0.01],
        }
    )


def _make_synthetic_div_df():
    return pd.DataFrame(
        {
            "year": [2010, 2011],
            "channel": ["semantic", "semantic"],
            "window": ["3", "3"],
            "hyperparams": ["", ""],
            "value": [0.55, 0.65],
        }
    )


def _make_synthetic_boot_df(k=5):
    rows = []
    rng = np.random.RandomState(42)
    for year in [2010, 2011]:
        for rep in range(k):
            rows.append(
                {
                    "method": "S2_energy",
                    "year": year,
                    "window": "3",
                    "hyperparams": "",
                    "replicate": rep,
                    "value": rng.uniform(0.4, 0.8),
                }
            )
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Test 1 — Schema: DivergenceSubsampleSchema exists
# ---------------------------------------------------------------------------


class TestDivergenceSubsampleSchema:
    """DivergenceSubsampleSchema is defined and validates correctly."""

    def test_schema_importable(self):
        from schemas import DivergenceSubsampleSchema  # noqa: F401

    def test_valid_dataframe_passes(self):
        from schemas import DivergenceSubsampleSchema

        df = pd.DataFrame(
            {
                "method": ["S2_energy", "S2_energy"],
                "year": [2010, 2010],
                "window": ["3", "3"],
                "hyperparams": ["", ""],
                "replicate": [0, 1],
                "value": [0.5, 0.6],
            }
        )
        DivergenceSubsampleSchema.validate(df)

    def test_extra_column_rejected(self):
        from schemas import DivergenceSubsampleSchema

        df = pd.DataFrame(
            {
                "method": ["S2_energy"],
                "year": [2010],
                "window": ["3"],
                "hyperparams": [""],
                "replicate": [0],
                "value": [0.5],
                "extra": ["oops"],
            }
        )
        with pytest.raises(Exception):
            DivergenceSubsampleSchema.validate(df)


# ---------------------------------------------------------------------------
# Test 2 — Smoke: R rows per cell when run with smoke fixture
# ---------------------------------------------------------------------------


class TestSubsampleReplicatesPresent:
    """compute_divergence_subsampled.py produces R rows per (year, window)."""

    def test_subsample_replicates_present_s2(self, tmp_path):
        """Smoke: R=3 replicates per cell for S2_energy on the smoke fixture."""
        # First produce the point-estimate CSV the script needs as input
        div_csv = tmp_path / "tab_div_S2_energy.csv"
        ret = subprocess.run(
            [
                sys.executable,
                os.path.join(SCRIPTS_DIR, "compute_divergence.py"),
                "--method",
                "S2_energy",
                "--output",
                str(div_csv),
            ],
            env=_smoke_env(),
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert ret.returncode == 0, f"compute_divergence failed:\n{ret.stderr}"

        div_df = pd.read_csv(div_csv)
        if div_df.empty:
            pytest.skip("Smoke fixture has no valid S2_energy cells")

        out_csv = tmp_path / "tab_subsample_S2_energy.csv"
        R = 3
        ret = _run_subsampled("S2_energy", div_csv, out_csv, r=R)
        assert ret.returncode == 0, (
            f"compute_divergence_subsampled.py failed:\n{ret.stderr}"
        )

        result = pd.read_csv(out_csv)
        counts = result.groupby(["year", "window"])["replicate"].count()
        wrong = counts[counts != R]
        assert wrong.empty, f"Expected {R} replicates per cell, got:\n{wrong}"

    def test_subsample_replicates_vary(self, tmp_path):
        """Subsampling draws must not all be identical (sampling-semantics test)."""
        div_csv = tmp_path / "tab_div_S2_energy.csv"
        ret = subprocess.run(
            [
                sys.executable,
                os.path.join(SCRIPTS_DIR, "compute_divergence.py"),
                "--method",
                "S2_energy",
                "--output",
                str(div_csv),
            ],
            env=_smoke_env(),
            capture_output=True,
            text=True,
            timeout=300,
        )
        assert ret.returncode == 0, ret.stderr

        div_df = pd.read_csv(div_csv)
        if div_df.empty:
            pytest.skip("No cells in smoke fixture")

        out_csv = tmp_path / "tab_subsample_S2_energy.csv"
        ret = _run_subsampled("S2_energy", div_csv, out_csv, r=5)
        assert ret.returncode == 0, ret.stderr

        result = pd.read_csv(out_csv)
        # At least one cell must show variation (equal-n draws should differ when
        # before and after window sizes differ; equal-size windows are a legitimate
        # no-op and produce identical replicates — the test only checks for the
        # overall absence of degenerate constant output across ALL cells).
        any_variation = any(
            grp["value"].nunique() > 1
            for _, grp in result.groupby(["year", "window"])
            if len(grp) > 1
        )
        assert any_variation, (
            "No subsampling variation in any cell — all replicates identical. "
            "Check that _make_subsample_rng produces distinct draws per replicate."
        )


# ---------------------------------------------------------------------------
# Test 3 — Summary: z_trim_lo ≤ z_median ≤ z_trim_hi
# ---------------------------------------------------------------------------


class TestZTrimRibbonBrackets:
    """After export_divergence_summary with subsample CSV, bracket inequality holds."""

    def test_z_trim_ribbon_bracket_median(self):
        """z_trim_lo ≤ z_median_subsample ≤ z_trim_hi for all non-null rows."""
        from export_divergence_summary import build_summary

        subsample_df = _make_synthetic_subsample_df(R=10)
        null_df = _make_synthetic_null_df()
        div_df = _make_synthetic_div_df()
        boot_df = _make_synthetic_boot_df()

        result = build_summary(
            div_df,
            null_df,
            boot_df,
            method="S2_energy",
            subsample_df=subsample_df,
        )

        with_ribbon = result.dropna(
            subset=["z_trim_lo", "z_trim_hi", "z_median_subsample"]
        )
        assert len(with_ribbon) > 0, "No rows with ribbon data"

        lo_ok = (with_ribbon["z_trim_lo"] <= with_ribbon["z_median_subsample"]).all()
        hi_ok = (with_ribbon["z_median_subsample"] <= with_ribbon["z_trim_hi"]).all()
        assert lo_ok, "z_trim_lo > z_median_subsample in some rows"
        assert hi_ok, "z_median_subsample > z_trim_hi in some rows"

    def test_z_trim_null_when_no_subsample(self):
        """When subsample_df is not provided, ribbon columns are NaN."""
        from export_divergence_summary import build_summary

        result = build_summary(
            _make_synthetic_div_df(),
            _make_synthetic_null_df(),
            _make_synthetic_boot_df(),
            method="S2_energy",
        )

        assert "z_trim_lo" in result.columns, "z_trim_lo column missing"
        assert result["z_trim_lo"].isna().all(), (
            "z_trim_lo should be NaN when no subsample_df provided"
        )
        assert result["z_trim_hi"].isna().all(), (
            "z_trim_hi should be NaN when no subsample_df provided"
        )

    def test_summary_schema_has_ribbon_columns(self):
        """DivergenceSummarySchema includes the four new ribbon columns."""
        from schemas import DivergenceSummarySchema

        # Schema definition should include the new columns
        schema_cols = set(DivergenceSummarySchema.columns.keys())
        for col in ("z_trim_lo", "z_trim_hi", "z_median_subsample", "n_subsamples"):
            assert col in schema_cols, f"Schema missing column: {col}"


# ---------------------------------------------------------------------------
# Test 4 — RNG independence: subsampling and permutation streams uncorrelated
# ---------------------------------------------------------------------------


class TestSubsampleRngIndependence:
    """Subsampling RNG stream must be independent of the permutation stream."""

    def test_make_subsample_rng_importable(self):
        """_make_subsample_rng must exist in _divergence_io."""
        from _divergence_io import _make_subsample_rng  # noqa: F401

    def test_subsample_rng_differs_by_replicate(self):
        """Different replicate indices produce different RNG streams."""
        from _divergence_io import _make_subsample_rng

        seed, y, w = 42, 2010, 3
        draws = []
        for r in range(5):
            rng = _make_subsample_rng(seed, y, w, r)
            draws.append(rng.randn(10).tolist())

        for i in range(len(draws)):
            for j in range(i + 1, len(draws)):
                assert draws[i] != draws[j], (
                    f"Replicate {i} and {j} produced identical RNG output"
                )

    def test_subsample_and_permutation_rng_uncorrelated(self):
        """Subsampling draws must be uncorrelated with permutation draws.

        Uses a synthetic 100×5 Gaussian fixture. Computes R=20 mean-shift
        statistics via independent subsampling RNGs and B=20 mean-shift
        statistics via permutation RNGs. |pearson correlation| < 0.5.
        """
        from _divergence_io import _make_subsample_rng, _make_window_rngs

        rng_data = np.random.RandomState(0)
        X = rng_data.randn(100, 5)
        Y = rng_data.randn(100, 5) + 0.3

        seed, y, w = 42, 2010, 3
        R = 20
        B = 20

        # Subsample stream: R draws
        n = min(len(X), len(Y))
        subsample_stats = []
        for r in range(R):
            rng_s = _make_subsample_rng(seed, y, w, r)
            idx = rng_s.choice(len(Y), n, replace=False)
            Y_sub = Y[idx]
            subsample_stats.append(float(np.linalg.norm(X.mean(0) - Y_sub.mean(0))))

        # Permutation stream: B draws (via extra_rng from _make_window_rngs)
        _, perm_rng = _make_window_rngs(seed, y, w)
        pooled = np.vstack([X, Y])
        perm_stats = []
        for _ in range(B):
            idx = perm_rng.permutation(len(pooled))
            X_p = pooled[idx[:n]]
            Y_p = pooled[idx[n : n + n]]
            perm_stats.append(float(np.linalg.norm(X_p.mean(0) - Y_p.mean(0))))

        min_len = min(len(subsample_stats), len(perm_stats))
        corr = float(np.corrcoef(subsample_stats[:min_len], perm_stats[:min_len])[0, 1])
        assert abs(corr) < 0.5, (
            f"Subsampling and permutation RNG streams are correlated: r={corr:.3f}"
        )

    def test_subsample_rng_no_overlap_with_null_model_seeds(self):
        """Subsampling seeds don't collide with null-model seed range.

        The null model uses seed + y*100 + w (subsample) and +50000 (perm).
        Our subsampling replicates use +100000 offset — verify the seed
        function produces values well above the null model range for all
        supported (y, w, r) combos.
        """
        from _divergence_io import _make_subsample_rng, _make_window_rngs

        seed = 42
        null_seeds = set()
        subsample_seeds = set()

        for y in range(1990, 2026):
            for w in [2, 3, 4]:
                s_rng, e_rng = _make_window_rngs(seed, y, w)
                # Extract the internal seed — RNG state bytes proxy
                null_seeds.add((s_rng.get_state()[1][0]))
                null_seeds.add((e_rng.get_state()[1][0]))
                for r in range(20):
                    sub_rng = _make_subsample_rng(seed, y, w, r)
                    subsample_seeds.add(sub_rng.get_state()[1][0])

        overlap = null_seeds & subsample_seeds
        assert len(overlap) == 0, (
            f"Seed collision between null model and subsampling: {overlap}"
        )
