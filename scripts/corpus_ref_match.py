#!/usr/bin/env python3
"""Match parsed citation refs to corpus works — discover ref_doi.

For each ref in ref_parsed.csv that lacks a ref_doi, attempt to match it
against refined_works.csv using fuzzy title matching (rapidfuzz token_sort_ratio
≥ 85) with year ±1 blocking.  Matched refs are written to ref_matches.csv
in REFS_COLUMNS schema, ready for merge_citations.py.

Ticket: #539
Depends on: #538 (GROBID-parsed refs)

Usage:
    uv run python scripts/ref_match_corpus.py
"""

import argparse
import os
from collections import defaultdict

import pandas as pd
from rapidfuzz import fuzz

from pipeline_text import normalize_title
from utils import CATALOGS_DIR, REFS_COLUMNS, get_logger, save_csv

log = get_logger("ref_match_corpus")

CACHE_DIR = os.path.join(CATALOGS_DIR, "enrich_cache")
REF_PARSED_PATH = os.path.join(CACHE_DIR, "ref_parsed.csv")
CORPUS_PATH = os.path.join(CATALOGS_DIR, "refined_works.csv")
OUTPUT_PATH = os.path.join(CACHE_DIR, "ref_matches.csv")

MATCH_THRESHOLD = 85  # rapidfuzz token_sort_ratio minimum
YEAR_TOLERANCE = 1    # ±1 year


def _build_corpus_index(corpus_path: str) -> dict[str, list[tuple[str, str]]]:
    """Build year-blocked lookup: year -> [(normalized_title, doi)]."""
    corpus = pd.read_csv(corpus_path, dtype=str, keep_default_na=False)
    index: dict[str, list[tuple[str, str]]] = defaultdict(list)

    for _, row in corpus.iterrows():
        doi = row.get("doi", "").strip()
        title = row.get("title", "").strip()
        year = str(row.get("year", ""))[:4]
        if not doi or not title or not year:
            continue
        nt = normalize_title(title)
        if len(nt) > 10:  # skip very short titles (false positive risk)
            index[year].append((nt, doi))

    return dict(index)


def match_refs_to_corpus(
    ref_parsed_path: str = REF_PARSED_PATH,
    corpus_path: str = CORPUS_PATH,
    output_path: str = OUTPUT_PATH,
) -> int:
    """Match parsed refs against corpus works by fuzzy title + year.

    Returns:
        Number of matched rows written.
    """
    index = _build_corpus_index(corpus_path)
    log.info("Corpus index: %d years, %d entries",
             len(index), sum(len(v) for v in index.values()))

    refs = pd.read_csv(ref_parsed_path, dtype=str, keep_default_na=False)
    log.info("Ref parsed: %d rows", len(refs))

    # Only process refs without a DOI
    matchable = refs[refs["ref_doi"].str.strip() == ""].copy()
    matchable = matchable[matchable["ref_title"].str.strip() != ""]
    log.info("Matchable (no DOI, has title): %d rows", len(matchable))

    matches = []
    for _, row in matchable.iterrows():
        nt = normalize_title(row["ref_title"])
        year = row["ref_year"].strip()[:4] if row["ref_year"].strip() else ""
        if not nt or not year or len(nt) <= 10:
            continue

        best_score = 0.0
        best_doi = ""

        # Check year ± tolerance
        try:
            base_year = int(year)
        except ValueError:
            continue

        for y_offset in range(-(YEAR_TOLERANCE), YEAR_TOLERANCE + 1):
            check_year = str(base_year + y_offset)
            for corp_title, corp_doi in index.get(check_year, []):
                score = fuzz.token_sort_ratio(nt, corp_title)
                if score > best_score:
                    best_score = score
                    best_doi = corp_doi
                if score == 100.0:
                    break
            if best_score == 100.0:
                break

        if best_score >= MATCH_THRESHOLD:
            matches.append({
                "source_doi": row["source_doi"],
                "source_id": row["source_id"],
                "ref_doi": best_doi,
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
    args = parser.parse_args()

    match_refs_to_corpus(
        ref_parsed_path=args.ref_parsed,
        corpus_path=args.corpus,
        output_path=args.output,
    )


if __name__ == "__main__":
    main()
