"""Tests for Phase 1 Makefile contract — #52, updated for DVC delegation (#129).

Tests verify:
- Phase 1 target definitions exist in correct order
- corpus meta-target delegates to run_corpus_pipeline.sh (which calls dvc repro)
- Artifact dependency contracts are expressed in dvc.yaml (not Makefile recipes)
- The old cheap pre-filter is absent from corpus-discover
"""

import os
import re
from pathlib import Path

import yaml

MAKEFILE = os.path.join(os.path.dirname(__file__), "..", "Makefile")
DVC_YAML = os.path.join(os.path.dirname(__file__), "..", "dvc.yaml")


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

    def test_corpus_target_delegates_to_script(self):
        """The 'corpus' meta-target must delegate to run_corpus_pipeline.sh.

        The pipeline logic (guards, dvc repro, auto-commit) lives in a
        standalone bash script for testability and readability. The Makefile
        simply invokes it.
        """
        mk = read_makefile()
        m = re.search(r"^corpus\s*:(.*?)(?=\n\S|\Z)", mk, re.MULTILINE | re.DOTALL)
        assert m, "corpus meta-target not found"
        body = m.group(0)
        assert "run_corpus_pipeline.sh" in body, \
            "corpus meta-target must delegate to scripts/run_corpus_pipeline.sh"

    def test_corpus_pipeline_script_calls_dvc_repro(self):
        """The extracted corpus pipeline script must call 'dvc repro'.

        Since DVC owns the dependency graph (dvc.yaml), the script must
        delegate to 'dvc repro' rather than chaining individual phase targets.
        """
        script = (Path(__file__).resolve().parent.parent / "scripts" / "run_corpus_pipeline.sh").read_text()
        assert "dvc repro" in script, \
            "run_corpus_pipeline.sh must call 'dvc repro' (DVC owns the pipeline DAG)"


# ---------------------------------------------------------------------------
# No cheap pre-filter in corpus-discover
# ---------------------------------------------------------------------------

class TestNoCheapPrefilter:
    def test_corpus_discover_does_not_call_cheap(self):
        """corpus-discover must not invoke corpus_filter.py --cheap."""
        mk = read_makefile()
        # Find the corpus-discover recipe (lines after the target until next target)
        m = re.search(
            r"^corpus-discover\s*:.*?\n((?:\t.*\n?)*)",
            mk, re.MULTILINE
        )
        assert m, "corpus-discover target not found"
        recipe = m.group(1)
        assert "--cheap" not in recipe, \
            "corpus-discover still invokes corpus_filter.py --cheap (remove it)"

    def test_corpus_discover_does_not_call_corpus_filter(self):
        """corpus-discover must not call corpus_filter.py at all."""
        mk = read_makefile()
        m = re.search(
            r"^corpus-discover\s*:.*?\n((?:\t.*\n?)*)",
            mk, re.MULTILINE
        )
        assert m, "corpus-discover target not found"
        recipe = m.group(1)
        assert "corpus_filter.py" not in recipe, \
            "corpus-discover must not run corpus_filter.py; filtering belongs in corpus-extend/corpus-filter"


# ---------------------------------------------------------------------------
# Contract output variables
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# DVC YAML cmd sanity
# ---------------------------------------------------------------------------

class TestDvcYamlCmds:
    """Each stage cmd must be a valid single-line shell command (no embedded newlines)."""

    def test_no_newlines_in_cmds(self):
        """YAML >- with extra-indented lines preserves newlines, breaking shell commands."""
        dvc_path = os.path.join(os.path.dirname(__file__), "..", "dvc.yaml")
        with open(dvc_path) as f:
            dvc = yaml.safe_load(f)
        for name, spec in dvc["stages"].items():
            cmd = spec.get("cmd", "")
            assert "\n" not in cmd, (
                f"Stage '{name}' cmd contains newlines — "
                f"YAML >- preserves them for extra-indented lines. "
                f"Put each command on one line."
            )


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
# Artifact dependency checks (now in dvc.yaml, not Makefile recipes)
# ---------------------------------------------------------------------------

def read_dvc_yaml():
    with open(DVC_YAML) as f:
        return yaml.safe_load(f)


class TestFailFastChecks:
    def test_corpus_enrich_checks_for_unified(self):
        """dvc.yaml enrich_works stage must declare unified_works.csv as a dependency.

        Previously the Makefile corpus-enrich recipe contained a fail-fast check.
        Now DVC owns the dependency graph: the contract is expressed in dvc.yaml
        deps, which DVC enforces before running the stage.
        """
        dvc = read_dvc_yaml()
        assert "enrich_works" in dvc.get("stages", {}), \
            "enrich_works stage missing from dvc.yaml"
        deps = dvc["stages"]["enrich_works"].get("deps", [])
        dep_paths = [str(d) for d in deps]
        assert any("unified_works.csv" in p for p in dep_paths), \
            "dvc.yaml enrich_works stage must list unified_works.csv in deps"

    def test_corpus_extend_checks_for_enriched(self):
        """dvc.yaml extend stage must declare enriched_works.csv as a dependency.

        Previously the Makefile corpus-extend recipe contained a fail-fast check.
        Now DVC owns the dependency graph: the contract is expressed in dvc.yaml
        deps, which DVC enforces before running the stage.
        """
        dvc = read_dvc_yaml()
        assert "extend" in dvc.get("stages", {}), "extend stage missing from dvc.yaml"
        deps = dvc["stages"]["extend"].get("deps", [])
        dep_paths = [str(d) for d in deps]
        assert any("enriched_works.csv" in p for p in dep_paths), \
            "dvc.yaml extend stage must list enriched_works.csv in deps"

    def test_corpus_filter_checks_for_extended(self):
        """dvc.yaml filter stage must declare extended_works.csv as a dependency.

        Previously the Makefile corpus-filter recipe contained a fail-fast check.
        Now DVC owns the dependency graph: the contract is expressed in dvc.yaml
        deps, which DVC enforces before running the stage.
        """
        dvc = read_dvc_yaml()
        assert "filter" in dvc.get("stages", {}), "filter stage missing from dvc.yaml"
        deps = dvc["stages"]["filter"].get("deps", [])
        dep_paths = [str(d) for d in deps]
        assert any("extended_works.csv" in p for p in dep_paths), \
            "dvc.yaml filter stage must list extended_works.csv in deps"


# ---------------------------------------------------------------------------
# Quarto project-wide include resolution (#217)
# ---------------------------------------------------------------------------

class TestProjectWideIncludes:
    """Quarto resolves includes across ALL project files, even when rendering
    a single document. Every render target must depend on all includes."""

    def test_citation_coverage_in_techrep_includes(self):
        """tab_citation_coverage.md is included transitively via citation-quality.md."""
        mk = read_makefile()
        m = re.search(r"^TECHREP_INCLUDES\s*:=\s*(.*?)(?=\n\S|\n\n)", mk,
                       re.MULTILINE | re.DOTALL)
        assert m, "TECHREP_INCLUDES not found"
        assert "tab_citation_coverage.md" in m.group(1), \
            "TECHREP_INCLUDES must list tab_citation_coverage.md (transitive dep of citation-quality.md)"

    def test_project_includes_variable_exists(self):
        """A PROJECT_INCLUDES variable must aggregate all per-document include sets."""
        mk = read_makefile()
        assert re.search(r"^PROJECT_INCLUDES\s*:?=", mk, re.MULTILINE), \
            "PROJECT_INCLUDES variable not declared"

    def test_manuscript_pdf_depends_on_project_includes(self):
        """manuscript.pdf must depend on PROJECT_INCLUDES, not just MANUSCRIPT_INCLUDES."""
        mk = read_makefile()
        m = re.search(r"^output/content/manuscript\.pdf\s*:(.*?)$", mk, re.MULTILINE)
        assert m, "manuscript.pdf target not found"
        assert "PROJECT_INCLUDES" in m.group(1), \
            "manuscript.pdf must depend on $(PROJECT_INCLUDES)"

    def test_techrep_pdf_depends_on_project_includes(self):
        """technical-report.pdf must depend on PROJECT_INCLUDES."""
        mk = read_makefile()
        m = re.search(r"^output/content/technical-report\.pdf\s*:(.*?)$", mk, re.MULTILINE)
        assert m, "technical-report.pdf target not found"
        assert "PROJECT_INCLUDES" in m.group(1), \
            "technical-report.pdf must depend on $(PROJECT_INCLUDES)"


# ---------------------------------------------------------------------------
# Manuscript archive checksums (#219)
# ---------------------------------------------------------------------------

class TestManuscriptArchiveChecksums:
    """Manuscript archive must ship checksums for inputs and output PDF."""

    def test_archive_manuscript_generates_checksums(self):
        """archive-manuscript recipe must produce a checksums file."""
        mk = read_makefile()
        m = re.search(
            r"^archive-manuscript\s*:.*?\n((?:\t.*\n?)*)",
            mk, re.MULTILINE,
        )
        assert m, "archive-manuscript target not found"
        recipe = m.group(1)
        assert "md5sum" in recipe, \
            "archive-manuscript must run md5sum to generate checksums"

    def test_archive_manuscript_includes_pdf(self):
        """archive-manuscript recipe must copy the built PDF into the archive."""
        mk = read_makefile()
        m = re.search(
            r"^archive-manuscript\s*:.*?\n((?:\t.*\n?)*)",
            mk, re.MULTILINE,
        )
        assert m, "archive-manuscript target not found"
        recipe = m.group(1)
        assert "manuscript.pdf" in recipe, \
            "archive-manuscript must include the built manuscript.pdf"
