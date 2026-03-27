"""Tests for scripts/lint_prose.sh — extracted prose linter."""

import os
import subprocess
from pathlib import Path

import pytest

PROJ_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJ_ROOT / "scripts" / "lint_prose.sh"


def test_script_exists():
    """The lint_prose.sh script must exist and be executable."""
    assert SCRIPT.exists(), f"{SCRIPT} not found"
    assert os.access(SCRIPT, os.X_OK), f"{SCRIPT} is not executable"


def test_script_has_strict_mode():
    """Script must use set -euo pipefail for safety."""
    text = SCRIPT.read_text()
    assert "set -euo pipefail" in text


def test_script_derives_proj_root():
    """Script must derive PROJ_ROOT from its own location, not hardcode paths."""
    text = SCRIPT.read_text()
    assert 'dirname' in text and 'PROJ_ROOT' in text


def test_script_checks_blacklisted_words():
    """Script must check for AI-tell blacklisted words."""
    text = SCRIPT.read_text()
    assert "delve" in text
    assert "nuanced" in text
    assert "multifaceted" in text


def test_script_checks_em_dashes():
    """Script must check for em-dash heavy paragraphs."""
    text = SCRIPT.read_text()
    assert "---" in text


def test_script_checks_contrast_farming():
    """Script must check for contrast farming pattern."""
    text = SCRIPT.read_text()
    assert "not .{3,60}, but " in text


@pytest.mark.integration
def test_script_runs_successfully():
    """The script must run and exit 0 on the real manuscript."""
    result = subprocess.run(
        ["bash", str(SCRIPT)],
        capture_output=True,
        text=True,
        cwd=PROJ_ROOT,
    )
    assert result.returncode == 0, f"lint_prose.sh failed:\n{result.stdout}\n{result.stderr}"
    assert "LINT-PROSE: PASS" in result.stdout


def test_makefile_delegates_to_script():
    """The Makefile lint-prose target must call the extracted script."""
    makefile = (PROJ_ROOT / "Makefile").read_text()
    assert "scripts/lint_prose.sh" in makefile
