"""Tests for export_corpus_table.py — ticket #252.

Verifies that the exported CSV has correct columns and that Raw counts
use from_* columns (not the source column fallback).
"""

import os
import pandas as pd
import pytest

TABLES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "content", "tables",
)
CSV_PATH = os.path.join(TABLES_DIR, "tab_corpus_sources.csv")


@pytest.fixture
def corpus_table():
    """Load the exported corpus sources table."""
    assert os.path.exists(CSV_PATH), f"Missing {CSV_PATH} — run export_corpus_table.py first"
    return pd.read_csv(CSV_PATH)


def test_required_columns(corpus_table):
    """Table must have Raw, Refined, and Unique columns."""
    for col in ("Raw", "Refined", "Unique"):
        assert col in corpus_table.columns, f"Missing column: {col}"


def test_raw_counts_use_from_columns(corpus_table):
    """Raw counts must reflect from_* totals, not primary-source fallback.

    The usecols=["source"] bug caused ISTEX Raw=1 and bibCNRS Raw=212.
    With from_* columns, ISTEX Raw>=4 and bibCNRS Raw>=233.
    """
    row_istex = corpus_table[corpus_table["Source"] == "ISTEX"]
    assert len(row_istex) == 1, "ISTEX row missing"
    assert row_istex.iloc[0]["Raw"] >= 4, (
        f"ISTEX Raw={row_istex.iloc[0]['Raw']} — likely still using source column fallback"
    )

    row_bib = corpus_table[corpus_table["Source"] == "bibCNRS"]
    assert len(row_bib) == 1, "bibCNRS row missing"
    assert row_bib.iloc[0]["Raw"] >= 233, (
        f"bibCNRS Raw={row_bib.iloc[0]['Raw']} — likely still using source column fallback"
    )


def test_unique_column_plausible(corpus_table):
    """Unique must be <= Refined for every source."""
    data_rows = corpus_table[corpus_table["Source"] != "TOTAL"]
    for _, row in data_rows.iterrows():
        if pd.notna(row.get("Unique")) and pd.notna(row.get("Refined")):
            assert row["Unique"] <= row["Refined"], (
                f"{row['Source']}: Unique ({row['Unique']}) > Refined ({row['Refined']})"
            )


def test_total_row_present(corpus_table):
    """A TOTAL row must exist."""
    total = corpus_table[corpus_table["Source"] == "TOTAL"]
    assert len(total) == 1, "Missing TOTAL row"
