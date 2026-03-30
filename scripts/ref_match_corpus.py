#!/usr/bin/env python3
"""Match parsed citation refs to corpus works — discover ref_doi.

For each ref in ref_parsed.csv that lacks a ref_doi, attempt to match it
against refined_works.csv using fuzzy title matching (rapidfuzz token_sort_ratio
≥ 85) with year ±1 blocking.  Matched refs are written to ref_matches.csv
in REFS_COLUMNS schema, ready for merge_citations.py.

Performance features (#567):
- JSONL cache keyed by (normalized_title, year) — re-runs hit cache
- Input dedup: unique (ref_title, ref_year) pairs matched once, fanned out
- Progress logging every 5K unique refs with ETA
- rapidfuzz process.extractOne for optimized matching

Ticket: #539, #567
Depends on: #538 (GROBID-parsed refs)

Usage:
    uv run python scripts/ref_match_corpus.py
"""

import argparse
import json
import os
import time

import pandas as pd
from rapidfuzz import fuzz, process

from pipeline_text import normalize_title
from utils import CATALOGS_DIR, REFS_COLUMNS, get_logger, save_csv

log = get_logger("ref_match_corpus")

CACHE_DIR = os.path.join(CATALOGS_DIR, "enrich_cache")
REF_PARSED_PATH = os.path.join(CACHE_DIR, "ref_parsed.csv")
CORPUS_PATH = os.path.join(CATALOGS_DIR, "refined_works.csv")
OUTPUT_PATH = os.path.join(CACHE_DIR, "ref_matches.csv")
CACHE_PATH = os.path.join(CACHE_DIR, "ref_match_cache.jsonl")

MATCH_THRESHOLD = 85  # rapidfuzz token_sort_ratio minimum
YEAR_TOLERANCE = 1    # ±1 year
PROGRESS_INTERVAL = 5000  # log every N unique refs


def _build_corpus_index(
    corpus_path: str,
) -> tuple[dict[str, list[str]], dict[str, str]]:
    """Build year-blocked lookup for rapidfuzz process.extractOne.

    Returns:
        year_choices: year -> [normalized_titles] for extractOne
        title_to_doi: normalized_title -> doi for result lookup
    """
    corpus = pd.read_csv(corpus_path, dtype=str, keep_default_na=False)
    year_choices: dict[str, list[str]] = {}
    title_to_doi: dict[str, str] = {}

    for _, row in corpus.iterrows():
        doi = row.get("doi", "").strip()
        title = row.get("title", "").strip()
        year = str(row.get("year", ""))[:4]
        if not doi or not title or not year:
            continue
        nt = normalize_title(title)
        if len(nt) > 10:  # skip very short titles (false positive risk)
            year_choices.setdefault(year, []).append(nt)
            title_to_doi[nt] = doi

    return year_choices, title_to_doi


def _load_cache(cache_path: str) -> dict[tuple[str, str], tuple[str, float]]:
    """Load JSONL cache: (normalized_title, year) -> (ref_doi, score)."""
    cache: dict[tuple[str, str], tuple[str, float]] = {}
    if not os.path.exists(cache_path):
        return cache
    with open(cache_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            entry = json.loads(line)
            key = (entry["normalized_title"], entry["year"])
            cache[key] = (entry["ref_doi"], entry["score"])
    log.info("Cache loaded: %d entries from %s", len(cache), cache_path)
    return cache


def _save_cache(
    cache: dict[tuple[str, str], tuple[str, float]],
    cache_path: str,
) -> None:
    """Write cache as JSONL, atomic via temp file."""
    cache_dir = os.path.dirname(cache_path)
    if cache_dir and not os.path.isdir(cache_dir):
        log.warning("Cache dir %s missing, skip save", cache_dir)
        return
    tmp_path = cache_path + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        for (nt, year), (ref_doi, score) in cache.items():
            json.dump({
                "normalized_title": nt,
                "year": year,
                "ref_doi": ref_doi,
                "score": score,
            }, f)
            f.write("\n")
    os.replace(tmp_path, cache_path)


def _match_one(
    nt: str,
    year: str,
    year_choices: dict[str, list[str]],
    title_to_doi: dict[str, str],
) -> tuple[str, float]:
    """Match a single normalized title against corpus index.

    Returns (ref_doi, score) or ("", 0.0) if no match.
    """
    try:
        base_year = int(year)
    except ValueError:
        return ("", 0.0)

    best_score = 0.0
    best_doi = ""

    for y_offset in range(-YEAR_TOLERANCE, YEAR_TOLERANCE + 1):
        check_year = str(base_year + y_offset)
        choices = year_choices.get(check_year, [])
        if not choices:
            continue

        result = process.extractOne(
            nt,
            choices,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=MATCH_THRESHOLD,
        )
        if result is not None:
            matched_title, score, _ = result
            if score > best_score:
                best_score = score
                best_doi = title_to_doi[matched_title]
            if best_score == 100.0:
                break

    return (best_doi, best_score)


def match_refs_to_corpus(
    ref_parsed_path: str = REF_PARSED_PATH,
    corpus_path: str = CORPUS_PATH,
    output_path: str = OUTPUT_PATH,
    cache_path: str = CACHE_PATH,
) -> int:
    """Match parsed refs against corpus works by fuzzy title + year.

    Returns:
        Number of matched rows written.
    """
    year_choices, title_to_doi = _build_corpus_index(corpus_path)
    total_entries = sum(len(v) for v in year_choices.values())
    log.info("Corpus index: %d years, %d entries",
             len(year_choices), total_entries)

    refs = pd.read_csv(ref_parsed_path, dtype=str, keep_default_na=False)
    log.info("Ref parsed: %d rows", len(refs))

    # Only process refs without a DOI
    matchable = refs[refs["ref_doi"].str.strip() == ""].copy()
    matchable = matchable[matchable["ref_title"].str.strip() != ""]
    log.info("Matchable (no DOI, has title): %d rows", len(matchable))

    # Normalize titles for dedup
    matchable["_nt"] = matchable["ref_title"].apply(normalize_title)
    matchable["_year"] = matchable["ref_year"].str.strip().str[:4]

    # Filter out short/empty normalized titles and missing years
    matchable = matchable[
        (matchable["_nt"].str.len() > 10) & (matchable["_year"] != "")
    ].copy()

    # Dedup: unique (normalized_title, year) pairs
    unique_pairs = matchable[["_nt", "_year"]].drop_duplicates()
    log.info("Unique (title, year) pairs to match: %d (dedup from %d)",
             len(unique_pairs), len(matchable))

    # Load cache
    cache = _load_cache(cache_path)
    cache_hits = 0
    new_matches = 0
    start_time = time.monotonic()

    # Match unique pairs, using cache where available
    results: dict[tuple[str, str], tuple[str, float]] = {}
    for i, (_, row) in enumerate(unique_pairs.iterrows()):
        nt = row["_nt"]
        year = row["_year"]
        key = (nt, year)

        if key in cache:
            results[key] = cache[key]
            cache_hits += 1
        else:
            ref_doi, score = _match_one(nt, year, year_choices, title_to_doi)
            results[key] = (ref_doi, score)
            cache[key] = (ref_doi, score)
            new_matches += 1

        # Progress logging
        processed = i + 1
        if processed % PROGRESS_INTERVAL == 0 or processed == len(unique_pairs):
            elapsed = time.monotonic() - start_time
            rate = processed / elapsed if elapsed > 0 else 0
            remaining = len(unique_pairs) - processed
            eta = remaining / rate if rate > 0 else 0
            log.info(
                "Progress: %d/%d unique refs (%.0f/s, ETA %.0fs) "
                "[cache hits: %d, new: %d]",
                processed, len(unique_pairs), rate, eta,
                cache_hits, new_matches,
            )

    # Save updated cache
    _save_cache(cache, cache_path)
    log.info("Cache saved: %d entries (%d hits, %d new)",
             len(cache), cache_hits, new_matches)

    # Fan out: map each matchable row to its match result
    matches = []
    for _, row in matchable.iterrows():
        key = (row["_nt"], row["_year"])
        ref_doi, score = results.get(key, ("", 0.0))
        if score >= MATCH_THRESHOLD and ref_doi:
            matches.append({
                "source_doi": row["source_doi"],
                "source_id": row["source_id"],
                "ref_doi": ref_doi,
                "ref_title": row["ref_title"],
                "ref_first_author": row["ref_first_author"],
                "ref_year": row["ref_year"],
                "ref_journal": row["ref_journal"],
                "ref_raw": row["ref_raw"],
            })

    result = pd.DataFrame(matches, columns=REFS_COLUMNS)
    save_csv(result, output_path)
    log.info("Matched %d refs → %s", len(result), output_path)
    return len(result)


def main():
    parser = argparse.ArgumentParser(
        description="Match parsed citation refs to corpus works")
    parser.add_argument("--ref-parsed", default=REF_PARSED_PATH,
                        help="Path to ref_parsed.csv")
    parser.add_argument("--corpus", default=CORPUS_PATH,
                        help="Path to refined_works.csv")
    parser.add_argument("--output", default=OUTPUT_PATH,
                        help="Output path for ref_matches.csv")
    parser.add_argument("--cache", default=CACHE_PATH,
                        help="Path to JSONL match cache")
    args = parser.parse_args()

    match_refs_to_corpus(
        ref_parsed_path=args.ref_parsed,
        corpus_path=args.corpus,
        output_path=args.output,
        cache_path=args.cache,
    )


if __name__ == "__main__":
    main()
