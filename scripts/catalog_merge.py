#!/usr/bin/env python3
"""Merge all source catalogs into a unified, deduplicated catalog.

Reads all data/catalogs/*_works.csv files and produces:
  data/catalogs/unified_works.csv

Deduplication: DOI-based (primary), then title+year fuzzy match (fallback).
Priority for field values: openalex > scopus > istex > jstor > bibcnrs > grey

Usage:
    python scripts/catalog_merge.py
"""

import glob
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import (CATALOGS_DIR, WORKS_COLUMNS, normalize_doi,
                   normalize_title, save_csv)

SOURCE_PRIORITY = ["openalex", "scopus", "istex", "jstor", "bibcnrs", "scispsace", "grey"]


def pick_best(group, col):
    """Pick best non-empty value from a group following source priority."""
    for src in SOURCE_PRIORITY:
        rows = group[group["source"] == src]
        for _, row in rows.iterrows():
            val = row[col]
            if pd.notna(val) and str(val).strip():
                return val
    # Fallback: first non-empty
    for _, row in group.iterrows():
        val = row[col]
        if pd.notna(val) and str(val).strip():
            return val
    return ""


def merge_group(group):
    """Merge a group of duplicate records into one."""
    sources = sorted(group["source"].unique(),
                     key=lambda s: SOURCE_PRIORITY.index(s)
                     if s in SOURCE_PRIORITY else 99)
    result = {}
    for col in WORKS_COLUMNS:
        if col == "source":
            result[col] = "|".join(sources)
        elif col == "cited_by_count":
            # Take max
            counts = pd.to_numeric(group[col], errors="coerce")
            result[col] = int(counts.max()) if counts.notna().any() else ""
        else:
            result[col] = pick_best(group, col)
    return result


def main():
    # Find all source catalogs
    pattern = os.path.join(CATALOGS_DIR, "*_works.csv")
    files = sorted(glob.glob(pattern))
    files = [f for f in files if "unified" not in os.path.basename(f)]

    if not files:
        print("No catalog files found in data/catalogs/")
        return

    print("Loading catalogs:")
    frames = []
    for f in files:
        name = os.path.basename(f).replace("_works.csv", "")
        try:
            df = pd.read_csv(f, encoding="utf-8", dtype=str, keep_default_na=False)
            print(f"  {name}: {len(df)} rows")
            frames.append(df)
        except Exception as e:
            print(f"  {name}: ERROR - {e}")

    if not frames:
        print("No data loaded.")
        return

    combined = pd.concat(frames, ignore_index=True)
    print(f"\nTotal records before dedup: {len(combined)}")

    # Normalize DOIs
    combined["_doi_norm"] = combined["doi"].apply(normalize_doi)

    # Pass 1: DOI-based dedup
    has_doi = combined[combined["_doi_norm"] != ""]
    no_doi = combined[combined["_doi_norm"] == ""]
    print(f"  With DOI: {len(has_doi)}, without DOI: {len(no_doi)}")

    merged_by_doi = []
    if len(has_doi) > 0:
        for doi, group in has_doi.groupby("_doi_norm"):
            merged_by_doi.append(merge_group(group))

    # Pass 2: title+year dedup for records without DOI
    merged_by_title = []
    if len(no_doi) > 0:
        no_doi = no_doi.copy()
        no_doi["_title_norm"] = no_doi["title"].apply(normalize_title)
        no_doi["_year"] = no_doi["year"].astype(str).str[:4]

        for (title, year), group in no_doi.groupby(["_title_norm", "_year"]):
            if title:  # skip empty titles
                merged_by_title.append(merge_group(group))

    all_merged = merged_by_doi + merged_by_title
    result = pd.DataFrame(all_merged)
    # Ensure we have all expected columns
    for col in WORKS_COLUMNS:
        if col not in result.columns:
            result[col] = ""
    result = result[WORKS_COLUMNS]

    # Add source_count
    result["source_count"] = result["source"].str.split("|").str.len()

    # Sort by year desc, then cited_by_count desc
    result["_year_sort"] = pd.to_numeric(result["year"], errors="coerce")
    result["_cite_sort"] = pd.to_numeric(result["cited_by_count"], errors="coerce")
    result = result.sort_values(["_year_sort", "_cite_sort"],
                                ascending=[False, False])
    result = result.drop(columns=["_year_sort", "_cite_sort"])

    save_csv(result, os.path.join(CATALOGS_DIR, "unified_works.csv"))

    print(f"\nSummary:")
    print(f"  Unified works: {len(result)}")
    print(f"  Multi-source works: {(result['source_count'] > 1).sum()}")
    print(f"  Source distribution:")
    for src in SOURCE_PRIORITY:
        count = result["source"].str.contains(src).sum()
        if count:
            print(f"    {src}: {count}")


if __name__ == "__main__":
    main()
