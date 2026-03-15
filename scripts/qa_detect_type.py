"""Detect and fix document type in the refined corpus.

Classifies each record as: article, review, book, book-chapter, report,
working-paper, conference-paper, dissertation, or other.

Uses heuristics on metadata fields (journal, DOI prefix, source, title patterns).
Adds a `doc_type` column and fixes misleading `journal` entries (e.g. "World Bank"
is a publisher, not a journal).

Usage:
    uv run python scripts/qa_detect_type.py [--apply]

Outputs:
    - stdout: type distribution summary
    - content/tables/qa_type_report.csv: classification report
    - data/catalogs/refined_works.csv: updated with doc_type column (with --apply)
"""

import argparse
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import CATALOGS_DIR, save_csv, BASE_DIR

# Publishers that are NOT journals (often stored in journal field)
PUBLISHERS_NOT_JOURNALS = {
    "world bank", "oecd", "oecd publishing", "imf", "international monetary fund",
    "undp", "unep", "unfccc", "iea", "irena", "adb", "asian development bank",
    "african development bank", "inter-american development bank",
    "european commission", "european investment bank",
    "climate policy initiative", "overseas development institute",
    "brookings institution", "chatham house", "wri", "world resources institute",
    "cifor", "cgiar", "fao", "giz",
    "springer", "elsevier", "wiley", "taylor & francis", "routledge",
    "cambridge university press", "oxford university press", "mit press",
    "palgrave macmillan", "edward elgar",
}

# DOI prefixes that indicate specific types
# 10.1596 = World Bank, 10.1787 = OECD, 10.5089 = IMF
REPORT_DOI_PREFIXES = {"10.1596", "10.1787", "10.5089", "10.18356"}
BOOK_DOI_PATTERNS = {
    r"10\.\d+/978",  # ISBN-based DOIs
    r"10\.1017/cbo",  # Cambridge books
    r"10\.1093/acprof",  # Oxford academic profiles
    r"10\.7551/mitpress",  # MIT Press
    r"10\.4324/",  # Routledge
}

# Title patterns
WORKING_PAPER_PATTERNS = [
    r"\bworking paper\b", r"\bwp\s*#?\d+", r"\bdiscussion paper\b",
    r"\bpolicy\s+research\s+working\s+paper\b", r"\bnber\b",
    r"\bcepr\b", r"\bssrn\b",
]
REPORT_TITLE_PATTERNS = [
    r"\breport\b", r"\bcountry\s+climate\s+and\s+development\b",
    r"\bworld\s+development\s+report\b", r"\bglobal\s+economic\s+prospects\b",
    r"\bevaluation\b.*\bpaper\b", r"\broadmap\b", r"\bmarket\s+study\b",
    r"\bguidelines?\b", r"\bhandbook\b",
]
BOOK_TITLE_PATTERNS = [
    r"^the\s+(economics|politics|political\s+economy)\s+of\b",
    r"\ba\s+(guide|companion|introduction)\s+to\b",
]
CONFERENCE_PATTERNS = [
    r"\bconference\b", r"\bproceedings\b", r"\bsymposium\b",
    r"\bworkshop\b",
]
DISSERTATION_PATTERNS = [
    r"\bdissertation\b", r"\bthesis\b", r"\bph\.?d\.?\b",
]


def classify_type(row):
    """Classify document type from metadata heuristics."""
    title = str(row.get("title", "") or "").lower()
    journal = str(row.get("journal", "") or "").lower().strip()
    doi = str(row.get("doi", "") or "").lower()
    source = str(row.get("source", "") or "").lower()
    abstract = str(row.get("abstract", "") or "")

    # Source-based shortcuts
    if "grey" in source:
        # Check if it's a working paper or a report
        for pat in WORKING_PAPER_PATTERNS:
            if re.search(pat, title, re.IGNORECASE):
                return "working-paper"
        return "report"

    if "teaching" in source:
        # Teaching canon is mostly books and seminal articles
        for pat in BOOK_DOI_PATTERNS:
            if re.search(pat, doi):
                return "book"
        if not journal or journal in ("nan", "none", ""):
            return "book"

    # DOI-based classification
    doi_prefix = doi.split("/")[0] if "/" in doi else ""
    if doi_prefix in REPORT_DOI_PREFIXES:
        for pat in WORKING_PAPER_PATTERNS:
            if re.search(pat, title, re.IGNORECASE):
                return "working-paper"
        return "report"
    for pat in BOOK_DOI_PATTERNS:
        if re.search(pat, doi):
            return "book"

    # Journal field analysis
    if journal and journal not in ("nan", "none", ""):
        journal_clean = journal.strip().lower()
        # Is it actually a publisher?
        if journal_clean in PUBLISHERS_NOT_JOURNALS:
            for pat in WORKING_PAPER_PATTERNS:
                if re.search(pat, title, re.IGNORECASE):
                    return "working-paper"
            return "report"
        # Conference proceedings journal names
        if any(w in journal_clean for w in ["proceedings", "conference", "symposium"]):
            return "conference-paper"
        # Energy Procedia, Procedia, etc.
        if "procedia" in journal_clean:
            return "conference-paper"
        # If journal looks like a real journal name, it's an article
        if len(journal_clean) > 3:
            return "article"

    # Title-based classification (no journal match)
    for pat in DISSERTATION_PATTERNS:
        if re.search(pat, title, re.IGNORECASE):
            return "dissertation"
    for pat in WORKING_PAPER_PATTERNS:
        if re.search(pat, title, re.IGNORECASE):
            return "working-paper"
    for pat in REPORT_TITLE_PATTERNS:
        if re.search(pat, title, re.IGNORECASE):
            return "report"
    for pat in CONFERENCE_PATTERNS:
        if re.search(pat, title, re.IGNORECASE):
            return "conference-paper"
    for pat in BOOK_TITLE_PATTERNS:
        if re.search(pat, title, re.IGNORECASE):
            return "book"

    # Fallback: if has a DOI and abstract, likely an article
    if doi and doi not in ("nan", "none", "") and len(abstract) > 100:
        return "article"

    return "other"


def main():
    parser = argparse.ArgumentParser(description="Detect and fix document types")
    parser.add_argument("--apply", action="store_true", help="Write doc_type to refined_works.csv")
    args = parser.parse_args()

    path = os.path.join(CATALOGS_DIR, "refined_works.csv")
    df = pd.read_csv(path)
    print(f"Loaded {len(df)} works")

    # Classify
    print("Classifying document types...")
    df["doc_type"] = df.apply(classify_type, axis=1)

    # Summary
    print(f"\n=== Document type distribution ===")
    print(df["doc_type"].value_counts())

    # By source
    PRIMARY_SOURCES = [
        "openalex", "openalex_historical", "istex", "bibcnrs",
        "scispsace", "grey", "teaching",
    ]
    print(f"\n=== Document type by source ===")
    for src in PRIMARY_SOURCES:
        from_col = f"from_{src}"
        mask = df[from_col] == 1 if from_col in df.columns else df["source"].str.contains(src, na=False)
        sub = df[mask]
        if len(sub) == 0:
            continue
        dist = sub["doc_type"].value_counts()
        n_article = dist.get("article", 0)
        pct = n_article / len(sub) * 100
        print(f"\n{src} (N={len(sub)}):")
        print(f"  {dist.to_dict()}")
        print(f"  → %article: {pct:.0f}%")

    # Flag misleading journal entries
    is_publisher = df["journal"].str.lower().str.strip().isin(PUBLISHERS_NOT_JOURNALS)
    n_misleading = is_publisher.sum()
    print(f"\n=== Misleading journal field (publisher name, not journal): {n_misleading} ===")
    if n_misleading > 0:
        print(df[is_publisher][["title", "journal", "doc_type"]].head(10).to_string(max_colwidth=60))

    # Save report
    report = df[["title", "journal", "source", "doc_type"]].copy()
    report_path = os.path.join(BASE_DIR, "content", "tables", "qa_type_report.csv")
    save_csv(report, report_path)

    if args.apply:
        full_df = pd.read_csv(path)
        full_df["doc_type"] = df["doc_type"]
        # Clean misleading journal entries: move publisher to a note, clear journal
        publisher_mask = full_df["journal"].str.lower().str.strip().isin(PUBLISHERS_NOT_JOURNALS)
        full_df.loc[publisher_mask, "journal"] = ""
        full_df.to_csv(path, index=False)
        print(f"\nUpdated {path} with doc_type column and cleaned journal field")
    else:
        print(f"\nDry run. Use --apply to write changes.")


if __name__ == "__main__":
    main()
