"""Tests for #298: LLM extraction cache for stage_extract.

Cache contract:
- Key: sha256(page_text):model_name
- Value: extracted references JSON array
- Storage: JSONL append file at data/syllabi/extract_cache.jsonl
- When text or model changes, cache misses and re-extracts

Tests verify (RED phase — functions don't exist yet):
- _extract_cache_key builds sha256(text):model keys
- _load_extract_cache / _save_extract_cache_entry roundtrip JSONL
- stage_extract references the cache infrastructure
"""

import hashlib
import json
import os
import sys

import pytest

SCRIPTS_DIR = os.path.join(os.path.dirname(__file__), "..", "scripts")
sys.path.insert(0, SCRIPTS_DIR)


class TestExtractCacheKey:
    """_extract_cache_key must produce sha256(text):model keys."""

    def test_key_format_is_sha256_colon_model(self):
        from catalog_syllabi import _extract_cache_key

        text = "Some syllabus page text"
        model = "google/gemma-2-27b-it"
        key = _extract_cache_key(text, model)

        expected_hash = hashlib.sha256(text.encode()).hexdigest()
        assert key == f"{expected_hash}:{model}"

    def test_different_text_gives_different_key(self):
        from catalog_syllabi import _extract_cache_key

        key1 = _extract_cache_key("text A", "model-x")
        key2 = _extract_cache_key("text B", "model-x")
        assert key1 != key2

    def test_different_model_gives_different_key(self):
        from catalog_syllabi import _extract_cache_key

        key1 = _extract_cache_key("same text", "model-x")
        key2 = _extract_cache_key("same text", "model-y")
        assert key1 != key2

    def test_same_inputs_give_same_key(self):
        from catalog_syllabi import _extract_cache_key

        key1 = _extract_cache_key("hello", "m")
        key2 = _extract_cache_key("hello", "m")
        assert key1 == key2

    def test_key_contains_full_64_char_hex_hash(self):
        from catalog_syllabi import _extract_cache_key

        key = _extract_cache_key("test", "model")
        hash_part = key.split(":")[0]
        assert len(hash_part) == 64
        # Verify it's valid hex
        int(hash_part, 16)


class TestExtractCacheRoundtrip:
    """_load_extract_cache / _save_extract_cache_entry must roundtrip JSONL."""

    @pytest.fixture
    def cache_path(self, tmp_path):
        return str(tmp_path / "extract_cache.jsonl")

    def test_load_empty_cache_returns_empty_dict(self, cache_path):
        from catalog_syllabi import _load_extract_cache

        cache = _load_extract_cache(cache_path)
        assert cache == {}

    def test_save_then_load_single_entry(self, cache_path):
        from catalog_syllabi import (
            _load_extract_cache,
            _save_extract_cache_entry,
        )

        key = "abc123:google/gemma-2-27b-it"
        refs = [{"title": "Climate Finance", "authors": "Smith", "year": 2020, "doi": "10.1/x"}]

        _save_extract_cache_entry(key, refs, cache_path)
        cache = _load_extract_cache(cache_path)

        assert key in cache
        assert cache[key] == refs

    def test_save_multiple_entries_roundtrip(self, cache_path):
        from catalog_syllabi import (
            _load_extract_cache,
            _save_extract_cache_entry,
        )

        entries = {
            "hash1:model-a": [{"title": "Paper 1"}],
            "hash2:model-a": [{"title": "Paper 2"}, {"title": "Paper 3"}],
            "hash3:model-b": [],
        }
        for key, refs in entries.items():
            _save_extract_cache_entry(key, refs, cache_path)

        cache = _load_extract_cache(cache_path)
        for key, refs in entries.items():
            assert cache[key] == refs

    def test_cache_file_is_valid_jsonl(self, cache_path):
        from catalog_syllabi import _save_extract_cache_entry

        _save_extract_cache_entry(
            "k1:m", [{"title": "T"}], cache_path
        )
        _save_extract_cache_entry(
            "k2:m", [{"title": "U"}], cache_path
        )

        with open(cache_path) as f:
            lines = f.readlines()
        assert len(lines) == 2
        for line in lines:
            rec = json.loads(line)
            assert "key" in rec
            assert "references" in rec

    def test_last_write_wins_on_duplicate_key(self, cache_path):
        """If the same key is saved twice, loading should return the last value."""
        from catalog_syllabi import (
            _load_extract_cache,
            _save_extract_cache_entry,
        )

        key = "dup:model"
        _save_extract_cache_entry(key, [{"title": "Old"}], cache_path)
        _save_extract_cache_entry(key, [{"title": "New"}], cache_path)

        cache = _load_extract_cache(cache_path)
        assert cache[key] == [{"title": "New"}]


class TestStageExtractUsesCache:
    """stage_extract must reference extract cache infrastructure."""

    def test_extract_cache_key_exists(self):
        """catalog_syllabi must export _extract_cache_key."""
        import catalog_syllabi

        assert hasattr(collect_syllabi, "_extract_cache_key"), \
            "_extract_cache_key function must exist in collect_syllabi"

    def test_load_extract_cache_exists(self):
        """catalog_syllabi must export _load_extract_cache."""
        import catalog_syllabi

        assert hasattr(collect_syllabi, "_load_extract_cache"), \
            "_load_extract_cache function must exist in collect_syllabi"

    def test_save_extract_cache_entry_exists(self):
        """catalog_syllabi must export _save_extract_cache_entry."""
        import catalog_syllabi

        assert hasattr(collect_syllabi, "_save_extract_cache_entry"), \
            "_save_extract_cache_entry function must exist in collect_syllabi"

    def test_extract_cache_path_defined(self):
        """catalog_syllabi must define EXTRACT_CACHE_PATH."""
        import catalog_syllabi

        assert hasattr(collect_syllabi, "EXTRACT_CACHE_PATH"), \
            "EXTRACT_CACHE_PATH constant must exist in collect_syllabi"
        assert "extract_cache" in catalog_syllabi.EXTRACT_CACHE_PATH
        assert catalog_syllabi.EXTRACT_CACHE_PATH.endswith(".jsonl")

    def test_stage_extract_source_mentions_cache(self):
        """stage_extract implementation must reference the extract cache.

        After the harvest/process split, the implementation lives in
        syllabi_process.stage_extract; catalog_syllabi.stage_extract is a
        thin wrapper that delegates to it.
        """
        import inspect

        import syllabi_process

        source = inspect.getsource(syllabi_process.stage_extract)
        assert "_extract_cache_key" in source or "_load_extract_cache" in source, \
            "stage_extract must use extract cache functions"
