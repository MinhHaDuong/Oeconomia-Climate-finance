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
                                                        [--run-id ID]
"""

import argparse
import json
import os
import sys
import time

import pandas as pd
import requests

sys.path.insert(0, os.path.dirname(__file__))
from utils import (CATALOGS_DIR, MAILTO, REFS_COLUMNS, normalize_doi,
                   sort_dois_by_priority, retry_get, save_run_report, make_run_id)

CITATIONS_PATH = os.path.join(CATALOGS_DIR, "citations.csv")
CHECKPOINT_PATH = os.path.join(CATALOGS_DIR, ".citations_oa_checkpoint.csv")
DONE_PATH = os.path.join(CATALOGS_DIR, ".citations_oa_done.txt")

OA_BASE = "https://api.openalex.org/works"
HEADERS = {"User-Agent": f"ClimateFinancePipeline/1.0 (mailto:{MAILTO})"}


def openalex_get(params, delay=0.15, counters=None,
                 request_timeout=60.0, max_retries=5,
                 retry_backoff=2.0, retry_jitter=1.0):
    """GET request to OpenAlex with polite delay and retry/backoff."""
    if counters is None:
        counters = {}
    params.setdefault("mailto", MAILTO)
    resp = retry_get(
        OA_BASE,
        params=params,
        headers=HEADERS,
        delay=delay,
        max_retries=max_retries,
        timeout=max(1, request_timeout),
        backoff_base=retry_backoff,
        jitter_max=retry_jitter,
        counters=counters,
    )
    return resp.json()


def fetch_source_batch(dois, counters=None,
                       request_timeout=60.0, max_retries=5,
                       retry_backoff=2.0, retry_jitter=1.0):
    """Phase 1: fetch referenced_works for a batch of source DOIs.

    Returns dict {source_doi: [openalex_id, ...]}
    """
    if counters is None:
        counters = {}
    doi_values = "|".join(dois)
    data = openalex_get(
        {
            "filter": f"doi:{doi_values}",
            "select": "id,doi,referenced_works",
            "per-page": len(dois),
        },
        counters=counters,
        request_timeout=request_timeout,
        max_retries=max_retries,
        retry_backoff=retry_backoff,
        retry_jitter=retry_jitter,
    )
    result = {}
    for item in data.get("results", []):
        source_doi = normalize_doi(item.get("doi", ""))
        if not source_doi:
            continue
        ref_ids = item.get("referenced_works", []) or []
        result[source_doi] = [
            r.split("/")[-1] for r in ref_ids if r
        ]
    return result


def resolve_openalex_ids(oa_ids, counters=None,
                         request_timeout=60.0, max_retries=5,
                         retry_backoff=2.0, retry_jitter=1.0):
    """Phase 2: resolve a list of OpenAlex IDs → (id, doi, title, year, journal).

    Returns dict {oa_id: {doi, title, year, journal}}
    """
    if not oa_ids:
        return {}
    if counters is None:
        counters = {}
    id_filter = "|".join(oa_ids)
    data = openalex_get(
        {
            "filter": f"openalex:{id_filter}",
            "select": "id,doi,title,publication_year,primary_location",
            "per-page": len(oa_ids),
        },
        counters=counters,
        request_timeout=request_timeout,
        max_retries=max_retries,
        retry_backoff=retry_backoff,
        retry_jitter=retry_jitter,
    )
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


def print_resume_preview(done_dois, all_dois, missing):
    """Print a startup summary of done-set/checkpoint state and remaining workload."""
    print("── Resume preview ─────────────────────────────────────────")
    print(f"  Corpus DOIs total:      {len(all_dois)}")
    print(f"  Done-set entries:       {len(done_dois)}")
    if os.path.exists(DONE_PATH):
        try:
            n = sum(1 for _ in open(DONE_PATH) if _.strip())
            print(f"  Done-set file rows:     {n}")
        except Exception:
            pass
    if os.path.exists(CHECKPOINT_PATH):
        try:
            n = max(0, sum(1 for _ in open(CHECKPOINT_PATH)) - 1)
            print(f"  Checkpoint rows:        {n}")
        except Exception:
            pass
    print(f"  Remaining to fetch:     {len(missing)}")
    print("────────────────────────────────────────────────────────────\n")


def main():
    parser = argparse.ArgumentParser(
        description="Enrich citations from OpenAlex (DOIs processed in priority order: "
                    "most-cited works first, deterministic)")
    parser.add_argument("--batch-size", type=int, default=50,
                        help="DOIs per OpenAlex request (max ~100)")
    parser.add_argument("--resolve-batch-size", type=int, default=100,
                        help="OpenAlex IDs to resolve per request")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max source DOIs to process (0=all)")
    parser.add_argument("--delay", type=float, default=0.15,
                        help="Delay between API requests (seconds)")
    parser.add_argument("--works-input",
                        default=os.path.join(CATALOGS_DIR, "unified_works.csv"),
                        help="Works CSV to read DOIs from (default: unified_works.csv)")
    parser.add_argument("--run-id", default=None,
                        help="Unique run identifier for the run report (default: timestamp)")
    parser.add_argument("--resume", action="store_true", default=True,
                        help="Resume from existing done-set/checkpoint (default: True)")
    parser.add_argument("--no-resume", dest="resume", action="store_false",
                        help="Ignore existing done-set/checkpoint and start fresh")
    parser.add_argument("--checkpoint-every", type=int, default=20,
                        help="Log checkpoint event every N batches (default: 20)")
    parser.add_argument("--request-timeout", type=float, default=60.0,
                        help="Per-request timeout in seconds (default: 60)")
    parser.add_argument("--max-retries", type=int, default=5,
                        help="Maximum retries for transient failures (default: 5)")
    parser.add_argument("--retry-backoff", type=float, default=2.0,
                        help="Base for exponential backoff in seconds (default: 2.0)")
    parser.add_argument("--retry-jitter", type=float, default=1.0,
                        help="Max random jitter added to backoff (default: 1.0)")
    parser.add_argument("--log-jsonl", default=None,
                        help="Path to write JSONL event log (optional)")
    args = parser.parse_args()

    run_id = args.run_id or make_run_id()
    t0 = time.time()
    p1_counters = {}
    p2_counters = {}

    def _log_event(event_type, **kwargs):
        """Write a structured event to the optional JSONL log."""
        if not args.log_jsonl:
            return
        import json as _json
        record = {"run_id": run_id, "event": event_type,
                  "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **kwargs}
        with open(args.log_jsonl, "a") as _f:
            _f.write(_json.dumps(record) + "\n")

    # If explicitly starting fresh, discard done-set and unmerged checkpoint.
    if not args.resume:
        if os.path.exists(DONE_PATH):
            os.remove(DONE_PATH)
        if os.path.exists(CHECKPOINT_PATH):
            os.remove(CHECKPOINT_PATH)

    # ── Load done-set (resumable) ─────────────────────────────────────────
    if args.resume and os.path.exists(DONE_PATH):
        with open(DONE_PATH) as f:
            done_dois = set(line.strip() for line in f if line.strip())
        print(f"Resuming: {len(done_dois)} DOIs already fetched from OpenAlex")
    else:
        done_dois = set()

    # Also count from checkpoint if a previous run crashed before merging
    if args.resume and os.path.exists(CHECKPOINT_PATH):
        ckpt_existing = pd.read_csv(CHECKPOINT_PATH, usecols=["source_doi"],
                                     low_memory=False)
        done_dois |= set(ckpt_existing["source_doi"].apply(normalize_doi).dropna())
        print(f"  (+{len(ckpt_existing)} rows in unmerged checkpoint)")

    # ── Corpus DOIs ───────────────────────────────────────────────────────
    works = pd.read_csv(
        args.works_input,
        dtype=str, keep_default_na=False,
    )
    all_dois = [
        normalize_doi(d) for d in works["doi"].unique()
        if normalize_doi(d) not in ("", "nan", "none")
    ]

    # Skip DOIs already covered by openalex_citations.csv
    oa_citations_path = os.path.join(CATALOGS_DIR, "openalex_citations.csv")
    if os.path.exists(oa_citations_path):
        oa_done = set(
            pd.read_csv(oa_citations_path, usecols=["source_doi"],
                        dtype=str, keep_default_na=False)["source_doi"]
            .apply(normalize_doi).unique()
        )
        print(f"Skipping {len(oa_done)} DOIs already in openalex_citations.csv")
        done_dois |= oa_done

    # Sort by priority (most-cited works first) for deterministic ordering.
    all_dois_sorted = sort_dois_by_priority(all_dois, works)
    missing = [d for d in all_dois_sorted if d not in done_dois]
    if args.limit:
        missing = missing[:args.limit]

    print_resume_preview(done_dois, all_dois, missing)
    _log_event("start", dois_total=len(all_dois), dois_done_before=len(done_dois),
               dois_to_fetch=len(missing))

    if not missing:
        print("Nothing to fetch.")
        return

    # Write checkpoint header once
    if not os.path.exists(CHECKPOINT_PATH) or os.path.getsize(CHECKPOINT_PATH) == 0:
        pd.DataFrame(columns=REFS_COLUMNS).to_csv(CHECKPOINT_PATH, index=False)

    # ── Phase 1: collect referenced_works IDs ────────────────────────────
    print("\nPhase 1: fetching referenced_works from OpenAlex...")
    all_source_refs = {}
    p1_errors = 0
    n_batches = (len(missing) + args.batch_size - 1) // args.batch_size

    for i in range(0, len(missing), args.batch_size):
        batch = missing[i:i + args.batch_size]
        batch_num = i // args.batch_size + 1
        try:
            result = fetch_source_batch(
                batch,
                counters=p1_counters,
                request_timeout=args.request_timeout,
                max_retries=args.max_retries,
                retry_backoff=args.retry_backoff,
                retry_jitter=args.retry_jitter,
            )
            all_source_refs.update(result)
            with open(DONE_PATH, "a") as f:
                for d in batch:
                    f.write(d + "\n")
        except Exception as e:
            print(f"  ERROR batch {batch_num}/{n_batches}: {e}")
            _log_event("phase1_batch_error", batch=batch_num, error=str(e))
            p1_errors += 1
            if p1_errors > 10:
                print("Too many errors, stopping.")
                break
            continue

        if batch_num % args.checkpoint_every == 0 or batch_num == n_batches:
            found_refs = sum(len(v) for v in all_source_refs.values())
            elapsed = time.time() - t0
            rate = (i + len(batch)) / elapsed if elapsed > 0 else 0
            eta = (len(missing) - i - len(batch)) / rate if rate > 0 else 0
            print(f"  Batch {batch_num}/{n_batches}: "
                  f"{len(all_source_refs)} sources, {found_refs} ref-IDs, "
                  f"{elapsed:.0f}s elapsed, ETA {eta:.0f}s")
            _log_event("phase1_checkpoint", batch=batch_num, sources=len(all_source_refs),
                       ref_ids=found_refs)

    # ── Phase 2: resolve OpenAlex IDs → DOIs + metadata ─────────────────
    all_oa_ids = list({
        oa_id
        for ref_list in all_source_refs.values()
        for oa_id in ref_list
        if oa_id
    })
    print(f"\nPhase 2: resolving {len(all_oa_ids)} unique OpenAlex IDs to DOIs...")

    id_metadata = {}
    p2_errors = 0
    n_resolve_batches = (len(all_oa_ids) + args.resolve_batch_size - 1) // args.resolve_batch_size

    for i in range(0, len(all_oa_ids), args.resolve_batch_size):
        batch_ids = all_oa_ids[i:i + args.resolve_batch_size]
        batch_num = i // args.resolve_batch_size + 1
        try:
            resolved = resolve_openalex_ids(
                batch_ids,
                counters=p2_counters,
                request_timeout=args.request_timeout,
                max_retries=args.max_retries,
                retry_backoff=args.retry_backoff,
                retry_jitter=args.retry_jitter,
            )
            id_metadata.update(resolved)
        except Exception as e:
            print(f"  ERROR resolve batch {batch_num}/{n_resolve_batches}: {e}")
            p2_errors += 1
            if p2_errors > 10:
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

    rows_deduped = 0
    if os.path.exists(CHECKPOINT_PATH) and os.path.getsize(CHECKPOINT_PATH) > 0:
        new_refs = pd.read_csv(CHECKPOINT_PATH, low_memory=False)
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
        dupes_mask = new_refs_real["_key"].isin(existing_keys)
        rows_deduped = int(dupes_mask.sum())
        new_refs_real = new_refs_real[~dupes_mask].drop(columns=["_key"])

        combined = pd.concat([existing, new_refs_real], ignore_index=True)
        combined.to_csv(CITATIONS_PATH, index=False)
        os.remove(CHECKPOINT_PATH)
        print(f"  Old rows:          {len(existing)}")
        print(f"  New rows (deduped): {len(new_refs_real)}")
        print(f"  Sentinels dropped: {is_sentinel.sum()}")
        print(f"  Duplicates removed: {rows_deduped}")
        print(f"  Combined:          {len(combined)}")
    else:
        print("  No new data to merge.")
        new_refs_real = pd.DataFrame(columns=REFS_COLUMNS)
        combined = existing

    elapsed = time.time() - t0
    print(f"\nDone in {elapsed:.0f}s")
    print(f"  Sources processed:  {len(all_source_refs)}")
    print(f"  OpenAlex IDs found: {len(all_oa_ids)}")
    print(f"  IDs resolved:       {len(id_metadata)}")
    print(f"  Reference rows:     {len(rows)}")
    print(f"  Errors (fetch):     {p1_errors}")
    print(f"  Errors (resolve):   {p2_errors}")

    counters = {
        "dois_total": len(all_dois),
        "dois_done_before": len(done_dois),
        "dois_to_fetch": len(missing),
        "sources_processed": len(all_source_refs),
        "openalex_ids_found": len(all_oa_ids),
        "ids_resolved": len(id_metadata),
        "rows_built": len(rows),
        "rows_appended": len(new_refs_real),
        "rows_deduped": rows_deduped,
        "p1_errors": p1_errors,
        "p2_errors": p2_errors,
        "p1_retries": p1_counters.get("retries", 0),
        "p1_rate_limited": p1_counters.get("rate_limited", 0),
        "p1_server_errors": p1_counters.get("server_errors", 0),
        "p2_retries": p2_counters.get("retries", 0),
        "p2_rate_limited": p2_counters.get("rate_limited", 0),
        "p2_server_errors": p2_counters.get("server_errors", 0),
        "elapsed_seconds": round(elapsed, 1),
    }
    report_path = save_run_report(counters, run_id, "enrich_citations_openalex")
    print(f"Run report: {report_path}")
    _log_event("complete", elapsed_seconds=round(elapsed, 1),
               rows_appended=len(new_refs_real), report_path=report_path)


if __name__ == "__main__":
    main()
