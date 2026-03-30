"""Regression tests: Phase 2 script outputs vs golden hash baseline.

The actual regression check runs via `make regression` (called by `make check`).
This file tests that the infrastructure is wired up correctly.

When a change is intentional, update the baseline:
    uv run python scripts/regression_hashes.py --save
and commit with an explanation of why outputs changed.
"""

import os
import sys

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
REGRESSION_SCRIPT = os.path.join(ROOT, "scripts", "regression_hashes.py")
GOLDEN_PATH = os.path.join(ROOT, "tests", "fixtures", "smoke", "golden_hashes.json")


class TestRegressionBaseline:
    """Golden hash baseline exists and is maintained."""

    def test_golden_hashes_exist(self):
        assert os.path.exists(GOLDEN_PATH), (
            "Golden hashes not found. Generate with: "
            "uv run python scripts/regression_hashes.py --save"
        )

    def test_golden_hashes_valid_json(self):
        import json
        with open(GOLDEN_PATH) as f:
            data = json.load(f)
        assert isinstance(data, dict)
        assert len(data) > 0, "Golden hashes file is empty"


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
