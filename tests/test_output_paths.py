"""Tests for #209: Generated Phase 2 tables must live in content/tables/, not content/_includes/.

Phase 2 script outputs (generated markdown tables) should be gitignored alongside
other generated artifacts in content/tables/. Hand-written includes stay in content/_includes/.
"""

import ast
import os

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")
SCRIPTS_DIR = os.path.join(ROOT, "scripts")

# Scripts that produce generated tables (Phase 2 outputs)
TABLE_SCRIPTS = [
    "export_tab_venues.py",
    "export_citation_coverage.py",
]


def _find_output_paths(script_path: str) -> list[str]:
    """Extract string literals that look like output paths from a Python script.

    Looks for os.path.join calls writing to content/_includes/ or content/tables/.
    """
    with open(script_path) as f:
        source = f.read()

    paths = []
    # Match string literals containing content/_includes or content/tables
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            val = node.value
            if "content" in val and ("_includes" in val or "tables" in val):
                paths.append(val)
    return paths


class TestNoScriptOutputToIncludes:
    """No Phase 2 script should write generated tables to content/_includes/."""

    @pytest.mark.parametrize("script", TABLE_SCRIPTS)
    def test_output_path_not_in_includes(self, script):
        path = os.path.join(SCRIPTS_DIR, script)
        assert os.path.isfile(path), f"{script} must exist"

        output_paths = _find_output_paths(path)
        for p in output_paths:
            assert "_includes" not in p, (
                f"{script} writes to content/_includes/ — "
                f"generated tables must go to content/tables/ (found: {p!r})"
            )

    @pytest.mark.parametrize("script", TABLE_SCRIPTS)
    def test_output_path_in_tables(self, script):
        path = os.path.join(SCRIPTS_DIR, script)
        output_paths = _find_output_paths(path)
        tables_paths = [p for p in output_paths if "tables" in p]
        assert tables_paths, (
            f"{script} must write output to content/tables/ "
            f"(found paths: {output_paths!r})"
        )
