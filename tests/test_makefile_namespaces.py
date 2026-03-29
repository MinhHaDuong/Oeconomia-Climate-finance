"""Tests for #510: Namespaced Makefile targets.

Verifies that Makefile targets are organized by concern:
  corpus-*     Phase 1 (collection, enrichment, alignment)
  analysis-*   Phase 2 (embeddings, clustering, breaks, figures)
  manuscript-* Phase 3 (Oeconomia rendering)
  datapaper-*  Phase 3 (RDJ4HSS rendering)
"""

import os
import re

MAKEFILE = os.path.join(os.path.dirname(__file__), "..", "Makefile")


def _read_makefile():
    with open(MAKEFILE) as f:
        return f.read()


class TestNamespacedTargets:
    """All four concern namespaces have targets in the Makefile."""

    def test_corpus_targets_exist(self):
        mk = _read_makefile()
        assert re.search(r"^corpus-\w+\s*:", mk, re.MULTILINE), (
            "No corpus-* target found"
        )

    def test_analysis_targets_exist(self):
        mk = _read_makefile()
        assert re.search(r"^analysis-\w+\s*:", mk, re.MULTILINE), (
            "No analysis-* target found"
        )

    def test_manuscript_targets_exist(self):
        mk = _read_makefile()
        assert re.search(r"^manuscript-\w+\s*:", mk, re.MULTILINE), (
            "No manuscript-* target found"
        )

    def test_datapaper_targets_exist(self):
        mk = _read_makefile()
        assert re.search(r"^datapaper-\w+\s*:", mk, re.MULTILINE), (
            "No datapaper-* target found"
        )

    def test_phony_includes_namespaced(self):
        """All namespace prefixes appear in .PHONY declaration."""
        mk = _read_makefile()
        phony_lines = re.findall(r"\.PHONY:.*", mk)
        phony_text = " ".join(phony_lines)
        for prefix in ["corpus-", "analysis-", "manuscript-", "datapaper-"]:
            assert prefix in phony_text, (
                f"No {prefix}* target in .PHONY declaration"
            )
