"""Tests for find_doi() — cached DOI lookup wrapper.

Verifies:
- find_doi returns a DOI string or empty string
- In-memory cache: second call with same title skips OpenAlex
- Disk cache: second call after clearing in-memory cache still skips OpenAlex
- Empty/whitespace titles return empty string without querying
- Titles below similarity threshold cache empty string
- author parameter: author-keyed cache takes priority, falls back to title-only
- search_doi passes author to OpenAlex search string when provided
"""

import os
import sys
from unittest.mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))


class TestResolveDoi:
    """Tests for the find_doi cache-transparent wrapper."""

    def test_find_doi_cached_in_memory(self):
        """Calling find_doi twice with same title queries OpenAlex only once."""
        from enrich_dois import find_doi, _title_cache

        _title_cache.clear()

        mock_doi = "10.1234/test-cached"
        with patch("enrich_dois.search_doi") as mock_search, \
             patch("enrich_dois.load_cache", return_value={}), \
             patch("enrich_dois.save_cache"):
            mock_search.return_value = (mock_doi, "W123", 0.95)

            # First call — should query OpenAlex
            result1 = find_doi("Test Paper on Climate Finance", 2023)
            assert result1 == mock_doi
            assert mock_search.call_count == 1

            # Second call — should hit in-memory cache, no new query
            result2 = find_doi("Test Paper on Climate Finance", 2023)
            assert result2 == mock_doi
            assert mock_search.call_count == 1  # Still 1, not 2

        _title_cache.clear()

    def test_find_doi_cached_on_disk(self):
        """After clearing in-memory cache, disk cache prevents re-query."""
        from enrich_dois import find_doi, _title_cache, normalize_title

        _title_cache.clear()

        title = "The Economics of Climate Change"
        tnorm = normalize_title(title)
        disk_key = f"title:{tnorm}"
        cached_doi = "10.5678/disk-cached"

        with patch("enrich_dois.search_doi") as mock_search, \
             patch("enrich_dois.load_cache", return_value={disk_key: cached_doi}), \
             patch("enrich_dois.save_cache"):

            result = find_doi(title, 2020)
            assert result == cached_doi
            # search_doi should NOT have been called — disk cache hit
            assert mock_search.call_count == 0

        _title_cache.clear()

    def test_find_doi_empty_title(self):
        """Empty or whitespace title returns empty string without querying."""
        from enrich_dois import find_doi, _title_cache

        _title_cache.clear()

        with patch("enrich_dois.search_doi") as mock_search:
            assert find_doi("") == ""
            assert find_doi("   ") == ""
            assert find_doi(None) == ""
            assert mock_search.call_count == 0

        _title_cache.clear()

    def test_find_doi_below_threshold(self):
        """Title match below TITLE_SIM_THRESHOLD caches empty string."""
        from enrich_dois import find_doi, _title_cache

        _title_cache.clear()

        with patch("enrich_dois.search_doi") as mock_search, \
             patch("enrich_dois.load_cache", return_value={}), \
             patch("enrich_dois.save_cache"):
            # Return low similarity — below 0.85 threshold
            mock_search.return_value = ("10.9999/bad-match", "W999", 0.50)

            result = find_doi("Completely Different Paper", 2023)
            assert result == ""  # Below threshold → empty

        _title_cache.clear()

    def test_find_doi_author_cache_key(self):
        """find_doi with author+year checks precise key first, then title-only."""
        from enrich_dois import find_doi, _title_cache, normalize_title

        _title_cache.clear()

        title = "Climate Risk and Financial Markets"
        author = "John Smith"
        tnorm = normalize_title(title)
        precise_key = f"title+meta:{tnorm}|john smith|2023"
        title_key = f"title:{tnorm}"

        # Scenario: precise cache has a different DOI than title-only cache
        disk = {
            precise_key: "10.1234/author-match",
            title_key: "10.1234/title-only-match",
        }

        with patch("enrich_dois.search_doi") as mock_search, \
             patch("enrich_dois.load_cache", return_value=disk), \
             patch("enrich_dois.save_cache"):

            result = find_doi(title, 2023, author=author)
            assert result == "10.1234/author-match"
            assert mock_search.call_count == 0  # Cache hit, no API call

        _title_cache.clear()

    def test_find_doi_author_falls_back_to_title_only(self):
        """When no author-keyed entry exists, fall back to title-only cache."""
        from enrich_dois import find_doi, _title_cache, normalize_title

        _title_cache.clear()

        title = "Green Bond Pricing Dynamics"
        author = "Jane Doe"
        tnorm = normalize_title(title)
        title_key = f"title:{tnorm}"

        # Only title-only key exists — no author key
        disk = {title_key: "10.5678/title-fallback"}

        with patch("enrich_dois.search_doi") as mock_search, \
             patch("enrich_dois.load_cache", return_value=disk), \
             patch("enrich_dois.save_cache"):

            result = find_doi(title, 2022, author=author)
            assert result == "10.5678/title-fallback"
            assert mock_search.call_count == 0

        _title_cache.clear()

    def test_find_doi_author_writes_both_cache_keys(self):
        """When author is provided, find_doi writes to both author and title keys."""
        from enrich_dois import find_doi, _title_cache

        _title_cache.clear()

        disk_cache = {}
        with patch("enrich_dois.search_doi") as mock_search, \
             patch("enrich_dois.load_cache", return_value=disk_cache), \
             patch("enrich_dois.save_cache") as mock_save:
            mock_search.return_value = ("10.1234/dual-key", "W789", 0.95)

            find_doi("Carbon Markets and Policy", 2021, author="Alice Brown")

            mock_save.assert_called_once()
            saved = mock_save.call_args[0][0]
            # Both keys should be present
            precise_keys = [k for k in saved if k.startswith("title+meta:")]
            title_keys = [k for k in saved if k.startswith("title:")]
            assert len(precise_keys) == 1
            assert len(title_keys) == 1
            assert saved[precise_keys[0]] == "10.1234/dual-key"
            assert saved[title_keys[0]] == "10.1234/dual-key"

        _title_cache.clear()

    def test_find_doi_no_author_still_works(self):
        """find_doi without author but with year writes precise + title keys."""
        from enrich_dois import find_doi, _title_cache

        _title_cache.clear()

        disk_cache = {}
        with patch("enrich_dois.search_doi") as mock_search, \
             patch("enrich_dois.load_cache", return_value=disk_cache), \
             patch("enrich_dois.save_cache") as mock_save:
            mock_search.return_value = ("10.1234/no-author", "W111", 0.90)

            result = find_doi("Basic Climate Paper", 2020)
            assert result == "10.1234/no-author"

            mock_save.assert_called_once()
            saved = mock_save.call_args[0][0]
            # Year alone creates a precise key (title+meta:..||2020)
            precise_keys = [k for k in saved if k.startswith("title+meta:")]
            title_keys = [k for k in saved if k.startswith("title:")]
            assert len(precise_keys) == 1
            assert len(title_keys) == 1
            assert "||2020" in precise_keys[0]

        _title_cache.clear()

    def test_search_doi_title_only_search(self):
        """OpenAlex search uses title-only — author is NOT appended to query.

        Author appended to OpenAlex fulltext search pollutes results.
        Author is only used for cache keying in find_doi(), not in the API call.
        """
        from enrich_dois import search_doi

        with patch("enrich_dois.polite_get") as mock_get:
            mock_get.return_value.json.return_value = {"results": []}

            search_doi("Climate Finance Overview", year=2023, author="Stern")

            # First call is OpenAlex
            oa_call = mock_get.call_args_list[0]
            params = oa_call[1]["params"] if "params" in oa_call[1] else oa_call[0][1]
            search_str = params["search"]
            assert "stern" not in search_str.lower(), \
                "Author should NOT be in search string — it breaks OpenAlex fulltext search"

    def test_search_doi_no_author(self):
        """OpenAlex search without author uses title-only (backward compatible)."""
        from enrich_dois import search_doi

        with patch("enrich_dois.polite_get") as mock_get:
            mock_get.return_value.json.return_value = {"results": []}

            search_doi("Climate Finance Overview", year=2023)

            # First call is OpenAlex
            oa_call = mock_get.call_args_list[0]
            params = oa_call[1]["params"] if "params" in oa_call[1] else oa_call[0][1]
            search_str = params["search"]
            assert search_str == "Climate Finance Overview"[:200]

    def test_search_doi_crossref_fallback(self):
        """When OpenAlex returns no match, search_doi falls back to Crossref."""
        from enrich_dois import search_doi

        # Mock OpenAlex: no results
        oa_response = type("R", (), {"json": lambda self: {"results": []}})()
        # Mock Crossref: returns a match
        cr_response = type("R", (), {"json": lambda self: {
            "message": {"items": [{
                "DOI": "10.1017/CBO9780511817434",
                "title": ["The Economics of Climate Change"],
            }]}
        }})()

        with patch("enrich_dois.polite_get") as mock_get:
            # First call = OpenAlex (no results), second = Crossref (match)
            mock_get.side_effect = [oa_response, cr_response]

            doi, oa_id, sim = search_doi("The Economics of Climate Change", 2006)
            assert doi == "10.1017/cbo9780511817434"
            assert sim >= 0.85
            assert mock_get.call_count == 2  # OA + Crossref

    def test_search_doi_no_crossref_when_oa_matches(self):
        """When OpenAlex returns a good match, Crossref is not queried."""
        from enrich_dois import search_doi

        oa_response = type("R", (), {"json": lambda self: {"results": [{
            "doi": "https://doi.org/10.1234/oa-match",
            "title": "Climate Finance Overview",
            "id": "https://openalex.org/W123",
        }]}})()

        with patch("enrich_dois.polite_get") as mock_get:
            mock_get.return_value = oa_response
            doi, oa_id, sim = search_doi("Climate Finance Overview")
            assert doi == "10.1234/oa-match"
            assert mock_get.call_count == 1  # Only OA, no Crossref

    def test_find_doi_saves_to_disk_cache(self):
        """find_doi saves result to disk cache after OpenAlex query."""
        from enrich_dois import find_doi, _title_cache

        _title_cache.clear()

        disk_cache = {}
        with patch("enrich_dois.search_doi") as mock_search, \
             patch("enrich_dois.load_cache", return_value=disk_cache), \
             patch("enrich_dois.save_cache") as mock_save:
            mock_search.return_value = ("10.1234/saved", "W456", 0.92)

            find_doi("A Paper Worth Caching", 2022)

            # save_cache should have been called with the updated cache
            mock_save.assert_called_once()
            saved = mock_save.call_args[0][0]
            # The disk cache should contain a "title:..." key
            title_keys = [k for k in saved if k.startswith("title:")]
            assert len(title_keys) == 1
            assert saved[title_keys[0]] == "10.1234/saved"

        _title_cache.clear()
