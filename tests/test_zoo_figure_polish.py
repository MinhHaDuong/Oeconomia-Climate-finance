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
    """_plot must plot the 'value' column, not 'z_score'."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import plot_zoo_results

    plotted_y = []
    original_plot = plt.Axes.plot

    def capture(self, *args, **kw):
        if len(args) >= 2:
            plotted_y.extend(list(args[1]))
        return original_plot(self, *args, **kw)

    monkeypatch.setattr(plt.Axes, "plot", capture)

    df = pd.DataFrame(
        {
            "year": [2005, 2006],
            "window": ["3", "3"],
            "z_score": [10.0, 20.0],  # high sentinel — must NOT appear
            "value": [0.11, 0.22],  # low sentinel — must appear
        }
    )
    output_stem = str(tmp_path / "test_raw")
    plot_zoo_results._plot(df, "S2_energy", output_stem)

    assert any(abs(v - 0.11) < 1e-5 for v in plotted_y), (
        f"raw value 0.11 not found in plotted Y values: {plotted_y}"
    )
    assert not any(abs(v - 10.0) < 1e-5 for v in plotted_y), (
        "z_score sentinel 10.0 was plotted — still using z_score column"
    )
