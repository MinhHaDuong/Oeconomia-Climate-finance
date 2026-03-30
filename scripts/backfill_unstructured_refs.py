#!/usr/bin/env python3
"""One-shot backfill: parse unstructured text in existing crossref_refs.csv.

Reads the cache, applies parse_ref_fields to rows with empty ref_title
but non-empty ref_raw, writes the result back. Idempotent — running
twice produces the same output.

Usage:
    uv run python scripts/backfill_unstructured_refs.py [--dry-run]
"""

import argparse
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from enrich_citations_batch import parse_ref_fields
from utils import CATALOGS_DIR, get_logger

log = get_logger("backfill_unstructured_refs")

CACHE_DIR = os.path.join(CATALOGS_DIR, "enrich_cache")
CACHE_PATH = os.path.join(CACHE_DIR, "crossref_refs.csv")


def _parse_row(raw_json):
    """Parse a ref_raw JSON string and return (title, author, year)."""
    try:
        ref = json.loads(raw_json)
    except (json.JSONDecodeError, TypeError):
        return "", "", ""
    p = parse_ref_fields(ref)
    return p["ref_title"], p["ref_first_author"], p["ref_year"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true",
                        help="Report counts without writing")
    args = parser.parse_args()

    log.info("Reading %s", CACHE_PATH)
    df = pd.read_csv(CACHE_PATH, dtype=str, keep_default_na=False,
                     on_bad_lines="warn")
    log.info("Total rows: %d", len(df))

    # Find rows that need backfill: empty title, non-empty ref_raw
    needs_backfill = (df["ref_title"] == "") & (df["ref_raw"] != "")
    n = needs_backfill.sum()
    log.info("Rows needing backfill: %d", n)

    if n == 0:
        log.info("Nothing to backfill.")
        return

    # Vectorized: apply parse to all candidate rows at once
    parsed = df.loc[needs_backfill, "ref_raw"].apply(_parse_row)
    titles = parsed.apply(lambda x: x[0])
    authors = parsed.apply(lambda x: x[1])
    years = parsed.apply(lambda x: x[2])

    # Only fill where the field was empty
    title_mask = (df.loc[needs_backfill, "ref_title"] == "") & (titles != "")
    author_mask = (df.loc[needs_backfill, "ref_first_author"] == "") & (authors != "")
    year_mask = (df.loc[needs_backfill, "ref_year"] == "") & (years != "")

    log.info("Will fill: %d titles, %d authors, %d years",
             title_mask.sum(), author_mask.sum(), year_mask.sum())

    if args.dry_run:
        log.info("Dry run — not writing.")
        return

    df.loc[needs_backfill & title_mask.reindex(df.index, fill_value=False),
           "ref_title"] = titles
    df.loc[needs_backfill & author_mask.reindex(df.index, fill_value=False),
           "ref_first_author"] = authors
    df.loc[needs_backfill & year_mask.reindex(df.index, fill_value=False),
           "ref_year"] = years

    log.info("Writing %s", CACHE_PATH)
    df.to_csv(CACHE_PATH, index=False)
    log.info("Done.")


if __name__ == "__main__":
    main()
