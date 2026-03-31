#!/usr/bin/env python3
"""Enrich missing abstracts in the refined corpus.

Four-step pipeline, each cached independently:
  1. Cross-source backfill (unified_works.csv DOI match)
  2. OpenAlex re-query (batch API, abstract_inverted_index)
  3. ISTEX fulltext extraction (local TEI XML)
  4. Semantic Scholar fallback (per-DOI API)

Note: Crossref is skipped because OpenAlex already ingests all Crossref
metadata, so step 2 covers everything Crossref would provide.

Usage:
    python scripts/enrich_abstracts.py [--dry-run] [--step N]
                                       [--run-id ID] [--checkpoint-every N]
"""

import argparse
import os
import re
import sys
import time
import xml.etree.ElementTree as ET

import pandas as pd
import requests
from pipeline_text import normalize_text
from utils import (
    CATALOGS_DIR,
    CONSECUTIVE_FAIL_LIMIT,
    MAILTO,
    OPENALEX_API_KEY,
    RAW_DIR,
    RateLimitExhausted,
    WatchedProgress,
    check_rate_limit,
    get_logger,
    make_run_id,
    normalize_doi,
    reconstruct_abstract,
    retry_get,
    save_run_report,
)

log = get_logger("enrich_abstracts")

MIN_ABSTRACT_LEN = 20
CACHE_DIR = os.path.join(CATALOGS_DIR, "enrich_cache")


def is_missing(val):
    """True if abstract value is empty/missing."""
    if pd.isna(val):
        return True
    s = str(val).strip()
    return s == "" or s.lower() in ("nan", "none")


def _is_paywall_stub(text):
    """Return True if text is a publisher paywall/stub abstract (#455)."""
    low = text.lower()
    if low.startswith("no access"):
        return True
    if "10.5751/es-" in low and len(low) < 500:
        return True
    if "not available for this content" in low:
        return True
    return False


def clean_abstract(text):
    """Strip HTML/XML/JATS tags, fix encoding, nullify paywall stubs."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)  # strip tags before normalize_text
    text = normalize_text(text)
    if len(text) < MIN_ABSTRACT_LEN:
        return ""
    if _is_paywall_stub(text):
        return ""
    return text


def load_cache(name):
    """Load a CSV cache file as {key: abstract} dict."""
    path = os.path.join(CACHE_DIR, f"{name}.csv")
    if not os.path.exists(path):
        return {}
    df = pd.read_csv(path)
    return dict(zip(df["key"].astype(str), df["abstract"].fillna("")))


def save_cache(name, data):
    """Save {key: abstract} dict as CSV cache."""
    os.makedirs(CACHE_DIR, exist_ok=True)
    path = os.path.join(CACHE_DIR, f"{name}.csv")
    df = pd.DataFrame([
        {"key": k, "abstract": v} for k, v in data.items()
    ])
    df.to_csv(path, index=False)


def _cache_size(name):
    """Return number of entries in a named cache (0 if absent)."""
    path = os.path.join(CACHE_DIR, f"{name}.csv")
    if not os.path.exists(path):
        return 0
    try:
        return max(0, sum(1 for _ in open(path)) - 1)  # rows minus header
    except OSError:
        return 0


def print_resume_preview(df):
    """Print a startup summary showing cache sizes and estimated workload."""
    total = len(df)
    missing = df["abstract"].apply(is_missing).sum()
    oa_cache = _cache_size("openalex_abstracts")
    s2_cache = _cache_size("s2_abstracts")
    log.info("Resume preview: %d works, %d missing (%.1f%%), "
             "OA cache=%d, S2 cache=%d",
             total, missing, missing / total * 100, oa_cache, s2_cache)


# --- Step 1: Cross-source backfill ---

def step1_cross_source(df, counters):
    """Fill missing abstracts from other records with the same DOI."""
    missing = df.index[df["_missing"]]
    counters["step1_attempted"] = len(missing)
    if len(missing) == 0:
        return 0

    # Load unified_works for DOI-based abstract lookup
    unified_path = os.path.join(CATALOGS_DIR, "unified_works.csv")
    unified = pd.read_csv(unified_path, usecols=["doi", "abstract"])
    unified["doi_norm"] = unified["doi"].apply(normalize_doi)
    unified = unified[unified["abstract"].notna() & (unified["abstract"].str.len() > MIN_ABSTRACT_LEN)]

    # Build DOI → best abstract map (longest abstract wins)
    doi_abs = {}
    for _, row in unified.iterrows():
        d = row["doi_norm"]
        if d and d not in ("", "nan", "none"):
            a = str(row["abstract"])
            if d not in doi_abs or len(a) > len(doi_abs[d]):
                doi_abs[d] = a

    filled = 0
    n = len(missing)
    for i, idx in enumerate(missing):
        doi = normalize_doi(df.at[idx, "doi"])
        if doi and doi in doi_abs:
            ab = clean_abstract(doi_abs[doi])
            if ab:
                df.at[idx, "abstract"] = ab
                df.at[idx, "_missing"] = False
                filled += 1
        if (i + 1) % 2000 == 0:
            log.info("Cross-source: %d/%d checked, %d filled", i + 1, n, filled)
    counters["step1_filled"] = filled
    return filled


# --- Step 2: OpenAlex re-query ---

def step2_openalex(df, counters, checkpoint_every=50,
                   request_timeout=60.0, max_retries=5,
                   retry_backoff=2.0, retry_jitter=1.0):
    """Re-query OpenAlex for works that may now have abstracts."""
    cache = load_cache("openalex_abstracts")
    missing = df.index[df["_missing"] & (df["from_openalex"] == 1)]
    if len(missing) == 0:
        return 0

    # Collect source_ids to query (skip cached)
    to_query = []
    cache_hits = 0
    for idx in missing:
        sid = str(df.at[idx, "source_id"])
        if sid in cache:
            cache_hits += 1
            continue
        to_query.append((idx, sid))

    counters["step2_attempted"] = len(to_query)
    counters["step2_cache_hits"] = cache_hits
    log.info("OpenAlex: %d uncached IDs to query (%d cache hits)",
             len(to_query), cache_hits)

    # Batch query (50 per request)
    batch_size = 50
    batches_done = 0
    consecutive_failures = 0
    for i in range(0, len(to_query), batch_size):
        batch = to_query[i:i + batch_size]
        ids = [sid for _, sid in batch]
        id_filter = "|".join(ids)
        params = {
            "filter": f"openalex_id:{id_filter}",
            "select": "id,abstract_inverted_index",
            "per_page": batch_size,
            "mailto": MAILTO,
        }
        if OPENALEX_API_KEY:
            params["api_key"] = OPENALEX_API_KEY
        try:
            resp = retry_get(
                "https://api.openalex.org/works",
                params=params,
                delay=0.15,
                timeout=max(1, request_timeout),
                max_retries=max_retries,
                backoff_base=retry_backoff,
                jitter_max=retry_jitter,
                counters=counters,
            )
            check_rate_limit(resp, "api.openalex.org")
            resp.raise_for_status()
            consecutive_failures = 0
            results = {
                r["id"].replace("https://openalex.org/", ""):
                    reconstruct_abstract(r.get("abstract_inverted_index"))
                for r in resp.json().get("results", [])
            }
            for sid in ids:
                cache[sid] = results.get(sid, "")
        except RateLimitExhausted:
            consecutive_failures += 1
            log.warning("Rate limit exhausted (%d/%d consecutive)",
                        consecutive_failures, CONSECUTIVE_FAIL_LIMIT)
            if consecutive_failures >= CONSECUTIVE_FAIL_LIMIT:
                log.error("Aborting Step 2: %d consecutive rate-limit failures.",
                          CONSECUTIVE_FAIL_LIMIT)
                break
        except Exception as e:
            log.warning("Batch %d failed: %s", i, e)
            counters["step2_errors"] = counters.get("step2_errors", 0) + 1
            for sid in ids:
                cache.setdefault(sid, "")

        batches_done += 1
        if batches_done % checkpoint_every == 0:
            save_cache("openalex_abstracts", cache)

        if batches_done % 10 == 0:
            log.info("OpenAlex: %d/%d queried",
                     min(i + batch_size, len(to_query)), len(to_query))

    save_cache("openalex_abstracts", cache)

    # Apply cached results
    filled = 0
    empty = 0
    for idx in missing:
        sid = str(df.at[idx, "source_id"])
        ab = clean_abstract(cache.get(sid, ""))
        if ab:
            df.at[idx, "abstract"] = ab
            df.at[idx, "_missing"] = False
            filled += 1
        else:
            empty += 1
    counters["step2_filled"] = filled
    counters["step2_empty_result"] = empty
    return filled


# --- Step 3: ISTEX fulltext extraction ---

def step3_istex(df, counters):
    """Extract abstracts from locally downloaded ISTEX TEI XML files."""
    missing = df.index[
        df["_missing"] & (df["from_istex"] == 1)
    ]
    counters["step3_attempted"] = len(missing)
    if len(missing) == 0:
        return 0

    raw_ids = set(os.listdir(RAW_DIR)) if os.path.isdir(RAW_DIR) else set()

    filled = 0
    n = len(missing)
    for i, idx in enumerate(missing):
        sid = str(df.at[idx, "source_id"])
        if sid not in raw_ids:
            continue

        doc_dir = os.path.join(RAW_DIR, sid)

        # Try TEI XML first
        tei_path = os.path.join(doc_dir, f"{sid}.tei.xml")
        if os.path.exists(tei_path):
            ab = extract_abstract_tei(tei_path)
            if ab:
                df.at[idx, "abstract"] = ab
                df.at[idx, "_missing"] = False
                filled += 1
                continue

        # Try cleaned text fallback (first paragraph)
        cleaned_path = os.path.join(doc_dir, f"{sid}.cleaned")
        if os.path.exists(cleaned_path):
            ab = extract_first_paragraph(cleaned_path)
            if ab:
                df.at[idx, "abstract"] = ab
                df.at[idx, "_missing"] = False
                filled += 1

        if (i + 1) % 500 == 0:
            log.info("ISTEX: %d/%d checked, %d filled", i + 1, n, filled)

    counters["step3_filled"] = filled
    return filled


def extract_abstract_tei(path):
    """Extract abstract text from a TEI XML file."""
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        for ab_elem in root.iter("{http://www.tei-c.org/ns/1.0}abstract"):
            text = "".join(ab_elem.itertext())
            return clean_abstract(text)
        # Try without namespace
        for ab_elem in root.iter("abstract"):
            text = "".join(ab_elem.itertext())
            return clean_abstract(text)
    except (ET.ParseError, OSError) as e:
        log.debug("TEI parse failed for %s: %s", path, e)
    return ""


def extract_first_paragraph(path):
    """Extract first substantial paragraph from cleaned text."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            text = f.read(5000)
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 50]
        if paragraphs:
            return clean_abstract(paragraphs[0])
    except OSError as e:
        log.debug("Could not read %s: %s", path, e)
    return ""


# --- Step 4: Semantic Scholar ---

def _fetch_s2_abstract(doi, request_timeout, max_retries, retry_backoff, retry_jitter,
                       s2_counters):
    """Fetch a single abstract from Semantic Scholar by DOI.

    Returns (abstract_text, status) where status is one of:
      "success", "empty", "4xx", "5xx", "error".
    The caller updates step-level counters based on status.
    """
    try:
        resp = retry_get(
            f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}",
            params={"fields": "abstract"},
            timeout=max(1, request_timeout),
            delay=3.0,
            max_retries=max_retries,
            backoff_base=retry_backoff,
            jitter_max=retry_jitter,
            counters=s2_counters,
        )
        check_rate_limit(resp, "Semantic Scholar")
        if resp.status_code == 200:
            ab = clean_abstract(resp.json().get("abstract", "") or "")
            return ab, "success" if ab else "empty"
        if resp.status_code in (404, 400):
            return "", "4xx"
        return "", "5xx"
    except RateLimitExhausted:
        raise
    except requests.exceptions.HTTPError as e:
        status = e.response.status_code if e.response is not None else 0
        return "", "4xx" if status in (404, 400) else "5xx"
    except Exception:
        return "", "error"


def step4_semantic_scholar(df, counters, checkpoint_every=50,
                           request_timeout=60.0, max_retries=5,
                           retry_backoff=2.0, retry_jitter=1.0):
    """Fetch abstracts from Semantic Scholar for remaining DOI-bearing works."""
    cache = load_cache("s2_abstracts")
    missing = df.index[df["_missing"] & df["_has_doi"]]
    if len(missing) == 0:
        return 0

    to_query = []
    cache_hits = 0
    for idx in missing:
        doi = normalize_doi(df.at[idx, "doi"])
        if doi in cache:
            cache_hits += 1
            continue
        to_query.append((idx, doi))

    counters["step4_attempted"] = len(to_query)
    counters["step4_cache_hits"] = cache_hits
    log.info("Semantic Scholar: %d uncached DOIs to query (%d cache hits)",
             len(to_query), cache_hits)

    # S2 is slow (3s/request) — log every 10 regardless of checkpoint_every
    s2_log_every = min(checkpoint_every, 10)
    s2_counters = {}
    consecutive_failures = 0
    for i, (idx, doi) in enumerate(to_query):
        try:
            ab, status = _fetch_s2_abstract(
                doi, request_timeout, max_retries, retry_backoff, retry_jitter,
                s2_counters)
            consecutive_failures = 0
        except RateLimitExhausted:
            consecutive_failures += 1
            log.warning("S2 rate limit exhausted (%d/%d consecutive)",
                        consecutive_failures, CONSECUTIVE_FAIL_LIMIT)
            if consecutive_failures >= CONSECUTIVE_FAIL_LIMIT:
                log.error("Aborting Step 4: %d consecutive rate-limit failures. "
                          "Cache saved — re-run to resume.",
                          CONSECUTIVE_FAIL_LIMIT)
                save_cache("s2_abstracts", cache)
                raise
            continue
        cache[doi] = ab

        counter_key = f"step4_{status}"
        counters[counter_key] = counters.get(counter_key, 0) + 1
        if status in ("5xx", "error") and i < 3:
            log.warning("S2 %s: %s response", doi, status)

        if (i + 1) % s2_log_every == 0:
            filled_so_far = counters.get("step4_success", 0)
            log.info("Semantic Scholar: %d/%d queried (filled: %d)",
                     i + 1, len(to_query), filled_so_far)
            sys.stdout.flush()
        if (i + 1) % checkpoint_every == 0:
            save_cache("s2_abstracts", cache)

    save_cache("s2_abstracts", cache)

    counters["step4_retries"] = s2_counters.get("retries", 0)
    counters["step4_rate_limited"] = s2_counters.get("rate_limited", 0)
    counters["step4_server_errors"] = s2_counters.get("server_errors", 0)
    counters["step4_client_errors"] = s2_counters.get("client_errors", 0)

    filled = 0
    for idx in missing:
        doi = normalize_doi(df.at[idx, "doi"])
        ab = cache.get(doi, "")
        if ab:
            df.at[idx, "abstract"] = ab
            df.at[idx, "_missing"] = False
            filled += 1
    counters["step4_filled"] = filled
    return filled


# --- Main ---

STEPS = {
    1: ("Cross-source backfill", step1_cross_source),
    2: ("OpenAlex re-query", step2_openalex),
    3: ("ISTEX fulltext extraction", step3_istex),
    4: ("Semantic Scholar fallback", step4_semantic_scholar),
}


def main():
    parser = argparse.ArgumentParser(description="Enrich missing abstracts")
    parser.add_argument("--output", default=None,
                        help="Stamp file path — written on success (DVC output)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Show counts, don't modify data")
    parser.add_argument("--step", type=int, default=0,
                        help="Run only this step (1-5, 0=all)")
    parser.add_argument("--works-input",
                        default=os.path.join(CATALOGS_DIR, "unified_works.csv"),
                        help="Input works CSV (default: unified_works.csv)")
    parser.add_argument("--run-id", default=None,
                        help="Unique run identifier for the run report (default: timestamp)")
    parser.add_argument("--resume", action="store_true", default=True,
                        help="Resume from existing caches/checkpoints (default: True)")
    parser.add_argument("--no-resume", dest="resume", action="store_false",
                        help="Ignore existing caches and start fresh")
    parser.add_argument("--checkpoint-every", type=int, default=50,
                        help="Flush Step 2/4 caches every N batches/items (default: 50)")
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
    parser.add_argument("--stuck-timeout", type=float, default=300,
                        help="Seconds without progress before stuck alert (default: 300)")
    parser.add_argument("--no-progress", action="store_true",
                        help="Disable progress bar (for non-TTY / CI)")
    args = parser.parse_args()

    run_id = args.run_id or make_run_id()
    t0 = time.time()

    def _log_event(event_type, **kwargs):
        """Write a structured event to the optional JSONL log."""
        if not args.log_jsonl:
            return
        import json as _json
        record = {"run_id": run_id, "event": event_type,
                  "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), **kwargs}
        with open(args.log_jsonl, "a") as _f:
            _f.write(_json.dumps(record) + "\n")

    path = args.works_input
    df = pd.read_csv(path)
    log.info("Loaded %d works from %s", len(df), path)
    _log_event("start", works_count=len(df), works_input=path)

    # Compute working columns
    df["_missing"] = df["abstract"].apply(is_missing)
    doi_s = df["doi"].apply(normalize_doi)
    df["_has_doi"] = doi_s.apply(lambda x: bool(x) and x not in ("", "nan", "none"))

    total_missing_before = int(df["_missing"].sum())

    if not args.resume:
        for cache_name in ("openalex_abstracts", "s2_abstracts"):
            cache_path = os.path.join(CACHE_DIR, f"{cache_name}.csv")
            if os.path.exists(cache_path):
                os.remove(cache_path)

    print_resume_preview(df)

    if args.dry_run:
        log.info("Dry run — not modifying data.")
        return

    steps = STEPS if args.step == 0 else {args.step: STEPS[args.step]}

    counters = {
        "missing_before": total_missing_before,
        "total_works": len(df),
    }
    step_results = {}

    # No flush_checkpoint needed: each step flushes its own cache periodically
    # and at completion. The old callback saved the DataFrame monolith, which
    # this script no longer produces (#428).
    with WatchedProgress(
        stuck_timeout=args.stuck_timeout,
        disable=args.no_progress,
    ) as wp:
        overall = wp.add_task(
            "Enriching abstracts", total=total_missing_before,
        )

        for step_num in sorted(steps):
            name, func = steps[step_num]
            before = int(df["_missing"].sum())
            log.info("Step %d: %s (%d still missing)", step_num, name, before)
            _log_event("step_start", step=step_num, name=name, missing_before=before)

            # Steps 2 and 4 accept checkpoint_every; others accept just counters
            if step_num in (2, 4):
                filled = func(
                    df,
                    counters,
                    args.checkpoint_every,
                    args.request_timeout,
                    args.max_retries,
                    args.retry_backoff,
                    args.retry_jitter,
                )
            else:
                filled = func(df, counters)

            # Advance overall progress by the number of abstracts filled
            if filled > 0:
                wp.advance(overall, filled)

            after = int(df["_missing"].sum())
            step_results[f"step{step_num}_name"] = name
            step_results[f"step{step_num}_before"] = before
            step_results[f"step{step_num}_after"] = after
            step_results[f"step{step_num}_filled"] = filled
            log.info("→ filled %d, remaining: %d", filled, after)
            _log_event("step_end", step=step_num, name=name, filled=filled, missing_after=after)

    # Cache-only: enrich_join.py applies caches to the monolith (#428)
    final_missing = int(df["_missing"].sum())

    elapsed = time.time() - t0

    log.info("Done. Abstracts: %d/%d (%.1f%%). Filled %d total. Elapsed: %.0fs",
             len(df) - final_missing, len(df),
             (len(df) - final_missing) / len(df) * 100,
             total_missing_before - final_missing, elapsed)

    # Structured run report
    counters.update({
        "missing_after": final_missing,
        "total_filled": total_missing_before - final_missing,
        "elapsed_seconds": round(elapsed, 1),
        "steps_run": sorted(steps.keys()),
    })
    counters.update(step_results)
    report_path = save_run_report(counters, run_id, "enrich_abstracts")
    log.info("Run report: %s", report_path)
    _log_event("complete", elapsed_seconds=round(elapsed, 1),
               total_filled=counters["total_filled"], report_path=report_path)

    if args.output:
        os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
        with open(args.output, "w") as f:
            f.write(time.strftime("%Y-%m-%dT%H:%M:%S%z") + "\n")
        log.info("Stamp: %s", args.output)


if __name__ == "__main__":
    main()
