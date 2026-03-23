"""Tests for crossref_lookup removal and resolve_doi integration.

Verifies:
- crossref_lookup is no longer defined in collect_syllabi.py
- stage_normalize uses resolve_doi from enrich_dois (not CrossRef)
- CLASSIFY_MODEL and EXTRACT_MODEL env vars are wired at call sites
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


class TestCrossrefRemoval:
    """Verify crossref_lookup is removed from collect_syllabi.py."""

    def test_no_crossref_lookup_function(self):
        """crossref_lookup should not be defined in collect_syllabi.py."""
        import collect_syllabi
        assert not hasattr(collect_syllabi, "crossref_lookup"), \
            "crossref_lookup should be removed — resolve_doi replaces it"

    def test_no_crossref_api_reference(self):
        """collect_syllabi.py should not reference api.crossref.org."""
        import collect_syllabi
        source = inspect.getsource(collect_syllabi)
        assert "crossref.org" not in source, \
            "CrossRef API reference should be removed — OpenAlex is the sole resolver"

    def test_normalize_stage_uses_resolve_doi(self):
        """stage_normalize should call resolve_doi, not crossref_lookup."""
        import collect_syllabi
        source = inspect.getsource(collect_syllabi.stage_normalize)
        assert "resolve_doi" in source, \
            "stage_normalize should call resolve_doi from enrich_dois"
        assert "crossref_lookup" not in source, \
            "stage_normalize should not reference crossref_lookup"


class TestModelEnvVars:
    """Verify per-task LLM model env vars are wired."""

    def test_classify_model_env_var(self):
        """stage_classify should read CLASSIFY_MODEL env var."""
        import collect_syllabi
        source = inspect.getsource(collect_syllabi.stage_classify)
        assert "CLASSIFY_MODEL" in source, \
            "stage_classify should use CLASSIFY_MODEL env var for model selection"

    def test_extract_model_env_var(self):
        """stage_extract should read EXTRACT_MODEL env var."""
        import collect_syllabi
        source = inspect.getsource(collect_syllabi.stage_extract)
        assert "EXTRACT_MODEL" in source, \
            "stage_extract should use EXTRACT_MODEL env var for model selection"
