"""
ticket 0075: window config matches §4.8 of companion paper.

The authoritative set is in §4.8 (Parameter sensitivity). This test
ensures config/analysis.yaml divergence.windows matches what the paper
declares for the sensitivity sweep.
"""

import re
from pathlib import Path

import yaml

ROOT = Path(__file__).parent.parent


def _load_config_windows():
    cfg = yaml.safe_load((ROOT / "config/analysis.yaml").read_text())
    return set(cfg["divergence"]["windows"])


def _load_paper_windows():
    paper_text = (ROOT / "content/multilayer-detection.qmd").read_text()
    # Slice §4.8 section only — between "### 4.8 Robustness" and "### 4.9"
    section_match = re.search(
        r"### 4\.8 Robustness(.*?)### 4\.9", paper_text, re.DOTALL
    )
    assert section_match, (
        "§4.8 Robustness section not found in multilayer-detection.qmd"
    )
    section = section_match.group(1)

    # Find LaTeX set notation e.g. \{2, 3, 4\} or {2, 3, 4}
    # The paper uses $w$ is varied over $\{2, 3, 4\}$
    set_matches = re.findall(r"\\?\{(\d+(?:,\s*\d+)+)\\?\}", section)
    assert set_matches, "No set of integers found in §4.8 — check paper text"

    # The first (and only) set in the sensitivity paragraph is the window set
    return set(int(x.strip()) for x in set_matches[0].split(","))


def test_windows_match():
    config_windows = _load_config_windows()
    paper_windows = _load_paper_windows()
    assert config_windows == paper_windows, (
        f"Config divergence.windows {config_windows} ≠ §4.8 paper windows {paper_windows}. "
        "Either drop w=5 from config or add it to the paper."
    )
