#!/usr/bin/env python3
"""Enrich unified catalog with citation data from Crossref.

For each DOI in unified_works.csv, queries Crossref for:
  - Outgoing references (cited works)
  - is-referenced-by-count (incoming citations)

Produces: data/catalogs/citations.csv

Usage:
    python scripts/enrich_citations.py [--limit N] [--delay SECONDS] [--resume]
"""

import argparse
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import (CATALOGS_DIR, REFS_COLUMNS, MAILTO,
                   normalize_doi, polite_get, save_csv,
                   load_checkpoint, append_checkpoint, delete_checkpoint)

CHECKPOINT = os.path.join(CATALOGS_DIR, ".citations_checkpoint.jsonl")


def fetch_references(doi, delay):
    """Fetch reference list for a single DOI from Crossref."""
    url = f"https://api.crossref.org/works/{doi}"
    try:
        resp = polite_get(url, delay=delay)
    except Exception as e:
        if "404" in str(e):
            return None, None
        raise

    data = resp.json().get("message", {})
    cited_by_count = data.get("is-referenced-by-count", "")

    refs = []
    for ref in data.get("reference", []):
        refs.append({
            "source_doi": doi,
            "source_id": "",
            "ref_doi": normalize_doi(ref.get("DOI", "")),
            "ref_title": ref.get("article-title",
                        ref.get("volume-title",
                        ref.get("series-title", ""))),
            "ref_first_author": ref.get("author", ""),
            "ref_year": ref.get("year", ""),
            "ref_journal": ref.get("journal-title", ""),
            "ref_raw": json.dumps(ref, ensure_ascii=False),
        })

    return refs, cited_by_count


def main():
    parser = argparse.ArgumentParser(
        description="Enrich with Crossref citation data")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max DOIs to process (0=all)")
    parser.add_argument("--delay", type=float, default=0.1,
                        help="Delay between requests in seconds")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from checkpoint")
    args = parser.parse_args()

    # Load unified catalog
    unified_path = os.path.join(CATALOGS_DIR, "unified_works.csv")
    if not os.path.exists(unified_path):
        print(f"Unified catalog not found at {unified_path}")
        print("Run catalog_merge.py first.")
        return

    df = pd.read_csv(unified_path, encoding="utf-8", dtype=str,
                     keep_default_na=False)
    dois = [d for d in df["doi"].unique() if d]
    print(f"Found {len(dois)} unique DOIs to process")

    # Load checkpoint
    done_dois = set()
    if args.resume:
        checkpoint_records = load_checkpoint(CHECKPOINT)
        done_dois = {r["source_doi"] for r in checkpoint_records}
        print(f"Already processed: {len(done_dois)} DOIs")
    else:
        delete_checkpoint(CHECKPOINT)

    remaining = [d for d in dois if d not in done_dois]
    if args.limit:
        remaining = remaining[:args.limit]
    print(f"Processing {len(remaining)} DOIs...")

    batch = []
    errors = 0
    for i, doi in enumerate(remaining):
        try:
            refs, cited_by = fetch_references(doi, args.delay)
        except Exception as e:
            print(f"  ERROR {doi}: {e}")
            errors += 1
            if errors > 20:
                print("Too many errors, stopping.")
                break
            continue

        if refs is None:
            # DOI not found in Crossref
            continue

        batch.extend(refs)

        if (i + 1) % 100 == 0:
            append_checkpoint(batch, CHECKPOINT)
            print(f"  Processed {i + 1}/{len(remaining)} DOIs "
                  f"({len(batch)} refs in batch)")
            batch = []

    # Flush remaining
    if batch:
        append_checkpoint(batch, CHECKPOINT)

    # Load all and save
    all_refs = load_checkpoint(CHECKPOINT)
    if not all_refs:
        print("No citation data retrieved.")
        return

    refs_df = pd.DataFrame(all_refs, columns=REFS_COLUMNS)
    save_csv(refs_df, os.path.join(CATALOGS_DIR, "citations.csv"))
    delete_checkpoint(CHECKPOINT)

    print(f"\nSummary:")
    print(f"  Total references: {len(refs_df)}")
    print(f"  Refs with DOI: {(refs_df['ref_doi'] != '').sum()}")
    print(f"  Unique source DOIs: {refs_df['source_doi'].nunique()}")
    print(f"  Errors: {errors}")


if __name__ == "__main__":
    main()
