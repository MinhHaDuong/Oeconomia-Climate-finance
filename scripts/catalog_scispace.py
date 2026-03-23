#!/usr/bin/env python3
"""Parse SciSpace AI-curated bibliographic data (RIS + CSV exports).

Reads from AI tech reports/SciSpace 1/ and AI tech reports/SciSpace 2/:
  - SciSpace 2 RIS export (curated corpus with DOIs, abstracts)
  - SciSpace 1 combined CSV (primary research compilation)
  - SciSpace 1 paper_table CSV (systematic literature review)

Produces: data/catalogs/scispace_works.csv

Usage:
    python scripts/catalog_scispace.py
"""

import argparse
import glob
import os
import re

import pandas as pd

from utils import BASE_DIR, CATALOGS_DIR, WORKS_COLUMNS, get_logger, normalize_doi, save_csv

log = get_logger("catalog_scispace")

SCISPSACE_DIR = os.path.join(BASE_DIR, "AI tech reports")
SCISPSACE1_DIR = os.path.join(SCISPSACE_DIR, "SciSpace 1")
SCISPSACE2_DIR = os.path.join(SCISPSACE_DIR, "SciSpace 2")


def parse_ris(path):
    """Parse SciSpace RIS export. Handles numbered entries (1., 2., ...)."""
    records = []
    current = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            # Skip SciSpace numbered entry markers
            if re.match(r"^\d+\.\s*$", line):
                continue
            if line.startswith("ER  -"):
                if current:
                    records.append(_ris_to_record(current))
                current = {}
            else:
                m = re.match(r"^([A-Z][A-Z0-9])  - (.*)$", line)
                if m:
                    tag, val = m.group(1), m.group(2)
                    if tag in ("AU", "KW", "A1"):
                        current.setdefault(tag, []).append(val)
                    else:
                        # For AB, accumulate (SciSpace puts long abstracts)
                        if tag == "AB" and "AB" in current:
                            current["AB"] += " " + val
                        else:
                            current[tag] = val
    if current:
        records.append(_ris_to_record(current))
    return records


def _ris_to_record(c):
    authors = c.get("AU", c.get("A1", []))
    if isinstance(authors, str):
        authors = [authors]
    return {
        "source": "scispace",
        "source_id": c.get("DO", ""),
        "doi": normalize_doi(c.get("DO", "")),
        "title": c.get("TI", c.get("T1", "")),
        "first_author": authors[0] if authors else "",
        "all_authors": " ; ".join(authors),
        "year": (c.get("PY", c.get("Y1", "")) or "")[:4],
        "journal": c.get("JO", c.get("T2", c.get("JF", ""))),
        "abstract": c.get("AB", ""),
        "language": c.get("LA", ""),
        "keywords": " ; ".join(c.get("KW", [])) if isinstance(c.get("KW"), list) else c.get("KW", ""),
        "categories": c.get("N1", c.get("TY", "")),
        "cited_by_count": "",
        "affiliations": "",
    }


def parse_scispace_csv(path):
    """Parse SciSpace CSV export (paper_table or combined format)."""
    try:
        df = pd.read_csv(path, encoding="utf-8", dtype=str, keep_default_na=False)
    except Exception as e:
        log.error("  Error reading %s: %s", os.path.basename(path), e)
        return []

    records = []
    for _, row in df.iterrows():
        title = row.get("Paper Title", "")
        if not title.strip():
            continue

        authors_raw = row.get("Author Names", "")
        # SciSpace uses newlines between authors
        authors = [a.strip() for a in authors_raw.replace("\n", ";").split(";") if a.strip()]

        doi_raw = row.get("DOI", "")
        year_raw = str(row.get("Publication Year", ""))

        # Categories: use Thematic Classification if available
        categories = row.get("Thematic Classification", "")
        if not categories:
            categories = row.get("Relevance", "")

        records.append({
            "source": "scispace",
            "source_id": row.get("Paper Link", ""),
            "doi": normalize_doi(doi_raw),
            "title": title,
            "first_author": authors[0] if authors else "",
            "all_authors": " ; ".join(authors),
            "year": year_raw[:4] if year_raw else "",
            "journal": row.get("Publication Title", ""),
            "abstract": row.get("Abstract", ""),
            "language": "",
            "keywords": "",
            "categories": categories,
            "cited_by_count": "",
            "affiliations": "",
        })
    return records


def main():
    all_records = []

    # 1. Parse SciSpace 2 RIS file(s)
    ris_files = glob.glob(os.path.join(SCISPSACE2_DIR, "*.ris"))
    for path in ris_files:
        log.info("Parsing RIS: %s", os.path.basename(path))
        recs = parse_ris(path)
        log.info("  %d records", len(recs))
        all_records.extend(recs)

    # 2. Parse SciSpace 1 key CSVs
    csv_files = [
        os.path.join(SCISPSACE1_DIR, "combined_climate_finance_primary_research.csv"),
        os.path.join(SCISPSACE1_DIR, "paper_table_systematic-li_aCaEsV.csv"),
    ]
    for path in csv_files:
        if os.path.exists(path):
            log.info("Parsing CSV: %s", os.path.basename(path))
            recs = parse_scispace_csv(path)
            log.info("  %d records", len(recs))
            all_records.extend(recs)

    if not all_records:
        log.info("No SciSpace records found.")
        return

    df = pd.DataFrame(all_records, columns=WORKS_COLUMNS)
    log.info("Total raw records: %d", len(df))

    # Deduplicate by normalized title
    before = len(df)
    df["_norm_title"] = df["title"].str.lower().str.strip()
    df = df.drop_duplicates(subset="_norm_title", keep="first")
    df = df.drop(columns="_norm_title")
    log.info("After dedup: %d (%d duplicates removed)", len(df), before - len(df))

    # Stats
    with_doi = (df["doi"] != "").sum()
    log.info("With DOI: %d, without DOI: %d", with_doi, len(df) - with_doi)

    save_csv(df, os.path.join(CATALOGS_DIR, "scispace_works.csv"))
    log.info("Saved %d works to scispace_works.csv", len(df))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    main()
