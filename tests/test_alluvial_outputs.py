"""Tests for issue #73: one-output-per-script principle for alluvial pipeline.

Tests verify (via static analysis — no data required):
- compute_breakpoints.py, compute_clusters.py, compute_lexical.py contain no
  save_figure() or plt.savefig() calls (compute scripts must not write figures)
- Makefile no longer routes compute_alluvial.py as a compute target
- Makefile declares the new split targets: compute_breakpoints.py + compute_clusters.py
- New plot scripts (plot_fig_k_sensitivity.py, plot_fig_lexical_tfidf.py) exist
- analyze_alluvial.py documents its deprecation horizon
"""

import os
import re

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
MAKEFILE = os.path.join(os.path.dirname(__file__), "..", "Makefile")


def read_script(name):
    with open(os.path.join(SCRIPTS_DIR, name)) as f:
        return f.read()


def read_makefile():
    with open(MAKEFILE) as f:
        return f.read()


# ---------------------------------------------------------------------------
# Compute scripts must not call save_figure() or plt.savefig()
# ---------------------------------------------------------------------------

class TestComputeScriptsNoFigures:
    """Compute scripts must not produce figure files."""

    def _assert_no_figure_calls(self, script_name):
        src = read_script(script_name)
        assert "save_figure(" not in src, (
            f"{script_name} calls save_figure() — compute scripts must not write figures. "
            "Move figure generation to a plot_*.py script."
        )
        assert "plt.savefig(" not in src, (
            f"{script_name} calls plt.savefig() — compute scripts must not write figures. "
            "Move figure generation to a plot_*.py script."
        )
        # Also check for fig.savefig pattern
        assert not re.search(r"\bfig\w*\.savefig\s*\(", src), (
            f"{script_name} calls .savefig() on a figure object. "
            "Move figure generation to a plot_*.py script."
        )

    def test_compute_breakpoints_no_figures(self):
        self._assert_no_figure_calls("compute_breakpoints.py")

    def test_compute_clusters_no_figures(self):
        self._assert_no_figure_calls("compute_clusters.py")

    def test_compute_lexical_no_figures(self):
        self._assert_no_figure_calls("compute_lexical.py")


# ---------------------------------------------------------------------------
# New scripts exist
# ---------------------------------------------------------------------------

class TestNewScriptsExist:
    def test_compute_breakpoints_exists(self):
        assert os.path.exists(os.path.join(SCRIPTS_DIR, "compute_breakpoints.py")), \
            "compute_breakpoints.py not found"

    def test_compute_clusters_exists(self):
        assert os.path.exists(os.path.join(SCRIPTS_DIR, "compute_clusters.py")), \
            "compute_clusters.py not found"

    def test_compute_lexical_exists(self):
        assert os.path.exists(os.path.join(SCRIPTS_DIR, "compute_lexical.py")), \
            "compute_lexical.py not found"

    def test_plot_fig_k_sensitivity_exists(self):
        assert os.path.exists(os.path.join(SCRIPTS_DIR, "plot_fig_k_sensitivity.py")), \
            "plot_fig_k_sensitivity.py not found"

    def test_plot_fig_lexical_tfidf_exists(self):
        assert os.path.exists(os.path.join(SCRIPTS_DIR, "plot_fig_lexical_tfidf.py")), \
            "plot_fig_lexical_tfidf.py not found"


# ---------------------------------------------------------------------------
# Makefile: new targets declared, old compute_alluvial.py rule removed
# ---------------------------------------------------------------------------

class TestMakefileTargets:
    def test_compute_breakpoints_is_makefile_prerequisite(self):
        mk = read_makefile()
        # Script appears as a prerequisite (Makefile uses $< so the script name
        # appears in the dependency list, not literally in the recipe line)
        assert re.search(r"scripts/compute_breakpoints\.py", mk), \
            "compute_breakpoints.py not referenced in Makefile as a prerequisite"
        # The rule it appears in must have a uv run recipe in the vicinity
        assert re.search(
            r"compute_breakpoints\.py[^\n]*\n(?:[^\n]*\n)*?\tuv run python \$<",
            mk
        ), "No uv run python $< recipe found after a rule listing compute_breakpoints.py"

    def test_compute_clusters_is_makefile_prerequisite(self):
        mk = read_makefile()
        assert re.search(r"scripts/compute_clusters\.py", mk), \
            "compute_clusters.py not referenced in Makefile as a prerequisite"
        assert re.search(
            r"compute_clusters\.py[^\n]*\n(?:[^\n]*\n)*?\tuv run python \$<",
            mk
        ), "No uv run python $< recipe found after a rule listing compute_clusters.py"

    def test_compute_alluvial_not_a_makefile_compute_target(self):
        """compute_alluvial.py must no longer be the recipe for any compute target.
        It may still appear as a dependency or comment, but not as a uv run recipe
        driving a table target.
        """
        mk = read_makefile()
        # A recipe line invoking compute_alluvial.py means we forgot to migrate
        recipe_lines = [
            line for line in mk.splitlines()
            if line.startswith("\tuv run python") and "compute_alluvial.py" in line
        ]
        assert len(recipe_lines) == 0, (
            f"compute_alluvial.py still used as a Makefile recipe in {len(recipe_lines)} rule(s):\n"
            + "\n".join(recipe_lines)
        )

    def test_tab_breakpoints_has_explicit_target(self):
        mk = read_makefile()
        assert "tab_breakpoints.csv" in mk, \
            "tab_breakpoints.csv not declared in Makefile"

    def test_tab_alluvial_has_explicit_target(self):
        mk = read_makefile()
        assert "tab_alluvial.csv" in mk, \
            "tab_alluvial.csv not declared in Makefile"

    def test_tab_lexical_tfidf_has_explicit_target(self):
        mk = read_makefile()
        assert "tab_lexical_tfidf.csv" in mk, \
            "tab_lexical_tfidf.csv not declared as a Makefile target (was previously undeclared)"

    def test_tab_k_sensitivity_has_explicit_target(self):
        mk = read_makefile()
        assert "tab_k_sensitivity.csv" in mk, \
            "tab_k_sensitivity.csv not declared as a Makefile target (was previously undeclared)"

    def test_fig_k_sensitivity_has_explicit_target(self):
        mk = read_makefile()
        assert "fig_k_sensitivity.png" in mk, \
            "fig_k_sensitivity.png not declared as a Makefile target"

    def test_lexical_figures_phony_target(self):
        mk = read_makefile()
        assert "lexical-figures" in mk, \
            "lexical-figures phony target not in Makefile"


# ---------------------------------------------------------------------------
# Deprecation policy: compute_alluvial.py and analyze_alluvial.py
# ---------------------------------------------------------------------------

class TestDeprecationDocs:
    def test_compute_alluvial_is_shim(self):
        src = read_script("compute_alluvial.py")
        assert "DEPRECATED" in src or "shim" in src.lower(), \
            "compute_alluvial.py should document that it is a backward-compat shim"

    def test_analyze_alluvial_documents_removal_milestone(self):
        src = read_script("analyze_alluvial.py")
        assert "v1.0" in src or "milestone" in src.lower(), \
            "analyze_alluvial.py should document its removal horizon (e.g. 'v1.0 milestone')"

    def test_compute_alluvial_shim_calls_compute_breakpoints(self):
        src = read_script("compute_alluvial.py")
        assert "compute_breakpoints.py" in src, \
            "compute_alluvial.py shim should delegate to compute_breakpoints.py"

    def test_compute_alluvial_shim_calls_compute_clusters(self):
        src = read_script("compute_alluvial.py")
        assert "compute_clusters.py" in src, \
            "compute_alluvial.py shim should delegate to compute_clusters.py"


# ---------------------------------------------------------------------------
# Argparse strictness: no parse_known_args in compute scripts
# ---------------------------------------------------------------------------

class TestArgparseStrictness:
    """Compute scripts must use parse_args() so typos are caught."""

    def test_compute_breakpoints_strict_args(self):
        src = read_script("compute_breakpoints.py")
        assert "parse_known_args" not in src, \
            "compute_breakpoints.py should use parse_args() for strict flag checking"

    def test_compute_clusters_strict_args(self):
        src = read_script("compute_clusters.py")
        assert "parse_known_args" not in src, \
            "compute_clusters.py should use parse_args() for strict flag checking"

    def test_compute_lexical_strict_args(self):
        src = read_script("compute_lexical.py")
        assert "parse_known_args" not in src, \
            "compute_lexical.py should use parse_args() for strict flag checking"

    def test_compute_lexical_has_main_guard(self):
        src = read_script("compute_lexical.py")
        assert "if __name__" in src, \
            "compute_lexical.py needs __main__ guard for importability"
