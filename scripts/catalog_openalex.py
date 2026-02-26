#!/usr/bin/env python3
"""Query OpenAlex API for climate finance literature.

Uses cursor-based pagination. Free API, no auth required.
Produces: data/catalogs/openalex_works.csv (~11K rows)

Usage:
    python scripts/catalog_openalex.py [--limit N] [--delay SECONDS] [--resume]
"""

import argparse
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import (CATALOGS_DIR, WORKS_COLUMNS, MAILTO,
                   normalize_doi, reconstruct_abstract, polite_get,
                   save_csv, load_checkpoint, append_checkpoint,
                   delete_checkpoint)

CHECKPOINT = os.path.join(CATALOGS_DIR, ".openalex_checkpoint.jsonl")


def fetch_query(search_term, delay, limit, existing_ids):
    """Fetch all works matching a search term via cursor pagination."""
    records = []
    cursor = "*"
    total_fetched = 0

    while cursor:
        params = {
            "filter": f'default.search:"{search_term}"',
            "per_page": 200,
            "cursor": cursor,
            "mailto": MAILTO,
        }
        resp = polite_get("https://api.openalex.org/works", params=params,
                          delay=delay)
        data = resp.json()

        remaining = resp.headers.get("X-RateLimit-Remaining-USD", "?")
        meta = data.get("meta", {})
        total = meta.get("count", "?")

        for r in data.get("results", []):
            oa_id = r.get("id", "").replace("https://openalex.org/", "")
            if oa_id in existing_ids:
                continue
            existing_ids.add(oa_id)

            authorships = r.get("authorships", [])
            first_author = ""
            all_authors_list = []
            affs_set = set()
            for auth in authorships:
                name = auth.get("author", {}).get("display_name", "")
                if name:
                    all_authors_list.append(name)
                    if not first_author:
                        first_author = name
                for inst in auth.get("institutions", []):
                    inst_name = inst.get("display_name")
                    if inst_name:
                        affs_set.add(inst_name)

            loc = r.get("primary_location") or {}
            source = loc.get("source") or {}
            journal = source.get("display_name", "")

            kw_list = r.get("keywords", [])
            keywords = " ; ".join(k.get("display_name", "")
                                  for k in (kw_list or []))

            concepts = r.get("concepts", [])
            categories = " ; ".join(
                c.get("display_name", "") for c in (concepts or [])
                if c.get("level", 99) <= 2
            )

            rec = {
                "source": "openalex",
                "source_id": oa_id,
                "doi": normalize_doi(r.get("doi")),
                "title": r.get("display_name", ""),
                "first_author": first_author,
                "all_authors": " ; ".join(all_authors_list),
                "year": r.get("publication_year", ""),
                "journal": journal,
                "abstract": reconstruct_abstract(
                    r.get("abstract_inverted_index")),
                "language": r.get("language", ""),
                "keywords": keywords,
                "categories": categories,
                "cited_by_count": r.get("cited_by_count", ""),
                "affiliations": " ; ".join(sorted(affs_set)),
            }
            records.append(rec)

        total_fetched += len(data.get("results", []))
        print(f"  [{search_term}] {total_fetched}/{total} "
              f"(budget remaining: ${remaining})")

        # Checkpoint every 2000 records
        if len(records) >= 2000:
            append_checkpoint(records, CHECKPOINT)
            records = []

        cursor = meta.get("next_cursor")

        if limit and total_fetched >= limit:
            print(f"  Reached limit ({limit}), stopping.")
            break

    return records


def main():
    parser = argparse.ArgumentParser(description="Query OpenAlex for climate finance")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max records to fetch (0=all)")
    parser.add_argument("--delay", type=float, default=0.2,
                        help="Delay between requests in seconds")
    parser.add_argument("--resume", action="store_true",
                        help="Resume from checkpoint")
    args = parser.parse_args()

    # Load checkpoint if resuming
    existing_ids = set()
    if args.resume:
        checkpoint_records = load_checkpoint(CHECKPOINT)
        existing_ids = {r["source_id"] for r in checkpoint_records}
        print(f"Resuming with {len(existing_ids)} already fetched")
    else:
        delete_checkpoint(CHECKPOINT)

    # Run two queries to cover English and French terms
    all_records = []
    for term in ["climate finance", "finance climat"]:
        print(f"\nQuerying: \"{term}\"")
        recs = fetch_query(term, args.delay, args.limit, existing_ids)
        all_records.extend(recs)

    # Flush remaining records to checkpoint
    if all_records:
        append_checkpoint(all_records, CHECKPOINT)

    # Load all from checkpoint and save final CSV
    final_records = load_checkpoint(CHECKPOINT)
    if not final_records:
        print("No records found.")
        return

    df = pd.DataFrame(final_records, columns=WORKS_COLUMNS)
    save_csv(df, os.path.join(CATALOGS_DIR, "openalex_works.csv"))
    delete_checkpoint(CHECKPOINT)

    print(f"\nSummary:")
    print(f"  Total works: {len(df)}")
    print(f"  With DOI: {(df['doi'] != '').sum()}")
    print(f"  Year range: {df['year'].min()} - {df['year'].max()}")
    print(f"  Unique journals: {df['journal'].nunique()}")


if __name__ == "__main__":
    main()
