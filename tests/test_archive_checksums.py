"""Tests for #210 — expected output checksums in analysis archive.

Verifies the Makefile archive-analysis recipe:
1. Generates an expected_outputs.md5 checksum file in the staging dir
2. The checksum file covers all expected output paths
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


def _archive_recipe():
    """Extract the archive-analysis recipe body from the Makefile."""
    with open(MAKEFILE) as f:
        mk = f.read()
    m = re.search(
        r"^archive-analysis\s*:.*?\n((?:\t.*\n?)*)",
        mk,
        re.MULTILINE,
    )
    assert m, "archive-analysis target not found in Makefile"
    return m.group(1)


class TestArchiveChecksums:
    def test_recipe_generates_checksum_file(self):
        """archive-analysis must create expected_outputs.md5."""
        recipe = _archive_recipe()
        assert "expected_outputs.md5" in recipe, (
            "archive-analysis recipe must generate expected_outputs.md5"
        )

    def test_checksum_file_covers_all_outputs(self):
        """Every expected output path must appear in the md5sum command."""
        recipe = _archive_recipe()
        for path in EXPECTED_OUTPUTS:
            assert path in recipe, (
                f"archive-analysis recipe must checksum {path}"
            )
