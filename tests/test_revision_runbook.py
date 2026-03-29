"""Tests for #512: Revision runbook exists and covers key scenarios."""

from pathlib import Path


def test_runbook_exists():
    """Revision runbook is in place and covers key scenarios."""
    runbook = Path("release/revision-runbook.md")
    assert runbook.exists(), "Revision runbook missing"
    text = runbook.read_text()
    for scenario in [
        "prose-only", "parameter change", "corpus expansion",
        "response letter", "zenodo",
    ]:
        assert scenario.lower() in text.lower(), (
            f"Runbook missing scenario: {scenario}"
        )


def test_runbook_has_cherry_pick_protocol():
    text = Path("release/revision-runbook.md").read_text()
    assert "cherry-pick" in text.lower(), "Runbook missing cherry-pick protocol"


def test_runbook_has_response_template():
    text = Path("release/revision-runbook.md").read_text()
    assert "reviewer" in text.lower(), "Runbook missing response letter template"
