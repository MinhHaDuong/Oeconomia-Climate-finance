"""TDD tests for ticket 0083 sensitivity grid."""

import os
import sys

import numpy as np
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


def _make_synthetic_cfg():
    """Minimal cfg dict for compute_grid — no file I/O, no real corpus."""
    return {
        "sensitivity": {
            "windows": [3, 5],
            "gaps": [0, 1],
            "dims": [8, 16],
            "equal_n_r": 1,
        },
        "divergence": {
            "windows": [3],  # overwritten per cell; present for _get_years_and_params
            "max_subsample": 500,
            "equal_n": True,
            "random_seed": 42,
            "gap": 1,
            "min_papers": 30,
            "min_papers_smoke": 5,
            "backend": "cpu",
        },
    }


def _make_synthetic_corpus(n_years=12, n_per_year=10, emb_dim=32):
    """Synthetic corpus with n_years*n_per_year < 200 docs (triggers smoke mode)."""
    rng = np.random.RandomState(0)
    years = list(range(1990, 1990 + n_years))
    doc_years = [y for y in years for _ in range(n_per_year)]
    df = pd.DataFrame({"year": doc_years})
    emb = rng.randn(len(doc_years), emb_dim).astype(np.float32)
    return df, emb


def test_compute_grid_unit(monkeypatch):
    """Unit: compute_grid produces valid output on a tiny synthetic corpus.

    compute_s2_energy is mocked so no GPU/dcor dependency is required.
    The test exercises the grid-loop, PCA reduction, z-scoring, and
    column assembly — the logic owned by compute_grid itself.
    """
    sys.path.insert(0, SCRIPTS_DIR)
    import compute_sensitivity_grid as csg

    # Build a fake compute_s2_energy that returns one row per valid year
    # for whatever window is in cfg["divergence"]["windows"].
    def _fake_s2(df, emb_proj, cfg):
        from _divergence_io import per_window_year_ranges

        windows = cfg["divergence"]["windows"]
        years_by_window = per_window_year_ranges(df, windows)
        rows = []
        for w, years in years_by_window.items():
            for y in years:
                rows.append(
                    {
                        "year": y,
                        "window": str(w),
                        "hyperparams": "default",
                        "value": float(y) * 0.01,
                    }
                )
        return (
            pd.DataFrame(rows)
            if rows
            else pd.DataFrame(columns=["year", "window", "hyperparams", "value"])
        )

    monkeypatch.setattr(csg, "compute_s2_energy", _fake_s2)

    df, emb = _make_synthetic_corpus()
    cfg = _make_synthetic_cfg()

    result = csg.compute_grid(df, emb, cfg)

    assert not result.empty, "compute_grid returned empty DataFrame"
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
    assert required <= set(result.columns), (
        f"Missing columns: {required - set(result.columns)}"
    )
    # Both configured dims must appear
    assert set(result["dim"].unique()) == {8, 16}, (
        f"Expected dims {{8, 16}}, got {set(result['dim'].unique())}"
    )
    # Both configured windows must appear
    assert set(result["window"].unique()) == {"3", "5"}, (
        f"Unexpected windows: {set(result['window'].unique())}"
    )
    # z_score column must be present (may be NaN for single-year groups)
    assert "z_score" in result.columns, "z_score column missing"
