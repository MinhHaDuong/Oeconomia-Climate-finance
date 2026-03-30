"""Tests for DOI lookup in the teaching pipeline.

Verifies:
- catalog_syllabi uses crossref_lookup with cache for teaching DOI resolution
- enrich_dois provides find_doi for the main corpus pipeline
- CLASSIFY_MODEL and EXTRACT_MODEL env vars are wired at call sites
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


class TestTeachingDOILookup:
    """Verify teaching pipeline uses CrossRef with cache."""

    def test_crossref_lookup_exists(self):
        """catalog_syllabi.py should have crossref_lookup for teaching DOI resolution."""
        import catalog_syllabi
        assert hasattr(catalog_syllabi, "crossref_lookup"), \
            "crossref_lookup should exist — teaching pipeline uses CrossRef"

    def test_crossref_cache_exists(self):
        """catalog_syllabi.py should have CrossRef cache infrastructure."""
        import catalog_syllabi
        assert hasattr(catalog_syllabi, "_load_crossref_cache"), \
            "CrossRef cache loader should exist"

    def test_normalize_stage_uses_crossref(self):
        """stage_normalize implementation should call crossref_lookup.

        After the harvest/process split, the implementation lives in
        syllabi_process; catalog_syllabi.stage_normalize is a thin wrapper.
        """
        import syllabi_process
        source = inspect.getsource(syllabi_process.stage_normalize)
        assert "crossref_lookup" in source, \
            "stage_normalize should call crossref_lookup for DOI resolution"


class TestMainCorpusDOILookup:
    """Verify main corpus pipeline has find_doi."""

    def test_find_doi_exists(self):
        """enrich_dois.py should have find_doi for main corpus."""
        import enrich_dois
        assert hasattr(enrich_dois, "find_doi"), \
            "find_doi should exist in enrich_dois for the main corpus pipeline"


class TestModelEnvVars:
    """Verify per-task LLM model env vars are wired."""

    def test_classify_model_env_var(self):
        """stage_classify implementation should read CLASSIFY_MODEL env var.

        After the harvest/process split, the implementation lives in
        syllabi_process; catalog_syllabi.stage_classify is a thin wrapper.
        """
        import syllabi_process
        source = inspect.getsource(syllabi_process.stage_classify)
        assert "CLASSIFY_MODEL" in source, \
            "stage_classify should use CLASSIFY_MODEL env var for model selection"

    def test_extract_model_env_var(self):
        """stage_extract implementation should read EXTRACT_MODEL env var.

        After the harvest/process split, the implementation lives in
        syllabi_process; catalog_syllabi.stage_extract is a thin wrapper.
        """
        import syllabi_process
        source = inspect.getsource(syllabi_process.stage_extract)
        assert "EXTRACT_MODEL" in source, \
            "stage_extract should use EXTRACT_MODEL env var for model selection"
