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

from qa_near_duplicates import detect_near_duplicate_groups


# ============================================================
# Fixtures
# ============================================================

COP27_ABSTRACT_VARIANT_A = (
    "The 2022 report of the Intergovernmental Panel on Climate Change (IPCC) "
    "paints a dark picture of the future of life on earth, if meaningful action "
    "is not taken to reverse current trends. Despite repeated warnings, the "
    "world has not done enough."
)

COP27_ABSTRACT_VARIANT_B = (
    "Wealthy nations must step up support for Africa and vulnerable countries "
    "in addressing past, present, and future impacts of climate change. The "
    "2022 report of the Intergovernmental Panel on Climate Change (IPCC) paints "
    "a dark picture of the future of life on earth."
)


@pytest.fixture
def cop27_df():
    """Synthetic DataFrame mimicking the COP27 coordinated publication.

    62 records with the same normalized title but different abstract variants
    (truncated, different starting paragraphs, minor punctuation differences),
    plus 5 unrelated papers.
    """
    records = []

    # 62 COP27 editorial variants — same title, varying abstracts
    title_variants = [
        "COP27 Climate Change Conference: urgent action needed for Africa and the world",
        "COP27 Climate Change Conference: Urgent action needed for Africa and the world",
        "COP27 Climate Change Conference: Urgent Action Needed for Africa and the World",
        "COP27 Climate Change Conference—Urgent Action Needed for Africa and the World",
    ]
    for i in range(62):
        title = title_variants[i % len(title_variants)]
        # Mix abstract variants: some have variant A, some B, some truncated
        if i % 3 == 0:
            abstract = COP27_ABSTRACT_VARIANT_A
        elif i % 3 == 1:
            abstract = COP27_ABSTRACT_VARIANT_B
        else:
            abstract = COP27_ABSTRACT_VARIANT_A[:150]  # truncated

        records.append({
            "doi": f"10.1000/cop27-{i:03d}",
            "title": title,
            "abstract": abstract,
            "year": 2022,
            "first_author": "Atwoli",
            "journal": f"Journal {i}",
        })

    # 5 unrelated papers with distinct titles and abstracts
    unrelated = [
        ("Carbon pricing mechanisms", "Carbon pricing mechanisms in the EU have evolved."),
        ("Green bonds overview", "Green bonds have emerged as a major financial instrument."),
        ("Adaptation finance gaps", "Adaptation finance in sub-Saharan Africa remains under-resourced."),
        ("Paris Agreement framework", "The Paris Agreement established international cooperation."),
        ("Renewable energy trends", "Renewable energy investment trends show accelerating growth."),
    ]
    for i, (title, abstract) in enumerate(unrelated):
        records.append({
            "doi": f"10.1000/other-{i:03d}",
            "title": title,
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

    def test_missing_abstracts_not_grouped(self):
        """Papers without abstracts sharing a title should NOT be grouped.

        Without abstract content to validate, we cannot confirm these are
        true near-duplicates vs. generic front-matter (e.g., "References").
        """
        df = pd.DataFrame({
            "doi": [f"10.1000/x-{i}" for i in range(10)],
            "title": ["Same coordinated editorial title"] * 10,
            "abstract": [None] * 10,
            "year": [2020] * 10,
        })
        groups = detect_near_duplicate_groups(df)
        assert groups.isna().all(), "No-abstract title groups should not be flagged"

    def test_short_identical_abstracts_grouped_by_title(self):
        """Papers with short but IDENTICAL abstracts and same title are grouped.

        The abstract prefix overlap check considers short normalized abstracts
        as matching when they're identical.
        """
        df = pd.DataFrame({
            "doi": [f"10.1000/s-{i}" for i in range(10)],
            "title": ["COP27 editorial: urgent action needed"] * 10,
            "abstract": ["Abstract content that is exactly the same in all ten copies of this paper."] * 10,
            "year": [2020] * 10,
        })
        groups = detect_near_duplicate_groups(df)
        assert groups.notna().all(), "Identical abstracts + same title should be grouped"

    def test_common_title_no_abstract_overlap_excluded(self):
        """Papers with a generic shared title (e.g., 'Editorial') but completely
        different abstracts should NOT be grouped."""
        df = pd.DataFrame({
            "doi": [f"10.1000/ed-{i}" for i in range(10)],
            "title": ["Editorial"] * 10,
            "abstract": [
                f"This editorial discusses topic {i} which is entirely "
                f"unique and unrelated to other editorials number {i * 37}."
                for i in range(10)
            ],
            "year": [2020] * 10,
        })
        groups = detect_near_duplicate_groups(df)
        assert groups.isna().all(), (
            "Generic titles with diverse abstracts must not form a group"
        )

    def test_min_group_size_respected(self, cop27_df):
        """Groups smaller than min_group_size should not be flagged."""
        groups = detect_near_duplicate_groups(cop27_df, min_group_size=100)
        assert groups.isna().all()

    def test_missing_abstract_column_returns_all_na(self):
        """DataFrame without 'abstract' column returns all NA gracefully."""
        df = pd.DataFrame({
            "doi": [f"10.1000/x-{i}" for i in range(10)],
            "title": ["Same title"] * 10,
            "year": [2020] * 10,
        })
        groups = detect_near_duplicate_groups(df)
        assert groups.isna().all()

    def test_emdash_title_normalization(self):
        """Em-dash and colon title variants normalize to the same key.

        Regression test: em-dash was previously stripped without leaving a
        space, producing 'conferenceurgent' instead of 'conference urgent'.
        """
        from qa_near_duplicates import _normalize_text

        colon = _normalize_text("COP27 Conference: Urgent Action")
        emdash = _normalize_text("COP27 Conference—Urgent Action")
        assert colon == emdash, f"Colon '{colon}' != em-dash '{emdash}'"
