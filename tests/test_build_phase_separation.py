"""Phase-2/Phase-3 separation for the manuscript writing workpackage (ticket 0131).

The harness Build rule requires that a writing-side build produce the manuscript
from handoff artifacts alone — no `uv run`, no data fetch. Two things enforce it:

1. The manuscript's small, byte-stable writing-facing deliverables (3 PNGs +
   tab_venues.md) are git-tracked, so a fresh worktree has them without running
   Phase 2 or pulling corpus data.
2. A standalone `manuscript.mk` renders the PDF/DOCX with prerequisites limited
   to committed prose + deliverables — no Phase-1 data dependency.
"""

import os
import subprocess

import pytest

REPO_ROOT = os.path.join(os.path.dirname(__file__), "..")
MANUSCRIPT_MK = os.path.join(REPO_ROOT, "manuscript.mk")

# The manuscript's writing-facing deliverables — what manuscript.qmd actually
# consumes via ![](figures/...) and {{< include tables/tab_venues.md >}}.
MANUSCRIPT_DELIVERABLES = [
    "content/figures/fig_bars_v1.png",
    "content/figures/fig_composition.png",
    "content/figures/fig_breaks.png",
    "content/tables/tab_venues.md",
]

# Tokens that betray a Phase-1/data dependency leaking into the writing build.
DATA_TOKENS = ["$(REFINED)", "$(DATA_DIR)", "refined_works", "data/"]


@pytest.mark.integration
@pytest.mark.parametrize("path", MANUSCRIPT_DELIVERABLES)
def test_deliverable_is_git_tracked(path):
    """Each manuscript deliverable must be tracked by git (like content/_includes/)."""
    result = subprocess.run(
        ["git", "ls-files", "--error-unmatch", path],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, (
        f"{path} is not git-tracked; a clean-room writing build cannot find it. "
        f"git ls-files said: {result.stderr.strip()}"
    )


def test_manuscript_mk_exists():
    assert os.path.isfile(MANUSCRIPT_MK), "manuscript.mk missing at repo root"


def test_manuscript_pdf_rule_has_no_data_prereq():
    """The manuscript.pdf rule (prereqs + recipe) must not reference Phase-1 data."""
    with open(MANUSCRIPT_MK) as f:
        text = f.read()

    # Isolate the output/content/manuscript.pdf rule block (prereq line + recipe).
    lines = text.splitlines()
    block = []
    in_rule = False
    for line in lines:
        if line.startswith("output/content/manuscript.pdf:"):
            in_rule = True
            block.append(line)
            continue
        if in_rule:
            # Recipe lines are tab-indented; a non-indented, non-blank line ends it.
            if line and not line[0].isspace():
                break
            block.append(line)
    assert block, "output/content/manuscript.pdf rule not found in manuscript.mk"

    rule_text = "\n".join(block)
    for token in DATA_TOKENS:
        assert token not in rule_text, (
            f"manuscript.pdf rule references Phase-1 data token {token!r}: "
            f"the writing build must depend on committed deliverables only.\n{rule_text}"
        )
