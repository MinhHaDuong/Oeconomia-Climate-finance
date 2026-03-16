#!/usr/bin/env python3
"""Extract syllabus readings into teaching_works.csv for the merge pipeline.

Reads:  data/teaching_sources.yaml
Writes: catalogs/teaching_works.csv   (all readings formatted for merge)

The merge pipeline (catalog_merge.py) handles deduplication against other
sources via DOI and title+year matching, and sets from_teaching=1 for any
work that appears in this file.

Usage:
    python scripts/build_teaching_canon.py
"""

import os
import sys

import pandas as pd
import yaml

sys.path.insert(0, os.path.dirname(__file__))
from utils import DATA_DIR, CATALOGS_DIR, WORKS_COLUMNS, normalize_doi, save_csv

YAML_PATH = os.path.join(DATA_DIR, "teaching_sources.yaml")


def load_teaching_sources():
    """Load and flatten teaching_sources.yaml into a list of (reading, meta) tuples."""
    with open(YAML_PATH, encoding="utf-8") as f:
        sources = yaml.safe_load(f)

    readings = []
    for src in sources:
        meta = {
            "institution": src["institution"],
            "course": src["course"],
            "level": src["level"],
            "region": src["region"],
            "year": src.get("year", ""),
        }
        for r in src.get("readings", []):
            reading = dict(r)
            reading["_meta"] = meta
            readings.append(reading)

    print(f"Loaded {len(readings)} readings from {len(sources)} institutions")
    return readings, sources


def build_teaching_works(readings):
    """Convert all syllabus readings into a WORKS_COLUMNS DataFrame.

    Each unique reading (by DOI or title) becomes one row. Duplicates across
    syllabi are deduplicated here; the merge will further deduplicate against
    other sources.
    """
    # Deduplicate by normalized DOI or title
    seen = set()
    rows = []

    for r in readings:
        doi = r.get("doi", "") or ""
        title = r.get("title", "") or ""
        authors = r.get("authors", "") or ""
        year = str(r.get("year", "") or "")

        # Dedup key: normalized DOI if available, else title
        ndoi = normalize_doi(doi)
        key = ndoi if ndoi else title.strip().lower()
        if not key:
            continue
        if key in seen:
            continue
        seen.add(key)

        row = {col: "" for col in WORKS_COLUMNS}
        row["source"] = "teaching"
        row["doi"] = doi
        row["title"] = title
        row["first_author"] = authors.split(",")[0].strip() if authors else ""
        row["all_authors"] = authors
        row["year"] = year
        rows.append(row)

    df = pd.DataFrame(rows, columns=WORKS_COLUMNS)
    # Only keep rows that have at least a title or DOI
    df = df[(df["title"].str.strip() != "") | (df["doi"].str.strip() != "")]
    return df


def main():
    print("Extracting teaching sources...")
    readings, sources = load_teaching_sources()

    print("\nBuilding teaching_works.csv...")
    works_df = build_teaching_works(readings)

    works_path = os.path.join(CATALOGS_DIR, "teaching_works.csv")
    save_csv(works_df, works_path)

    n_with_doi = (works_df["doi"].str.strip() != "").sum()
    n_title_only = len(works_df) - n_with_doi
    print(f"\n{'='*60}")
    print(f"TEACHING WORKS SUMMARY")
    print(f"{'='*60}")
    print(f"  Institutions surveyed: {len(sources)}")
    print(f"  Total readings: {len(readings)}")
    print(f"  Unique works extracted: {len(works_df)}")
    print(f"    With DOI: {n_with_doi}")
    print(f"    Title-only: {n_title_only}")


if __name__ == "__main__":
    main()
