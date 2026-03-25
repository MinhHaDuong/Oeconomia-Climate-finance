"""Tests for near-duplicate abstract detection (#416).

The COP27 editorial (Atwoli et al. 2022) was published simultaneously in 62+
journals with different DOIs. These are bibliographically distinct works but
contain the same text. The detection should flag them under a shared group ID.
"""

import os
import sys

import pandas as pd
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from detect_near_duplicates import detect_near_duplicate_groups


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture
def cop27_df():
    """Synthetic DataFrame mimicking the COP27 coordinated publication.

    62 records with near-identical abstracts (minor punctuation/truncation
    differences), plus 5 unrelated papers.
    """
    cop27_abstract_base = (
        "The 2022 report of the Intergovernmental Panel on Climate Change (IPCC) "
        "paints a dark picture of the future of life on earth, if meaningful action "
        "is not taken to reverse current trends. Despite repeated warnings, the "
        "world has not done enough. The editorial is being published simultaneously "
        "in over 50 journals to highlight the urgency of action needed."
    )
    records = []

    # 62 COP27 editorial variants
    for i in range(62):
        abstract = cop27_abstract_base
        # Introduce minor variation: Oxford comma, truncation, punctuation
        if i % 3 == 1:
            abstract = abstract.replace("earth, if", "earth if")
        if i % 5 == 0:
            abstract = abstract[:250]  # truncated
        if i % 7 == 0:
            abstract = abstract.replace("50 journals", "fifty journals")
        records.append({
            "doi": f"10.1000/cop27-{i:03d}",
            "title": "COP27 Climate Change Conference: urgent action needed for Africa and the world",
            "abstract": abstract,
            "year": 2022,
            "first_author": "Atwoli",
            "journal": f"Journal {i}",
        })

    # 5 unrelated papers with distinct abstracts
    unrelated = [
        "Carbon pricing mechanisms in the European Union have evolved significantly.",
        "Green bonds have emerged as a major financial instrument for climate.",
        "Adaptation finance in sub-Saharan Africa remains critically under-resourced.",
        "The Paris Agreement established a framework for international cooperation.",
        "Renewable energy investment trends show accelerating growth worldwide.",
    ]
    for i, abstract in enumerate(unrelated):
        records.append({
            "doi": f"10.1000/other-{i:03d}",
            "title": f"Unrelated paper {i}",
            "abstract": abstract,
            "year": 2020 + i,
            "first_author": f"Author{i}",
            "journal": f"Other Journal {i}",
        })

    return pd.DataFrame(records)


@pytest.fixture
def no_duplicate_df():
    """DataFrame with no near-duplicate abstracts."""
    records = []
    for i in range(20):
        records.append({
            "doi": f"10.1000/unique-{i:03d}",
            "title": f"Unique paper {i}",
            "abstract": f"This is a completely unique abstract number {i} about topic {i * 17}.",
            "year": 2020,
            "first_author": f"Author{i}",
            "journal": f"Journal {i}",
        })
    return pd.DataFrame(records)


# ============================================================
# Core contract: COP27 group detection
# ============================================================

class TestCOP27GroupDetection:
    """First test from ticket: all 62 COP27 editorial records share
    the same near_duplicate_group value."""

    def test_cop27_records_share_group(self, cop27_df):
        groups = detect_near_duplicate_groups(cop27_df)
        cop27_groups = groups.iloc[:62]
        # All 62 should have a non-null group
        assert cop27_groups.notna().all(), "All COP27 records must be assigned a group"
        # All 62 should share the same group ID
        assert cop27_groups.nunique() == 1, (
            f"All COP27 records must share one group, got {cop27_groups.nunique()}"
        )

    def test_unrelated_papers_have_no_group(self, cop27_df):
        groups = detect_near_duplicate_groups(cop27_df)
        other_groups = groups.iloc[62:]
        # Unrelated papers should not be in any near-duplicate group
        assert other_groups.isna().all(), "Unrelated papers must not have a group"

    def test_returns_series_aligned_with_input(self, cop27_df):
        groups = detect_near_duplicate_groups(cop27_df)
        assert isinstance(groups, pd.Series)
        assert len(groups) == len(cop27_df)
        assert groups.index.equals(cop27_df.index)

    def test_group_column_name(self, cop27_df):
        groups = detect_near_duplicate_groups(cop27_df)
        assert groups.name == "near_duplicate_group"


# ============================================================
# Edge cases
# ============================================================

class TestEdgeCases:
    def test_no_duplicates(self, no_duplicate_df):
        groups = detect_near_duplicate_groups(no_duplicate_df)
        assert groups.isna().all(), "No groups expected when all abstracts are unique"

    def test_empty_dataframe(self):
        df = pd.DataFrame(columns=["doi", "title", "abstract", "year"])
        groups = detect_near_duplicate_groups(df)
        assert len(groups) == 0

    def test_missing_abstracts_excluded(self):
        """Papers without abstracts should not be grouped together."""
        df = pd.DataFrame({
            "doi": [f"10.1000/x-{i}" for i in range(10)],
            "title": [f"Paper {i}" for i in range(10)],
            "abstract": [None] * 10,
            "year": [2020] * 10,
        })
        groups = detect_near_duplicate_groups(df)
        assert groups.isna().all(), "Papers with no abstract should not form groups"

    def test_short_abstracts_excluded(self):
        """Very short abstracts should not trigger grouping."""
        df = pd.DataFrame({
            "doi": [f"10.1000/s-{i}" for i in range(10)],
            "title": [f"Paper {i}" for i in range(10)],
            "abstract": ["Abstract."] * 10,
            "year": [2020] * 10,
        })
        groups = detect_near_duplicate_groups(df)
        assert groups.isna().all(), "Very short abstracts should not form groups"

    def test_min_group_size_respected(self, cop27_df):
        """Groups smaller than min_group_size should not be flagged."""
        # With min_group_size=100, even 62 COP27 records won't form a group
        groups = detect_near_duplicate_groups(cop27_df, min_group_size=100)
        assert groups.isna().all()
