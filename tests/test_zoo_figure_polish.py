"""Tests for figure-polish changes in plot_zoo_results.py (ticket 0103).

RED phase: these tests fail before _METHOD_TITLES and Z=0 axhline are added.
"""

import os
import sys

import pandas as pd

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


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


def test_z0_axhline_present(tmp_path, monkeypatch):
    """_plot adds a Z=0 reference line."""
    import matplotlib.pyplot as plt
    import plot_zoo_results

    hlines = []
    original = plt.Axes.axhline

    def capture(self, y=0, **kw):
        hlines.append(y)
        return original(self, y, **kw)

    monkeypatch.setattr(plt.Axes, "axhline", capture)
    df = pd.DataFrame(
        {
            "year": [2005, 2006],
            "window": ["3", "3"],
            "z_score": [0.5, 1.0],
            "value": [0.1, 0.2],
        }
    )
    output_stem = str(tmp_path / "test_fig")
    plot_zoo_results._plot(df, "S2_energy", output_stem)
    assert 0 in hlines or 0.0 in hlines, "Z=0 reference line not added"
