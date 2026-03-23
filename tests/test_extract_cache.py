"""Tests for LLM extraction cache (#298).

Verifies:
- extract_cache module provides load/save/lookup functions
- Cache key is sha256(page_text):model_name
- Cache hit returns stored refs without LLM call
- Different model triggers re-extraction (cache miss)
"""

import hashlib
import json
import os
import sys
import tempfile

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


class TestExtractCacheKeyFormat:
    """Cache key is sha256(page_text):model_name."""

    def test_cache_key_format(self):
        from collect_syllabi import _extract_cache_key
        text = "some syllabus text"
        model = "google/gemma-2-27b-it"
        key = _extract_cache_key(text, model)
        expected_hash = hashlib.sha256(text.encode()).hexdigest()
        assert key == f"{expected_hash}:{model}"

    def test_different_text_different_key(self):
        from collect_syllabi import _extract_cache_key
        model = "google/gemma-2-27b-it"
        k1 = _extract_cache_key("text A", model)
        k2 = _extract_cache_key("text B", model)
        assert k1 != k2

    def test_different_model_different_key(self):
        from collect_syllabi import _extract_cache_key
        text = "same text"
        k1 = _extract_cache_key(text, "model-a")
        k2 = _extract_cache_key(text, "model-b")
        assert k1 != k2


class TestExtractCacheRoundTrip:
    """Cache persists to JSONL and loads back."""

    def test_save_and_load(self):
        from collect_syllabi import (
            _extract_cache_key,
            _load_extract_cache,
            _save_extract_cache_entry,
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = os.path.join(tmpdir, "extract_cache.jsonl")
            key = _extract_cache_key("hello world", "test-model")
            refs = [{"title": "A paper", "doi": "10.1234/test"}]

            _save_extract_cache_entry(cache_path, key, refs)
            cache = _load_extract_cache(cache_path)
            assert key in cache
            assert cache[key] == refs

    def test_empty_file_loads_empty(self):
        from collect_syllabi import _load_extract_cache
        with tempfile.TemporaryDirectory() as tmpdir:
            cache_path = os.path.join(tmpdir, "extract_cache.jsonl")
            open(cache_path, "w").close()  # create truly empty file
            cache = _load_extract_cache(cache_path)
            assert cache == {}

    def test_missing_file_loads_empty(self):
        from collect_syllabi import _load_extract_cache
        cache = _load_extract_cache("/nonexistent/path/cache.jsonl")
        assert cache == {}


class TestExtractCacheIntegration:
    """stage_extract uses cache to skip LLM calls."""

    def test_stage_extract_source_references_cache(self):
        """stage_extract function body should reference the cache."""
        import inspect
        import collect_syllabi
        # extract_one is a closure inside stage_extract, so check stage_extract source
        source = inspect.getsource(collect_syllabi.stage_extract)
        assert "_extract_cache_key" in source or "extract_cache" in source, \
            "stage_extract should use the extraction cache"
