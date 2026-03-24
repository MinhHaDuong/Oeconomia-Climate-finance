"""AGENTS.md size guard.

AGENTS.md is loaded into every Claude Code conversation via CLAUDE.md.
Anthropic recommends keeping CLAUDE.md under 200 lines.

When the harness is extracted (PR #224), this test travels with it.
"""

import os

ROOT = os.path.join(os.path.dirname(__file__), "..")
AGENTS_MD = os.path.join(ROOT, "AGENTS.md")

SMELL_THRESHOLD = 150  # lines — time to trim
HARD_CEILING = 200  # Anthropic recommended limit


def _line_count():
    with open(AGENTS_MD) as f:
        return len(f.readlines())


def test_under_smell_threshold():
    """AGENTS.md above the smell threshold — consider trimming."""
    lines = _line_count()
    assert lines <= SMELL_THRESHOLD, (
        f"AGENTS.md is {lines} lines (smell threshold: {SMELL_THRESHOLD}). "
        f"Consider extracting sections to docs/ or runbooks/."
    )


def test_under_hard_ceiling():
    """AGENTS.md must stay under the hard ceiling (Anthropic limit)."""
    lines = _line_count()
    assert lines <= HARD_CEILING, (
        f"AGENTS.md is {lines} lines — exceeds the {HARD_CEILING}-line ceiling. "
        f"Claude Code truncates beyond this."
    )
