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

import pandas as pd

from utils import CATALOGS_DIR, get_logger, save_csv, BASE_DIR

log = get_logger("qa_detect_type")

# Publishers that are NOT journals (often stored in journal field)
PUBLISHERS_NOT_JOURNALS = {
    "world bank",
    "oecd",
    "oecd publishing",
    "imf",
    "international monetary fund",
    "undp",
    "unep",
    "unfccc",
    "iea",
    "irena",
    "adb",
    "asian development bank",
    "african development bank",
    "inter-american development bank",
    "european commission",
    "european investment bank",
    "climate policy initiative",
    "overseas development institute",
    "brookings institution",
    "chatham house",
    "wri",
    "world resources institute",
    "cifor",
    "cgiar",
    "fao",
    "giz",
    "springer",
    "elsevier",
    "wiley",
    "taylor & francis",
    "routledge",
    "cambridge university press",
    "oxford university press",
    "mit press",
    "palgrave macmillan",
    "edward elgar",
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
    r"\bworking paper\b",
    r"\bwp\s*#?\d+",
    r"\bdiscussion paper\b",
    r"\bpolicy\s+research\s+working\s+paper\b",
    r"\bnber\b",
    r"\bcepr\b",
    r"\bssrn\b",
]
REPORT_TITLE_PATTERNS = [
    r"\breport\b",
    r"\bcountry\s+climate\s+and\s+development\b",
    r"\bworld\s+development\s+report\b",
    r"\bglobal\s+economic\s+prospects\b",
    r"\bevaluation\b.*\bpaper\b",
    r"\broadmap\b",
    r"\bmarket\s+study\b",
    r"\bguidelines?\b",
    r"\bhandbook\b",
]
BOOK_TITLE_PATTERNS = [
    r"^the\s+(economics|politics|political\s+economy)\s+of\b",
    r"\ba\s+(guide|companion|introduction)\s+to\b",
]
CONFERENCE_PATTERNS = [
    r"\bconference\b",
    r"\bproceedings\b",
    r"\bsymposium\b",
    r"\bworkshop\b",
]
DISSERTATION_PATTERNS = [
    r"\bdissertation\b",
    r"\bthesis\b",
    r"\bph\.?d\.?\b",
]


def _match_any(patterns, text, flags=re.IGNORECASE):
    """Return True if any regex pattern matches text."""
    return any(re.search(pat, text, flags) for pat in patterns)


def _is_empty(value):
    """Return True if a metadata field is missing / blank / NaN-like."""
    return not value or value in ("nan", "none", "")


def _classify_from_source(source, title, doi, journal):
    """Source-based shortcuts (grey literature, teaching canon)."""
    if "grey" in source:
        return (
            "working-paper" if _match_any(WORKING_PAPER_PATTERNS, title) else "report"
        )
    if "teaching" in source:
        if _match_any(BOOK_DOI_PATTERNS, doi, flags=0):
            return "book"
        if _is_empty(journal):
            return "book"
    return None


def _classify_from_doi(doi, title):
    """DOI-prefix and DOI-pattern classification."""
    doi_prefix = doi.split("/")[0] if "/" in doi else ""
    if doi_prefix in REPORT_DOI_PREFIXES:
        return (
            "working-paper" if _match_any(WORKING_PAPER_PATTERNS, title) else "report"
        )
    if _match_any(BOOK_DOI_PATTERNS, doi, flags=0):
        return "book"
    return None


def _classify_from_journal(journal, title):
    """Journal-field analysis: publisher check, proceedings, real journal."""
    if _is_empty(journal):
        return None
    # journal is already lowered+stripped by classify_type
    if journal in PUBLISHERS_NOT_JOURNALS:
        return (
            "working-paper" if _match_any(WORKING_PAPER_PATTERNS, title) else "report"
        )
    if any(w in journal for w in ("proceedings", "conference", "symposium")):
        return "conference-paper"
    if "procedia" in journal:
        return "conference-paper"
    if len(journal) > 3:
        return "article"
    return None


# Ordered list of (patterns, doc_type) for title-based fallback classification.
_TITLE_RULES = [
    (DISSERTATION_PATTERNS, "dissertation"),
    (WORKING_PAPER_PATTERNS, "working-paper"),
    (REPORT_TITLE_PATTERNS, "report"),
    (CONFERENCE_PATTERNS, "conference-paper"),
    (BOOK_TITLE_PATTERNS, "book"),
]


def _classify_from_title(title):
    """Title-based classification when journal is absent."""
    for patterns, doc_type in _TITLE_RULES:
        if _match_any(patterns, title):
            return doc_type
    return None


def classify_type(row):
    """Classify document type from metadata heuristics."""
    title = str(row.get("title", "") or "").lower()
    journal = str(row.get("journal", "") or "").lower().strip()
    doi = str(row.get("doi", "") or "").lower()
    source = str(row.get("source", "") or "").lower()
    abstract = str(row.get("abstract", "") or "")

    result = _classify_from_source(source, title, doi, journal)
    if result:
        return result

    result = _classify_from_doi(doi, title)
    if result:
        return result

    result = _classify_from_journal(journal, title)
    if result:
        return result

    result = _classify_from_title(title)
    if result:
        return result

    # Fallback: if has a DOI and abstract, likely an article
    if not _is_empty(doi) and len(abstract) > 100:
        return "article"

    return "other"


def main():
    parser = argparse.ArgumentParser(description="Detect and fix document types")
    parser.add_argument(
        "--apply", action="store_true", help="Write doc_type to refined_works.csv"
    )
    args = parser.parse_args()

    path = os.path.join(CATALOGS_DIR, "refined_works.csv")
    df = pd.read_csv(path)
    log.info("Loaded %d works", len(df))

    # Classify
    log.info("Classifying document types...")
    df["doc_type"] = df.apply(classify_type, axis=1)

    # Summary
    log.info("=== Document type distribution ===")
    log.info("\n%s", df["doc_type"].value_counts())

    # By source
    PRIMARY_SOURCES = [
        "openalex",
        "openalex_historical",
        "istex",
        "bibcnrs",
        "scispsace",
        "grey",
        "teaching",
    ]
    log.info("=== Document type by source ===")
    for src in PRIMARY_SOURCES:
        from_col = f"from_{src}"
        mask = (
            df[from_col] == 1
            if from_col in df.columns
            else df["source"].str.contains(src, na=False)
        )
        sub = df[mask]
        if len(sub) == 0:
            continue
        dist = sub["doc_type"].value_counts()
        n_article = dist.get("article", 0)
        pct = n_article / len(sub) * 100
        log.info("%s (N=%d):", src, len(sub))
        log.info("  %s", dist.to_dict())
        log.info("  -> %%article: %.0f%%", pct)

    # Flag misleading journal entries
    is_publisher = df["journal"].str.lower().str.strip().isin(PUBLISHERS_NOT_JOURNALS)
    n_misleading = is_publisher.sum()
    log.info(
        "=== Misleading journal field (publisher name, not journal): %d ===",
        n_misleading,
    )
    if n_misleading > 0:
        log.info(
            "\n%s",
            df[is_publisher][["title", "journal", "doc_type"]]
            .head(10)
            .to_string(max_colwidth=60),
        )

    # Save report
    report = df[["title", "journal", "source", "doc_type"]].copy()
    report_path = os.path.join(BASE_DIR, "content", "tables", "qa_type_report.csv")
    save_csv(report, report_path)

    if args.apply:
        full_df = pd.read_csv(path)
        full_df["doc_type"] = df["doc_type"]
        # Clean misleading journal entries: move publisher to a note, clear journal
        publisher_mask = (
            full_df["journal"].str.lower().str.strip().isin(PUBLISHERS_NOT_JOURNALS)
        )
        full_df.loc[publisher_mask, "journal"] = ""
        full_df.to_csv(path, index=False)
        log.info("Updated %s with doc_type column and cleaned journal field", path)
    else:
        log.info("Dry run. Use --apply to write changes.")


if __name__ == "__main__":
    main()
