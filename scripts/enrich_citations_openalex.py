#!/usr/bin/env python3
"""Enrich citations from OpenAlex referenced_works.

For every DOI in the works input, queries OpenAlex for its referenced_works
list and resolves each OpenAlex work ID to a DOI + bibliographic metadata.

Writes to enrich_cache/openalex_refs.csv (append-only, persistent).
The cache IS the data — no separate done-file. A DOI is done if it has
rows (real refs or sentinel) in the cache, OR if it already appears in
openalex_citations.csv (catalog-stage harvest).

The downstream merge_citations.py step reads this cache + the Crossref
cache and produces the DVC-tracked citations.csv.

Two-phase approach:
  Phase 1: batch-fetch source works → collect referenced_works OpenAlex IDs.
  Phase 2: batch-resolve OpenAlex IDs → get DOIs, title, first author, year, journal.

Usage:
    uv run python scripts/enrich_citations_openalex.py [--batch-size 50] [--limit N]
"""

import argparse
import json
import os
import time

import pandas as pd

from utils import (CATALOGS_DIR, MAILTO, OPENALEX_API_KEY, normalize_doi,
                   sort_dois_by_priority, retry_get, save_run_report,
                   make_run_id, get_logger)

log = get_logger("enrich_citations_openalex")

CACHE_DIR = os.path.join(CATALOGS_DIR, "enrich_cache")
CACHE_PATH = os.path.join(CACHE_DIR, "openalex_refs.csv")
SENTINEL_REF_DOI = "__NO_REFS__"

OA_REFS_COLUMNS = [
    "source_doi", "ref_oa_id", "ref_doi", "ref_title",
    "ref_first_author", "ref_year", "ref_journal",
]

OA_BASE = "https://api.openalex.org/works"
HEADERS = {"User-Agent": f"ClimateFinancePipeline/1.0 (mailto:{MAILTO})"}


def openalex_get(params, delay=0.15, counters=None,
                 request_timeout=60.0, max_retries=5,
                 retry_backoff=2.0, retry_jitter=1.0):
    """GET request to OpenAlex with polite delay and retry/backoff."""
    if counters is None:
        counters = {}
    params.setdefault("mailto", MAILTO)
    if OPENALEX_API_KEY:
        params.setdefault("api_key", OPENALEX_API_KEY)
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
    """Phase 2: resolve OpenAlex IDs → (id, doi, title, first_author, year, journal).

    Returns dict {oa_id: {doi, title, first_author, year, journal}}
    """
    if not oa_ids:
        return {}
    if counters is None:
        counters = {}
    id_filter = "|".join(oa_ids)
    data = openalex_get(
        {
            "filter": f"openalex:{id_filter}",
            "select": "id,doi,title,publication_year,primary_location,authorships,type,cited_by_count,ids",
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
        # Extract first author from authorships
        authorships = item.get("authorships", []) or []
        first_author = ""
        if authorships:
            author_obj = authorships[0].get("author", {}) or {}
            first_author = author_obj.get("display_name", "") or ""
        result[oa_id] = {
            "doi": doi,
            "title": title,
            "first_author": first_author,
            "year": year,
            "journal": journal,
        }
    return result


def load_done_dois(cache_path, oa_citations_path=None):
    """Load done DOIs from the cache file + catalog-stage openalex_citations.csv.

    A DOI is "done" if it has rows in the cache (real refs or sentinel),
    or if it appears as source_doi in openalex_citations.csv (already harvested).
    """
    done = set()

    # From cache file
    if os.path.exists(cache_path):
        try:
            df = pd.read_csv(cache_path, usecols=["source_doi"],
                             dtype=str, keep_default_na=False)
            done = set(df["source_doi"].apply(normalize_doi)) - {"", "nan", "none"}
            log.info("Cache: %d unique source DOIs in %s", len(done), cache_path)
        except (pd.errors.EmptyDataError, KeyError):
            log.warning("Cache corrupt or empty: %s", cache_path)

    # From catalog-stage harvest (these DOIs were already processed)
    oa_citations_path = oa_citations_path or os.path.join(
        CATALOGS_DIR, "openalex_citations.csv")
    if os.path.exists(oa_citations_path):
        try:
            oa_done = set(
                pd.read_csv(oa_citations_path, usecols=["source_doi"],
                            dtype=str, keep_default_na=False)["source_doi"]
                .apply(normalize_doi).unique()
            ) - {"", "nan", "none"}
            log.info("Catalog citations: %d source DOIs in %s",
                     len(oa_done), oa_citations_path)
            done |= oa_done
        except (pd.errors.EmptyDataError, KeyError):
            pass

    return done


def _build_citation_rows(all_source_refs, id_metadata):
    """Convert source→ref_ids mapping into flat citation rows."""
    rows = []
    for source_doi, ref_ids in all_source_refs.items():
        if not ref_ids:
            # Sentinel for DOIs found but with no refs
            rows.append({
                "source_doi": source_doi,
                "ref_oa_id": "",
                "ref_doi": SENTINEL_REF_DOI,
                "ref_title": "",
                "ref_first_author": "",
                "ref_year": "",
                "ref_journal": "",
            })
            continue
        for oa_id in ref_ids:
            meta = id_metadata.get(oa_id, {})
            rows.append({
                "source_doi": source_doi,
                "ref_oa_id": oa_id,
                "ref_doi": meta.get("doi", ""),
                "ref_title": meta.get("title", ""),
                "ref_first_author": meta.get("first_author", ""),
                "ref_year": meta.get("year", ""),
                "ref_journal": meta.get("journal", ""),
            })
    return rows


def main():
    parser = argparse.ArgumentParser(
        description="Enrich citations from OpenAlex (most-cited first)")
    parser.add_argument("--batch-size", type=int, default=50,
                        help="DOIs per OpenAlex request (max ~100)")
    parser.add_argument("--resolve-batch-size", type=int, default=100,
                        help="OpenAlex IDs to resolve per request")
    parser.add_argument("--limit", type=int, default=0,
                        help="Max source DOIs to process (0=all)")
    parser.add_argument("--delay", type=float, default=0.15,
                        help="Delay between API requests (seconds)")
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
    p1_counters = {}
    p2_counters = {}

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
        pd.DataFrame({c: pd.Series(dtype=str) for c in OA_REFS_COLUMNS}).to_csv(
            CACHE_PATH, index=False)

    # Load done DOIs from cache + catalog harvest (cache-is-data)
    done_dois = load_done_dois(CACHE_PATH)

    # Corpus DOIs
    works = pd.read_csv(args.works_input, dtype=str, keep_default_na=False)
    all_dois = [
        normalize_doi(d) for d in works["doi"].unique()
        if normalize_doi(d) not in ("", "nan", "none")
    ]

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

    # ── Phase 1: collect referenced_works IDs ────────────────────────────
    log.info("Phase 1: fetching referenced_works from OpenAlex...")
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
        except Exception as e:
            log.error("Batch %d/%d: %s", batch_num, n_batches, e)
            _log_event("phase1_batch_error", batch=batch_num, error=str(e))
            p1_errors += 1
            if p1_errors > 10:
                log.error("Too many errors, stopping.")
                break
            continue

        if batch_num % 20 == 0 or batch_num == n_batches:
            found_refs = sum(len(v) for v in all_source_refs.values())
            elapsed = time.time() - t0
            rate = (i + len(batch)) / elapsed if elapsed > 0 else 0
            eta = (len(missing) - i - len(batch)) / rate if rate > 0 else 0
            log.info("P1 batch %d/%d: %d sources, %d ref-IDs, ETA %.0fs",
                     batch_num, n_batches, len(all_source_refs), found_refs, eta)

    # ── Phase 2: resolve OpenAlex IDs → DOIs + metadata ─────────────────
    all_oa_ids = list({
        oa_id
        for ref_list in all_source_refs.values()
        for oa_id in ref_list
        if oa_id
    })
    log.info("Phase 2: resolving %d unique OpenAlex IDs to DOIs...", len(all_oa_ids))

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
            log.error("Resolve batch %d/%d: %s", batch_num, n_resolve_batches, e)
            p2_errors += 1
            if p2_errors > 10:
                log.error("Too many errors, stopping resolution.")
                break
            continue

        if batch_num % 20 == 0 or batch_num == n_resolve_batches:
            log.info("P2 resolve %d/%d: %d IDs resolved",
                     batch_num, n_resolve_batches, len(id_metadata))

    # ── Build rows and append to cache ────────────────────────────────
    rows = _build_citation_rows(all_source_refs, id_metadata)

    if rows:
        batch_df = pd.DataFrame(rows, columns=OA_REFS_COLUMNS)
        batch_df.to_csv(CACHE_PATH, mode="a", header=False, index=False)
        log.info("Appended %d rows to %s", len(rows), CACHE_PATH)

    elapsed = time.time() - t0
    log.info("Done in %.0fs: %d sources, %d OA IDs, %d resolved, "
             "%d rows, errors: %d fetch + %d resolve",
             elapsed, len(all_source_refs), len(all_oa_ids),
             len(id_metadata), len(rows), p1_errors, p2_errors)

    counters = {
        "dois_total": len(all_dois),
        "dois_done_before": len(done_dois),
        "dois_to_fetch": len(missing),
        "sources_processed": len(all_source_refs),
        "openalex_ids_found": len(all_oa_ids),
        "ids_resolved": len(id_metadata),
        "rows_written": len(rows),
        "p1_errors": p1_errors,
        "p2_errors": p2_errors,
        "elapsed_seconds": round(elapsed, 1),
    }
    report_path = save_run_report(counters, run_id, "enrich_citations_openalex")
    log.info("Run report: %s", report_path)
    _log_event("complete", elapsed_seconds=round(elapsed, 1),
               rows_written=len(rows), report_path=report_path)


if __name__ == "__main__":
    main()
