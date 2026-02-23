#!/usr/bin/env python3
"""Parse user-provided JSTOR/Constellate/EconLit exports.

Looks for CSV or RIS files in data/exports/ and converts to unified format.
Produces: data/catalogs/jstor_works.csv

Usage:
    # First, manually download exports to data/exports/
    python scripts/catalog_jstor.py
"""

import csv
import glob
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import (CATALOGS_DIR, EXPORTS_DIR, WORKS_COLUMNS, normalize_doi,
                   save_csv)

INSTRUCTIONS = """No JSTOR/Constellate/EconLit export found in data/exports/.

Option A - JSTOR Constellate (recommended):
  1. Go to https://constellate.org/
  2. Search: "climate finance" OR "finance climat"
  3. Build a dataset, then export as CSV
  4. Save to data/exports/constellate_export.csv

Option B - EconLit via EBSCO (through bibCNRS):
  1. Go to https://bib.cnrs.fr/
  2. Access EconLit (EBSCO)
  3. Search: "climate finance" in Abstract/Title
  4. Export results as CSV
  5. Save to data/exports/econlit_export.csv

Then re-run this script."""


def parse_constellate_csv(path):
    """Parse Constellate CSV export."""
    records = []
    df = pd.read_csv(path, encoding="utf-8", low_memory=False)
    # Constellate columns vary; try common ones
    for _, row in df.iterrows():
        records.append({
            "source": "jstor",
            "source_id": str(row.get("id", row.get("isPartOf", ""))),
            "doi": normalize_doi(row.get("doi", row.get("DOI", ""))),
            "title": str(row.get("title", row.get("Title", ""))),
            "first_author": str(row.get("creator", row.get("Author Names", ""))).split(";")[0].strip(),
            "all_authors": str(row.get("creator", row.get("Author Names", ""))),
            "year": str(row.get("publicationYear", row.get("Publication Year", "")))[:4],
            "journal": str(row.get("isPartOf", row.get("Publication Title", ""))),
            "abstract": str(row.get("abstract", row.get("Abstract", ""))),
            "language": str(row.get("language", "")),
            "keywords": "",
            "categories": str(row.get("outputType", row.get("Publication Type", ""))),
            "cited_by_count": "",
            "affiliations": "",
        })
    return records


def parse_ris(path):
    """Parse RIS format (used by EBSCO exports)."""
    records = []
    current = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("ER  -"):
                if current:
                    records.append({
                        "source": "jstor",
                        "source_id": current.get("ID", ""),
                        "doi": normalize_doi(current.get("DO", "")),
                        "title": current.get("TI", current.get("T1", "")),
                        "first_author": current.get("AU", [""])[0] if isinstance(current.get("AU"), list) else current.get("AU", ""),
                        "all_authors": " ; ".join(current["AU"]) if isinstance(current.get("AU"), list) else current.get("AU", ""),
                        "year": current.get("PY", current.get("Y1", ""))[:4],
                        "journal": current.get("JO", current.get("T2", current.get("JF", ""))),
                        "abstract": current.get("AB", ""),
                        "language": current.get("LA", ""),
                        "keywords": " ; ".join(current.get("KW", [])) if isinstance(current.get("KW"), list) else current.get("KW", ""),
                        "categories": current.get("TY", ""),
                        "cited_by_count": "",
                        "affiliations": "",
                    })
                current = {}
            else:
                m = re.match(r"^([A-Z][A-Z0-9])  - (.*)$", line)
                if m:
                    tag, val = m.group(1), m.group(2)
                    if tag in ("AU", "KW"):
                        current.setdefault(tag, []).append(val)
                    else:
                        current[tag] = val
    return records


def main():
    csv_files = glob.glob(os.path.join(EXPORTS_DIR, "*.csv"))
    ris_files = glob.glob(os.path.join(EXPORTS_DIR, "*.ris"))
    # Filter for jstor/constellate/econlit patterns
    relevant = [f for f in csv_files + ris_files
                if any(kw in os.path.basename(f).lower()
                       for kw in ("jstor", "constellate", "econlit", "ebsco"))]

    if not relevant:
        # Try all CSV/RIS files in exports
        relevant = csv_files + ris_files

    if not relevant:
        print(INSTRUCTIONS)
        return

    all_records = []
    for path in relevant:
        print(f"Parsing: {os.path.basename(path)}")
        if path.endswith(".ris"):
            all_records.extend(parse_ris(path))
        else:
            all_records.extend(parse_constellate_csv(path))

    if not all_records:
        print("No records extracted from files.")
        return

    df = pd.DataFrame(all_records, columns=WORKS_COLUMNS)
    save_csv(df, os.path.join(CATALOGS_DIR, "jstor_works.csv"))
    print(f"\nSummary: {len(df)} works from {len(relevant)} file(s)")


if __name__ == "__main__":
    main()
