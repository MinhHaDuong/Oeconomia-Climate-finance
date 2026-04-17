"""Tests for companion paper prose: all [TO WRITE] sections must be filled.

Each test checks that a section heading exists, contains no [TO WRITE]
placeholder, and includes key terms that the prose must cover.
"""

import os
import re

ROOT = os.path.join(os.path.dirname(__file__), "..")
COMPANION = os.path.join(ROOT, "content", "companion-paper.qmd")


def read(path):
    with open(path) as f:
        return f.read()


def section_h2(text, heading):
    """Extract text from a ## heading to the next ## heading."""
    pattern = rf"(## {re.escape(heading)}.*?)(?=\n## |\Z)"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1) if match else ""


def section_h3(text, heading):
    """Extract text from a ### heading to the next ### or ## heading."""
    pattern = rf"(### {re.escape(heading)}.*?)(?=\n### |\n## |\Z)"
    match = re.search(pattern, text, re.DOTALL)
    return match.group(1) if match else ""


class TestRelatedWork:
    """§2 must have prose in all four subsections."""

    def test_21_no_placeholder(self):
        s = section_h3(read(COMPANION), "2.1 Topic models in scientometrics")
        assert s, "§2.1 heading not found"
        assert "[TO WRITE" not in s

    def test_21_cites_lda(self):
        s = section_h3(read(COMPANION), "2.1 Topic models in scientometrics")
        assert "LDA" in s or "latent Dirichlet" in s.lower()

    def test_22_no_placeholder(self):
        s = section_h3(read(COMPANION), "2.2 Structural change detection")
        assert s, "§2.2 heading not found"
        assert "[TO WRITE" not in s

    def test_23_no_placeholder(self):
        s = section_h3(read(COMPANION), "2.3 Embedding-based scientometrics")
        assert s, "§2.3 heading not found"
        assert "[TO WRITE" not in s

    def test_23_cites_embeddings(self):
        s = section_h3(read(COMPANION), "2.3 Embedding-based scientometrics")
        assert "embedding" in s.lower() or "SPECTER" in s

    def test_24_no_placeholder(self):
        s = section_h3(read(COMPANION), "2.4 Climate finance bibliometrics")
        assert s, "§2.4 heading not found"
        assert "[TO WRITE" not in s


class TestResults51:
    """§5.1 Z-score time series (ticket 0064 rewrite of old 5.1 design)."""

    def test_no_placeholder(self):
        s = section_h3(read(COMPANION), "5.1 Z-score time series")
        assert s, "§5.1 heading not found"
        assert "[TO WRITE" not in s

    def test_mentions_peak_z(self):
        s = section_h3(read(COMPANION), "5.1 Z-score time series")
        assert "peak" in s.lower() and ("z = " in s.lower() or "$z" in s.lower()), (
            "§5.1 must report per-method peak Z"
        )


class TestResults52:
    """§5.2 Transition zones and multi-signal validation (ticket 0064)."""

    def test_no_placeholder(self):
        s = section_h3(
            read(COMPANION), "5.2 Transition zones and multi-signal validation"
        )
        assert s, "§5.2 heading not found"
        assert "[TO WRITE" not in s

    def test_mentions_validation(self):
        s = section_h3(
            read(COMPANION), "5.2 Transition zones and multi-signal validation"
        )
        assert "validat" in s.lower() and "zone" in s.lower(), (
            "§5.2 must discuss validated transition zones"
        )


class TestResults53:
    """§5.3 Censored-gap confirmation (ticket 0064)."""

    def test_mentions_censored(self):
        s = section_h3(read(COMPANION), "5.3 Censored-gap confirmation")
        assert s, "§5.3 heading not found"
        assert "censor" in s.lower() or "gap" in s.lower(), (
            "§5.3 must discuss censored-gap pass"
        )


class TestDiscussion:
    """§6 Discussion must have prose in all subsections."""

    def test_comparison_no_placeholder(self):
        """§6.1 must compare with topic models."""
        t = read(COMPANION)
        # Accept either old or new numbering
        s = section_h3(t, "6.1 Comparison with topic model approaches") or section_h3(
            t, "6.3 Comparison with topic model approaches"
        )
        assert s, "§6 comparison section not found"
        assert "[TO WRITE" not in s

    def test_limitations_no_placeholder(self):
        t = read(COMPANION)
        s = section_h3(t, "6.4 Limitations") or section_h3(t, "6.3 Limitations")
        assert s, "§6 limitations section not found"
        assert "[TO WRITE" not in s

    def test_contribution_no_placeholder(self):
        t = read(COMPANION)
        s = section_h3(t, "6.5 Methodological contribution") or section_h3(
            t, "6.2 Methodological contributions"
        )
        assert s, "§6 contribution section not found"
        assert "[TO WRITE" not in s

    def test_generalizability_no_placeholder(self):
        t = read(COMPANION)
        s = section_h3(t, "6.2 Generalizability") or section_h3(
            t, "6.3 Generalizability"
        )
        assert s, "§6 generalizability section not found"
        assert "[TO WRITE" not in s


class TestConclusion:
    """§7 Conclusion must have prose."""

    def test_no_placeholder(self):
        s = section_h2(read(COMPANION), "7. Conclusion")
        assert s, "§7 heading not found"
        assert "[TO WRITE" not in s

    def test_mentions_framework(self):
        s = section_h2(read(COMPANION), "7. Conclusion")
        assert "framework" in s.lower() or "method" in s.lower()


class TestNoRemainingPlaceholders:
    """No [TO WRITE] placeholders should remain in the entire file."""

    def test_global_no_to_write(self):
        text = read(COMPANION)
        # Exclude HTML comments from the check
        text_no_comments = re.sub(r"<!--.*?-->", "", text, flags=re.DOTALL)
        matches = re.findall(r"\[TO WRITE.*?\]", text_no_comments)
        assert not matches, f"Remaining [TO WRITE] placeholders: {matches}"
