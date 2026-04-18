"""Numeric-fill checks for companion-paper.qmd + companion-paper-vars.yml (ticket 0064).

Ticket 0057 stubbed §5 with `{{< meta X >}}` placeholders and ticket 0058 added
figure blocks. Ticket 0064 populates the placeholders with concrete numbers
computed from the real-corpus pipeline outputs.

Keep these tests mechanical — they enforce resolution and figure wiring only.
Scientific validity of the values belongs to `compute_companion_vars.py`.
"""

import os
import re
from pathlib import Path

import yaml

REPO = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAPER = REPO / "content" / "companion-paper.qmd"
VARS = REPO / "content" / "companion-paper-vars.yml"


def _paper_text() -> str:
    return PAPER.read_text(encoding="utf-8")


def _vars_dict() -> dict:
    return yaml.safe_load(VARS.read_text(encoding="utf-8"))


def test_vars_file_exists():
    assert VARS.exists(), f"missing {VARS}"


def test_every_meta_placeholder_resolves():
    """Every `{{< meta X >}}` in the paper must be a key in the vars file."""
    text = _paper_text()
    vars_ = _vars_dict()
    unresolved = []
    for match in re.findall(r"{{<\s*meta\s+(\w+)\s*>}}", text):
        if match not in vars_:
            unresolved.append(match)
    assert not unresolved, f"Unresolved placeholders: {sorted(set(unresolved))}"


def test_four_figures_cross_referenced():
    text = _paper_text()
    for fig in ["fig-zseries", "fig-heatmap", "fig-terms", "fig-community"]:
        assert f"@{fig}" in text, f"Missing figure cross-reference: @{fig}"


def test_no_legacy_seed_axis_vars():
    """The retired seed-axis/PCA/bimodality design must leave no residue."""
    vars_ = _vars_dict()
    forbidden_prefixes = ("bim_", "pca_", "seed_axis_")
    stale = [k for k in vars_ if k.startswith(forbidden_prefixes)]
    assert not stale, f"Legacy vars still present: {stale}"


def test_peak_z_values_are_numeric_strings():
    """Peak Z-score vars should parse as floats (ticket 0064 honest-data pact)."""
    vars_ = _vars_dict()
    for key in ("s2_peak_z_w3", "l1_peak_z_w3", "g9_peak_z_w3"):
        assert key in vars_, f"Missing key {key}"
        value = str(vars_[key])
        float(value)  # raises if unparseable
