"""Regression tests: Phase 2 script outputs vs golden hash baseline.

Runs deterministic scripts on the 100-row smoke fixture, hashes outputs
(with float-rounding tolerance for CSV/JSON), and compares against
golden_hashes.json checked into the smoke fixture directory.

This catches unintentional output changes introduced by refactoring,
dependency upgrades, or parameter drift. When a change is intentional,
update the golden baseline: `uv run python scripts/regression_hashes.py --save`
and commit with an explanation.

Floats are rounded to 8 significant digits before hashing, so
insignificant floating-point noise across platforms does not trigger
false positives.
"""

import os
import subprocess
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
REGRESSION_SCRIPT = os.path.join(ROOT, "scripts", "regression_hashes.py")
GOLDEN_PATH = os.path.join(ROOT, "tests", "fixtures", "smoke", "golden_hashes.json")


@pytest.mark.integration
class TestRegressionHashes:
    """Phase 2 outputs match the golden hash baseline."""

    def test_golden_hashes_exist(self):
        assert os.path.exists(GOLDEN_PATH), (
            "Golden hashes not found. Generate with: "
            "uv run python scripts/regression_hashes.py --save"
        )

    @pytest.mark.slow
    def test_outputs_match_golden(self):
        """Run all registered scripts and compare against golden baseline."""
        if not os.path.exists(GOLDEN_PATH):
            pytest.skip("Golden hashes not yet generated")

        result = subprocess.run(
            [sys.executable, REGRESSION_SCRIPT, "--check"],
            capture_output=True, text=True,
            timeout=300,
            env={
                **os.environ,
                "PYTHONHASHSEED": "0",
                "SOURCE_DATE_EPOCH": "0",
                "MPLBACKEND": "Agg",
            },
        )
        assert result.returncode == 0, (
            f"Regression check failed:\n{result.stdout}\n{result.stderr}"
        )


class TestRegressionInfra:
    """Regression infrastructure exists and is wired up."""

    def test_makefile_has_regression_target(self):
        import re
        with open(os.path.join(ROOT, "Makefile")) as f:
            content = f.read()
        assert re.search(r"^regression\s*:", content, re.MULTILINE), (
            "Makefile missing 'regression' target"
        )

    def test_regression_script_exists(self):
        assert os.path.exists(REGRESSION_SCRIPT)

    def test_registry_is_nonempty(self):
        """The regression script registers at least one script."""
        sys.path.insert(0, os.path.join(ROOT, "scripts"))
        try:
            from regression_hashes import REGISTRY
            assert len(REGISTRY) > 0, "REGISTRY is empty"
        finally:
            sys.path.pop(0)
