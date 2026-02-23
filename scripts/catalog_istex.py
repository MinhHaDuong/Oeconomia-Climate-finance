#!/usr/bin/env python3
"""Build catalog from local ISTEX JSON metadata files.

Reads data/raw/<hash>/<hash>.json and produces:
  - data/catalogs/istex_works.csv  (484 articles)
  - data/catalogs/istex_refs.csv   (~20K cited references)
"""

import glob
import json
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import (CATALOGS_DIR, RAW_DIR, WORKS_COLUMNS, REFS_COLUMNS,
                   normalize_doi, save_csv)


def is_email(s):
    return bool(re.search(r"[^@\s]+@[^@\s]+\.[^@\s]+", s))


def parse_article(json_path):
    """Parse one ISTEX JSON file into a works record and a list of ref records."""
    with open(json_path, encoding="utf-8") as f:
        d = json.load(f)

    source_id = d.get("_id", "")
    doi = normalize_doi(d.get("doi"))
    title = d.get("title", "")
    authors = d.get("author", [])
    first_author = authors[0]["name"] if authors else ""
    all_authors = " ; ".join(a.get("name", "") for a in authors)

    # Affiliations (filter out email-only entries)
    affs = []
    for a in authors:
        for aff in a.get("affiliations", []):
            if aff and not is_email(aff):
                affs.append(aff)
    affiliations = " ; ".join(dict.fromkeys(affs))  # deduplicate, preserve order

    year = d.get("publicationDate", "")
    journal = d.get("host", {}).get("title", "")
    abstract = d.get("abstract", "")
    lang = d.get("language", [])
    language = lang[0] if lang else ""

    kw = d.get("keywords", {}).get("teeft", [])
    keywords = " ; ".join(kw[:20])

    cats = d.get("categories", {})
    cat_parts = []
    for system in ("wos", "scopus", "scienceMetrix", "inist"):
        vals = cats.get(system, [])
        if vals:
            cat_parts.append(f"{system}:{';'.join(vals)}")
    categories = " | ".join(cat_parts)

    work = {
        "source": "istex",
        "source_id": source_id,
        "doi": doi,
        "title": title,
        "first_author": first_author,
        "all_authors": all_authors,
        "year": year,
        "journal": journal,
        "abstract": abstract,
        "language": language,
        "keywords": keywords,
        "categories": categories,
        "cited_by_count": "",
        "affiliations": affiliations,
    }

    # Parse refBibs
    refs = []
    for rb in d.get("refBibs", []):
        ref_doi = normalize_doi(rb.get("doi"))
        ref_title = rb.get("title", "")
        host = rb.get("host", {})

        # Determine ref_journal: if refBib has its own title, host.title is the journal
        # If refBib has no title, host.title might be a book title
        ref_journal = host.get("title", "") if ref_title else ""

        # If no article-level title, use host title as the title
        if not ref_title:
            ref_title = host.get("title", "")

        # First author
        ref_authors = rb.get("author", host.get("author", []))
        ref_first_author = ref_authors[0].get("name", "") if ref_authors else ""

        ref_year = rb.get("publicationDate", host.get("publicationDate", ""))

        refs.append({
            "source_doi": doi,
            "source_id": source_id,
            "ref_doi": ref_doi,
            "ref_title": ref_title,
            "ref_first_author": ref_first_author,
            "ref_year": ref_year,
            "ref_journal": ref_journal,
            "ref_raw": json.dumps(rb, ensure_ascii=False),
        })

    return work, refs


def main():
    pattern = os.path.join(RAW_DIR, "*", "*.json")
    json_files = sorted(glob.glob(pattern))
    # Exclude manifest.json
    json_files = [f for f in json_files if not f.endswith("manifest.json")]
    print(f"Found {len(json_files)} ISTEX JSON files")

    works = []
    all_refs = []
    for i, jf in enumerate(json_files):
        work, refs = parse_article(jf)
        works.append(work)
        all_refs.extend(refs)
        if (i + 1) % 100 == 0:
            print(f"  Parsed {i + 1}/{len(json_files)}...")

    works_df = pd.DataFrame(works, columns=WORKS_COLUMNS)
    refs_df = pd.DataFrame(all_refs, columns=REFS_COLUMNS)

    save_csv(works_df, os.path.join(CATALOGS_DIR, "istex_works.csv"))
    save_csv(refs_df, os.path.join(CATALOGS_DIR, "istex_refs.csv"))

    print(f"\nSummary:")
    print(f"  Works: {len(works_df)}")
    print(f"  References: {len(refs_df)}")
    print(f"  Refs with DOI: {(refs_df['ref_doi'] != '').sum()}")
    print(f"  Year range: {works_df['year'].min()} - {works_df['year'].max()}")


if __name__ == "__main__":
    main()
