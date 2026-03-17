#!/usr/bin/env python3
"""Build catalog from ISTEX (French national archive).

Two modes:
  --api     Query the ISTEX search API (default, fully reproducible)
  --local   Parse pre-downloaded JSON files from data/raw/

Produces:
  - data/catalogs/istex_works.csv
  - data/catalogs/istex_refs.csv  (cited references with DOIs)

Usage:
    python scripts/catalog_istex.py [--api | --local]
"""

import argparse
import glob
import json
import os
import re
import sys

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import (CATALOGS_DIR, RAW_DIR, WORKS_COLUMNS, REFS_COLUMNS,
                   get_logger, normalize_doi, polite_get, save_csv,
                   pool_path, append_to_pool, load_pool_records,
                   load_collect_config)

log = get_logger("catalog_istex")

ISTEX_API = "https://api.istex.fr/document/"
_BASE_QUERY = '"climate finance" OR "finance climat" OR "finance climatique"'
ISTEX_OUTPUT = "id,doi,title,author,publicationDate,host,abstract,language,keywords,categories,refBibs"
PAGE_SIZE = 100


def is_email(s):
    return bool(re.search(r"[^@\s]+@[^@\s]+\.[^@\s]+", s))


def build_record(d):
    """Build a works record + refs list from an ISTEX document dict.

    Works with both API responses and local JSON files.
    The field names are the same in both formats.
    """
    source_id = d.get("id", d.get("_id", ""))
    doi_raw = d.get("doi")
    # API returns doi as a list, local as a string
    if isinstance(doi_raw, list):
        doi_raw = doi_raw[0] if doi_raw else ""
    doi = normalize_doi(doi_raw)

    title = d.get("title", "")
    authors = d.get("author", [])
    first_author = authors[0]["name"] if authors else ""
    all_authors = " ; ".join(a.get("name", "") for a in authors)

    # Affiliations (filter out email-only entries)
    affs = []
    for a in authors:
        for aff in a.get("affiliations", []):
            if aff and not is_email(aff):
                affs.append(aff)
    affiliations = " ; ".join(dict.fromkeys(affs))

    year = d.get("publicationDate", "")
    journal = d.get("host", {}).get("title", "")
    abstract = d.get("abstract", "")
    lang = d.get("language", [])
    language = lang[0] if lang else ""

    kw = d.get("keywords", {})
    if isinstance(kw, dict):
        kw = kw.get("teeft", [])
    elif not isinstance(kw, list):
        kw = []
    keywords = " ; ".join(kw[:20])

    cats = d.get("categories", {})
    cat_parts = []
    for system in ("wos", "scopus", "scienceMetrix", "inist"):
        vals = cats.get(system, [])
        if vals:
            cat_parts.append(f"{system}:{';'.join(vals)}")
    categories = " | ".join(cat_parts)

    work = {
        "source": "istex",
        "source_id": source_id,
        "doi": doi,
        "title": title,
        "first_author": first_author,
        "all_authors": all_authors,
        "year": year,
        "journal": journal,
        "abstract": abstract,
        "language": language,
        "keywords": keywords,
        "categories": categories,
        "cited_by_count": "",
        "affiliations": affiliations,
    }

    # Parse refBibs
    refs = []
    for rb in d.get("refBibs", []) or []:
        ref_doi = normalize_doi(rb.get("doi"))
        ref_title = rb.get("title", "")
        host = rb.get("host", {})

        ref_journal = host.get("title", "") if ref_title else ""
        if not ref_title:
            ref_title = host.get("title", "")

        ref_authors = rb.get("author", host.get("author", []))
        ref_first_author = ref_authors[0].get("name", "") if ref_authors else ""
        ref_year = rb.get("publicationDate", host.get("publicationDate", ""))

        refs.append({
            "source_doi": doi,
            "source_id": source_id,
            "ref_doi": ref_doi,
            "ref_title": ref_title,
            "ref_first_author": ref_first_author,
            "ref_year": ref_year,
            "ref_journal": ref_journal,
            "ref_raw": json.dumps(rb, ensure_ascii=False),
        })

    return work, refs


# --- API mode ---

def build_istex_query(year_min=None, year_max=None):
    """Build ISTEX query string with optional year bounds.

    ISTEX uses publicationDate field with bracket syntax: [YYYY TO YYYY].
    """
    q = _BASE_QUERY
    if year_min is not None and year_max is not None:
        q += f" AND publicationDate:[{year_min} TO {year_max}]"
    return q


def fetch_istex_api(year_min=None, year_max=None):
    """Fetch all results from ISTEX search API, store in pool."""
    pf = pool_path("istex", "climate_finance")
    all_records = []
    offset = 0
    query = build_istex_query(year_min, year_max)

    # First request to get total
    params = {
        "q": query,
        "size": PAGE_SIZE,
        "output": ISTEX_OUTPUT,
        "from": offset,
    }
    resp = polite_get(ISTEX_API, params=params, delay=0.5)
    data = resp.json()
    total = data.get("total", 0)
    log.info("ISTEX API: %d results for query (years: %s–%s)",
             total, year_min or "?", year_max or "?")

    while True:
        params = {
            "q": query,
            "size": PAGE_SIZE,
            "output": ISTEX_OUTPUT,
            "from": offset,
        }
        resp = polite_get(ISTEX_API, params=params, delay=0.5)
        data = resp.json()
        hits = data.get("hits", [])

        if not hits:
            break

        append_to_pool(hits, pf)
        all_records.extend(hits)
        offset += len(hits)
        log.info("  Fetched %d/%d", offset, total)

        if offset >= total:
            break

    log.info("  %d records saved to pool", len(all_records))
    return all_records


def extract_from_pool():
    """Build CSV from pool records."""
    log.info("Loading ISTEX pool records...")
    all_raw = load_pool_records("istex")
    log.info("  %d raw records in pool", len(all_raw))

    # Deduplicate by ISTEX ID
    seen = set()
    unique = []
    for r in all_raw:
        rid = r.get("id", r.get("_id", ""))
        if rid not in seen:
            seen.add(rid)
            unique.append(r)
    log.info("  %d unique after dedup", len(unique))
    return unique


# --- Local mode ---

def load_local_json():
    """Load ISTEX documents from local JSON files."""
    pattern = os.path.join(RAW_DIR, "*", "*.json")
    json_files = sorted(glob.glob(pattern))
    json_files = [f for f in json_files if not f.endswith("manifest.json")]
    log.info("Found %d local ISTEX JSON files", len(json_files))

    records = []
    for jf in json_files:
        with open(jf, encoding="utf-8") as f:
            records.append(json.load(f))
    return records


# --- Main ---

def main():
    parser = argparse.ArgumentParser(
        description="ISTEX catalog builder for climate finance")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--api", action="store_true", default=True,
                      help="Query ISTEX search API (default)")
    mode.add_argument("--local", action="store_true",
                      help="Parse local JSON files from data/raw/")
    parser.add_argument("--extract-only", action="store_true",
                        help="Build CSV from existing pool, don't download")
    args = parser.parse_args()

    collect_cfg = load_collect_config()
    year_min = collect_cfg["year_min"]
    year_max = collect_cfg["year_max"]
    log.info("Year bounds from corpus_collect.yaml: %d–%d", year_min, year_max)

    if args.local:
        raw_records = load_local_json()
    elif args.extract_only:
        raw_records = extract_from_pool()
    else:
        raw_records = fetch_istex_api(year_min=year_min, year_max=year_max)

    works = []
    all_refs = []
    for i, d in enumerate(raw_records):
        work, refs = build_record(d)
        works.append(work)
        all_refs.extend(refs)
        if (i + 1) % 100 == 0:
            log.info("  Processed %d/%d...", i + 1, len(raw_records))

    works_df = pd.DataFrame(works, columns=WORKS_COLUMNS)
    refs_df = pd.DataFrame(all_refs, columns=REFS_COLUMNS)

    save_csv(works_df, os.path.join(CATALOGS_DIR, "istex_works.csv"))
    if len(refs_df) > 0:
        save_csv(refs_df, os.path.join(CATALOGS_DIR, "istex_refs.csv"))

    log.info("Summary:")
    log.info("  Works: %d", len(works_df))
    log.info("  References: %d", len(refs_df))
    if len(refs_df) > 0:
        log.info("  Refs with DOI: %d", (refs_df['ref_doi'] != '').sum())
    log.info("  Year range: %s - %s", works_df['year'].min(), works_df['year'].max())


if __name__ == "__main__":
    main()
