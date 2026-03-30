"""Tests for #56: Documentation consistency with Phase 1 contract.

The canonical Phase 1 pipeline artifacts are:
  unified_works.csv  → enriched_works.csv → extended_works.csv → refined_works.csv

Makefile targets:
  corpus-discover → corpus-enrich → corpus-extend → corpus-filter

Docs must:
  1. Name all four intermediate artifacts
  2. Name all four Make targets
  3. Not refer to a 'cheap' pre-filter step occurring before enrichment
  4. Describe Phase 1 as having four steps/phases (not two)
"""

import os
import re

import pytest

ROOT = os.path.join(os.path.dirname(__file__), "..")

AGENTS_MD = os.path.join(ROOT, "AGENTS.md")
CODING_GUIDELINES_MD = os.path.join(ROOT, ".claude", "rules", "coding.md")
ARCHITECTURE_MD = os.path.join(ROOT, ".claude", "rules", "architecture.md")
README_MD = os.path.join(ROOT, "README.md")
CORPUS_CONSTRUCTION_MD = os.path.join(ROOT, "content", "_includes", "corpus-construction.md")
REPRODUCIBILITY_MD = os.path.join(ROOT, "content", "_includes", "reproducibility.md")


def read(path):
    with open(path) as f:
        return f.read()


# ---------------------------------------------------------------------------
# AGENTS.md
# ---------------------------------------------------------------------------

class TestArchitectureMd:
    """Pipeline contract docs live in .claude/rules/architecture.md."""

    def test_all_four_artifacts_mentioned(self):
        """architecture.md must mention all four Phase 1 intermediate artifacts."""
        text = read(ARCHITECTURE_MD)
        for artifact in ["unified_works.csv", "enriched_works.csv",
                         "extended_works.csv", "refined_works.csv"]:
            assert artifact in text, \
                f"architecture.md missing artifact: {artifact}"

    def test_all_four_make_targets_mentioned(self):
        """architecture.md must mention all four corpus Makefile targets."""
        text = read(ARCHITECTURE_MD)
        for target in ["corpus-discover", "corpus-enrich", "corpus-extend", "corpus-filter"]:
            assert target in text, \
                f"architecture.md missing Makefile target: {target}"

    def test_no_cheap_prefilter_as_pipeline_step(self):
        """architecture.md must not describe 'cheap filter' as a step before enrichment."""
        text = read(ARCHITECTURE_MD)
        assert "cheap filter" not in text.lower(), \
            "architecture.md still describes 'cheap filter' as a pipeline step"

    def test_phase1_has_four_steps(self):
        """architecture.md Phase 1 section should describe four steps."""
        text = read(ARCHITECTURE_MD)
        phase1_section = re.search(
            r"Phase 1.*?(?=Phase 2|##|\Z)", text, re.DOTALL | re.IGNORECASE
        )
        assert phase1_section, "architecture.md must have a Phase 1 section"
        section_text = phase1_section.group(0)
        steps_found = sum(
            1 for step in ["discover", "enrich", "extend", "filter"]
            if step in section_text.lower()
        )
        assert steps_found >= 4, (
            f"architecture.md Phase 1 section mentions only {steps_found}/4 pipeline steps "
            f"(discover, enrich, extend, filter)"
        )


# ---------------------------------------------------------------------------
# corpus-construction.md
# ---------------------------------------------------------------------------

class TestCorpusConstructionMd:
    def test_all_four_artifacts_in_diagram_or_prose(self):
        """corpus-construction.md must mention all four Phase 1 intermediate artifacts."""
        text = read(CORPUS_CONSTRUCTION_MD)
        for artifact in ["unified_works.csv", "enriched_works.csv",
                         "extended_works.csv", "refined_works.csv"]:
            assert artifact in text, \
                f"corpus-construction.md missing artifact: {artifact}"

    def test_no_cheap_filter_before_enrich(self):
        """corpus-construction.md must not describe cheap filter as a step before enrichment."""
        text = read(CORPUS_CONSTRUCTION_MD)
        # The old pipeline had:  unified → cheap filter → enrichment → refined
        # The new pipeline has:  unified → enrichment → extend (flag) → filter
        assert "cheap filter" not in text.lower(), \
            "corpus-construction.md still describes 'cheap filter' before enrichment"

    def test_pipeline_diagram_has_four_stages(self):
        """Pipeline diagram/description must include all four stages."""
        text = read(CORPUS_CONSTRUCTION_MD)
        stages_found = sum(
            1 for stage in ["discover", "enrich", "extend", "filter"]
            if stage in text.lower()
        )
        assert stages_found >= 4, (
            f"corpus-construction.md mentions only {stages_found}/4 pipeline stages"
        )


# ---------------------------------------------------------------------------
# reproducibility.md
# ---------------------------------------------------------------------------

class TestReproducibilityMd:
    def test_artifact_table_has_extended_works(self):
        """reproducibility.md artifact/script table must include extended_works.csv."""
        text = read(REPRODUCIBILITY_MD)
        assert "extended_works.csv" in text, \
            "reproducibility.md artifact table missing extended_works.csv"

    def test_artifact_table_has_enriched_works(self):
        """reproducibility.md artifact/script table must include enriched_works.csv."""
        text = read(REPRODUCIBILITY_MD)
        assert "enriched_works.csv" in text, \
            "reproducibility.md artifact table missing enriched_works.csv"

    def test_corpus_filter_shows_split_modes(self):
        """reproducibility.md must show corpus_filter.py --extend and --filter modes."""
        text = read(REPRODUCIBILITY_MD)
        assert "--extend" in text or "extend" in text, \
            "reproducibility.md must document corpus_filter.py --extend mode"
        assert "--filter" in text or ("corpus_filter" in text and "filter" in text), \
            "reproducibility.md must document corpus_filter.py --filter mode"


# ---------------------------------------------------------------------------
# README.md
# ---------------------------------------------------------------------------

class TestReadmeMd:
    """README.md is vision-only; pipeline details live in .claude/rules/coding.md."""

    def test_points_to_coding_rules(self):
        """README.md should reference coding rules for pipeline details."""
        text = read(README_MD)
        assert "coding" in text, \
            "README.md should reference .claude/rules/coding.md"
