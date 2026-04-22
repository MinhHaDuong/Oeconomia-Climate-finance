"""Tests for per-method min_papers config overrides (ticket 0101).

RED phase: these tests fail until config/analysis.yaml is updated with
c2st.min_papers and semantic.S4_frechet.min_papers overrides.
"""

from pipeline_loaders import load_analysis_config


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
