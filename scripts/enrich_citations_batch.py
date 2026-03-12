#!/usr/bin/env python3
"""Batch-enrich citations from Crossref using DOI filter endpoint.

Finds all DOIs in refined_works.csv that are missing from citations.csv,
then queries Crossref in batches of 50 DOIs per request.

Appends new rows to the existing citations.csv (does not overwrite).

Usage:
    uv run python scripts/enrich_citations_batch.py [--batch-size 50] [--limit N]
"""

import argparse
import json
import os
import sys
import time

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(__file__))
from utils import CATALOGS_DIR, REFS_COLUMNS, MAILTO, normalize_doi, sort_dois_by_priority

CITATIONS_PATH = os.path.join(CATALOGS_DIR, "citations.csv")
CHECKPOINT_PATH = os.path.join(CATALOGS_DIR, ".citations_batch_checkpoint.csv")
URL = "https://api.crossref.org/works"
HEADERS = {"User-Agent": f"ClimateFinancePipeline/1.0 (mailto:{MAILTO})"}


def fetch_batch(dois, delay=0.2):
    """Fetch references for a batch of DOIs using the filter endpoint."""
    doi_filter = ",".join(f"doi:{d}" for d in dois)
    params = {
        "filter": doi_filter,
        "select": "DOI,reference,is-referenced-by-count",
        "rows": len(dois),
        "mailto": MAILTO,
    }
    time.sleep(delay)
    resp = requests.get(URL, params=params, headers=HEADERS, timeout=60)
    if resp.status_code == 429:
        retry_after = int(resp.headers.get("Retry-After", 10))
        print(f"  Rate limited. Waiting {retry_after}s...")
        time.sleep(retry_after)
        resp = requests.get(URL, params=params, headers=HEADERS, timeout=60)
    resp.raise_for_status()

    rows = []
    for item in resp.json().get("message", {}).get("items", []):
        source_doi = normalize_doi(item.get("DOI", ""))
        for ref in item.get("reference", []):
            rows.append({
                "source_doi": source_doi,
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
    found_dois = {normalize_doi(it.get("DOI", ""))
                  for it in resp.json()["message"]["items"]}
    return rows, found_dois


def main():
    parser = argparse.ArgumentParser(
        description="Batch-enrich citations (DOIs processed in priority order: "
                    "most-cited works first, deterministic)"
    )
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--limit", type=int, default=0,
                        help="Max DOIs to process in priority order (0=all)")
    parser.add_argument("--delay", type=float, default=0.2,
                        help="Delay between batch requests")
    parser.add_argument("--works-input", default="refined_works.csv",
                        metavar="FILE",
                        help="Works CSV filename in CATALOGS_DIR (default: refined_works.csv)")
    args = parser.parse_args()

    # Load existing citations to find already-fetched DOIs
    if os.path.exists(CITATIONS_PATH):
        existing = pd.read_csv(CITATIONS_PATH, low_memory=False)
        existing["source_doi"] = existing["source_doi"].apply(normalize_doi)
        done_dois = set(existing["source_doi"].dropna()) - {"", "nan", "none"}
        print(f"Existing citations.csv: {len(existing)} rows, "
              f"{len(done_dois)} unique source DOIs")
    else:
        existing = pd.DataFrame(columns=REFS_COLUMNS)
        done_dois = set()

    # Also count DOIs from checkpoint (partial run)
    if os.path.exists(CHECKPOINT_PATH):
        ckpt = pd.read_csv(CHECKPOINT_PATH, low_memory=False)
        ckpt_dois = set(ckpt["source_doi"].apply(normalize_doi)) - {"", "nan", "none"}
        done_dois |= ckpt_dois
        print(f"Checkpoint: {len(ckpt)} rows, {len(ckpt_dois)} DOIs already fetched")
    else:
        ckpt = pd.DataFrame(columns=REFS_COLUMNS)

    # All DOIs in refined_works
    works = pd.read_csv(os.path.join(CATALOGS_DIR, args.works_input),
                        dtype=str, keep_default_na=False)
    all_dois = [normalize_doi(d) for d in works["doi"].unique() if d]
    all_dois = [d for d in all_dois if d and d not in ("", "nan", "none")]

    # Sort by priority (most-cited works first) for deterministic ordering.
    # The checkpoint ensures already-done DOIs are skipped regardless of order,
    # so priority only determines which DOIs are chosen when --limit is set.
    all_dois_sorted = sort_dois_by_priority(all_dois, works)
    missing = [d for d in all_dois_sorted if d not in done_dois]

    if args.limit:
        missing = missing[:args.limit]

    print(f"Total DOIs: {len(all_dois)}")
    print(f"Already done: {len(done_dois)}")
    print(f"To fetch: {len(missing)}")

    if not missing:
        print("Nothing to fetch.")
        return

    # Write checkpoint header once upfront
    if not os.path.exists(CHECKPOINT_PATH) or os.path.getsize(CHECKPOINT_PATH) == 0:
        pd.DataFrame(columns=REFS_COLUMNS).to_csv(CHECKPOINT_PATH, index=False)

    # Process in batches
    total_refs = 0
    total_found = 0
    errors = 0
    t0 = time.time()

    for i in range(0, len(missing), args.batch_size):
        batch_dois = missing[i:i + args.batch_size]
        batch_num = i // args.batch_size + 1
        n_batches = (len(missing) + args.batch_size - 1) // args.batch_size

        try:
            refs, found_dois = fetch_batch(batch_dois, delay=args.delay)
        except Exception as e:
            print(f"  ERROR batch {batch_num}: {e}")
            errors += 1
            if errors > 10:
                print("Too many errors, stopping.")
                break
            continue

        total_refs += len(refs)
        total_found += len(found_dois)

        # Append refs to checkpoint (header already written)
        if refs:
            batch_df = pd.DataFrame(refs, columns=REFS_COLUMNS)
            batch_df.to_csv(CHECKPOINT_PATH, mode="a", header=False,
                            index=False)

        # Record DOIs found but with no refs (so we skip on resume)
        for d in found_dois - {r["source_doi"] for r in refs}:
            sentinel = pd.DataFrame([{
                "source_doi": d, "source_id": "", "ref_doi": "",
                "ref_title": "", "ref_first_author": "", "ref_year": "",
                "ref_journal": "", "ref_raw": "",
            }])
            sentinel.to_csv(CHECKPOINT_PATH, mode="a", header=False,
                            index=False)

        elapsed = time.time() - t0
        rate = (i + len(batch_dois)) / elapsed if elapsed > 0 else 0
        eta = (len(missing) - i - len(batch_dois)) / rate if rate > 0 else 0

        if batch_num % 10 == 0 or batch_num == n_batches:
            print(f"  Batch {batch_num}/{n_batches}: "
                  f"{total_found} DOIs found, {total_refs} refs, "
                  f"{elapsed:.0f}s elapsed, ETA {eta:.0f}s")

    # Merge checkpoint into existing citations.csv
    print(f"\nMerging checkpoint into citations.csv...")
    if os.path.exists(CHECKPOINT_PATH):
        new_refs = pd.read_csv(CHECKPOINT_PATH, low_memory=False)
        # Drop sentinel rows (all fields empty except source_doi)
        is_sentinel = (
            (new_refs["ref_doi"].isna() | (new_refs["ref_doi"] == ""))
            & (new_refs["ref_title"].isna() | (new_refs["ref_title"] == ""))
            & (new_refs["ref_first_author"].isna()
               | (new_refs["ref_first_author"] == ""))
        )
        new_refs_real = new_refs[~is_sentinel]
        combined = pd.concat([existing, new_refs_real], ignore_index=True)
        combined.to_csv(CITATIONS_PATH, index=False)
        os.remove(CHECKPOINT_PATH)
        print(f"  Old: {len(existing)} rows")
        print(f"  New: {len(new_refs_real)} rows")
        print(f"  Sentinels dropped: {is_sentinel.sum()}")
        print(f"  Combined: {len(combined)} rows")
    else:
        print("  No new data to merge.")

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.0f}s")
    print(f"  DOIs found in Crossref: {total_found}")
    print(f"  Total new references: {total_refs}")
    print(f"  Errors: {errors}")


if __name__ == "__main__":
    main()
