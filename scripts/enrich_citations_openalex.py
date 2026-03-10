#!/usr/bin/env python3
"""Enrich citations from OpenAlex referenced_works.

For every DOI in refined_works.csv, queries OpenAlex for its referenced_works
list and resolves each OpenAlex work ID to a DOI + bibliographic metadata.
Appends new rows to citations.csv in the same format as enrich_citations_batch.py.

Two-phase approach:
  Phase 1: batch-fetch source works → collect referenced_works OpenAlex IDs.
  Phase 2: batch-resolve OpenAlex IDs → get DOIs, title, year, journal.

Uses a persistent done-set (.citations_oa_done.txt) so runs are resumable.

Usage:
    uv run python scripts/enrich_citations_openalex.py [--batch-size 50] [--limit N]
"""

import argparse
import json
import os
import sys
import time

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(__file__))
from utils import CATALOGS_DIR, MAILTO, REFS_COLUMNS, normalize_doi

CITATIONS_PATH = os.path.join(CATALOGS_DIR, "citations.csv")
CHECKPOINT_PATH = os.path.join(CATALOGS_DIR, ".citations_oa_checkpoint.csv")
DONE_PATH = os.path.join(CATALOGS_DIR, ".citations_oa_done.txt")

OA_BASE = "https://api.openalex.org/works"
HEADERS = {"User-Agent": f"ClimateFinancePipeline/1.0 (mailto:{MAILTO})"}


def openalex_get(params, delay=0.15):
    """GET request to OpenAlex with polite delay and rate-limit handling."""
    time.sleep(delay)
    params.setdefault("mailto", MAILTO)
    resp = requests.get(OA_BASE, params=params, headers=HEADERS, timeout=60)
    if resp.status_code == 429:
        wait = int(resp.headers.get("Retry-After", 10))
        print(f"  Rate limited. Waiting {wait}s...")
        time.sleep(wait)
        resp = requests.get(OA_BASE, params=params, headers=HEADERS, timeout=60)
    resp.raise_for_status()
    return resp.json()


def fetch_source_batch(dois):
    """Phase 1: fetch referenced_works for a batch of source DOIs.

    Returns dict {source_doi: [openalex_id, ...]}
    """
    # OpenAlex multi-value filter: single key with |-separated values
    doi_values = "|".join(dois)
    data = openalex_get({
        "filter": f"doi:{doi_values}",
        "select": "id,doi,referenced_works",
        "per-page": len(dois),
    })
    result = {}
    for item in data.get("results", []):
        source_doi = normalize_doi(item.get("doi", ""))
        if not source_doi:
            continue
        ref_ids = item.get("referenced_works", []) or []
        # IDs are full URLs like https://openalex.org/W123; normalize to Wxxxxxx
        result[source_doi] = [
            r.split("/")[-1] for r in ref_ids if r
        ]
    return result


def resolve_openalex_ids(oa_ids):
    """Phase 2: resolve a list of OpenAlex IDs → (id, doi, title, year, journal).

    Returns dict {oa_id: {doi, title, year, journal}}
    """
    if not oa_ids:
        return {}
    # OpenAlex ID filter uses openalex: prefix with |-separated short IDs
    id_filter = "|".join(oa_ids)
    data = openalex_get({
        "filter": f"openalex:{id_filter}",
        "select": "id,doi,title,publication_year,primary_location",
        "per-page": len(oa_ids),
    })
    result = {}
    for item in data.get("results", []):
        oa_id = item.get("id", "").split("/")[-1]
        doi = normalize_doi(item.get("doi", ""))
        title = item.get("title", "") or ""
        year = str(item.get("publication_year", "")) if item.get("publication_year") else ""
        loc = item.get("primary_location") or {}
        source = loc.get("source") or {}
        journal = source.get("display_name", "") or ""
        result[oa_id] = {
            "doi": doi,
            "title": title,
            "year": year,
            "journal": journal,
        }
    return result


def main():
    parser = argparse.ArgumentParser(description="Enrich citations from OpenAlex")
    parser.add_argument("--batch-size", type=int, default=50,
                        help="DOIs per OpenAlex request (max ~100)")
    parser.add_argument("--resolve-batch-size", type=int, default=100,
                        help="OpenAlex IDs to resolve per request")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max source DOIs to process (0=all)")
    parser.add_argument("--delay", type=float, default=0.15,
                        help="Delay between API requests (seconds)")
    args = parser.parse_args()

    # ── Load done-set (resumable) ─────────────────────────────────────────
    if os.path.exists(DONE_PATH):
        with open(DONE_PATH) as f:
            done_dois = set(line.strip() for line in f if line.strip())
        print(f"Resuming: {len(done_dois)} DOIs already fetched from OpenAlex")
    else:
        done_dois = set()

    # Also count from checkpoint if a previous run crashed before merging
    if os.path.exists(CHECKPOINT_PATH):
        ckpt_existing = pd.read_csv(CHECKPOINT_PATH, usecols=["source_doi"],
                                     low_memory=False)
        done_dois |= set(ckpt_existing["source_doi"].apply(normalize_doi).dropna())
        print(f"  (+{len(ckpt_existing)} rows in unmerged checkpoint)")

    # ── Corpus DOIs ───────────────────────────────────────────────────────
    works = pd.read_csv(
        os.path.join(CATALOGS_DIR, "refined_works.csv"),
        dtype=str, keep_default_na=False,
    )
    all_dois = [
        normalize_doi(d) for d in works["doi"].unique()
        if normalize_doi(d) not in ("", "nan", "none")
    ]

    # Skip DOIs already covered by openalex_citations.csv (extracted during
    # catalog_openalex.py discovery — no need to re-fetch from the API).
    oa_citations_path = os.path.join(CATALOGS_DIR, "openalex_citations.csv")
    if os.path.exists(oa_citations_path):
        oa_done = set(
            pd.read_csv(oa_citations_path, usecols=["source_doi"],
                        dtype=str, keep_default_na=False)["source_doi"]
            .apply(normalize_doi).unique()
        )
        print(f"Skipping {len(oa_done)} DOIs already in openalex_citations.csv")
        done_dois |= oa_done

    missing = [d for d in all_dois if d not in done_dois]
    if args.limit:
        missing = missing[:args.limit]

    print(f"Corpus DOIs:   {len(all_dois)}")
    print(f"Already done:  {len(done_dois)}")
    print(f"To fetch:      {len(missing)}")

    if not missing:
        print("Nothing to fetch.")
        return

    # Write checkpoint header once
    if not os.path.exists(CHECKPOINT_PATH) or os.path.getsize(CHECKPOINT_PATH) == 0:
        pd.DataFrame(columns=REFS_COLUMNS).to_csv(CHECKPOINT_PATH, index=False)

    # ── Phase 1: collect referenced_works IDs ────────────────────────────
    print("\nPhase 1: fetching referenced_works from OpenAlex...")
    t0 = time.time()
    # source_doi → list of OpenAlex IDs
    all_source_refs = {}
    errors = 0
    n_batches = (len(missing) + args.batch_size - 1) // args.batch_size

    for i in range(0, len(missing), args.batch_size):
        batch = missing[i:i + args.batch_size]
        batch_num = i // args.batch_size + 1
        try:
            result = fetch_source_batch(batch)
            all_source_refs.update(result)
            # Record all queried DOIs as done (even if not found in OA)
            with open(DONE_PATH, "a") as f:
                for d in batch:
                    f.write(d + "\n")
        except Exception as e:
            print(f"  ERROR batch {batch_num}/{n_batches}: {e}")
            errors += 1
            if errors > 10:
                print("Too many errors, stopping.")
                break
            continue

        if batch_num % 20 == 0 or batch_num == n_batches:
            found_refs = sum(len(v) for v in all_source_refs.values())
            elapsed = time.time() - t0
            rate = (i + len(batch)) / elapsed if elapsed > 0 else 0
            eta = (len(missing) - i - len(batch)) / rate if rate > 0 else 0
            print(f"  Batch {batch_num}/{n_batches}: "
                  f"{len(all_source_refs)} sources, {found_refs} ref-IDs, "
                  f"{elapsed:.0f}s elapsed, ETA {eta:.0f}s")

    # ── Phase 2: resolve OpenAlex IDs → DOIs + metadata ─────────────────
    # Collect all unique referenced OpenAlex IDs
    all_oa_ids = list({
        oa_id
        for ref_list in all_source_refs.values()
        for oa_id in ref_list
        if oa_id
    })
    print(f"\nPhase 2: resolving {len(all_oa_ids)} unique OpenAlex IDs to DOIs...")

    id_metadata = {}
    resolve_errors = 0
    n_resolve_batches = (len(all_oa_ids) + args.resolve_batch_size - 1) // args.resolve_batch_size

    for i in range(0, len(all_oa_ids), args.resolve_batch_size):
        batch_ids = all_oa_ids[i:i + args.resolve_batch_size]
        batch_num = i // args.resolve_batch_size + 1
        try:
            resolved = resolve_openalex_ids(batch_ids)
            id_metadata.update(resolved)
        except Exception as e:
            print(f"  ERROR resolve batch {batch_num}/{n_resolve_batches}: {e}")
            resolve_errors += 1
            if resolve_errors > 10:
                print("Too many errors, stopping resolution.")
                break
            continue

        if batch_num % 20 == 0 or batch_num == n_resolve_batches:
            print(f"  Resolve batch {batch_num}/{n_resolve_batches}: "
                  f"{len(id_metadata)} IDs resolved")

    # ── Build rows and write checkpoint ──────────────────────────────────
    print("\nBuilding citation rows...")
    rows = []
    for source_doi, ref_ids in all_source_refs.items():
        for oa_id in ref_ids:
            meta = id_metadata.get(oa_id, {})
            rows.append({
                "source_doi": source_doi,
                "source_id": f"openalex:{oa_id}",
                "ref_doi": meta.get("doi", ""),
                "ref_title": meta.get("title", ""),
                "ref_first_author": "",
                "ref_year": meta.get("year", ""),
                "ref_journal": meta.get("journal", ""),
                "ref_raw": json.dumps({"openalex_id": oa_id}, ensure_ascii=False),
            })

    if rows:
        batch_df = pd.DataFrame(rows, columns=REFS_COLUMNS)
        batch_df.to_csv(CHECKPOINT_PATH, mode="a", header=False, index=False)

    # ── Merge checkpoint into citations.csv ───────────────────────────────
    print("\nMerging into citations.csv...")
    existing = pd.read_csv(CITATIONS_PATH, low_memory=False)

    if os.path.exists(CHECKPOINT_PATH) and os.path.getsize(CHECKPOINT_PATH) > 0:
        new_refs = pd.read_csv(CHECKPOINT_PATH, low_memory=False)
        # Drop sentinel rows (all key fields empty)
        is_sentinel = (
            (new_refs["ref_doi"].isna() | (new_refs["ref_doi"] == ""))
            & (new_refs["ref_title"].isna() | (new_refs["ref_title"] == ""))
        )
        new_refs_real = new_refs[~is_sentinel].copy()

        # Remove duplicates already in citations.csv (same source_doi + ref_doi)
        existing_keys = set(
            zip(existing["source_doi"].apply(normalize_doi),
                existing["ref_doi"].fillna("").apply(normalize_doi))
        )
        new_refs_real["_key"] = list(zip(
            new_refs_real["source_doi"].apply(normalize_doi),
            new_refs_real["ref_doi"].fillna("").apply(normalize_doi),
        ))
        new_refs_real = new_refs_real[
            ~new_refs_real["_key"].isin(existing_keys)
        ].drop(columns=["_key"])

        combined = pd.concat([existing, new_refs_real], ignore_index=True)
        combined.to_csv(CITATIONS_PATH, index=False)
        os.remove(CHECKPOINT_PATH)
        print(f"  Old rows:          {len(existing)}")
        print(f"  New rows (deduped): {len(new_refs_real)}")
        print(f"  Sentinels dropped: {is_sentinel.sum()}")
        print(f"  Combined:          {len(combined)}")
    else:
        print("  No new data to merge.")

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.0f}s")
    print(f"  Sources processed:  {len(all_source_refs)}")
    print(f"  OpenAlex IDs found: {len(all_oa_ids)}")
    print(f"  IDs resolved:       {len(id_metadata)}")
    print(f"  Reference rows:     {len(rows)}")
    print(f"  Errors (fetch):     {errors}")
    print(f"  Errors (resolve):   {resolve_errors}")


if __name__ == "__main__":
    main()
