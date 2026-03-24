#!/usr/bin/env python3
"""Batch-enrich citations from Crossref using DOI filter endpoint.

Finds all DOIs in refined_works.csv that are missing from citations.csv,
then queries Crossref in batches of 50 DOIs per request.

Appends new rows to the existing citations.csv (does not overwrite).

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

CITATIONS_PATH = os.path.join(CATALOGS_DIR, "citations.csv")
CHECKPOINT_PATH = os.path.join(CATALOGS_DIR, ".citations_batch_checkpoint.csv")
CACHE_DIR = os.path.join(CATALOGS_DIR, "enrich_cache")
DONE_CACHE_PATH = os.path.join(CACHE_DIR, "citations_done.csv")
URL = "https://api.crossref.org/works"
HEADERS = {"User-Agent": f"ClimateFinancePipeline/1.0 (mailto:{MAILTO})"}
SENTINEL_REF_DOI = "__NO_REFS__"  # Marker for DOIs found but with no references
MAX_CONSECUTIVE_ERRORS = 5


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

    data = resp.json()  # Parse once (#3)
    items = data.get("message", {}).get("items", [])

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
            assert set(row.keys()) == set(REFS_COLUMNS), (  # (#9)
                f"fetch_batch keys {set(row.keys())} != REFS_COLUMNS {set(REFS_COLUMNS)}"
            )
            rows.append(row)
    found_dois = {normalize_doi(it.get("DOI", "")) for it in items}
    return rows, found_dois


def load_done_dois(citations_path, done_cache_path):
    """Load the set of source DOIs already fetched.

    Reads from the persistent cache (enrich_cache/citations_done.csv) which
    survives DVC stage re-runs, unlike citations.csv which DVC deletes before
    re-running. Falls back to citations.csv for backward compatibility.
    """
    done = set()
    # Primary source: persistent cache (not a DVC output)
    if os.path.exists(done_cache_path):
        try:
            df = pd.read_csv(done_cache_path, dtype=str, keep_default_na=False)
            done |= set(df["source_doi"]) - {"", "nan", "none"}
            log.info("Done cache: %d DOIs from %s", len(done), done_cache_path)
        except (pd.errors.EmptyDataError, KeyError):
            log.warning("Done cache corrupt or empty: %s", done_cache_path)
    # Fallback: citations.csv (present on first migration, absent after DVC clean)
    if os.path.exists(citations_path):
        try:
            df = pd.read_csv(citations_path, usecols=["source_doi"],
                             dtype=str, keep_default_na=False)
            csv_dois = set(df["source_doi"].apply(normalize_doi)) - {"", "nan", "none"}
            done |= csv_dois
            log.info("citations.csv: %d unique source DOIs", len(csv_dois))
        except (pd.errors.EmptyDataError, KeyError):
            pass
    return done


def save_done_cache(done_dois, done_cache_path):
    """Persist the set of processed source DOIs to the cache file."""
    os.makedirs(os.path.dirname(done_cache_path), exist_ok=True)
    pd.DataFrame(sorted(done_dois), columns=["source_doi"]).to_csv(
        done_cache_path, index=False
    )
    log.info("Done cache updated: %d DOIs → %s", len(done_dois), done_cache_path)


def print_resume_preview(done_dois, all_dois, missing):
    """Print a startup summary showing checkpoint state and remaining workload."""
    ckpt_rows = 0
    if os.path.exists(CHECKPOINT_PATH):
        try:
            ckpt_rows = max(0, sum(1 for _ in open(CHECKPOINT_PATH)) - 1)
        except Exception:
            pass
    log.info("Resume: %d DOIs total, %d done, %d in checkpoint, %d remaining",
             len(all_dois), len(done_dois), ckpt_rows, len(missing))


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
    parser.add_argument("--works-input",
                        default=os.path.join(CATALOGS_DIR, "unified_works.csv"),
                        help="Works CSV to read DOIs from (default: unified_works.csv)")
    parser.add_argument("--run-id", default=None,
                        help="Unique run identifier for the run report (default: timestamp)")
    parser.add_argument("--resume", action="store_true", default=True,
                        help="Resume from existing checkpoint (default: True)")
    parser.add_argument("--no-resume", dest="resume", action="store_false",
                        help="Ignore existing checkpoint and start fresh")
    parser.add_argument("--checkpoint-every", type=int, default=50,
                        help="Flush checkpoint every N batches (default: 50, 0=only at end)")
    parser.add_argument("--request-timeout", type=float, default=60.0,
                        help="Per-request timeout in seconds (default: 60)")
    parser.add_argument("--max-retries", type=int, default=5,
                        help="Maximum retries for transient failures (default: 5)")
    parser.add_argument("--retry-backoff", type=float, default=2.0,
                        help="Base for exponential backoff in seconds (default: 2.0)")
    parser.add_argument("--retry-jitter", type=float, default=1.0,
                        help="Max random jitter added to backoff (default: 1.0)")
    parser.add_argument("--citations-input", default=CITATIONS_PATH,
                        help="Path to existing citations CSV (default: auto)")
    parser.add_argument("--log-jsonl", default=None,
                        help="Path to write JSONL event log (optional)")
    args = parser.parse_args()

    citations_path = args.citations_input
    checkpoint_path = os.path.join(os.path.dirname(citations_path),
                                   ".citations_batch_checkpoint.csv")
    done_cache_path = os.path.join(os.path.dirname(citations_path),
                                   "enrich_cache", "citations_done.csv")

    run_id = args.run_id or make_run_id()
    t0 = time.time()
    counters = {}

    def _log_event(event_type, **kwargs):
        """Write a structured event to the optional JSONL log."""
        if not args.log_jsonl:
            return
        record = {"run_id": run_id, "event": event_type,
                  "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **kwargs}
        with open(args.log_jsonl, "a") as f:
            f.write(json.dumps(record) + "\n")  # (#8) reuse top-level json

    # If explicitly starting fresh, discard any stale unmerged checkpoint.
    if not args.resume and os.path.exists(checkpoint_path):
        os.remove(checkpoint_path)

    # Load already-fetched DOIs from persistent cache (survives DVC re-runs)
    done_dois = load_done_dois(citations_path, done_cache_path)

    # Load existing citations.csv for merging later (may be absent after DVC clean)
    if os.path.exists(citations_path):
        existing = pd.read_csv(citations_path, dtype=str,  # (#1)
                               keep_default_na=False)
        existing["source_doi"] = existing["source_doi"].apply(normalize_doi)
    else:
        existing = pd.DataFrame(columns=REFS_COLUMNS)

    # Also count DOIs from checkpoint (partial run)
    if args.resume and os.path.exists(checkpoint_path):
        ckpt = pd.read_csv(checkpoint_path, dtype=str,  # (#2)
                           keep_default_na=False)
        ckpt_dois = set(ckpt["source_doi"].apply(normalize_doi)) - {"", "nan", "none"}
        done_dois |= ckpt_dois
        log.info("Checkpoint: %d rows, %d DOIs already fetched",
                 len(ckpt), len(ckpt_dois))
    else:
        ckpt = pd.DataFrame(columns=REFS_COLUMNS)

    # All DOIs in works input
    works = pd.read_csv(args.works_input,
                        dtype=str, keep_default_na=False)
    all_dois = [normalize_doi(d) for d in works["doi"].unique() if d]
    all_dois = [d for d in all_dois if d and d not in ("", "nan", "none")]

    # Sort by priority (most-cited works first) for deterministic ordering.
    all_dois_sorted = sort_dois_by_priority(all_dois, works)
    missing = [d for d in all_dois_sorted if d not in done_dois]

    if args.limit:
        missing = missing[:args.limit]

    print_resume_preview(done_dois, all_dois, missing)
    _log_event("start", dois_total=len(all_dois), dois_done_before=len(done_dois),
               dois_to_fetch=len(missing))

    if not missing:
        log.info("Nothing to fetch.")
        # Persist done-set on early exit (ensures migration from citations.csv)
        save_done_cache(done_dois - {"", "nan", "none"}, done_cache_path)
        return

    # Write checkpoint header once upfront
    if not os.path.exists(checkpoint_path) or os.path.getsize(checkpoint_path) == 0:
        pd.DataFrame(columns=REFS_COLUMNS).to_csv(checkpoint_path, index=False)

    # Process in batches
    total_refs = 0
    total_found = 0
    consecutive_errors = 0  # (#10) reset on success, not cumulative
    checkpoint_flushes = 0
    n_batches = (len(missing) + args.batch_size - 1) // args.batch_size
    checkpoint_every = args.checkpoint_every if args.checkpoint_every > 0 else n_batches + 1

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
            if consecutive_errors > MAX_CONSECUTIVE_ERRORS:
                log.error("Too many consecutive errors (%d), stopping.",
                          consecutive_errors)
                break
            continue

        consecutive_errors = 0  # (#10) reset on success
        total_refs += len(refs)
        total_found += len(found_dois)

        # Append refs to checkpoint (header already written)
        if refs:
            batch_df = pd.DataFrame(refs, columns=REFS_COLUMNS)
            batch_df.to_csv(checkpoint_path, mode="a", header=False,
                            index=False)

        # Record DOIs found but with no refs (so we skip on resume).
        # Batch sentinels into one write instead of N file opens (#4).
        no_ref_dois = found_dois - {r["source_doi"] for r in refs}
        if no_ref_dois:
            sentinel_rows = [{
                "source_doi": d, "source_id": "", "ref_doi": SENTINEL_REF_DOI,
                "ref_title": "", "ref_first_author": "", "ref_year": "",
                "ref_journal": "", "ref_raw": "",
            } for d in no_ref_dois]
            pd.DataFrame(sentinel_rows, columns=REFS_COLUMNS).to_csv(
                checkpoint_path, mode="a", header=False, index=False)

        checkpoint_flushes += 1
        if checkpoint_flushes % checkpoint_every == 0:
            _log_event("checkpoint", batch=batch_num, total_refs=total_refs,
                       total_found=total_found)

        elapsed = time.time() - t0
        rate = (i + len(batch_dois)) / elapsed if elapsed > 0 else 0
        eta = (len(missing) - i - len(batch_dois)) / rate if rate > 0 else 0

        if batch_num % 10 == 0 or batch_num == n_batches:
            log.info("Batch %d/%d: %d DOIs found, %d refs, ETA %.0fs",
                     batch_num, n_batches, total_found, total_refs, eta)

    # Merge checkpoint into existing citations.csv
    log.info("Merging checkpoint into citations.csv...")
    if os.path.exists(checkpoint_path):
        new_refs = pd.read_csv(checkpoint_path, dtype=str,
                               keep_default_na=False)
        # Drop sentinel rows (marker: ref_doi == SENTINEL_REF_DOI).
        # Also drop legacy sentinels (all non-key fields empty).
        is_sentinel = (new_refs["ref_doi"] == SENTINEL_REF_DOI)
        non_key_cols = [c for c in REFS_COLUMNS if c != "source_doi"]
        is_sentinel = is_sentinel | new_refs[non_key_cols].eq("").all(axis=1)
        new_refs_real = new_refs[~is_sentinel]
        combined = pd.concat([existing, new_refs_real], ignore_index=True)
        combined.to_csv(citations_path, index=False)
        os.remove(checkpoint_path)
        log.info("Merged: %d old + %d new (-%d sentinels) = %d rows",
                 len(existing), len(new_refs_real),
                 int(is_sentinel.sum()), len(combined))
    else:
        log.info("No new data to merge.")
        new_refs_real = pd.DataFrame(columns=REFS_COLUMNS)
        combined = existing

    # Persist done-set so it survives DVC re-runs (citations.csv gets deleted)
    # (#6) normalize consistently — combined is already str dtype
    all_done = ((done_dois
                 | set(combined["source_doi"].apply(normalize_doi)))
                - {"", "nan", "none"})
    save_done_cache(all_done, done_cache_path)

    elapsed = time.time() - t0
    log.info("Done in %.0fs: %d DOIs found, %d refs, %d consecutive errors at exit",
             elapsed, total_found, total_refs, consecutive_errors)

    counters.update({
        "dois_total": len(all_dois),
        "dois_done_before": len(done_dois),
        "dois_to_fetch": len(missing),
        "dois_found": total_found,
        "refs_written": total_refs,
        "checkpoint_flush_count": checkpoint_flushes,
        "consecutive_errors_at_exit": consecutive_errors,
        "elapsed_seconds": round(elapsed, 1),
    })
    report_path = save_run_report(counters, run_id, "enrich_citations_batch")
    log.info("Run report: %s", report_path)
    _log_event("complete", elapsed_seconds=round(elapsed, 1),
               refs_written=total_refs, report_path=report_path)


if __name__ == "__main__":
    main()
