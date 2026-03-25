"""Tests for enrich_embeddings — abstract boilerplate detection."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pandas as pd
import pytest

from enrich_embeddings import is_boilerplate_abstract, build_text


class TestIsBoilerplateAbstract:
    """is_boilerplate_abstract should return True for junk abstracts."""

    def test_none_is_boilerplate(self):
        assert is_boilerplate_abstract(None) is True

    def test_empty_string_is_boilerplate(self):
        assert is_boilerplate_abstract("") is True

    def test_short_string_is_boilerplate(self):
        assert is_boilerplate_abstract(".") is True
        assert is_boilerplate_abstract("editorial reviewed") is True

    def test_international_audience(self):
        assert is_boilerplate_abstract("International audience") is True
        assert is_boilerplate_abstract("international audience") is True
        assert is_boilerplate_abstract("  International audience  ") is True

    def test_peer_reviewed(self):
        assert is_boilerplate_abstract("peer reviewed") is True
        assert is_boilerplate_abstract("Peer Reviewed") is True

    def test_eu_repo_semantics(self):
        assert is_boilerplate_abstract("info:eu-repo/semantics/inPress") is True
        assert is_boilerplate_abstract("info:eu-repo/semantics/published") is True
        assert is_boilerplate_abstract("info:eu-repo/semantics/acceptedVersion") is True

    def test_title_repeated_as_abstract(self):
        title = "Climate Finance and Development"
        assert is_boilerplate_abstract(title, title=title) is True
        # Case-insensitive
        assert is_boilerplate_abstract(title.upper(), title=title) is True

    def test_short_allcaps_is_boilerplate(self):
        """Short ALL CAPS abstracts are truncated titles — skip them."""
        assert is_boilerplate_abstract("AZRBAYCANDA YAIL") is True

    def test_legitimate_abstract_passes(self):
        good = (
            "This paper examines the role of climate finance in developing "
            "countries, focusing on adaptation funding mechanisms."
        )
        assert is_boilerplate_abstract(good) is False

    def test_legitimate_abstract_with_title(self):
        good = (
            "We analyze climate finance flows from 2000 to 2020 and find "
            "significant gaps in adaptation funding for vulnerable nations."
        )
        assert is_boilerplate_abstract(good, title="Climate finance flows") is False


class TestBuildTextBoilerplateSkip:
    """build_text should skip boilerplate abstracts, falling back to title only."""

    def test_boilerplate_abstract_excluded(self):
        row = pd.Series({
            "title": "Climate Finance Trends",
            "abstract": "International audience",
            "keywords": None,
        })
        result = build_text(row)
        assert result == "Climate Finance Trends"
        assert "International audience" not in result

    def test_good_abstract_included(self):
        row = pd.Series({
            "title": "Climate Finance Trends",
            "abstract": "A comprehensive study of global climate finance mechanisms and their effectiveness.",
            "keywords": None,
        })
        result = build_text(row)
        assert "comprehensive study" in result

    def test_title_repeated_as_abstract_excluded(self):
        row = pd.Series({
            "title": "Climate Finance Trends",
            "abstract": "Climate Finance Trends",
            "keywords": "climate; finance",
        })
        result = build_text(row)
        # Should have title and keywords but not the repeated abstract
        assert "climate, finance" in result
        # The abstract IS the title, so the text should just be title + keywords
        parts = result.split(". ")
        assert len(parts) == 2  # title + keywords, no extra abstract
