#!/usr/bin/env python3
"""Merge all source catalogs into a unified, deduplicated catalog.

Reads the 6 declared per-source catalogs from data/catalogs/ and produces:
  data/catalogs/unified_works.csv

Only these files are loaded (matching dvc.yaml catalog_merge deps):
  bibcnrs, istex, openalex, grey, teaching, scispsace

Deduplication: DOI-based (primary), then normalized title+year match (fallback).
Priority for field values follows SOURCE_PRIORITY list.

Usage:
    python scripts/catalog_merge.py
"""

import argparse
import os

import pandas as pd
import yaml

from utils import (BASE_DIR, CATALOGS_DIR, FROM_COLS, WORKS_COLUMNS,
                   get_logger, normalize_doi, normalize_title, save_csv)

log = get_logger("catalog_merge")

SOURCE_PRIORITY = ["openalex", "semanticscholar", "scopus", "istex", "bibcnrs", "scispsace", "grey", "teaching"]


SOURCE_RANK = {s: i for i, s in enumerate(SOURCE_PRIORITY)}


def _dedup_vectorized(df, group_col):
    """Vectorized dedup: sort by priority, pick first non-empty per group.

    1. Add a priority rank column and sort so highest-priority rows come first.
    2. Replace empty strings with NaN so groupby().first() skips them.
    3. Use first() for text columns, max() for cited_by_count, any() for from_*.
    """
    df = df.copy()
    df["_rank"] = df["source"].map(SOURCE_RANK).fillna(99)
    df = df.sort_values(["_rank", group_col])

    # cited_by_count as numeric for max aggregation
    df["_cbc_num"] = pd.to_numeric(df["cited_by_count"], errors="coerce")

    # Replace empty strings with NaN so first() skips them
    text_cols = [c for c in WORKS_COLUMNS if c != "cited_by_count"]
    df[text_cols] = df[text_cols].replace("", pd.NA)

    # Build aggregation: first() for text, max() for citations, max() for from_*
    agg = {c: "first" for c in text_cols}
    agg["_cbc_num"] = "max"
    for col in FROM_COLS:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)
            agg[col] = "max"

    result = df.groupby(group_col, sort=False).agg(agg)

    # Restore cited_by_count from numeric max
    result["cited_by_count"] = result["_cbc_num"].apply(
        lambda x: str(int(x)) if pd.notna(x) else "")
    result = result.drop(columns=["_cbc_num"])

    # Fill NaN back to empty string
    result[text_cols] = result[text_cols].fillna("")

    # Ensure from_* columns exist and are int
    for col in FROM_COLS:
        if col not in result.columns:
            result[col] = 0
        else:
            result[col] = result[col].astype(int)

    return result.reset_index(drop=True)


def catalog_files_from_dvc():
    """Read catalog_merge deps from dvc.yaml — single source of truth."""
    dvc_path = os.path.join(BASE_DIR, "dvc.yaml")
    with open(dvc_path) as f:
        dvc = yaml.safe_load(f)
    deps = dvc["stages"]["catalog_merge"]["deps"]
    return [d for d in deps if d.endswith("_works.csv")]


def main():
    # Load only the catalogs declared as deps in dvc.yaml
    catalog_deps = catalog_files_from_dvc()
    files = [os.path.join(BASE_DIR, d) for d in catalog_deps]
    missing = [f for f in files if not os.path.exists(f)]
    if missing:
        for f in missing:
            log.warning("missing catalog: %s", f)
        files = [f for f in files if os.path.exists(f)]

    if not files:
        log.error("No catalog files found in data/catalogs/")
        return

    log.info("Loading catalogs:")
    frames = []
    for f in files:
        name = os.path.basename(f).replace("_works.csv", "")
        try:
            df = pd.read_csv(f, encoding="utf-8", dtype=str, keep_default_na=False)
            log.info("  %s: %d rows", name, len(df))
            frames.append(df)
        except Exception as e:
            log.error("  %s: ERROR - %s", name, e)

    if not frames:
        log.error("No data loaded.")
        return

    combined = pd.concat(frames, ignore_index=True)
    log.info("Total records before dedup: %d", len(combined))

    # Normalize DOIs
    combined["_doi_norm"] = combined["doi"].apply(normalize_doi)

    # Set from_* provenance columns based on source field
    for col in FROM_COLS:
        src_name = col.replace("from_", "")
        combined[col] = (combined["source"] == src_name).astype(int)

    # Pass 1: DOI-based dedup (vectorized)
    has_doi = combined[combined["_doi_norm"] != ""]
    no_doi = combined[combined["_doi_norm"] == ""]
    log.info("  With DOI: %d, without DOI: %d", len(has_doi), len(no_doi))

    parts = []
    if len(has_doi) > 0:
        parts.append(_dedup_vectorized(has_doi, "_doi_norm"))
        log.info("  After DOI dedup: %d", len(parts[-1]))

    # Pass 2: title+year dedup for records without DOI (vectorized)
    if len(no_doi) > 0:
        no_doi = no_doi.copy()
        no_doi["_title_norm"] = no_doi["title"].apply(normalize_title)
        no_doi["_year"] = no_doi["year"].astype(str).str[:4]
        # Drop empty titles
        no_doi = no_doi[no_doi["_title_norm"] != ""]
        if len(no_doi) > 0:
            # Composite key for groupby
            no_doi["_title_year"] = no_doi["_title_norm"] + "|" + no_doi["_year"]
            parts.append(_dedup_vectorized(no_doi, "_title_year"))
            log.info("  After title dedup: %d", len(parts[-1]))

    result = pd.concat(parts, ignore_index=True) if parts else pd.DataFrame()

    # Ensure all expected columns
    for col in WORKS_COLUMNS:
        if col not in result.columns:
            result[col] = ""
    for col in FROM_COLS:
        if col not in result.columns:
            result[col] = 0
    result = result[WORKS_COLUMNS + FROM_COLS]

    # Add source_count
    result["source_count"] = result[FROM_COLS].sum(axis=1).astype(int)

    # Sort by year desc, then cited_by_count desc
    result["_year_sort"] = pd.to_numeric(result["year"], errors="coerce")
    result["_cite_sort"] = pd.to_numeric(result["cited_by_count"], errors="coerce")
    result = result.sort_values(["_year_sort", "_cite_sort"],
                                ascending=[False, False])
    result = result.drop(columns=["_year_sort", "_cite_sort"])

    save_csv(result, os.path.join(CATALOGS_DIR, "unified_works.csv"))

    log.info("Summary:")
    log.info("  Unified works: %d", len(result))
    log.info("  Multi-source works: %d", (result['source_count'] > 1).sum())
    log.info("  Source distribution:")
    for col in FROM_COLS:
        src_name = col.replace("from_", "")
        count = (result[col] == 1).sum()
        if count:
            log.info("    %s: %d", src_name, count)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    main()
