#!/usr/bin/env python3
"""Parse unstructured Crossref citation strings via GROBID.

Reads crossref_refs.csv, extracts unstructured text from ref_raw for rows
with empty ref_title, sends to GROBID processCitation API, caches results
as JSONL, and writes ref_parsed.csv with REFS_COLUMNS schema.

corpus_merge_citations.py reads this as a third input alongside crossref_refs.csv
and openalex_refs.csv.

Requires: GROBID running at --grobid-url (default http://localhost:8070).

Usage:
    uv run python scripts/corpus_parse_citations_grobid.py [--limit N] [--dry-run]
"""

import argparse
import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

import pandas as pd
from utils import (
    CATALOGS_DIR,
    REFS_COLUMNS,
    get_logger,
    make_run_id,
    normalize_doi,
    save_run_report,
)

log = get_logger("corpus_parse_citations_grobid")

CACHE_DIR = os.path.join(CATALOGS_DIR, "enrich_cache")
CROSSREF_CACHE = os.path.join(CACHE_DIR, "crossref_refs.csv")
PARSE_CACHE = os.path.join(CACHE_DIR, "grobid_parsed.jsonl")
OUTPUT_PATH = os.path.join(CACHE_DIR, "ref_parsed.csv")

DEFAULT_GROBID_URL = "http://localhost:8070"


# ---------------------------------------------------------------------------
# TEI XML parsing
# ---------------------------------------------------------------------------

def parse_tei_citation(tei_xml: str) -> dict:
    """Extract title, first_author, year, journal from GROBID TEI XML.

    Returns dict with keys: title, first_author, year, journal.
    All values are strings; empty string if not found.
    """
    if not tei_xml or not tei_xml.strip():
        return {"title": "", "first_author": "", "year": "", "journal": ""}

    try:
        root = ET.fromstring(tei_xml)
    except ET.ParseError:
        return {"title": "", "first_author": "", "year": "", "journal": ""}

    # Title: try analytic (article) first, then monograph (book)
    title = ""
    for tag in ["analytic", "monogr"]:
        elem = root.find(f".//{tag}//title")
        if elem is not None and elem.text:
            title = elem.text.strip()
            break

    # First author surname
    first_author = ""
    surname = root.find(".//{*}surname")
    if surname is not None and surname.text:
        first_author = surname.text.strip()

    # Year
    year = ""
    date = root.find(".//{*}date")
    if date is not None:
        when = date.get("when", "")
        if when:
            year = when[:4]

    # Journal
    journal = ""
    j_elem = root.find('.//monogr/title[@level="j"]')
    if j_elem is not None and j_elem.text:
        journal = j_elem.text.strip()

    return {
        "title": title,
        "first_author": first_author,
        "year": year,
        "journal": journal,
    }


# ---------------------------------------------------------------------------
# Cache
# ---------------------------------------------------------------------------

def build_cache_key(text: str) -> str:
    """Deterministic cache key from unstructured text."""
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


def load_parse_cache(path: str) -> dict:
    """Load JSONL cache: {cache_key: {title, first_author, year, journal}}."""
    cache = {}
    if not os.path.exists(path):
        return cache
    with open(path, encoding="utf-8") as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                key = entry.pop("_key")
                cache[key] = entry
            except (json.JSONDecodeError, KeyError):
                log.warning("Skipping corrupted cache line %d in %s", lineno, path)
    return cache


def save_parse_cache(cache: dict, path: str) -> None:
    """Save cache as JSONL."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for key, entry in cache.items():
            row = {"_key": key, **entry}
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# GROBID API
# ---------------------------------------------------------------------------

def call_grobid(text: str, grobid_url: str) -> str:
    """Send a citation string to GROBID processCitation, return TEI XML."""
    url = f"{grobid_url}/api/processCitation"
    data = urllib.parse.urlencode({
        "citations": text,
        "consolidateCitations": "0",
    }).encode()
    req = urllib.request.Request(url, data=data)
    try:
        resp = urllib.request.urlopen(req, timeout=10)
        return resp.read().decode("utf-8")
    except Exception as e:
        log.debug("GROBID error for %s: %s", text[:50], e)
        return ""


# ---------------------------------------------------------------------------
# Output assembly
# ---------------------------------------------------------------------------

def _build_output_rows(unstructured, cache, cr):
    """Assemble output rows from parsed cache entries."""
    rows = []
    for key, (_text, indices) in unstructured.items():
        parsed = cache.get(key)
        if not parsed or not parsed.get("title"):
            continue
        for idx in indices:
            rows.append({
                "source_doi": cr.at[idx, "source_doi"],
                "source_id": "",
                "ref_doi": cr.at[idx, "ref_doi"],
                "ref_title": parsed["title"],
                "ref_first_author": parsed["first_author"],
                "ref_year": parsed["year"],
                "ref_journal": parsed.get("journal", ""),
                "ref_raw": cr.at[idx, "ref_raw"],
            })
    return rows


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--limit", type=int, default=0,
                        help="Max unique strings to process (0=all)")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--grobid-url", default=DEFAULT_GROBID_URL)
    parser.add_argument("--checkpoint-every", type=int, default=5000)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()

    run_id = args.run_id or make_run_id()
    t0 = time.time()

    # Verify GROBID is running
    try:
        version_url = f"{args.grobid_url}/api/version"
        resp = urllib.request.urlopen(version_url, timeout=5)
        version = resp.read().decode()
        log.info("GROBID version: %s", version)
    except Exception as e:
        log.error("GROBID not reachable at %s: %s", args.grobid_url, e)
        return

    # Load crossref cache
    log.info("Reading %s", CROSSREF_CACHE)
    cr = pd.read_csv(CROSSREF_CACHE, dtype=str, keep_default_na=False,
                     on_bad_lines="warn")
    log.info("Total rows: %d", len(cr))

    # Find rows needing parsing: empty title, non-empty ref_raw
    needs_parse = (cr["ref_title"] == "") & (cr["ref_raw"] != "")
    candidates = cr.loc[needs_parse]
    log.info("Rows needing parse: %d", len(candidates))

    # Extract unique unstructured texts
    unstructured = {}  # cache_key → (unstructured_text, [indices])
    for idx, raw in candidates["ref_raw"].items():
        try:
            ref = json.loads(raw)
            text = ref.get("unstructured", "").strip()
            if not text:
                continue
        except (json.JSONDecodeError, TypeError):
            continue
        key = build_cache_key(text)
        if key not in unstructured:
            unstructured[key] = (text, [])
        unstructured[key][1].append(idx)

    log.info("Unique unstructured strings: %d", len(unstructured))

    # Load existing parse cache
    cache = load_parse_cache(PARSE_CACHE)
    cached = sum(1 for k in unstructured if k in cache)
    log.info("Already cached: %d, to parse: %d", cached, len(unstructured) - cached)

    if args.dry_run:
        log.info("Dry run — not calling GROBID.")
        return

    # Parse uncached strings via GROBID
    to_parse = [(k, v[0]) for k, v in unstructured.items() if k not in cache]
    if args.limit:
        to_parse = to_parse[:args.limit]

    parsed_count = 0
    for i, (key, text) in enumerate(to_parse):
        tei = call_grobid(text, args.grobid_url)
        result = parse_tei_citation(tei)
        cache[key] = result
        parsed_count += 1

        if (i + 1) % args.checkpoint_every == 0:
            save_parse_cache(cache, PARSE_CACHE)
            log.info("Checkpoint: %d/%d parsed, cache saved", i + 1, len(to_parse))

    # Final cache save
    save_parse_cache(cache, PARSE_CACHE)
    log.info("Parsed %d new strings, cache total: %d", parsed_count, len(cache))

    # Build ref_parsed.csv: one row per (source_doi, parsed ref)
    rows = _build_output_rows(unstructured, cache, cr)

    if rows:
        result = pd.DataFrame(rows, columns=REFS_COLUMNS)
        from pipeline_io import save_csv
        save_csv(result, OUTPUT_PATH)
        log.info("Wrote %d rows to %s", len(result), OUTPUT_PATH)
    else:
        log.info("No parsed results to write.")

    # Compute fill stats from output rows
    filled_title = sum(1 for r in rows if r["ref_title"])
    filled_author = sum(1 for r in rows if r["ref_first_author"])
    filled_year = sum(1 for r in rows if r["ref_year"])

    elapsed = time.time() - t0
    log.info("Done in %.0fs: %d titles, %d authors, %d years filled",
             elapsed, filled_title, filled_author, filled_year)

    counters = {
        "total_rows": len(cr),
        "needs_parse": int(needs_parse.sum()),
        "unique_strings": len(unstructured),
        "cached_before": cached,
        "parsed_new": parsed_count,
        "output_rows": len(rows),
        "filled_title": filled_title,
        "filled_author": filled_author,
        "filled_year": filled_year,
        "elapsed_seconds": round(elapsed, 1),
    }
    report_path = save_run_report(counters, run_id, "parse_citations_grobid")
    log.info("Run report: %s", report_path)


if __name__ == "__main__":
    main()
