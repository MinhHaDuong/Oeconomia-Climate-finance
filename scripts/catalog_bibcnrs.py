#!/usr/bin/env python3
"""Parse user-provided bibCNRS exports (RIS or BibTeX).

bibCNRS is a web portal (https://bib.cnrs.fr/) requiring CNRS credentials.
It aggregates WoS, EconLit, FRANCIS, PASCAL, and other databases.

Purpose: complement OpenAlex with non-English literature (French, Chinese, Japanese, German).
OpenAlex under-represents these languages. bibCNRS adds 242 works (after dedup) from
three queries: French (finance climat), Chinese (气候金融/气候融资), Japanese (気候金融/グリーンファイナンス)

Produces: data/catalogs/bibcnrs_works.csv

Usage:
    # First, export from bib.cnrs.fr to data/exports/
    python scripts/catalog_bibcnrs.py
"""

import argparse
import glob
import os
import re

import pandas as pd
from utils import (
    CATALOGS_DIR,
    EXPORTS_DIR,
    WORKS_COLUMNS,
    get_logger,
    normalize_doi,
    save_csv,
)

log = get_logger("catalog_bibcnrs")

INSTRUCTIONS = """No bibCNRS export found in data/exports/.

To use this script (French-language complement to OpenAlex):
1. Go to https://bib.cnrs.fr/ (requires CNRS Janus credentials)
2. Search across databases (EconLit, WoS, FRANCIS...):
   TI "finance climat" OR TI "finance climatique"
   (~332 results as of 2026-02)
3. Select all results, export as RIS (.ris) in batches of 100
4. Save files to data/exports/ (e.g. bibcnrs_001.ris, bibcnrs_002.ris, ...)
5. Re-run this script

Note: English query ("climate finance") returns 19,915 results already
covered by OpenAlex. The French query targets OpenAlex's blind spot."""


def parse_ris(path):
    """Parse RIS format."""
    records = []
    current = {}
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            line = line.rstrip("\n")
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
                        current[tag] = val
    if current:
        records.append(_ris_to_record(current))
    return records


def _ris_to_record(c):
    authors = c.get("AU", c.get("A1", []))
    if isinstance(authors, str):
        authors = [authors]
    return {
        "source": "bibcnrs",
        "source_id": c.get("ID", c.get("AN", "")),
        "doi": normalize_doi(c.get("DO", "")),
        "title": c.get("TI", c.get("T1", "")),
        "first_author": authors[0] if authors else "",
        "all_authors": " ; ".join(authors),
        "year": (c.get("PY", c.get("Y1", "")) or "")[:4],
        "journal": c.get("JO", c.get("T2", c.get("JF", ""))),
        "abstract": c.get("AB", ""),
        "language": c.get("LA", ""),
        "keywords": " ; ".join(c.get("KW", [])) if isinstance(c.get("KW"), list) else c.get("KW", ""),
        "categories": c.get("TY", ""),
        "cited_by_count": "",
        "affiliations": "",
    }


def parse_bibtex(path):
    """Simple BibTeX parser (no external deps)."""
    records = []
    with open(path, encoding="utf-8", errors="replace") as f:
        content = f.read()

    # Split on @type{key, ...}
    entries = re.findall(r"@(\w+)\{([^,]*),(.*?)\n\}", content, re.DOTALL)
    for entry_type, key, body in entries:
        fields = {}
        for m in re.finditer(r"(\w+)\s*=\s*[{\"](.+?)[}\"]", body):
            fields[m.group(1).lower()] = m.group(2)

        authors_raw = fields.get("author", "")
        authors = [a.strip() for a in authors_raw.split(" and ")]

        records.append({
            "source": "bibcnrs",
            "source_id": key.strip(),
            "doi": normalize_doi(fields.get("doi", "")),
            "title": fields.get("title", ""),
            "first_author": authors[0] if authors else "",
            "all_authors": " ; ".join(authors),
            "year": fields.get("year", "")[:4],
            "journal": fields.get("journal", fields.get("booktitle", "")),
            "abstract": fields.get("abstract", ""),
            "language": fields.get("language", ""),
            "keywords": fields.get("keywords", ""),
            "categories": entry_type,
            "cited_by_count": "",
            "affiliations": "",
        })
    return records


def main():
    ris_files = glob.glob(os.path.join(EXPORTS_DIR, "bibcnrs*.ris")) + \
                glob.glob(os.path.join(EXPORTS_DIR, "francis*.ris")) + \
                glob.glob(os.path.join(EXPORTS_DIR, "pascal*.ris"))
    bib_files = glob.glob(os.path.join(EXPORTS_DIR, "bibcnrs*.bib")) + \
                glob.glob(os.path.join(EXPORTS_DIR, "francis*.bib")) + \
                glob.glob(os.path.join(EXPORTS_DIR, "pascal*.bib"))

    all_files = ris_files + bib_files
    if not all_files:
        # Try any RIS/BibTeX in exports
        all_ris = set(glob.glob(os.path.join(EXPORTS_DIR, "*.ris")))
        all_bib = set(glob.glob(os.path.join(EXPORTS_DIR, "*.bib")))
        all_files = list(all_ris | all_bib)

    if not all_files:
        log.info(INSTRUCTIONS)
        return

    all_records = []
    for path in all_files:
        log.info("Parsing: %s", os.path.basename(path))
        if path.endswith(".ris"):
            all_records.extend(parse_ris(path))
        elif path.endswith(".bib"):
            all_records.extend(parse_bibtex(path))

    if not all_records:
        log.info("No records extracted.")
        return

    df = pd.DataFrame(all_records, columns=WORKS_COLUMNS)

    # Deduplicate by title (overlapping bibCNRS export batches)
    before = len(df)
    df["_norm_title"] = df["title"].str.lower().str.strip()
    df = df.drop_duplicates(subset="_norm_title", keep="first")
    df = df.drop(columns="_norm_title")
    if before > len(df):
        log.info("Deduplicated: %d -> %d (%d duplicates removed)", before, len(df), before - len(df))

    save_csv(df, os.path.join(CATALOGS_DIR, "bibcnrs_works.csv"))
    log.info("Summary: %d works", len(df))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    main()
