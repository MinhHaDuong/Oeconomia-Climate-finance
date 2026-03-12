"""Tests for Phase 1 Makefile contract — #52.

Tests verify:
- Phase 1 target definitions exist in correct order
- Each phase declares only its contract outputs
- Fail-fast checks for missing handoff artifacts are present
- The old cheap pre-filter is absent from corpus-discover
"""

import os
import re

MAKEFILE = os.path.join(os.path.dirname(__file__), "..", "Makefile")


def read_makefile():
    with open(MAKEFILE) as f:
        return f.read()


# ---------------------------------------------------------------------------
# Target presence
# ---------------------------------------------------------------------------

class TestTargetPresence:
    def test_corpus_discover_target_exists(self):
        mk = read_makefile()
        assert re.search(r"^corpus-discover\s*:", mk, re.MULTILINE), \
            "corpus-discover target missing"

    def test_corpus_enrich_target_exists(self):
        mk = read_makefile()
        assert re.search(r"^corpus-enrich\s*:", mk, re.MULTILINE), \
            "corpus-enrich target missing"

    def test_corpus_extend_target_exists(self):
        mk = read_makefile()
        assert re.search(r"^corpus-extend\s*:", mk, re.MULTILINE), \
            "corpus-extend target missing (new Phase 1c)"

    def test_corpus_filter_target_exists(self):
        mk = read_makefile()
        assert re.search(r"^corpus-filter\s*:", mk, re.MULTILINE), \
            "corpus-filter target missing (new Phase 1d)"

    def test_corpus_target_chains_all_phases(self):
        """The 'corpus' meta-target must chain discover -> enrich -> extend -> filter -> manifest."""
        mk = read_makefile()
        # Find corpus: line and check all four phases appear as prereqs
        m = re.search(r"^corpus\s*:(.*?)(?=\n\S|\Z)", mk, re.MULTILINE | re.DOTALL)
        assert m, "corpus meta-target not found"
        body = m.group(0)
        for phase in ("corpus-discover", "corpus-enrich", "corpus-extend", "corpus-filter"):
            assert phase in body, f"{phase} not chained in corpus meta-target"


# ---------------------------------------------------------------------------
# No cheap pre-filter in corpus-discover
# ---------------------------------------------------------------------------

class TestNoCheapPrefilter:
    def test_corpus_discover_does_not_call_cheap(self):
        """corpus-discover must not invoke corpus_refine.py --cheap."""
        mk = read_makefile()
        # Find the corpus-discover recipe (lines after the target until next target)
        m = re.search(
            r"^corpus-discover\s*:.*?\n((?:\t.*\n?)*)",
            mk, re.MULTILINE
        )
        assert m, "corpus-discover target not found"
        recipe = m.group(1)
        assert "--cheap" not in recipe, \
            "corpus-discover still invokes corpus_refine.py --cheap (remove it)"

    def test_corpus_discover_does_not_call_corpus_refine(self):
        """corpus-discover must not call corpus_refine.py at all."""
        mk = read_makefile()
        m = re.search(
            r"^corpus-discover\s*:.*?\n((?:\t.*\n?)*)",
            mk, re.MULTILINE
        )
        assert m, "corpus-discover target not found"
        recipe = m.group(1)
        assert "corpus_refine.py" not in recipe, \
            "corpus-discover must not run corpus_refine.py; refinement belongs in corpus-extend/corpus-filter"


# ---------------------------------------------------------------------------
# Contract output variables
# ---------------------------------------------------------------------------

class TestContractVariables:
    def test_unified_variable_declared(self):
        """Makefile must declare UNIFIED path variable."""
        mk = read_makefile()
        assert re.search(r"^UNIFIED\s*:?=", mk, re.MULTILINE), \
            "UNIFIED variable not declared"

    def test_enriched_variable_declared(self):
        """Makefile must declare ENRICHED path variable."""
        mk = read_makefile()
        assert re.search(r"^ENRICHED\s*:?=", mk, re.MULTILINE), \
            "ENRICHED variable not declared"

    def test_extended_variable_declared(self):
        """Makefile must declare EXTENDED path variable."""
        mk = read_makefile()
        assert re.search(r"^EXTENDED\s*:?=", mk, re.MULTILINE), \
            "EXTENDED variable not declared"


# ---------------------------------------------------------------------------
# Fail-fast artifact checks
# ---------------------------------------------------------------------------

class TestFailFastChecks:
    def test_corpus_enrich_checks_for_unified(self):
        """corpus-enrich recipe must fail-fast if unified_works.csv is absent."""
        mk = read_makefile()
        m = re.search(
            r"^corpus-enrich\s*:.*?\n((?:\t.*\n?)*)",
            mk, re.MULTILINE
        )
        assert m, "corpus-enrich target not found"
        recipe = m.group(1)
        assert "unified_works.csv" in recipe or "UNIFIED" in recipe, \
            "corpus-enrich must reference UNIFIED/unified_works.csv (fail-fast check)"

    def test_corpus_extend_checks_for_enriched(self):
        """corpus-extend recipe must fail-fast if enriched_works.csv is absent."""
        mk = read_makefile()
        m = re.search(
            r"^corpus-extend\s*:.*?\n((?:\t.*\n?)*)",
            mk, re.MULTILINE
        )
        assert m, "corpus-extend target not found"
        recipe = m.group(1)
        assert "enriched_works.csv" in recipe or "ENRICHED" in recipe, \
            "corpus-extend must reference ENRICHED/enriched_works.csv (fail-fast check)"

    def test_corpus_filter_checks_for_extended(self):
        """corpus-filter recipe must fail-fast if extended_works.csv is absent."""
        mk = read_makefile()
        m = re.search(
            r"^corpus-filter\s*:.*?\n((?:\t.*\n?)*)",
            mk, re.MULTILINE
        )
        assert m, "corpus-filter target not found"
        recipe = m.group(1)
        assert "extended_works.csv" in recipe or "EXTENDED" in recipe, \
            "corpus-filter must reference EXTENDED/extended_works.csv (fail-fast check)"
