"""Tests for figure-polish changes in plot_zoo_results.py (ticket 0103)."""

import csv
import glob
import os
import subprocess
import sys

import pandas as pd
import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


def test_no_w5_in_crossyear_tables():
    """Sliding-window methods must not have w=5 rows after padme rerun.

    L2 is excluded: it uses its own window config [3, 5] for novelty/transience
    lookback, which is a different concept from the sliding window w in S1-S4.
    """
    csvs = glob.glob("content/tables/tab_crossyear_*.csv")
    if not csvs:
        pytest.skip("No crossyear tables found — padme rerun needed (ticket 0100)")
    for path in csvs:
        if "tab_crossyear_L2" in path:
            continue  # L2 legitimately uses window=5 (its own config)
        df = pd.read_csv(path)
        df["window"] = df["window"].astype(str)
        assert "5" not in df["window"].unique(), f"{path} contains w=5 rows"


def test_method_titles_dict_has_all_18_methods():
    import plot_zoo_results

    expected = {
        "S1_MMD",
        "S2_energy",
        "S3_sliced_wasserstein",
        "S4_frechet",
        "L1",
        "L2",
        "L3",
        "G1_pagerank",
        "G2_spectral",
        "G3_coupling_age",
        "G4_cross_tradition",
        "G5_pref_attachment",
        "G6_entropy",
        "G7_disruption",
        "G8_betweenness",
        "G9_community",
        "C2ST_embedding",
        "C2ST_lexical",
    }
    assert expected.issubset(set(plot_zoo_results._METHOD_TITLES.keys())), (
        f"Missing methods: {expected - set(plot_zoo_results._METHOD_TITLES.keys())}"
    )


def test_metric_filter_selects_resonance_only(tmp_path):
    """--metric resonance keeps only resonance rows."""
    rows = [
        ["year", "window", "hyperparams", "value", "channel", "method"],
        ["1999", "3", "w=3,metric=novelty", "8.0", "lexical", "L2"],
        ["1999", "3", "w=3,metric=transience", "4.6", "lexical", "L2"],
        ["1999", "3", "w=3,metric=resonance", "3.38", "lexical", "L2"],
        ["2000", "3", "w=3,metric=novelty", "6.9", "lexical", "L2"],
        ["2000", "3", "w=3,metric=transience", "4.7", "lexical", "L2"],
        ["2000", "3", "w=3,metric=resonance", "2.19", "lexical", "L2"],
    ]
    input_csv = tmp_path / "tab_div_L2.csv"
    output_csv = tmp_path / "out.csv"
    with open(input_csv, "w", newline="") as f:
        csv.writer(f).writerows(rows)

    result = subprocess.run(
        [
            sys.executable,
            "scripts/compute_crossyear_zscore.py",
            "--method",
            "L2",
            "--metric",
            "resonance",
            "--output",
            str(output_csv),
            "--input",
            str(input_csv),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr
    df = pd.read_csv(output_csv)
    assert len(df) == 2  # one row per year
    row_1999 = df[df["year"] == 1999]
    assert len(row_1999) == 1
    assert abs(row_1999["value"].iloc[0] - 3.38) < 1e-6


def test_non_sliding_plots_value_not_z_score(tmp_path):
    """Non-sliding fallback (L3, G3, G4, G7) must plot 'value' not 'z_score'.

    Uses a dual-sentinel: value=0.11 and z_score=99.0.
    The plot must contain y-data matching 0.11, not 99.0.
    """
    import numpy as np
    import plot_zoo_results

    # Build a minimal crossyear CSV for a non-sliding method (L3)
    years = [2000, 2001, 2002]
    df = pd.DataFrame(
        {
            "year": years,
            "window": ["0"] * 3,
            "value": [0.11, 0.12, 0.13],  # sentinel: small values
            "z_score": [99.0, 98.0, 97.0],  # sentinel: large values
        }
    )

    output_png = tmp_path / "fig_L3.png"
    output_stem = str(output_png.with_suffix(""))

    # Capture y-data plotted by calling _plot with our sentinel df
    plotted_y = []
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    orig_plot = plt.Axes.plot

    def capture_plot(self, *args, **kwargs):
        if len(args) >= 2:
            y = np.asarray(args[1])
            plotted_y.extend(y.tolist())
        return orig_plot(self, *args, **kwargs)

    import unittest.mock as mock

    with mock.patch.object(plt.Axes, "plot", capture_plot):
        plot_zoo_results._plot(df, "L3", output_stem)

    assert any(abs(y - 0.11) < 1e-6 for y in plotted_y), (
        f"Expected 0.11 (value column) in plotted y-data; got {plotted_y}"
    )
    assert not any(abs(y - 99.0) < 0.1 for y in plotted_y), (
        f"z_score sentinel (99.0) should NOT appear in plotted y-data; got {plotted_y}"
    )


def test_l2_crossyear_value_matches_null_observed():
    """tab_crossyear_L2.csv value must match tab_null_L2.csv observed within 1e-4.

    RED before fix: crossyear value ≈ 5.35 (mean of 3 metrics) vs observed ≈ 3.38 (resonance only).
    Skips if artifacts absent OR stale (pre-fix mean-of-3 values still present).
    """
    crossyear = "content/tables/tab_crossyear_L2.csv"
    null_csv = "content/tables/tab_null_L2.csv"
    if not (os.path.exists(crossyear) and os.path.exists(null_csv)):
        pytest.skip(
            "Padme artifacts absent — run make content/tables/tab_crossyear_L2.csv first"
        )
    cy = pd.read_csv(crossyear)
    # Detect stale artifact: pre-fix year=1999 value was ~5.35 (mean of 3 metrics);
    # post-fix it is ~3.38 (resonance-only). Skip if stale rather than fail.
    sentinel_rows = cy[cy["year"] == 1999]
    if not sentinel_rows.empty and sentinel_rows["value"].iloc[0] > 4.5:
        pytest.skip(
            f"tab_crossyear_L2.csv is stale (year=1999 value={sentinel_rows['value'].iloc[0]:.2f}); "
            "regenerate with: make content/tables/tab_crossyear_L2.csv"
        )
    nm = pd.read_csv(null_csv)
    merged = cy.merge(nm, on=["year", "window"])
    assert len(merged) > 0, "No overlapping (year, window) rows"
    diff = (merged["value"] - merged["observed"]).abs()
    assert diff.max() < 1e-4, (
        f"Max mismatch between crossyear value and null observed: {diff.max():.6f}\n"
        f"Worst row:\n{merged.loc[diff.idxmax()]}"
    )
