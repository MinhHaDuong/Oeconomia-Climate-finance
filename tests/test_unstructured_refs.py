"""Tests for unstructured Crossref reference parsing in fetch_batch."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest
from enrich_citations_batch import parse_ref_fields


class TestParseRefFields:
    """parse_ref_fields extracts metadata from Crossref reference objects."""

    def test_structured_ref_unchanged(self):
        """Named fields take priority over unstructured text."""
        ref = {
            "article-title": "Climate policy report",
            "author": "Brown",
            "year": "2003",
        }
        result = parse_ref_fields(ref)
        assert result["ref_title"] == "Climate policy report"
        assert result["ref_first_author"] == "Brown"
        assert result["ref_year"] == "2003"

    def test_unstructured_only(self):
        """When no named fields exist, parse the unstructured blob."""
        ref = {
            "unstructured": "Brown, 2003. Climate policy report.",
            "key": "k1",
        }
        result = parse_ref_fields(ref)
        assert result["ref_title"] == "Brown, 2003. Climate policy report."
        assert result["ref_year"] == "2003"
        assert result["ref_first_author"] == "Brown"

    def test_unstructured_no_year(self):
        """Unstructured text without a 4-digit year."""
        ref = {"unstructured": "IPCC, Special report on climate."}
        result = parse_ref_fields(ref)
        assert result["ref_title"] == "IPCC, Special report on climate."
        assert result["ref_year"] == ""
        assert result["ref_first_author"] == "IPCC"

    def test_unstructured_no_comma(self):
        """Unstructured text with no comma — author extraction falls back to empty."""
        ref = {"unstructured": "2003 World Development Report"}
        result = parse_ref_fields(ref)
        assert result["ref_title"] == "2003 World Development Report"
        assert result["ref_year"] == "2003"
        assert result["ref_first_author"] == ""

    def test_unstructured_empty(self):
        """Empty unstructured field treated same as missing."""
        ref = {"unstructured": "", "key": "k1"}
        result = parse_ref_fields(ref)
        assert result["ref_title"] == ""
        assert result["ref_year"] == ""
        assert result["ref_first_author"] == ""

    def test_volume_title_fallback(self):
        """volume-title used when article-title is absent."""
        ref = {"volume-title": "Handbook of Climate Economics", "year": "2019"}
        result = parse_ref_fields(ref)
        assert result["ref_title"] == "Handbook of Climate Economics"
        assert result["ref_year"] == "2019"

    def test_series_title_fallback(self):
        """series-title used when both article-title and volume-title absent."""
        ref = {"series-title": "NBER Working Papers", "year": "2010"}
        result = parse_ref_fields(ref)
        assert result["ref_title"] == "NBER Working Papers"

    def test_structured_fields_not_overridden_by_unstructured(self):
        """When structured fields exist, unstructured text is ignored."""
        ref = {
            "article-title": "Real title",
            "author": "Smith",
            "year": "2020",
            "unstructured": "Jones, 1999. Wrong title.",
        }
        result = parse_ref_fields(ref)
        assert result["ref_title"] == "Real title"
        assert result["ref_first_author"] == "Smith"
        assert result["ref_year"] == "2020"

    def test_partial_structured_with_unstructured_fallback(self):
        """Year from structured, title+author from unstructured when missing."""
        ref = {
            "year": "2015",
            "unstructured": "Greenpeace, 2003. Sinks in the CDM.",
        }
        result = parse_ref_fields(ref)
        assert result["ref_year"] == "2015"  # structured wins
        assert result["ref_title"] == "Greenpeace, 2003. Sinks in the CDM."
        assert result["ref_first_author"] == "Greenpeace"
