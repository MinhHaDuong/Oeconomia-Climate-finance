#!/usr/bin/env python3
"""Merge citation caches into a single citations.csv.

Reads source-specific cache files from enrich_cache/:
  - crossref_refs.csv   (source_doi, ref_doi, ref_title, ..., ref_raw)
  - openalex_refs.csv   (source_doi, ref_oa_id, ref_doi, ref_title, ...)

Produces citations.csv with REFS_COLUMNS schema, deduplicated on
(source_doi, ref_doi). Sentinel rows are excluded.

This script is the final step of the enrich_citations DVC stage.
It runs after the Crossref and OpenAlex passes (which can run in parallel).
DVC may wipe citations.csv before a re-run — this merge regenerates it
from the persistent caches in seconds, with no API calls.

Usage:
    uv run python scripts/merge_citations.py
"""

import argparse
import os

import pandas as pd
from utils import CATALOGS_DIR, REFS_COLUMNS, get_logger, normalize_doi, save_csv

log = get_logger("merge_citations")

CACHE_DIR = os.path.join(CATALOGS_DIR, "enrich_cache")
CROSSREF_CACHE = os.path.join(CACHE_DIR, "crossref_refs.csv")
OPENALEX_CACHE = os.path.join(CACHE_DIR, "openalex_refs.csv")
OUTPUT_PATH = os.path.join(CATALOGS_DIR, "citations.csv")
SENTINEL_REF_DOI = "__NO_REFS__"


def merge_citations(cache_dir=None, output_path=None):
    """Merge crossref + openalex caches into a single citations.csv.

    Args:
        cache_dir: Path to enrich_cache/ directory (default: CACHE_DIR)
        output_path: Path for output citations.csv (default: OUTPUT_PATH)

    Returns:
        Number of rows written.

    """
    cache_dir = cache_dir or CACHE_DIR
    output_path = output_path or OUTPUT_PATH

    crossref_path = os.path.join(cache_dir, "crossref_refs.csv")
    openalex_path = os.path.join(cache_dir, "openalex_refs.csv")

    frames = []

    # Read Crossref cache — already has REFS_COLUMNS schema.
    # on_bad_lines="warn" tolerates partial trailing lines from crash-during-append.
    if os.path.exists(crossref_path):
        cr = pd.read_csv(crossref_path, dtype=str, keep_default_na=False,
                         on_bad_lines="warn")
        log.info("Crossref cache: %d rows", len(cr))
        frames.append(cr)
    else:
        log.info("No Crossref cache at %s", crossref_path)

    # Read OpenAlex cache — has ref_oa_id, needs mapping to REFS_COLUMNS
    if os.path.exists(openalex_path):
        oa = pd.read_csv(openalex_path, dtype=str, keep_default_na=False,
                         on_bad_lines="warn")
        log.info("OpenAlex cache: %d rows", len(oa))
        # Map to REFS_COLUMNS: ref_oa_id → source_id, fill missing columns
        oa_mapped = pd.DataFrame({
            "source_doi": oa["source_doi"],
            "source_id": oa.get("ref_oa_id", pd.Series(dtype=str)).apply(
                lambda x: f"openalex:{x}" if x else ""),
            "ref_doi": oa.get("ref_doi", pd.Series(dtype=str)),
            "ref_title": oa.get("ref_title", pd.Series(dtype=str)),
            "ref_first_author": oa.get("ref_first_author", pd.Series(dtype=str)),
            "ref_year": oa.get("ref_year", pd.Series(dtype=str)),
            "ref_journal": oa.get("ref_journal", pd.Series(dtype=str)),
            "ref_raw": "",
        })
        frames.append(oa_mapped)
    else:
        log.info("No OpenAlex cache at %s", openalex_path)

    if not frames:
        log.info("No cache files found — writing empty citations.csv")
        empty = pd.DataFrame({c: pd.Series(dtype=str) for c in REFS_COLUMNS})
        save_csv(empty, output_path)
        return 0

    combined = pd.concat(frames, ignore_index=True)

    # Remove sentinel rows
    is_sentinel = combined["ref_doi"] == SENTINEL_REF_DOI
    n_sentinel = int(is_sentinel.sum())
    combined = combined[~is_sentinel]

    # Normalize DOIs for dedup
    combined["_src_norm"] = combined["source_doi"].apply(
        lambda x: normalize_doi(x) if x else "")
    combined["_ref_norm"] = combined["ref_doi"].apply(
        lambda x: normalize_doi(x) if x else "")

    # Dedup: for rows with ref_doi, dedup on (source_doi, ref_doi).
    # For rows without ref_doi (books/reports), dedup on
    # (source_doi, ref_title, ref_first_author, ref_year) to catch
    # the same book reference from both Crossref and OpenAlex.
    # Normalize title/author to lowercase for case-insensitive matching.
    has_ref_doi = combined["_ref_norm"] != ""
    with_doi = combined[has_ref_doi].drop_duplicates(
        subset=["_src_norm", "_ref_norm"], keep="first")
    without_doi = combined[~has_ref_doi].copy()
    without_doi["_title_norm"] = without_doi["ref_title"].str.lower().str.strip()
    without_doi["_author_norm"] = without_doi["ref_first_author"].str.lower().str.strip()
    without_doi = without_doi.drop_duplicates(
        subset=["_src_norm", "_title_norm", "_author_norm", "ref_year"],
        keep="first")
    without_doi = without_doi.drop(columns=["_title_norm", "_author_norm"])

    result = pd.concat([with_doi, without_doi], ignore_index=True)
    n_deduped = len(combined) - len(result)

    # Drop internal columns, ensure REFS_COLUMNS order
    result = result[REFS_COLUMNS]
    save_csv(result, output_path)

    log.info("Merged: %d rows (-%d sentinels, -%d dupes) → %s",
             len(result), n_sentinel, n_deduped, output_path)
    return len(result)


def main():
    parser = argparse.ArgumentParser(
        description="Merge citation caches into citations.csv")
    parser.add_argument("--cache-dir", default=CACHE_DIR,
                        help="Path to enrich_cache/ directory")
    parser.add_argument("--output", default=OUTPUT_PATH,
                        help="Output path for merged citations.csv")
    args = parser.parse_args()

    merge_citations(cache_dir=args.cache_dir, output_path=args.output)


if __name__ == "__main__":
    main()
