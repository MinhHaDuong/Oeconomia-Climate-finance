"""Tests for GROBID-based citation parsing."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest
from corpus_parse_citations_grobid import parse_tei_citation, build_cache_key


class TestParseTeiCitation:
    """parse_tei_citation extracts structured fields from GROBID TEI XML."""

    def test_book_citation(self):
        tei = """<biblStruct>
        <monogr>
            <author><persName><forename type="first">N</forename>
            <surname>Stern</surname></persName></author>
            <title level="m">The Economics of Climate Change</title>
            <imprint><publisher>Cambridge University Press</publisher>
            <date type="published" when="2007">2007</date></imprint>
        </monogr>
        </biblStruct>"""
        result = parse_tei_citation(tei)
        assert result["title"] == "The Economics of Climate Change"
        assert result["first_author"] == "Stern"
        assert result["year"] == "2007"

    def test_journal_article(self):
        tei = """<biblStruct>
        <analytic>
            <author><persName><forename type="first">R</forename>
            <surname>Tol</surname></persName></author>
            <title level="a">The Economic Effects of Climate Change</title>
        </analytic>
        <monogr>
            <title level="j">Journal of Economic Perspectives</title>
            <imprint><date type="published" when="2009">2009</date></imprint>
        </monogr>
        </biblStruct>"""
        result = parse_tei_citation(tei)
        assert result["title"] == "The Economic Effects of Climate Change"
        assert result["first_author"] == "Tol"
        assert result["year"] == "2009"
        assert result["journal"] == "Journal of Economic Perspectives"

    def test_empty_tei(self):
        result = parse_tei_citation("")
        assert result["title"] == ""
        assert result["first_author"] == ""
        assert result["year"] == ""

    def test_no_author(self):
        tei = """<biblStruct>
        <monogr>
            <title level="m">Climate Report</title>
            <imprint><date type="published" when="2020">2020</date></imprint>
        </monogr>
        </biblStruct>"""
        result = parse_tei_citation(tei)
        assert result["title"] == "Climate Report"
        assert result["first_author"] == ""
        assert result["year"] == "2020"


class TestBuildCacheKey:
    """Cache key is a hash of the unstructured text."""

    def test_deterministic(self):
        assert build_cache_key("some text") == build_cache_key("some text")

    def test_different_texts(self):
        assert build_cache_key("text a") != build_cache_key("text b")

    def test_strips_whitespace(self):
        assert build_cache_key("  some text  ") == build_cache_key("some text")
