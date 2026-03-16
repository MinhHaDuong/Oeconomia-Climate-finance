"""Tests for #96: Document seed axis PCA decomposition in companion paper.

Sections 5.3 and 5.4 of companion-paper.qmd must contain prose
(not [TO WRITE] placeholders) presenting bimodality results and
the PCA decomposition of the seed axis.
"""

import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..")

COMPANION = os.path.join(ROOT, "content", "companion-paper.qmd")


def read(path):
    with open(path) as f:
        return f.read()


def extract_section(text, heading):
    """Extract text from a ### heading to the next ### or ## heading."""
    pattern = rf"(### {re.escape(heading)}.*?)(?=\n### |\n## |\Z)"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1) if match else ""


class TestSection53:
    """§5.3 Efficiency--accountability polarization must have prose."""

    def test_no_to_write_placeholder(self):
        text = read(COMPANION)
        section = extract_section(text, "5.3 Efficiency--accountability polarization")
        assert section, "§5.3 heading not found in companion-paper.qmd"
        assert "[TO WRITE" not in section, "§5.3 still contains [TO WRITE] placeholder"

    def test_mentions_dbic(self):
        text = read(COMPANION)
        section = extract_section(text, "5.3 Efficiency--accountability polarization")
        assert "BIC" in section or "ΔBIC" in section or "bim_dbic" in section, \
            "§5.3 must present ΔBIC evidence for bimodality"

    def test_mentions_cross_validation(self):
        text = read(COMPANION)
        section = extract_section(text, "5.3 Efficiency--accountability polarization")
        assert "TF-IDF" in section or "lexical" in section, \
            "§5.3 must mention cross-validation with lexical method"

    def test_mentions_temporal_pattern(self):
        text = read(COMPANION)
        section = extract_section(text, "5.3 Efficiency--accountability polarization")
        assert "2015" in section or "post-2015" in section or "period" in section, \
            "§5.3 must discuss the temporal emergence of bimodality"


class TestSection54:
    """§5.4 The divide as PC2, not PC1 must have prose."""

    def test_no_to_write_placeholder(self):
        text = read(COMPANION)
        section = extract_section(text, "5.4 The divide as PC2, not PC1")
        assert section, "§5.4 heading not found in companion-paper.qmd"
        assert "[TO WRITE" not in section, "§5.4 still contains [TO WRITE] placeholder"

    def test_mentions_pc1_orthogonal(self):
        text = read(COMPANION)
        section = extract_section(text, "5.4 The divide as PC2, not PC1")
        assert "PC1" in section, "§5.4 must discuss PC1's orthogonality to seed axis"

    def test_mentions_pc2_alignment(self):
        text = read(COMPANION)
        section = extract_section(text, "5.4 The divide as PC2, not PC1")
        assert "PC2" in section, "§5.4 must discuss PC2's alignment with seed axis"

    def test_mentions_variance(self):
        text = read(COMPANION)
        section = extract_section(text, "5.4 The divide as PC2, not PC1")
        assert "variance" in section or "var_pct" in section, \
            "§5.4 must report explained variance"

    def test_mentions_erratum(self):
        """The ticket requires documenting the corrected values."""
        text = read(COMPANION)
        section = extract_section(text, "5.4 The divide as PC2, not PC1")
        assert "earlier" in section.lower() or "previous" in section.lower() \
            or "corrected" in section.lower() or "erratum" in section.lower(), \
            "§5.4 must note the correction of earlier reported values"
