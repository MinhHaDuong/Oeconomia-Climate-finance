"""Tests for coding-guidelines.md § Script hygiene and § Python style.

These tests enforce mechanically verifiable conventions. Each test is
designed to be red against the current codebase, documenting the gap
between guidelines and reality. Alignment tickets will fix the code;
these tests stay to prevent regression.

IMPORTANT: none of these changes may alter archive outputs. The
test_archive_bit_invariance class verifies that archive checksums
(expected_outputs.md5, checksums.md5) remain identical after refactoring.

Uses existing code checkers where available:
- ruff C901: McCabe cyclomatic complexity (threshold 10)
- ruff PLR0915: too many statements per function (threshold 50)
- ruff PLR0912: too many branches per function (threshold 12)
- ruff UP006/UP007/UP035: legacy typing imports
- ast: bare print() detection, sys.path hacks
"""

import ast
import os
import re
import subprocess
import sys
import textwrap

import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(REPO, "scripts")
MAKEFILE = os.path.join(REPO, "Makefile")

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _all_scripts():
    """Return sorted list of .py files in scripts/ and its subdirectories.

    Returns paths relative to SCRIPTS_DIR (e.g. "utils.py",
    "archive_traditions/detect_traditions_v1.py").
    """
    result = []
    for dirpath, _dirnames, filenames in os.walk(SCRIPTS_DIR):
        for f in filenames:
            if f.endswith(".py") and not f.startswith("__"):
                rel = os.path.relpath(os.path.join(dirpath, f), SCRIPTS_DIR)
                result.append(rel)
    return sorted(result)


def _read_script(name):
    """Read a script by its path relative to SCRIPTS_DIR."""
    path = os.path.join(SCRIPTS_DIR, name)
    with open(path) as f:
        return f.read()


def _parse_script(name):
    return ast.parse(_read_script(name), filename=name)


def _scripts_with_main_guard():
    """Scripts that have if __name__ == '__main__'."""
    result = []
    for name in _all_scripts():
        source = _read_script(name)
        if re.search(r'if\s+__name__\s*==\s*["\']__main__["\']', source):
            result.append(name)
    return result


# Scripts that are pure libraries (no __main__ guard, imported by others).
# These are exempt from argparse checks (no __main__ guard).
LIBRARY_SCRIPTS = {"utils.py", "plot_style.py", "refine_flags.py"}

# Subdirectory scripts that legitimately need sys.path.insert to reach
# the parent scripts/ directory for utils imports.
_SYSPATH_EXEMPT = {
    os.path.join("archive_traditions", f)
    for f in (
        "detect_traditions_v2.py",
        "detect_traditions_v3.py",
        "detect_traditions_pre2015.py",
        "detect_traditions_pre2020.py",
    )
}

_RUFF_AVAILABLE = subprocess.run(
    ["uv", "run", "ruff", "--version"], capture_output=True
).returncode == 0


# ---------------------------------------------------------------------------
# 1. No sys.path hacks
# ---------------------------------------------------------------------------

class TestNoSysPathHacks:
    """scripts/ must not contain sys.path.insert() calls.

    The project should use pyproject.toml packaging instead.
    Subdirectory scripts that genuinely need sys.path to reach the parent
    scripts/ directory are listed in _SYSPATH_EXEMPT.
    """

    def test_no_sys_path_insert(self):
        """No script may use sys.path.insert() unless in _SYSPATH_EXEMPT."""
        violators = []
        for name in _all_scripts():
            if name in _SYSPATH_EXEMPT:
                continue
            source = _read_script(name)
            if "sys.path.insert" in source or "sys.path.append" in source:
                violators.append(name)
        assert not violators, (
            f"{len(violators)} scripts use sys.path hacks "
            f"(should use pyproject.toml packaging): {violators[:10]}..."
        )


# ---------------------------------------------------------------------------
# 2. Centralized research parameters
# ---------------------------------------------------------------------------

class TestCentralizedConstants:
    """Research parameters must come from config/analysis.yaml, not hardcoded.

    CITE_THRESHOLD = 50 is currently defined in 8 scripts independently.
    It should be read via load_analysis_config()['clustering']['cite_threshold'].
    """

    # Constants that must not be defined as module-level literals in scripts.
    # They belong in config/analysis.yaml.
    FORBIDDEN_CONSTANTS = {
        "CITE_THRESHOLD": "clustering.cite_threshold",
    }

    def test_cite_threshold_not_hardcoded(self):
        """CITE_THRESHOLD must not be defined as a literal in any script."""
        violators = []
        for name in _all_scripts():
            source = _read_script(name)
            # Match lines like: CITE_THRESHOLD = 50
            if re.search(r"^CITE_THRESHOLD\s*=\s*\d+", source, re.MULTILINE):
                violators.append(name)
        assert not violators, (
            f"CITE_THRESHOLD hardcoded in {len(violators)} scripts "
            f"(should read from config/analysis.yaml): {violators}"
        )

    def test_config_has_cite_threshold(self):
        """config/analysis.yaml must define clustering.cite_threshold."""
        import yaml
        config_path = os.path.join(REPO, "config", "analysis.yaml")
        with open(config_path) as f:
            cfg = yaml.safe_load(f)
        assert "clustering" in cfg, "analysis.yaml missing 'clustering' section"
        assert "cite_threshold" in cfg["clustering"], (
            "analysis.yaml clustering section must define cite_threshold"
        )


# ---------------------------------------------------------------------------
# 3. Every entry point gets argparse
# ---------------------------------------------------------------------------

class TestArgparsePresence:
    """Every script with __main__ guard must use argparse.

    All entry-point scripts now have argparse. This test prevents
    regressions — each must have a parser with at least --help.
    """

    def test_main_scripts_have_argparse(self):
        """Every __main__ script must import or use argparse."""
        main_scripts = _scripts_with_main_guard()
        violators = []
        for name in main_scripts:
            if name in LIBRARY_SCRIPTS:
                continue
            source = _read_script(name)
            if "argparse" not in source and "ArgumentParser" not in source:
                violators.append(name)
        assert not violators, (
            f"{len(violators)} entry-point scripts lack argparse "
            f"(coding guidelines require it): {violators}"
        )


# ---------------------------------------------------------------------------
# 4. Ruff pyupgrade rules (modern Python 3.10+)
# ---------------------------------------------------------------------------

class TestRuffModernPython:
    """Ruff UP rules catch legacy typing imports and old-style unions.

    UP006: Use builtin types (list[] not List[])
    UP007: Use X | Y not Union[X, Y]
    UP035: Deprecated typing imports
    """

    @pytest.mark.skipif(not _RUFF_AVAILABLE, reason="ruff not available")
    def test_no_legacy_typing(self):
        """No legacy typing imports (List, Dict, Tuple, Optional, Union)."""
        result = subprocess.run(
            ["uv", "run", "ruff", "check", "--select", "UP006,UP007,UP035",
             "--no-fix", SCRIPTS_DIR],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"Ruff found legacy typing patterns:\n{result.stdout}"
        )

    @pytest.mark.skipif(not _RUFF_AVAILABLE, reason="ruff not available")
    def test_no_future_annotations(self):
        """No from __future__ import annotations (we target 3.10+)."""
        violators = []
        for name in _all_scripts():
            source = _read_script(name)
            if "from __future__ import annotations" in source:
                violators.append(name)
        assert not violators, (
            f"Scripts with __future__ annotations (not needed on 3.10+): {violators}"
        )


# ---------------------------------------------------------------------------
# 5. Complexity and length (ruff C901, PLR0915, PLR0912)
# ---------------------------------------------------------------------------


class TestFunctionComplexity:
    """Functions must not exceed calibrated complexity thresholds.

    Thresholds calibrated against the 63-script codebase:
    - C901=15: catches 16 genuinely complex functions, ignores linear
      research scripts that happen to have sequential setup (11-14 range).
    - PLR0915=80: catches 9 monolithic functions (>80 statements),
      ignores moderate-length main() that are just sequential pipelines.
    - PLR0912=15: catches 14 branchy functions, ignores moderate counts
      that arise from standard error handling patterns.

    Ruff defaults (10/50/12) are textbook-strict and produce 85 alerts,
    many of which are noise for procedural data scripts. These calibrated
    thresholds focus on the real god functions.
    """

    @pytest.mark.skipif(not _RUFF_AVAILABLE, reason="ruff not available")
    def test_mccabe_complexity(self):
        """No function exceeds McCabe complexity 15 (C901)."""
        result = subprocess.run(
            ["uv", "run", "ruff", "check", "--select", "C901",
             "--config", "lint.mccabe.max-complexity = 15",
             "--no-fix", SCRIPTS_DIR],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"Ruff C901: functions too complex (McCabe > 15):\n{result.stdout}"
        )

    @pytest.mark.skipif(not _RUFF_AVAILABLE, reason="ruff not available")
    def test_function_length(self):
        """No function exceeds 80 statements (PLR0915)."""
        result = subprocess.run(
            ["uv", "run", "ruff", "check", "--select", "PLR0915",
             "--config", "lint.pylint.max-statements = 80",
             "--no-fix", SCRIPTS_DIR],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"Ruff PLR0915: functions with too many statements (> 80):\n"
            f"{result.stdout}"
        )

    @pytest.mark.skipif(not _RUFF_AVAILABLE, reason="ruff not available")
    def test_branch_count(self):
        """No function exceeds 15 branches (PLR0912)."""
        result = subprocess.run(
            ["uv", "run", "ruff", "check", "--select", "PLR0912",
             "--config", "lint.pylint.max-branches = 15",
             "--no-fix", SCRIPTS_DIR],
            capture_output=True, text=True,
        )
        assert result.returncode == 0, (
            f"Ruff PLR0912: functions with too many branches (> 15):\n"
            f"{result.stdout}"
        )


class TestModuleLength:
    """Modules must not grow unbounded.

    Two thresholds:
    - 500 lines: smell (warns, does not fail)
    - 800 lines: wall (hard fail — split the module)
    """

    SMELL_LINES = 500
    MAX_MODULE_LINES = 800

    def test_no_god_modules(self):
        """No script exceeds 800 lines."""
        violators = []
        for name in _all_scripts():
            path = os.path.join(SCRIPTS_DIR, name)
            with open(path) as f:
                lines = sum(1 for _ in f)
            if lines > self.MAX_MODULE_LINES:
                violators.append((name, lines))
        assert not violators, (
            f"{len(violators)} scripts exceed {self.MAX_MODULE_LINES} lines "
            f"(split into focused modules): "
            + ", ".join(f"{n} ({l}L)" for n, l in violators)
        )

    def test_module_length_smell(self):
        """Warn (not fail) when scripts exceed 500 lines."""
        smelly = []
        for name in _all_scripts():
            path = os.path.join(SCRIPTS_DIR, name)
            with open(path) as f:
                lines = sum(1 for _ in f)
            if lines > self.SMELL_LINES:
                smelly.append((name, lines))
        if smelly:
            import warnings
            warnings.warn(
                f"{len(smelly)} scripts exceed {self.SMELL_LINES} lines "
                f"(consider splitting): "
                + ", ".join(f"{n} ({l}L)" for n, l in smelly)
            )


# ---------------------------------------------------------------------------
# 6. Archive bit-invariance
# ---------------------------------------------------------------------------

class TestArchiveBitInvariance:
    """Refactoring must not change archive outputs.

    The archive recipes (archive-analysis, archive-manuscript) produce
    checksum files. After any refactoring PR, archive outputs must match
    the v1.0-submission baseline byte-for-byte.

    These tests verify the structural prerequisites:
    - Archive recipes generate checksum files
    - ANALYSIS_OUTPUTS is complete
    - Archive scripts list matches Makefile recipe
    """

    def _read_makefile(self):
        with open(MAKEFILE) as f:
            return f.read()

    def test_analysis_archive_has_verify_target(self):
        """The analysis archive Makefile must include a 'verify' target
        that checks md5sums, so reviewers can confirm bit-invariance."""
        archive_mk = os.path.join(REPO, "Makefile.analysis-manuscript")
        with open(archive_mk) as f:
            content = f.read()
        assert re.search(r"^verify\s*:", content, re.MULTILINE), (
            "Makefile.analysis-manuscript must have a 'verify' target "
            "that runs md5sum -c expected_outputs.md5"
        )

    def test_analysis_archive_checksums_cover_all_outputs(self):
        """expected_outputs.md5 must be generated from $(ANALYSIS_OUTPUTS)."""
        mk = self._read_makefile()
        m = re.search(
            r"^archive-analysis\s*:.*?\n((?:\t.*\n?)*)",
            mk, re.MULTILINE,
        )
        assert m, "archive-analysis recipe not found"
        recipe = m.group(1)
        assert "ANALYSIS_OUTPUTS" in recipe, (
            "archive-analysis checksum generation must use $(ANALYSIS_OUTPUTS)"
        )

    def test_archive_scripts_match_recipe(self):
        """Every script copied into the archive must appear in ANALYSIS_OUTPUTS deps
        or the archive recipe. No orphan scripts in the archive."""
        mk = self._read_makefile()
        m = re.search(
            r"^archive-analysis\s*:.*?\n((?:\t.*\n?)*)",
            mk, re.MULTILINE,
        )
        assert m, "archive-analysis recipe not found"
        recipe = m.group(1)
        # Extract all .py files copied
        copied_scripts = re.findall(r"scripts/(\w+\.py)", recipe)
        # Each copied script must either be in the Makefile's dep graph
        # or be a utility (utils.py, plot_style.py)
        utilities = {"utils.py", "plot_style.py"}
        for script in copied_scripts:
            if script in utilities:
                continue
            # Script must appear as a dependency somewhere in the Makefile
            assert script in mk, (
                f"Archive copies {script} but it's not referenced "
                f"in Makefile dependency graph"
            )


# ---------------------------------------------------------------------------
# 7. No bare print() in scripts (existing convention, mechanical check)
# ---------------------------------------------------------------------------

class TestNoBarePrint:
    """Scripts must use logging, not print(). Already clean — prevent regression."""

    def test_no_bare_print(self):
        """No script may use bare print() calls (use log.info() instead)."""
        violators = []
        for name in _all_scripts():
            if name in LIBRARY_SCRIPTS:
                continue
            tree = _parse_script(name)
            for node in ast.walk(tree):
                if (isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "print"):
                    violators.append(name)
                    break
        assert not violators, (
            f"{len(violators)} scripts use bare print() "
            f"(should use logging): {violators[:10]}"
        )
