#!/usr/bin/env python3
"""Batch-enrich citations from Crossref using DOI filter endpoint.

Finds all DOIs in the works input that are missing from the Crossref
citation cache, then queries Crossref in batches.

Writes to enrich_cache/crossref_refs.csv (append-only, persistent).
The cache IS the data — no separate "done" file. A DOI is done if it
has rows (real refs or sentinel) in the cache.

The downstream merge_citations.py step reads this cache + the OpenAlex
cache and produces the DVC-tracked citations.csv.

Usage:
    uv run python scripts/enrich_citations_batch.py [--batch-size 50] [--limit N]
                                                     [--run-id ID]
"""

import argparse
import json
import os
import time

import pandas as pd

from utils import (CATALOGS_DIR, REFS_COLUMNS, MAILTO, normalize_doi,
                   sort_dois_by_priority, retry_get, save_run_report, make_run_id,
                   get_logger)

log = get_logger("enrich_citations_batch")

CACHE_DIR = os.path.join(CATALOGS_DIR, "enrich_cache")
CACHE_PATH = os.path.join(CACHE_DIR, "crossref_refs.csv")
URL = "https://api.crossref.org/works"
HEADERS = {"User-Agent": f"ClimateFinancePipeline/1.0 (mailto:{MAILTO})"}
SENTINEL_REF_DOI = "__NO_REFS__"  # Marker for DOIs found but with no references
MAX_CONSECUTIVE_ERRORS = 3  # Stop after this many consecutive failures


def fetch_batch(dois, delay=0.2, counters=None,
                request_timeout=60.0, max_retries=5,
                retry_backoff=2.0, retry_jitter=1.0):
    """Fetch references for a batch of DOIs using the filter endpoint."""
    if counters is None:
        counters = {}
    doi_filter = ",".join(f"doi:{d}" for d in dois)
    params = {
        "filter": doi_filter,
        "select": "DOI,reference,is-referenced-by-count",
        "rows": len(dois),
        "mailto": MAILTO,
    }
    resp = retry_get(
        URL,
        params=params,
        headers=HEADERS,
        delay=delay,
        max_retries=max_retries,
        timeout=max(1, request_timeout),
        backoff_base=retry_backoff,
        jitter_max=retry_jitter,
        counters=counters,
    )
    resp.raise_for_status()

    data = resp.json()
    items = data.get("message", {}).get("items", [])

    _expected_keys = set(REFS_COLUMNS)

    rows = []
    for item in items:
        source_doi = normalize_doi(item.get("DOI", ""))
        for ref in item.get("reference", []):
            row = {
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
            }
            rows.append(row)

    if rows:
        assert set(rows[0].keys()) == _expected_keys, (
            f"fetch_batch keys {set(rows[0].keys())} != REFS_COLUMNS {_expected_keys}"
        )
    found_dois = {normalize_doi(it.get("DOI", "")) for it in items}
    return rows, found_dois


def load_done_dois(cache_path):
    """Load the set of source DOIs already in the cache.

    A DOI is "done" if it has any row (real ref or sentinel) in the cache.
    No separate done-file needed — the cache IS the data.
    """
    done = set()
    if os.path.exists(cache_path):
        try:
            df = pd.read_csv(cache_path, usecols=["source_doi"],
                             dtype=str, keep_default_na=False)
            done = set(df["source_doi"].apply(normalize_doi)) - {"", "nan", "none"}
            log.info("Cache: %d unique source DOIs in %s", len(done), cache_path)
        except (pd.errors.EmptyDataError, KeyError):
            log.warning("Cache corrupt or empty: %s", cache_path)
    return done


def main():
    parser = argparse.ArgumentParser(
        description="Batch-enrich citations from Crossref (DOIs processed in priority order: "
                    "most-cited works first, deterministic)")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--limit", type=int, default=0,
                        help="Max DOIs to process (0=all)")
    parser.add_argument("--delay", type=float, default=0.2,
                        help="Delay between batch requests")
    parser.add_argument("--works-input",
                        default=os.path.join(CATALOGS_DIR, "enriched_works.csv"),
                        help="Works CSV to read DOIs from (default: enriched_works.csv)")
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--request-timeout", type=float, default=60.0)
    parser.add_argument("--max-retries", type=int, default=5)
    parser.add_argument("--retry-backoff", type=float, default=2.0)
    parser.add_argument("--retry-jitter", type=float, default=1.0)
    parser.add_argument("--log-jsonl", default=None)
    args = parser.parse_args()

    run_id = args.run_id or make_run_id()
    t0 = time.time()
    counters = {}

    def _log_event(event_type, **kwargs):
        if not args.log_jsonl:
            return
        record = {"run_id": run_id, "event": event_type,
                  "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **kwargs}
        with open(args.log_jsonl, "a") as f:
            f.write(json.dumps(record) + "\n")

    # Ensure cache directory exists
    os.makedirs(CACHE_DIR, exist_ok=True)

    # Initialize cache file with header if needed
    if not os.path.exists(CACHE_PATH) or os.path.getsize(CACHE_PATH) == 0:
        pd.DataFrame({c: pd.Series(dtype=str) for c in REFS_COLUMNS}).to_csv(
            CACHE_PATH, index=False)

    # Load done DOIs directly from cache (cache-is-data)
    done_dois = load_done_dois(CACHE_PATH)

    # All DOIs in works input
    works = pd.read_csv(args.works_input, dtype=str, keep_default_na=False)
    all_dois = [normalize_doi(d) for d in works["doi"].unique() if d]
    all_dois = [d for d in all_dois if d and d not in ("", "nan", "none")]

    all_dois_sorted = sort_dois_by_priority(all_dois, works)
    missing = [d for d in all_dois_sorted if d not in done_dois]

    if args.limit:
        missing = missing[:args.limit]

    log.info("Resume: %d DOIs total, %d done, %d remaining",
             len(all_dois), len(done_dois), len(missing))
    _log_event("start", dois_total=len(all_dois), dois_done_before=len(done_dois),
               dois_to_fetch=len(missing))

    if not missing:
        log.info("Nothing to fetch.")
        return

    # Process in batches, appending directly to cache
    total_refs = 0
    total_found = 0
    consecutive_errors = 0
    n_batches = (len(missing) + args.batch_size - 1) // args.batch_size

    for i in range(0, len(missing), args.batch_size):
        batch_dois = missing[i:i + args.batch_size]
        batch_num = i // args.batch_size + 1

        try:
            refs, found_dois = fetch_batch(
                batch_dois, delay=args.delay, counters=counters,
                request_timeout=args.request_timeout,
                max_retries=args.max_retries,
                retry_backoff=args.retry_backoff,
                retry_jitter=args.retry_jitter,
            )
        except Exception as e:
            log.error("Batch %d: %s", batch_num, e)
            _log_event("batch_error", batch=batch_num, error=str(e))
            consecutive_errors += 1
            if consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                log.error("Too many consecutive errors (%d), stopping.",
                          consecutive_errors)
                break
            continue

        consecutive_errors = 0
        total_refs += len(refs)
        total_found += len(found_dois)

        # Append real refs to cache
        if refs:
            batch_df = pd.DataFrame(refs, columns=REFS_COLUMNS)
            batch_df.to_csv(CACHE_PATH, mode="a", header=False, index=False)

        # Write sentinel rows for DOIs found but with no refs
        no_ref_dois = found_dois - {r["source_doi"] for r in refs}
        if no_ref_dois:
            sentinel_rows = [{
                "source_doi": d, "source_id": "", "ref_doi": SENTINEL_REF_DOI,
                "ref_title": "", "ref_first_author": "", "ref_year": "",
                "ref_journal": "", "ref_raw": "",
            } for d in no_ref_dois]
            pd.DataFrame(sentinel_rows, columns=REFS_COLUMNS).to_csv(
                CACHE_PATH, mode="a", header=False, index=False)

        elapsed = time.time() - t0
        rate = (i + len(batch_dois)) / elapsed if elapsed > 0 else 0
        eta = (len(missing) - i - len(batch_dois)) / rate if rate > 0 else 0

        if batch_num % 10 == 0 or batch_num == n_batches:
            log.info("Batch %d/%d: %d DOIs found, %d refs, ETA %.0fs",
                     batch_num, n_batches, total_found, total_refs, eta)

    elapsed = time.time() - t0
    log.info("Done in %.0fs: %d DOIs found, %d refs, %d consecutive errors at exit",
             elapsed, total_found, total_refs, consecutive_errors)

    counters.update({
        "dois_total": len(all_dois),
        "dois_done_before": len(done_dois),
        "dois_to_fetch": len(missing),
        "dois_found": total_found,
        "refs_written": total_refs,
        "consecutive_errors_at_exit": consecutive_errors,
        "elapsed_seconds": round(elapsed, 1),
    })
    report_path = save_run_report(counters, run_id, "enrich_citations_batch")
    log.info("Run report: %s", report_path)
    _log_event("complete", elapsed_seconds=round(elapsed, 1),
               refs_written=total_refs, report_path=report_path)


if __name__ == "__main__":
    main()
