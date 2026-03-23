"""Tests for resolve_doi() — cached DOI lookup wrapper.

Verifies:
- resolve_doi returns a DOI string or empty string
- In-memory cache: second call with same title skips OpenAlex
- Disk cache: second call after clearing in-memory cache still skips OpenAlex
- Empty/whitespace titles return empty string without querying
- Titles below similarity threshold cache empty string
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


class TestResolveDoi:
    """Tests for the resolve_doi cache-transparent wrapper."""

    def test_resolve_doi_cached_in_memory(self):
        """Calling resolve_doi twice with same title queries OpenAlex only once."""
        from enrich_dois import resolve_doi, _title_cache

        _title_cache.clear()

        mock_doi = "10.1234/test-cached"
        with patch("enrich_dois.search_doi") as mock_search, \
             patch("enrich_dois.load_cache", return_value={}), \
             patch("enrich_dois.save_cache"):
            mock_search.return_value = (mock_doi, "W123", 0.95)

            # First call — should query OpenAlex
            result1 = resolve_doi("Test Paper on Climate Finance", 2023)
            assert result1 == mock_doi
            assert mock_search.call_count == 1

            # Second call — should hit in-memory cache, no new query
            result2 = resolve_doi("Test Paper on Climate Finance", 2023)
            assert result2 == mock_doi
            assert mock_search.call_count == 1  # Still 1, not 2

        _title_cache.clear()

    def test_resolve_doi_cached_on_disk(self):
        """After clearing in-memory cache, disk cache prevents re-query."""
        from enrich_dois import resolve_doi, _title_cache, normalize_title

        _title_cache.clear()

        title = "The Economics of Climate Change"
        tnorm = normalize_title(title)
        disk_key = f"title:{tnorm}"
        cached_doi = "10.5678/disk-cached"

        with patch("enrich_dois.search_doi") as mock_search, \
             patch("enrich_dois.load_cache", return_value={disk_key: cached_doi}), \
             patch("enrich_dois.save_cache"):

            result = resolve_doi(title, 2020)
            assert result == cached_doi
            # search_doi should NOT have been called — disk cache hit
            assert mock_search.call_count == 0

        _title_cache.clear()

    def test_resolve_doi_empty_title(self):
        """Empty or whitespace title returns empty string without querying."""
        from enrich_dois import resolve_doi, _title_cache

        _title_cache.clear()

        with patch("enrich_dois.search_doi") as mock_search:
            assert resolve_doi("") == ""
            assert resolve_doi("   ") == ""
            assert resolve_doi(None) == ""
            assert mock_search.call_count == 0

        _title_cache.clear()

    def test_resolve_doi_below_threshold(self):
        """Title match below TITLE_SIM_THRESHOLD caches empty string."""
        from enrich_dois import resolve_doi, _title_cache

        _title_cache.clear()

        with patch("enrich_dois.search_doi") as mock_search, \
             patch("enrich_dois.load_cache", return_value={}), \
             patch("enrich_dois.save_cache"):
            # Return low similarity — below 0.85 threshold
            mock_search.return_value = ("10.9999/bad-match", "W999", 0.50)

            result = resolve_doi("Completely Different Paper", 2023)
            assert result == ""  # Below threshold → empty

        _title_cache.clear()

    def test_resolve_doi_saves_to_disk_cache(self):
        """resolve_doi saves result to disk cache after OpenAlex query."""
        from enrich_dois import resolve_doi, _title_cache

        _title_cache.clear()

        disk_cache = {}
        with patch("enrich_dois.search_doi") as mock_search, \
             patch("enrich_dois.load_cache", return_value=disk_cache), \
             patch("enrich_dois.save_cache") as mock_save:
            mock_search.return_value = ("10.1234/saved", "W456", 0.92)

            resolve_doi("A Paper Worth Caching", 2022)

            # save_cache should have been called with the updated cache
            mock_save.assert_called_once()
            saved = mock_save.call_args[0][0]
            # The disk cache should contain a "title:..." key
            title_keys = [k for k in saved if k.startswith("title:")]
            assert len(title_keys) == 1
            assert saved[title_keys[0]] == "10.1234/saved"

        _title_cache.clear()
