"""Tests for analysis archive: checksums (#210) and Dockerfile (#214).

Verifies the Makefile:
1. Declares ANALYSIS_OUTPUTS covering all expected output paths
2. Uses ANALYSIS_OUTPUTS as prerequisites of archive-analysis
3. Generates expected_outputs.md5 in the archive staging dir
4. Ships a Dockerfile consistent with the archive's Makefile
"""

import os
import re

from makefile_helper import read_makefile as _read_makefile

PROJECT_ROOT = os.path.join(os.path.dirname(__file__), "..")
DOCKERFILE = os.path.join(PROJECT_ROOT, "Dockerfile.analysis")
MAKEFILE_ANALYSIS = os.path.join(PROJECT_ROOT, "Makefile.analysis-manuscript")

# The outputs that reviewers must be able to verify (from ticket #210).
EXPECTED_OUTPUTS = [
    "content/figures/fig_bars.png",
    "content/figures/fig_composition.png",
    "content/tables/tab_venues.md",
    "content/tables/tab_alluvial.csv",
    "content/tables/tab_core_shares.csv",
    "content/tables/tab_bimodality.csv",
    "content/tables/tab_axis_detection.csv",
    "content/tables/tab_pole_papers.csv",
    "content/tables/cluster_labels.json",
]


class TestAnalysisOutputsVariable:
    """ANALYSIS_OUTPUTS must list every output reviewers need to verify."""

    def test_variable_declared(self):
        mk = _read_makefile()
        assert re.search(r"^ANALYSIS_OUTPUTS\s*:?=", mk, re.MULTILINE), \
            "ANALYSIS_OUTPUTS variable not declared"

    def test_variable_covers_all_outputs(self):
        mk = _read_makefile()
        for path in EXPECTED_OUTPUTS:
            assert path in mk, (
                f"ANALYSIS_OUTPUTS must include {path}"
            )


    def test_no_includes_in_outputs(self):
        """ANALYSIS_OUTPUTS must not reference content/_includes/ (Phase 2 outputs live in content/tables/)."""
        mk = _read_makefile()
        m = re.search(
            r"^ANALYSIS_OUTPUTS\s*:?=(.*?)(?=\n\S|\Z)",
            mk,
            re.MULTILINE | re.DOTALL,
        )
        assert m, "ANALYSIS_OUTPUTS variable not found"
        value = m.group(1)
        assert "_includes/" not in value, (
            "ANALYSIS_OUTPUTS must not reference content/_includes/ — "
            "generated tables live in content/tables/"
        )


class TestArchiveScripts:
    """archive-analysis must copy all scripts needed to reproduce outputs."""

    def test_export_citation_coverage_copied(self):
        mk = _read_makefile()
        m = re.search(
            r"^archive-analysis\s*:.*?\n((?:\t.*\n?)*)",
            mk,
            re.MULTILINE,
        )
        assert m, "archive-analysis recipe not found"
        recipe = m.group(1)
        assert "export_citation_coverage.py" in recipe, (
            "archive-analysis must copy export_citation_coverage.py"
        )


class TestArchiveChecksums:
    """archive-analysis must depend on outputs and generate checksums."""

    def test_archive_depends_on_outputs(self):
        """archive-analysis prerequisites must include $(ANALYSIS_OUTPUTS)."""
        mk = _read_makefile()
        m = re.search(r"^archive-analysis\s*:(.*?)$", mk, re.MULTILINE)
        assert m, "archive-analysis target not found"
        deps = m.group(1)
        assert "ANALYSIS_OUTPUTS" in deps, (
            "archive-analysis must depend on $(ANALYSIS_OUTPUTS)"
        )

    def test_recipe_generates_checksum_file(self):
        """archive-analysis must create expected_outputs.md5."""
        mk = _read_makefile()
        m = re.search(
            r"^archive-analysis\s*:.*?\n((?:\t.*\n?)*)",
            mk,
            re.MULTILINE,
        )
        assert m, "archive-analysis recipe not found"
        recipe = m.group(1)
        assert "expected_outputs.md5" in recipe, (
            "archive-analysis recipe must generate expected_outputs.md5"
        )


def _read_dockerfile():
    with open(DOCKERFILE) as f:
        return f.read()


def _read_makefile_analysis():
    with open(MAKEFILE_ANALYSIS) as f:
        return f.read()


class TestDockerfileAnalysis:
    """Dockerfile.analysis must be consistent with the archive layout."""

    def test_dockerfile_exists(self):
        assert os.path.isfile(DOCKERFILE), "Dockerfile.analysis missing"

    def test_archive_ships_dockerfile(self):
        """archive-analysis recipe must copy Dockerfile.analysis into the archive."""
        mk = _read_makefile()
        m = re.search(
            r"^archive-analysis\s*:.*?\n((?:\t.*\n?)*)",
            mk,
            re.MULTILINE,
        )
        assert m, "archive-analysis recipe not found"
        recipe = m.group(1)
        assert "Dockerfile.analysis" in recipe, (
            "archive-analysis must copy Dockerfile.analysis into archive"
        )

    def test_installs_uv(self):
        """Dockerfile must install uv (the archive uses uv sync / uv run)."""
        df = _read_dockerfile()
        assert "uv" in df, "Dockerfile must install uv"

    def test_installs_make(self):
        """Dockerfile must install make (the archive runs make && make verify)."""
        df = _read_dockerfile()
        assert "make" in df, "Dockerfile must install make"

    def test_cmd_runs_make_and_verify(self):
        """Dockerfile CMD must run both make and make verify."""
        df = _read_dockerfile()
        assert "make" in df and "verify" in df, (
            "Dockerfile CMD must run make and make verify"
        )

    def test_cmd_targets_exist_in_analysis_makefile(self):
        """Every make target in Dockerfile CMD must exist in Makefile.analysis-manuscript."""
        df = _read_dockerfile()
        mk_analysis = _read_makefile_analysis()
        # Extract targets from CMD line: expect "make" and "make verify"
        # Verify that 'figures' (default goal) and 'verify' targets exist
        assert re.search(r"^\.DEFAULT_GOAL\s*:=", mk_analysis, re.MULTILINE), (
            "Makefile.analysis-manuscript must define .DEFAULT_GOAL"
        )
        assert re.search(r"^verify\s*:", mk_analysis, re.MULTILINE), (
            "Makefile.analysis-manuscript must have a 'verify' target "
            "(Dockerfile CMD runs 'make verify')"
        )

    def test_runs_uv_sync(self):
        """Dockerfile must run uv sync before CMD (dependencies must be installed at build time)."""
        df = _read_dockerfile()
        assert "uv sync" in df, (
            "Dockerfile must run 'uv sync' to install dependencies at build time"
        )
