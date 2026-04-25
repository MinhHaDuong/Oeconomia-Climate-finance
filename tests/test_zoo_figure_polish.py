"""Tests for figure-polish changes in plot_zoo_results.py (ticket 0103)."""

import glob
import os
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


def test_zoo_plots_raw_values_not_zscores(tmp_path, monkeypatch):
    """_plot draws the 'value' column, not 'z_score'."""
    import matplotlib.pyplot as plt
    import plot_zoo_results

    plotted_y = []
    original = plt.Axes.plot

    def capture(self, x, y, **kw):
        plotted_y.extend(list(y))
        return original(self, x, y, **kw)

    monkeypatch.setattr(plt.Axes, "plot", capture)
    # value=0.11 is the sentinel; z_score=10.0 should never appear
    df = pd.DataFrame(
        {
            "year": [2005, 2006],
            "window": ["3", "3"],
            "z_score": [10.0, 10.0],
            "value": [0.11, 0.11],
        }
    )
    output_stem = str(tmp_path / "test_fig")
    plot_zoo_results._plot(df, "S2_energy", output_stem)
    assert 0.11 in plotted_y, f"Expected value=0.11 in plotted data, got: {plotted_y}"
    assert 10.0 not in plotted_y, "z_score sentinel 10.0 must not appear in plot"
