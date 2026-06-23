"""Governance guards for the editorial brief and polarity rule (ticket 0148).

These pin the *infrastructure* contract, not manuscript prose: the brief exists
with the schema the `/review-pr-prose` auditor consumes, and writing.md carries
the CI test-polarity rule that keeps positive intent out of CI.
"""

import os
import re

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
BRIEF = os.path.join(ROOT, "docs", "editorial-brief.md")
WRITING_RULE = os.path.join(ROOT, ".claude", "rules", "writing.md")

pytestmark = pytest.mark.adherence


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return fh.read()


def _entries(text):
    """H2 decision entries (skip the document title and any preamble)."""
    return re.findall(r"^## (.+)$", text, re.MULTILINE)


def test_brief_exists_with_entries():
    assert os.path.exists(BRIEF), "docs/editorial-brief.md must exist (ticket 0148)"
    entries = _entries(_read(BRIEF))
    assert len(entries) >= 3, f"editorial brief has too few decisions: {entries}"


def test_every_entry_has_schema_fields():
    """Each decision carries the Decision/Rationale/Ticket/Status schema."""
    text = _read(BRIEF)
    blocks = re.split(r"^## ", text, flags=re.MULTILINE)[1:]
    for block in blocks:
        title = block.splitlines()[0].strip()
        for field in ("**Decision:**", "**Rationale:**", "**Ticket:**", "**Status:**"):
            assert field in block, f"brief entry {title!r} is missing {field}"


def test_writing_md_has_polarity_rule():
    text = _read(WRITING_RULE)
    assert "CI test polarity rule" in text, "writing.md must carry the polarity rule"
    assert "negative guards" in text
    assert "docs/editorial-brief.md" in text, (
        "the polarity rule must point positive intent to the editorial brief"
    )


def test_review_pr_prose_consumes_brief():
    """The /review-pr-prose skill reads the brief (skip if skill absent in CI)."""
    skill = os.path.expanduser("~/.claude/skills/review-pr-prose/SKILL.md")
    if not os.path.exists(skill):
        pytest.skip("review-pr-prose skill not present in this checkout")
    assert "docs/editorial-brief.md" in _read(skill), (
        "the prose-review skill must read docs/editorial-brief.md (action 3)"
    )
