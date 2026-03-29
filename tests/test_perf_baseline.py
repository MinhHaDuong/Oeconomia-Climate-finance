"""Tests for #514: Performance baseline — time_target wrapper."""

import json
import os
import subprocess
import sys

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
MAKEFILE = os.path.join(os.path.dirname(__file__), "..", "Makefile")


class TestTimeTarget:
    """time_target.sh produces valid JSONL records."""

    @pytest.mark.integration
    def test_produces_valid_jsonl(self, tmp_path):
        out = tmp_path / "timings.jsonl"
        result = subprocess.run(
            ["bash", os.path.join(SCRIPTS_DIR, "time_target.sh"),
             "test_label", str(out), "sleep", "0.1"],
            capture_output=True, text=True,
            timeout=30,
        )
        assert result.returncode == 0, f"time_target.sh failed:\n{result.stderr}"
        assert out.exists(), "No output file produced"
        record = json.loads(out.read_text().strip().split("\n")[-1])
        assert "label" in record
        assert "wall_s" in record
        assert record["label"] == "test_label"
        assert record["wall_s"] > 0

    @pytest.mark.integration
    def test_appends_to_existing_file(self, tmp_path):
        out = tmp_path / "timings.jsonl"
        for label in ["run1", "run2"]:
            subprocess.run(
                ["bash", os.path.join(SCRIPTS_DIR, "time_target.sh"),
                 label, str(out), "true"],
                capture_output=True, text=True,
                timeout=10,
            )
        lines = out.read_text().strip().split("\n")
        assert len(lines) == 2
        assert json.loads(lines[0])["label"] == "run1"
        assert json.loads(lines[1])["label"] == "run2"


class TestMakefileBenchmark:
    def test_benchmark_target_exists(self):
        import re
        with open(MAKEFILE) as f:
            mk = f.read()
        assert re.search(r"^benchmark\s*:", mk, re.MULTILINE), (
            "Makefile missing 'benchmark' target"
        )
