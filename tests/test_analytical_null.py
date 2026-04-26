"""Tests for compute_analytical_null.py — C2ST analytical null (ticket 0115).

Red test: c2st_analytical_null formula (Hanley-McNeil).
"""

import os
import sys

import pandas as pd

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


def test_c2st_analytical_null_formula():
    """C2ST analytical null: Hanley-McNeil formula."""
    from compute_analytical_null import c2st_analytical_null

    n_b, n_a = 200, 200
    mean, std = c2st_analytical_null(n_b, n_a)
    assert abs(mean - 0.5) < 1e-9
    expected_std = ((n_b + n_a + 1) / (12 * n_b * n_a)) ** 0.5
    assert abs(std - expected_std) < 1e-12


def test_c2st_analytical_null_asymmetric():
    """Hanley-McNeil formula works for unequal group sizes."""
    from compute_analytical_null import c2st_analytical_null

    n_b, n_a = 100, 300
    mean, std = c2st_analytical_null(n_b, n_a)
    assert abs(mean - 0.5) < 1e-9
    expected_std = ((n_b + n_a + 1) / (12 * n_b * n_a)) ** 0.5
    assert abs(std - expected_std) < 1e-12


def test_c2st_analytical_null_std_decreases_with_n():
    """Larger samples give tighter null distribution."""
    from compute_analytical_null import c2st_analytical_null

    _, std_small = c2st_analytical_null(50, 50)
    _, std_large = c2st_analytical_null(500, 500)
    assert std_small > std_large


def test_analytical_null_flag_no_crash(tmp_path):
    """--analytical-null flag in plot_zoo_results must not crash with valid CSV."""
    import plot_zoo_results

    # Build a minimal analytical null CSV
    an_df = pd.DataFrame(
        {
            "year": [2000, 2001, 2002, 2003],
            "window": ["3", "3", "3", "3"],
            "observed": [0.0, 0.0, 0.0, 0.0],
            "null_mean": [0.5, 0.5, 0.5, 0.5],
            "null_std": [0.025, 0.025, 0.025, 0.025],
            "z_score": [float("nan")] * 4,
            "p_value": [float("nan")] * 4,
        }
    )
    an_path = tmp_path / "tab_analytical_null_C2ST_embedding.csv"
    an_df.to_csv(an_path, index=False)

    # Build a minimal crossyear CSV
    df = pd.DataFrame(
        {
            "year": [2000, 2001, 2002, 2003],
            "window": ["3", "3", "3", "3"],
            "value": [0.52, 0.55, 0.61, 0.58],
            "z_score": [0.3, 0.8, 1.5, 1.1],
        }
    )
    output_png = tmp_path / "fig_zoo_C2ST_embedding.png"
    output_stem = str(output_png.with_suffix(""))

    import matplotlib

    matplotlib.use("Agg")

    # Must not raise
    an_loaded = plot_zoo_results._load_analytical_null(str(an_path))
    assert an_loaded is not None
    plot_zoo_results._plot(
        df, "C2ST_embedding", output_stem, analytical_null_df=an_loaded
    )


def test_load_analytical_null_returns_none_for_missing_file():
    """_load_analytical_null with a non-existent path returns None (graceful)."""
    import plot_zoo_results

    assert (
        plot_zoo_results._load_analytical_null("/nonexistent/path/tab_an.csv") is None
    )


def test_load_analytical_null_returns_none_when_path_is_none():
    """_load_analytical_null(None) must return None without raising."""
    import plot_zoo_results

    assert plot_zoo_results._load_analytical_null(None) is None


def test_c2st_analytical_agrees_with_mc():
    """Analytical null_std matches permutation-based MC std within 3 SE.

    Fixture: n_b=n_a=150, n_perm=300.  Random uniform scores under H0.
    Validates the Hanley-McNeil formula against an empirical permutation
    distribution (the core of the overlay's visual agreement claim).
    """
    import numpy as np
    from compute_analytical_null import c2st_analytical_null
    from sklearn.metrics import roc_auc_score

    rng = np.random.RandomState(42)
    n_b, n_a = 150, 150
    n_perm = 300

    scores = rng.uniform(0, 1, n_b + n_a)
    labels = np.array([1] * n_b + [0] * n_a)

    auc_vals = [roc_auc_score(rng.permutation(labels), scores) for _ in range(n_perm)]
    mc_mean = float(np.mean(auc_vals))
    mc_std = float(np.std(auc_vals))

    _, an_std = c2st_analytical_null(n_b, n_a)

    assert abs(mc_mean - 0.5) < 0.03, f"MC mean {mc_mean:.4f} not near 0.5"
    se = an_std / (2 * n_perm) ** 0.5
    assert abs(mc_std - an_std) < 3 * se, (
        f"MC std {mc_std:.5f} differs from analytical {an_std:.5f} by "
        f"{abs(mc_std - an_std):.5f} > 3 SE ({3 * se:.5f})"
    )
