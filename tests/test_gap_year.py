"""Tests that year t is excluded from both windows when gap=1."""

import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


def test_split_year_excluded_from_before_window():
    """Year t must not appear in before-window when gap=1."""
    from _divergence_semantic import _get_window_embeddings

    # Build synthetic df: papers at years 2000-2005
    df = pd.DataFrame({"year": list(range(2000, 2006)), "work_id": range(6)})
    emb = np.eye(6)
    cfg = {"divergence": {"gap": 1, "max_subsample": 1000}}

    # Split year t=2003, window=2: before should be [2001, 2002], not including 2003
    result = _get_window_embeddings(
        df, emb, year=2003, window=2, side="before", min_papers=1, max_subsample=1000
    )
    # result is array of embeddings for years 2001-2002
    # Confirm year 2003 row (index 3) is NOT in result
    assert result is not None
    # The before window should have exactly 2 papers (years 2001, 2002)
    assert len(result) == 2


def test_split_year_excluded_from_after_window():
    """Year t must not appear in after-window when gap=1."""
    from _divergence_semantic import _get_window_embeddings

    # Build synthetic df: papers at years 2000-2005
    df = pd.DataFrame({"year": list(range(2000, 2006)), "work_id": range(6)})
    emb = np.eye(6)

    # Split year t=2003, window=2: after should be [2004, 2005], not including 2003
    result = _get_window_embeddings(
        df, emb, year=2003, window=2, side="after", min_papers=1, max_subsample=1000
    )
    assert result is not None
    # The after window should have exactly 2 papers (years 2004, 2005)
    assert len(result) == 2


def test_before_window_with_explicit_gap_param():
    """_get_window_embeddings accepts gap parameter and uses it."""
    from _divergence_semantic import _get_window_embeddings

    df = pd.DataFrame({"year": list(range(2000, 2010)), "work_id": range(10)})
    emb = np.eye(10)

    # gap=2: before=[2001, 2002], after=[2007, 2008] for t=2004, w=3
    before = _get_window_embeddings(
        df,
        emb,
        year=2004,
        window=3,
        side="before",
        min_papers=1,
        max_subsample=1000,
        gap=2,
    )
    assert before is not None
    assert len(before) == 2  # years 2001, 2002 only

    after = _get_window_embeddings(
        df,
        emb,
        year=2004,
        window=3,
        side="after",
        min_papers=1,
        max_subsample=1000,
        gap=2,
    )
    assert after is not None
    assert len(after) == 2  # t+gap=2006, t+w=2007: years 2006, 2007


def test_citation_window_gap_before():
    """_sliding_window_graph before-window excludes year t when gap=1."""
    from _divergence_citation import _sliding_window_graph

    works = pd.DataFrame(
        {
            "doi": [f"doi:{y}" for y in range(2000, 2006)],
            "year": list(range(2000, 2006)),
        }
    )
    internal_edges = pd.DataFrame(columns=["source_doi", "ref_doi", "source_year"])

    # t=2003, w=2, gap=1 (default): before=[2001, 2002], not 2003
    G = _sliding_window_graph(works, internal_edges, year=2003, window=2, side="before")
    node_years = {int(doi.split(":")[1]) for doi in G.nodes()}
    assert 2003 not in node_years, (
        f"Year 2003 should not be in before-window, got: {node_years}"
    )
    assert node_years == {2001, 2002}, f"Expected {{2001, 2002}}, got {node_years}"


def test_citation_window_gap_after():
    """_sliding_window_graph after-window excludes year t when gap=1."""
    from _divergence_citation import _sliding_window_graph

    works = pd.DataFrame(
        {
            "doi": [f"doi:{y}" for y in range(2000, 2006)],
            "year": list(range(2000, 2006)),
        }
    )
    internal_edges = pd.DataFrame(columns=["source_doi", "ref_doi", "source_year"])

    # t=2003, w=2, gap=1 (default): after=[2004, 2005]
    G = _sliding_window_graph(works, internal_edges, year=2003, window=2, side="after")
    node_years = {int(doi.split(":")[1]) for doi in G.nodes()}
    assert 2003 not in node_years, (
        f"Year 2003 should not be in after-window, got: {node_years}"
    )
    assert node_years == {2004, 2005}, f"Expected {{2004, 2005}}, got {node_years}"


def test_lexical_iter_excludes_split_year():
    """_iter_lexical_window_pairs before-window excludes year t when gap=1."""
    from _divergence_lexical import _iter_lexical_window_pairs

    # Build synthetic df with abstracts
    years = list(range(2000, 2010))
    df = pd.DataFrame(
        {
            "year": years,
            "abstract": [f"climate finance policy year {y}" for y in years],
        }
    )
    cfg = {
        "divergence": {
            "gap": 1,
            "windows": [2],
            "max_subsample": 1000,
            "random_seed": 42,
            "equal_n": False,
            "lexical": {
                "tfidf_max_features": 100,
                "tfidf_min_df": 1,
                "low_n_threshold": 1,
            },
        }
    }

    for y, w, X_before, X_after, _vec in _iter_lexical_window_pairs(df, cfg):
        # The before window for split year y should NOT include year y itself
        n_before = X_before.shape[0]
        # For w=2 and gap=1: before=[y-2, y-1] has 2 papers, after=[y+1, y+2] has 2 papers
        assert n_before == 2, (
            f"For year={y}, w={w}: expected 2 before-papers (gap=1), got {n_before}"
        )
