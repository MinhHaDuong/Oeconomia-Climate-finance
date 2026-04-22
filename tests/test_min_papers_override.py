"""Tests for per-method min_papers config overrides (ticket 0101).

Verifies that:
- config/analysis.yaml carries the per-method overrides
- get_min_papers() returns the correct value per method
- c2st.min_papers >= 50 (5-fold CV needs n>=50 for stable AUC)
- semantic.S4_frechet.min_papers >= 300 (covariance requires n > PCA dim=256)
"""

import os
import sys

from pipeline_loaders import load_analysis_config

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


def test_c2st_min_papers_override():
    """C2ST uses min_papers=50, not the global 30."""
    cfg = load_analysis_config()
    global_min = cfg["divergence"]["min_papers"]
    c2st_min = cfg["divergence"].get("c2st", {}).get("min_papers", global_min)
    assert c2st_min >= 50


def test_frechet_min_papers_override():
    """S4_frechet uses min_papers=300 (n > PCA reduced dim for valid covariance)."""
    cfg = load_analysis_config()
    frechet_min = (
        cfg["divergence"].get("semantic", {}).get("S4_frechet", {}).get("min_papers", 0)
    )
    assert frechet_min >= 300


def test_get_min_papers_returns_c2st_override():
    """get_min_papers('c2st') returns >= 50 for all C2ST method names."""
    from _divergence_io import get_min_papers

    assert get_min_papers("c2st") >= 50
    assert get_min_papers("C2ST_embedding") >= 50
    assert get_min_papers("C2ST_lexical") >= 50


def test_get_min_papers_returns_frechet_override():
    """get_min_papers('S4_frechet') returns >= 300."""
    from _divergence_io import get_min_papers

    assert get_min_papers("S4_frechet") >= 300


def test_get_min_papers_global_fallback():
    """get_min_papers() with no method returns global min_papers."""
    from _divergence_io import get_min_papers

    cfg = load_analysis_config()
    global_min = cfg["divergence"]["min_papers"]
    assert get_min_papers() == global_min
