#!/usr/bin/env python3
"""Mine keywords and concepts from core climate finance papers via OpenAlex.

Reads refined_works.csv, selects core papers (cited_by_count >= 50),
queries OpenAlex for their keywords and concepts, and ranks by frequency.

Output: prints ranked keyword/concept tables to stdout.

Usage:
    python scripts/mine_openalex_keywords.py [--min-citations 50]
"""

import argparse
import os
from collections import Counter

import pandas as pd
from utils import CATALOGS_DIR, MAILTO, OPENALEX_API_KEY, get_logger, polite_get

log = get_logger("mine_openalex_keywords")

OA_API = "https://api.openalex.org/works"


def fetch_openalex_metadata(dois, batch_size=50):
    """Fetch keywords and concepts for a list of DOIs from OpenAlex.

    Uses the filter endpoint with batched DOI pipes (max 50 per request).
    """
    results = []
    doi_list = [d for d in dois if d]
    total = len(doi_list)

    for i in range(0, total, batch_size):
        batch = doi_list[i:i + batch_size]
        doi_filter = "|".join(f"https://doi.org/{d}" for d in batch)
        params = {
            "filter": f"doi:{doi_filter}",
            "select": "id,doi,keywords,concepts,topics",
            "per_page": 200,
            "mailto": MAILTO,
        }
        if OPENALEX_API_KEY:
            params["api_key"] = OPENALEX_API_KEY
        resp = polite_get(OA_API, params=params, delay=0.15)
        data = resp.json()
        results.extend(data.get("results", []))
        log.info("  Fetched %d/%d DOIs (%d found)",
                 min(i + batch_size, total), total, len(results))

    return results


def extract_keywords(results):
    """Extract and count keywords from OpenAlex results."""
    keyword_counter = Counter()
    for r in results:
        # New-style keywords (post-2024 OpenAlex)
        for kw in r.get("keywords", []):
            if isinstance(kw, dict):
                term = kw.get("keyword", kw.get("display_name", ""))
            else:
                term = str(kw)
            if term:
                keyword_counter[term.lower()] += 1
    return keyword_counter


def extract_concepts(results):
    """Extract and count L0/L1/L2 concepts from OpenAlex results."""
    concept_counter = Counter()
    for r in results:
        for c in r.get("concepts", []):
            level = c.get("level", 99)
            name = c.get("display_name", "")
            if name and level <= 2:
                concept_counter[f"L{level}: {name}"] += 1
    return concept_counter


def extract_topics(results):
    """Extract and count topics from OpenAlex results."""
    topic_counter = Counter()
    for r in results:
        for t in r.get("topics", []):
            name = t.get("display_name", "")
            if name:
                topic_counter[name] += 1
    return topic_counter


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-citations", type=int, default=50,
                        help="Minimum cited_by_count for core papers (default: 50)")
    args = parser.parse_args()

    # Load corpus
    refined_path = os.path.join(CATALOGS_DIR, "refined_works.csv")
    df = pd.read_csv(refined_path)
    log.info("Loaded %d refined works", len(df))

    # Filter core papers
    core = df[df["cited_by_count"] >= args.min_citations].copy()
    log.info("Core papers (cited_by_count >= %d): %d", args.min_citations, len(core))

    # Get DOIs
    core_dois = core["doi"].dropna().unique().tolist()
    core_dois = [d for d in core_dois if d.strip()]
    log.info("Core papers with DOIs: %d", len(core_dois))

    # Fetch from OpenAlex
    log.info("Fetching metadata from OpenAlex...")
    results = fetch_openalex_metadata(core_dois)
    log.info("Got metadata for %d papers", len(results))

    # Extract and rank
    keywords = extract_keywords(results)
    concepts = extract_concepts(results)
    topics = extract_topics(results)

    log.info("=" * 70)
    log.info("TOP 60 KEYWORDS (from OpenAlex keyword field)")
    log.info("=" * 70)
    for term, count in keywords.most_common(60):
        pct = 100 * count / len(results) if results else 0
        log.info("  %4d (%5.1f%%)  %s", count, pct, term)

    log.info("=" * 70)
    log.info("TOP 40 CONCEPTS (L0-L2)")
    log.info("=" * 70)
    for term, count in concepts.most_common(40):
        pct = 100 * count / len(results) if results else 0
        log.info("  %4d (%5.1f%%)  %s", count, pct, term)

    log.info("=" * 70)
    log.info("TOP 40 TOPICS")
    log.info("=" * 70)
    for term, count in topics.most_common(40):
        pct = 100 * count / len(results) if results else 0
        log.info("  %4d (%5.1f%%)  %s", count, pct, term)

    # Summary for query design
    log.info("=" * 70)
    log.info("POTENTIAL QUERY TERMS NOT IN CURRENT TIERS")
    log.info("=" * 70)
    current_terms = {
        "climate finance", "carbon finance", "green climate fund",
        "adaptation fund", "clean development mechanism",
        "global environment facility", "carbon market", "green bonds",
        "climate bonds", "redd", "stranded assets", "climate risk",
        "just transition", "loss and damage", "paris agreement",
        "kyoto", "mitigation finance", "adaptation financing",
    }
    for term, count in keywords.most_common(100):
        t_lower = term.lower()
        if count >= 5 and not any(ct in t_lower for ct in current_terms):
            log.info("  %4d  %s", count, term)


if __name__ == "__main__":
    main()
