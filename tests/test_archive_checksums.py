"""Tests for #210 — expected output checksums in analysis archive.

Verifies the Makefile:
1. Declares ANALYSIS_OUTPUTS covering all expected output paths
2. Uses ANALYSIS_OUTPUTS as prerequisites of archive-analysis
3. Generates expected_outputs.md5 in the archive staging dir
"""

import os
import re

MAKEFILE = os.path.join(os.path.dirname(__file__), "..", "Makefile")

# The outputs that reviewers must be able to verify (from ticket #210).
EXPECTED_OUTPUTS = [
    "content/figures/fig_bars.png",
    "content/figures/fig_composition.png",
    "content/_includes/tab_venues.md",
    "content/tables/tab_alluvial.csv",
    "content/tables/tab_core_shares.csv",
    "content/tables/tab_bimodality.csv",
    "content/tables/tab_axis_detection.csv",
    "content/tables/tab_pole_papers.csv",
    "content/tables/cluster_labels.json",
]


def _read_makefile():
    with open(MAKEFILE) as f:
        return f.read()


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
