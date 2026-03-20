"""Regression tests for classify_type refactoring.

Ensures the refactored function produces identical output to the original
for representative inputs covering all code paths.
"""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "scripts"))

from qa_detect_type import classify_type


# Each tuple: (description, row_dict, expected_type)
CASES = [
    # Source-based shortcuts
    ("grey source → working-paper when title matches",
     {"source": "grey", "title": "A Working Paper on Climate", "journal": "", "doi": "", "abstract": ""},
     "working-paper"),
    ("grey source → report by default",
     {"source": "grey", "title": "Climate Finance Overview", "journal": "", "doi": "", "abstract": ""},
     "report"),
    ("teaching source with book DOI → book",
     {"source": "teaching", "title": "Climate Economics", "journal": "", "doi": "10.1017/cbo123", "abstract": ""},
     "book"),
    ("teaching source without journal → book",
     {"source": "teaching", "title": "Climate Economics", "journal": "", "doi": "10.1234/foo", "abstract": ""},
     "book"),
    # DOI-based classification
    ("World Bank DOI + WP title → working-paper",
     {"source": "openalex", "title": "Policy Research Working Paper 1234", "journal": "", "doi": "10.1596/foo", "abstract": ""},
     "working-paper"),
    ("World Bank DOI → report",
     {"source": "openalex", "title": "Country Report", "journal": "", "doi": "10.1596/bar", "abstract": ""},
     "report"),
    ("ISBN-based DOI → book",
     {"source": "openalex", "title": "A Book", "journal": "", "doi": "10.1234/978-blah", "abstract": ""},
     "book"),
    # Journal field analysis
    ("publisher in journal field + WP title → working-paper",
     {"source": "openalex", "title": "NBER Working Paper", "journal": "World Bank", "doi": "", "abstract": ""},
     "working-paper"),
    ("publisher in journal field → report",
     {"source": "openalex", "title": "Some Study", "journal": "World Bank", "doi": "", "abstract": ""},
     "report"),
    ("proceedings journal → conference-paper",
     {"source": "openalex", "title": "A Paper", "journal": "Conference Proceedings of X", "doi": "", "abstract": ""},
     "conference-paper"),
    ("procedia journal → conference-paper",
     {"source": "openalex", "title": "A Paper", "journal": "Energy Procedia", "doi": "", "abstract": ""},
     "conference-paper"),
    ("real journal → article",
     {"source": "openalex", "title": "A Paper", "journal": "Nature Climate Change", "doi": "", "abstract": ""},
     "article"),
    # Title-based classification (no journal)
    ("dissertation title → dissertation",
     {"source": "openalex", "title": "A PhD Dissertation on Climate", "journal": "", "doi": "", "abstract": ""},
     "dissertation"),
    ("working paper title → working-paper",
     {"source": "openalex", "title": "Discussion Paper on Finance", "journal": "", "doi": "", "abstract": ""},
     "working-paper"),
    ("report title → report",
     {"source": "openalex", "title": "Climate Guidelines for Banks", "journal": "", "doi": "", "abstract": ""},
     "report"),
    ("conference title → conference-paper",
     {"source": "openalex", "title": "Proceedings of Climate Summit", "journal": "", "doi": "", "abstract": ""},
     "conference-paper"),
    ("book title pattern → book",
     {"source": "openalex", "title": "The Economics of Climate Change", "journal": "", "doi": "", "abstract": ""},
     "book"),
    # Fallback: DOI + abstract → article
    ("DOI + long abstract → article",
     {"source": "openalex", "title": "Something", "journal": "", "doi": "10.1234/x",
      "abstract": "A" * 101},
     "article"),
    # Ultimate fallback
    ("no signals → other",
     {"source": "openalex", "title": "Something", "journal": "", "doi": "", "abstract": ""},
     "other"),
]


class TestClassifyType:
    """Regression tests: classify_type must return the same result after refactoring."""

    def test_all_paths(self):
        """Every representative input produces the expected doc type."""
        failures = []
        for desc, row, expected in CASES:
            result = classify_type(row)
            if result != expected:
                failures.append(f"  {desc}: expected {expected!r}, got {result!r}")
        assert not failures, "classify_type regression:\n" + "\n".join(failures)
