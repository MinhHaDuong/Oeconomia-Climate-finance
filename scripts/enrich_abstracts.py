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

sys.path.insert(0, os.path.dirname(__file__))
from utils import (CATALOGS_DIR, RAW_DIR, MAILTO, save_csv,
                   reconstruct_abstract, normalize_doi, polite_get,
                   retry_get, save_run_report, make_run_id)

MIN_ABSTRACT_LEN = 20
CACHE_DIR = os.path.join(CATALOGS_DIR, "enrich_cache")


def is_missing(val):
    """True if abstract value is empty/missing."""
    if pd.isna(val):
        return True
    s = str(val).strip()
    return s == "" or s.lower() in ("nan", "none")


def clean_abstract(text):
    """Strip HTML/XML/JATS tags, normalize whitespace."""
    if not text:
        return ""
    text = re.sub(r"<[^>]+>", " ", text)  # strip tags
    text = re.sub(r"&[a-z]+;", " ", text)  # strip entities
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) < MIN_ABSTRACT_LEN:
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
    except Exception:
        return 0


def print_resume_preview(df):
    """Print a startup summary showing cache sizes and estimated workload."""
    total = len(df)
    missing = df["abstract"].apply(is_missing).sum()
    oa_cache = _cache_size("openalex_abstracts")
    s2_cache = _cache_size("s2_abstracts")
    print("── Resume preview ─────────────────────────────────────────")
    print(f"  Total works:            {total}")
    print(f"  Missing abstracts:      {missing} ({missing / total * 100:.1f}%)")
    print(f"  OpenAlex cache entries: {oa_cache}")
    print(f"  Semantic Scholar cache: {s2_cache}")
    print("────────────────────────────────────────────────────────────\n")


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
    for idx in missing:
        doi = normalize_doi(df.at[idx, "doi"])
        if doi and doi in doi_abs:
            ab = clean_abstract(doi_abs[doi])
            if ab:
                df.at[idx, "abstract"] = ab
                df.at[idx, "_missing"] = False
                filled += 1
    counters["step1_filled"] = filled
    return filled


# --- Step 2: OpenAlex re-query ---

def step2_openalex(df, counters, checkpoint_every=50):
    """Re-query OpenAlex for works that may now have abstracts."""
    cache = load_cache("openalex_abstracts")
    missing = df.index[df["_missing"] & df["source"].str.contains("openalex", na=False)]
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
    print(f"  OpenAlex: {len(to_query)} uncached IDs to query ({cache_hits} cache hits)")

    # Batch query (50 per request)
    batch_size = 50
    batches_done = 0
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
        try:
            resp = polite_get("https://api.openalex.org/works",
                              params=params, delay=0.15)
            results = {
                r["id"].replace("https://openalex.org/", ""):
                    reconstruct_abstract(r.get("abstract_inverted_index"))
                for r in resp.json().get("results", [])
            }
            for sid in ids:
                cache[sid] = results.get(sid, "")
        except Exception as e:
            print(f"  Warning: batch {i} failed: {e}")
            counters["step2_errors"] = counters.get("step2_errors", 0) + 1
            for sid in ids:
                cache.setdefault(sid, "")

        batches_done += 1
        if batches_done % checkpoint_every == 0:
            save_cache("openalex_abstracts", cache)

        if (i // batch_size) % 20 == 0 and i > 0:
            print(f"  OpenAlex: {i + len(batch)}/{len(to_query)}")

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
        df["_missing"] & df["source"].str.contains("istex", na=False)
    ]
    counters["step3_attempted"] = len(missing)
    if len(missing) == 0:
        return 0

    raw_ids = set(os.listdir(RAW_DIR)) if os.path.isdir(RAW_DIR) else set()

    filled = 0
    for idx in missing:
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

    counters["step3_filled"] = filled
    return filled


def extract_abstract_tei(path):
    """Extract abstract text from a TEI XML file."""
    try:
        tree = ET.parse(path)
        root = tree.getroot()
        ns = {"tei": "http://www.tei-c.org/ns/1.0"}
        for ab_elem in root.iter("{http://www.tei-c.org/ns/1.0}abstract"):
            text = "".join(ab_elem.itertext())
            return clean_abstract(text)
        # Try without namespace
        for ab_elem in root.iter("abstract"):
            text = "".join(ab_elem.itertext())
            return clean_abstract(text)
    except Exception:
        pass
    return ""


def extract_first_paragraph(path):
    """Extract first substantial paragraph from cleaned text."""
    try:
        with open(path, encoding="utf-8", errors="ignore") as f:
            text = f.read(5000)
        paragraphs = [p.strip() for p in text.split("\n\n") if len(p.strip()) > 50]
        if paragraphs:
            return clean_abstract(paragraphs[0])
    except Exception:
        pass
    return ""


# --- Step 4: Semantic Scholar ---

def step4_semantic_scholar(df, counters, checkpoint_every=50):
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
    print(f"  Semantic Scholar: {len(to_query)} uncached DOIs to query ({cache_hits} cache hits)")

    s2_counters = {}
    for i, (idx, doi) in enumerate(to_query):
        try:
            # S2 public API requires ≥3s between requests to avoid 429s
            resp = retry_get(
                f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}",
                params={"fields": "abstract"},
                timeout=15,
                delay=3.0,
                max_retries=3,
                counters=s2_counters,
            )
            if resp.status_code == 200:
                ab = resp.json().get("abstract", "") or ""
                cache[doi] = clean_abstract(ab)
                if cache[doi]:
                    counters["step4_success"] = counters.get("step4_success", 0) + 1
                else:
                    counters["step4_empty_result"] = counters.get("step4_empty_result", 0) + 1
            elif resp.status_code in (404, 400):
                counters["step4_4xx"] = counters.get("step4_4xx", 0) + 1
                cache[doi] = ""
            else:
                cache[doi] = ""
        except requests.exceptions.HTTPError as e:
            status = e.response.status_code if e.response is not None else 0
            if status in (404, 400):
                counters["step4_4xx"] = counters.get("step4_4xx", 0) + 1
            else:
                counters["step4_5xx"] = counters.get("step4_5xx", 0) + 1
            if i < 3:
                print(f"  Warning: S2 {doi}: {e}")
            cache[doi] = ""
        except Exception as e:
            if i < 3:
                print(f"  Warning: S2 {doi}: {e}")
            cache[doi] = ""

        if (i + 1) % checkpoint_every == 0:
            print(f"  Semantic Scholar: {i + 1}/{len(to_query)}")
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
    parser.add_argument("--dry-run", action="store_true",
                        help="Show counts, don't modify data")
    parser.add_argument("--step", type=int, default=0,
                        help="Run only this step (1-5, 0=all)")
    parser.add_argument("--works-input",
                        default=os.path.join(CATALOGS_DIR, "unified_works.csv"),
                        help="Input/output works CSV (default: unified_works.csv)")
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
    print(f"Loaded {len(df)} works from {path}")
    _log_event("start", works_count=len(df), works_input=path)

    # Compute working columns
    df["_missing"] = df["abstract"].apply(is_missing)
    doi_s = df["doi"].apply(normalize_doi)
    df["_has_doi"] = doi_s.apply(lambda x: bool(x) and x not in ("", "nan", "none"))

    total_missing_before = int(df["_missing"].sum())

    print_resume_preview(df)

    if args.dry_run:
        print("Dry run — not modifying data.")
        return

    steps = STEPS if args.step == 0 else {args.step: STEPS[args.step]}

    counters = {
        "missing_before": total_missing_before,
        "total_works": len(df),
    }
    step_results = {}

    for step_num in sorted(steps):
        name, func = steps[step_num]
        before = int(df["_missing"].sum())
        print(f"Step {step_num}: {name} ({before} still missing)")
        _log_event("step_start", step=step_num, name=name, missing_before=before)

        # Steps 2 and 4 accept checkpoint_every; others accept just counters
        if step_num in (2, 4):
            filled = func(df, counters, args.checkpoint_every)
        else:
            filled = func(df, counters)

        after = int(df["_missing"].sum())
        step_results[f"step{step_num}_name"] = name
        step_results[f"step{step_num}_before"] = before
        step_results[f"step{step_num}_after"] = after
        step_results[f"step{step_num}_filled"] = filled
        print(f"  → filled {filled}, remaining: {after}\n")
        _log_event("step_end", step=step_num, name=name, filled=filled, missing_after=after)

    # Save
    final_missing = int(df["_missing"].sum())
    df.drop(columns=["_missing", "_has_doi"], inplace=True)
    save_csv(df, path)

    elapsed = time.time() - t0

    print(f"Done. Abstracts: {len(df) - final_missing}/{len(df)} "
          f"({(len(df) - final_missing) / len(df) * 100:.1f}%)")
    print(f"Filled {total_missing_before - final_missing} abstracts total.")
    print(f"Elapsed: {elapsed:.0f}s")

    # Structured run report
    counters.update({
        "missing_after": final_missing,
        "total_filled": total_missing_before - final_missing,
        "elapsed_seconds": round(elapsed, 1),
        "steps_run": sorted(steps.keys()),
    })
    counters.update(step_results)
    report_path = save_run_report(counters, run_id, "enrich_abstracts")
    print(f"Run report: {report_path}")
    _log_event("complete", elapsed_seconds=round(elapsed, 1),
               total_filled=counters["total_filled"], report_path=report_path)


if __name__ == "__main__":
    main()
