"""Tests for #516: Determinism checker — run twice, diff outputs.

Verifies that Phase 2 scripts produce byte-identical output on two runs
with the same input (PYTHONHASHSEED=0, SOURCE_DATE_EPOCH=0).
"""

import filecmp
import os
import subprocess
import sys

import pytest

SMOKE_DIR = os.path.join(os.path.dirname(__file__), "fixtures", "smoke")
SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
MAKEFILE = os.path.join(os.path.dirname(__file__), "..", "Makefile")


def _smoke_env():
    return {
        **os.environ,
        "CLIMATE_FINANCE_DATA": SMOKE_DIR,
        "PYTHONHASHSEED": "0",
        "SOURCE_DATE_EPOCH": "0",
        "MPLBACKEND": "Agg",
    }


def _run_twice(script, args, out_name, tmp_path):
    """Run a script twice into separate dirs, return (path1, path2)."""
    for run_id in ("run1", "run2"):
        out_dir = tmp_path / run_id
        out_dir.mkdir()
        # Create content subdirs that scripts expect
        (out_dir / "content" / "figures").mkdir(parents=True)
        (out_dir / "content" / "tables").mkdir(parents=True)
        out_path = out_dir / "content" / "figures" / out_name
        result = subprocess.run(
            [sys.executable, os.path.join(SCRIPTS_DIR, script),
             "--output", str(out_path)] + args,
            capture_output=True, text=True,
            env=_smoke_env(),
            timeout=60,
        )
        assert result.returncode == 0, (
            f"{script} run {run_id} failed:\n{result.stderr}"
        )
    return (
        tmp_path / "run1" / "content" / "figures" / out_name,
        tmp_path / "run2" / "content" / "figures" / out_name,
    )


@pytest.mark.slow
class TestDeterminism:
    """Phase 2 figure scripts produce identical output on two runs."""

    def test_fig_bars_deterministic(self, tmp_path):
        p1, p2 = _run_twice(
            "plot_fig1_bars.py", [], "fig_bars.png", tmp_path
        )
        assert p1.exists() and p2.exists()
        assert filecmp.cmp(str(p1), str(p2), shallow=False), (
            "plot_fig1_bars.py produced different output on two runs"
        )

    def test_fig_bars_v1_deterministic(self, tmp_path):
        p1, p2 = _run_twice(
            "plot_fig1_bars.py", ["--v1-only"],
            "fig_bars_v1.png", tmp_path,
        )
        assert p1.exists() and p2.exists()
        assert filecmp.cmp(str(p1), str(p2), shallow=False), (
            "plot_fig1_bars.py --v1-only produced different output on two runs"
        )


class TestMakeTarget:
    def test_determinism_check_target_exists(self):
        import re
        with open(MAKEFILE) as f:
            mk = f.read()
        assert re.search(r"^determinism-check\s*:", mk, re.MULTILINE), (
            "Makefile missing 'determinism-check' target"
        )
