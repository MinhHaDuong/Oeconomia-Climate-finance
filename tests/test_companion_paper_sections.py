"""Structural checks for companion-paper.qmd (ticket 0057).

The companion paper (QSS submission, epic 0026) presents a lean six-method
design for endogenous periodization. Its Method section (§4) must cover
nine subsections in a fixed order; its Results section (§5) is stubbed until
the compute pipeline fills numbers (ticket 0064).

Keep this test mechanical: substring presence in the source .qmd.
"""

import os
import re
from pathlib import Path

REPO = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PAPER = REPO / "content" / "companion-paper.qmd"


def _text() -> str:
    return PAPER.read_text(encoding="utf-8")


# Nine §4 subsection headings. Checked case-insensitively for resilience
# to capitalisation tweaks, but the concept word must appear literally.
METHOD_SECTIONS = [
    "Objective",
    "Representations",
    "Temporal segmentation",
    "Distributional comparison",
    "Statistical inference",
    "Transition zone",
    "Censored-gap",
    "Robustness",
    "Interpretation",
]


def test_paper_exists():
    assert PAPER.exists(), f"missing {PAPER}"


def test_method_has_nine_subsections():
    text = _text().lower()
    missing = [s for s in METHOD_SECTIONS if s.lower() not in text]
    assert not missing, f"Method section missing subsections: {missing}"


def test_method_subsections_are_numbered_headings():
    """Each §4 subsection must be a level-3 heading numbered 4.1 through 4.9."""
    text = _text()
    for n in range(1, 10):
        pattern = rf"^###\s+4\.{n}\b"
        assert re.search(pattern, text, re.MULTILINE), (
            f"Missing heading '### 4.{n} ...' for §4 subsection {n}"
        )


def test_no_old_method_includes():
    """Old method/results includes must be gone (the rewrite is inline)."""
    text = _text()
    forbidden = [
        "structural-breaks.md",
        "bimodality-analysis.md",
        "pca-scatter.md",
        "alluvial-diagram.md",
        "embedding-generation.md",
    ]
    present = [f for f in forbidden if f in text]
    assert not present, f"Old includes still referenced: {present}"


def test_results_stubs_figure_refs():
    """§5 must reference the four figures ticket 0058 will materialise."""
    text = _text()
    for ref in ["@fig-zseries", "@fig-heatmap", "@fig-terms", "@fig-community"]:
        assert ref in text, f"Missing figure reference: {ref}"


def test_results_uses_meta_placeholders():
    """§5 stubs numbers via {{< meta ... >}} — does not hardcode them."""
    text = _text()
    # At least the lead-panel peaks and a validated zone must be stubbed.
    expected_vars = [
        "s2_peak_year_w3",
        "l1_peak_year_w3",
        "g9_peak_year_w3",
        "zone_1_start",
    ]
    missing = [v for v in expected_vars if f"{{{{< meta {v} >}}}}" not in text]
    assert not missing, f"Missing §5 meta placeholders: {missing}"


def test_no_obsolete_findings_in_abstract():
    """Abstract must not retain the old four-finding / PC2 framing."""
    text = _text()
    forbidden = [
        "PC2, not PC1",
        "efficiency--accountability divide",
        "four findings",
        "ΔBIC",
    ]
    present = [f for f in forbidden if f in text]
    assert not present, f"Obsolete claim survives in paper: {present}"
