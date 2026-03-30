"""Tests for normalize_text() — encoding cleanup for aggregator metadata."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

import pytest

from pipeline_text import normalize_text


class TestNormalizeText:
    """normalize_text fixes encoding artifacts from upstream aggregator APIs."""

    def test_none_returns_empty(self):
        assert normalize_text(None) == ""

    def test_empty_returns_empty(self):
        assert normalize_text("") == ""

    def test_clean_text_unchanged(self):
        assert normalize_text("Climate finance in developing countries") == (
            "Climate finance in developing countries"
        )

    # --- HTML entities (the biggest category: ~1800 rows) ---

    def test_html_named_entity_amp(self):
        assert normalize_text("R&amp;D investment") == "R&D investment"

    def test_html_named_entity_lt_gt(self):
        assert normalize_text("T &lt; 2°C and E &gt; 0") == "T < 2°C and E > 0"

    def test_html_numeric_decimal_entity(self):
        # &#13; is carriage return, should become space
        assert normalize_text("carbon&#13;\n pricing") == "carbon pricing"

    def test_html_numeric_hex_entity(self):
        assert normalize_text("India and Capacity&#x0D;Building") == (
            "India and Capacity Building"
        )

    def test_html_numeric_smart_quote(self):
        # &#146; is Windows-1252 right single quote in some old HTML
        # ftfy normalizes curly quotes to straight quotes
        assert normalize_text("EU&#146;s 2009 climate") == "EU's 2009 climate"

    def test_double_encoded_entity(self):
        # &amp;#43; → &#43; → +
        assert normalize_text("REDD&amp;#43;") == "REDD+"

    # --- Mojibake (double-encoded UTF-8) ---

    def test_mojibake_smart_quotes(self):
        # â€™ is UTF-8 for ' (U+2019) misread as Latin-1
        assert "win" in normalize_text("potential \u00e2\u0080\u0099win-win\u00e2\u0080\u0099")

    def test_mojibake_accented_e(self):
        # Ã© is UTF-8 for é misread as Latin-1
        assert normalize_text("r\u00c3\u00a9flexions") == "réflexions"

    def test_mojibake_accented_a(self):
        assert normalize_text("Bogot\u00c3\u00a1") == "Bogotá"

    # --- Zero-width and invisible characters ---

    def test_zero_width_space_removed(self):
        assert normalize_text("zero\u200bwidth") == "zerowidth"

    def test_soft_hyphen_removed(self):
        assert normalize_text("soft\u00adhyphen") == "softhyphen"

    def test_bom_removed(self):
        assert normalize_text("\ufeffRimal Abeed") == "Rimal Abeed"

    # --- Literal escape sequences ---

    def test_literal_backslash_n(self):
        assert normalize_text("line one\\nline two") == "line one line two"

    def test_literal_backslash_t(self):
        assert normalize_text("tab\\there") == "tab here"

    def test_literal_backslash_r(self):
        assert normalize_text("return\\rhere") == "return here"

    # --- Whitespace normalization ---

    def test_collapses_whitespace(self):
        assert normalize_text("  extra   spaces  ") == "extra spaces"

    def test_real_newlines_collapsed(self):
        assert normalize_text("line one\nline two\rthree") == "line one line two three"

    # --- Preserves valid Unicode ---

    def test_preserves_real_accents(self):
        assert normalize_text("café résumé naïve") == "café résumé naïve"

    def test_curly_quotes_normalized_to_straight(self):
        # ftfy normalizes curly quotes to ASCII equivalents — fine for corpus text
        assert normalize_text("the world\u2019s climate") == "the world's climate"

    def test_preserves_cjk(self):
        assert normalize_text("气候金融 気候金融") == "气候金融 気候金融"
