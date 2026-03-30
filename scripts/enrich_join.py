"""Assemble enriched_works.csv from unified_works.csv + enrichment caches.

Each enrichment script (enrich_dois, enrich_abstracts, enrich_language,
summarize_abstracts) writes to its own cache in enrich_cache/. This script
joins all caches onto the base table to produce the enriched monolith.

This decouples enrichment stages in DVC: each can run independently,
and only this join stage produces the shared output. See #428.

Usage:
    uv run python scripts/enrich_join.py [--unified PATH] [--output PATH]
"""

import argparse
import json
import math
import os

import pandas as pd
from pipeline_text import normalize_doi, normalize_lang
from utils import CATALOGS_DIR, get_logger, save_csv

log = get_logger("enrich_join")

CACHE_DIR_DEFAULT = os.path.join(CATALOGS_DIR, "enrich_cache")
TOKEN_LIMIT = 1000


def _is_missing(val):
    """True if a string value is empty/missing/NaN."""
    if pd.isna(val):
        return True
    s = str(val).strip()
    return s == "" or s.lower() in ("nan", "none")


def _count_tokens(text: str) -> int:
    """Count whitespace-separated tokens."""
    if not text or (isinstance(text, float) and math.isnan(text)):
        return 0
    return len(str(text).split())


def _load_csv_cache(path, key_col, val_col):
    """Load a two-column CSV cache as {key: value} dict."""
    if not os.path.exists(path):
        log.info("Cache not found (ok on first run): %s", path)
        return {}
    try:
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
    except pd.errors.EmptyDataError:
        return {}
    return dict(zip(df[key_col].astype(str), df[val_col]))


def _load_summary_cache(path):
    """Load JSONL summary cache as {doi: entry_dict}."""
    if not os.path.exists(path):
        return {}
    result = {}
    with open(path) as f:
        for lineno, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                log.warning("Skipping malformed JSON at %s:%d", path, lineno)
                continue
            doi = entry.get("doi", "")
            if doi:
                result[doi] = entry
    return result


def _is_valid_doi(doi):
    """Return True if doi is a usable string (not empty/nan/none)."""
    return bool(doi) and doi not in ("nan", "none")


def _apply_doi_cache(df, cache_dir):
    """Fill missing DOIs from the doi_resolved cache."""
    doi_cache = _load_csv_cache(
        os.path.join(cache_dir, "doi_resolved.csv"),
        "source_id", "doi",
    )
    applied = 0
    for idx in df.index:
        if _is_missing(df.at[idx, "doi"]):
            resolved = doi_cache.get(str(df.at[idx, "source_id"]), "")
            if resolved:
                df.at[idx, "doi"] = resolved
                applied += 1
    log.info("DOI cache: applied %d (cache has %d entries)", applied, len(doi_cache))
    return applied


def _crossfill_abstracts(df):
    """Fill missing abstracts from other records sharing the same DOI.

    Keeps the longest abstract per DOI, matching enrich_abstracts.py step1.
    """
    doi_abstract = {}
    for idx in df.index:
        doi = normalize_doi(df.at[idx, "doi"])
        if not _is_valid_doi(doi):
            continue
        abstract = df.at[idx, "abstract"]
        if not _is_missing(abstract):
            a = str(abstract)
            if doi not in doi_abstract or len(a) > len(doi_abstract[doi]):
                doi_abstract[doi] = a

    filled = 0
    for idx in df.index:
        if _is_missing(df.at[idx, "abstract"]):
            doi = normalize_doi(df.at[idx, "doi"])
            if _is_valid_doi(doi) and doi in doi_abstract:
                df.at[idx, "abstract"] = doi_abstract[doi]
                filled += 1
    log.info("Cross-source backfill: %d abstracts", filled)
    return filled


def _apply_abstract_caches(df, cache_dir):
    """Fill missing abstracts from OpenAlex and Semantic Scholar caches."""
    oa_cache = _load_csv_cache(
        os.path.join(cache_dir, "openalex_abstracts.csv"), "key", "abstract")
    s2_cache = _load_csv_cache(
        os.path.join(cache_dir, "s2_abstracts.csv"), "key", "abstract")

    applied = 0
    for idx in df.index:
        if _is_missing(df.at[idx, "abstract"]):
            sid = str(df.at[idx, "source_id"])
            doi = normalize_doi(df.at[idx, "doi"])
            val = oa_cache.get(sid, "")
            if not val and doi:
                val = s2_cache.get(doi, "")
            if val:
                df.at[idx, "abstract"] = val
                applied += 1
    log.info("Abstract caches: applied %d (OA=%d, S2=%d entries)",
             applied, len(oa_cache), len(s2_cache))
    return applied


def _apply_language_cache(df, cache_dir):
    """Normalize language codes and fill missing from cache."""
    df["language"] = df["language"].apply(normalize_lang)
    lang_cache = _load_csv_cache(
        os.path.join(cache_dir, "language_resolved.csv"), "key", "language")

    applied = 0
    for idx in df.index:
        if _is_missing(df.at[idx, "language"]):
            doi = normalize_doi(df.at[idx, "doi"])
            sid = str(df.at[idx, "source_id"])
            lang = lang_cache.get(doi, "") if doi else ""
            if not lang:
                lang = lang_cache.get(sid, "")
            if lang:
                df.at[idx, "language"] = lang
                applied += 1
    log.info("Language cache: applied %d (cache has %d entries)",
             applied, len(lang_cache))
    return applied


def _apply_summaries(df, cache_dir):
    """Apply cached LLM summaries for oversized abstracts and set abstract_status."""
    summary_cache = _load_summary_cache(
        os.path.join(cache_dir, "abstract_summaries_cache.jsonl"))

    statuses = []
    for idx in df.index:
        abstract = df.at[idx, "abstract"]
        if _is_missing(abstract):
            statuses.append("missing")
        elif _count_tokens(abstract) > TOKEN_LIMIT:
            doi = normalize_doi(df.at[idx, "doi"])
            entry = summary_cache.get(doi, {}) if doi else {}
            summary = entry.get("summary", "")
            if summary and not entry.get("error"):
                df.at[idx, "abstract"] = summary
                statuses.append("generated")
            else:
                statuses.append("too_long")
        else:
            statuses.append("original")

    df["abstract_status"] = statuses
    status_counts = df["abstract_status"].value_counts().to_dict()
    log.info("Abstract status: %s", status_counts)


def join_enrichments(unified_path, output_path, cache_dir=None):
    """Read unified_works.csv + all caches → write enriched_works.csv."""
    if cache_dir is None:
        cache_dir = CACHE_DIR_DEFAULT

    df = pd.read_csv(unified_path)
    log.info("Loaded %d works from %s", len(df), unified_path)

    _apply_doi_cache(df, cache_dir)
    _crossfill_abstracts(df)
    _apply_abstract_caches(df, cache_dir)
    _apply_language_cache(df, cache_dir)
    _apply_summaries(df, cache_dir)

    save_csv(df, output_path)
    log.info("Wrote %d rows to %s", len(df), output_path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--unified",
        default=os.path.join(CATALOGS_DIR, "unified_works.csv"),
        help="Input unified_works.csv (default: %(default)s)",
    )
    parser.add_argument(
        "--output",
        default=os.path.join(CATALOGS_DIR, "enriched_works.csv"),
        help="Output enriched_works.csv (default: %(default)s)",
    )
    parser.add_argument(
        "--cache-dir",
        default=CACHE_DIR_DEFAULT,
        help="Directory containing enrichment caches (default: %(default)s)",
    )
    args = parser.parse_args()
    join_enrichments(args.unified, args.output, args.cache_dir)


if __name__ == "__main__":
    main()
