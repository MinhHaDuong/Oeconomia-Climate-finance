"""Tests for export_language_table.py — ticket #402.

Verifies that:
- normalise_language handles common edge cases correctly
- the data paper includes the language table
- the script is importable and the normalise function works
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

ROOT = os.path.join(os.path.dirname(__file__), "..")
DATA_PAPER = os.path.join(ROOT, "content", "data-paper.qmd")
SCRIPT = os.path.join(ROOT, "scripts", "export_language_table.py")


def read(path):
    with open(path) as f:
        return f.read()


# --- Unit tests for normalise_language ---

def test_plain_code_unchanged():
    from export_language_table import normalise_language
    assert normalise_language("en") == "en"


def test_locale_normalised_underscore():
    from export_language_table import normalise_language
    assert normalise_language("en_US") == "en"


def test_locale_normalised_hyphen():
    from export_language_table import normalise_language
    assert normalise_language("zh-CN") == "zh"


def test_none_returns_unknown():
    from export_language_table import normalise_language
    import pandas as pd
    assert normalise_language(pd.NA) == "unknown"
    assert normalise_language(float("nan")) == "unknown"


def test_empty_string_returns_empty():
    """Empty string is not NaN — it stays as an empty string after strip/lower."""
    from export_language_table import normalise_language
    assert normalise_language("") == ""


def test_uppercase_lowercased():
    from export_language_table import normalise_language
    assert normalise_language("FR") == "fr"


# --- Integration: data paper includes the language table ---

def test_data_paper_includes_language_table():
    text = read(DATA_PAPER)
    assert "tables/tab_languages.md" in text, (
        "data-paper.qmd must include tables/tab_languages.md"
    )


def test_data_paper_references_tbl_languages():
    text = read(DATA_PAPER)
    assert "@tbl-languages" in text, (
        "data-paper.qmd must reference @tbl-languages"
    )


def test_script_exists():
    assert os.path.isfile(SCRIPT), f"Missing script: {SCRIPT}"
