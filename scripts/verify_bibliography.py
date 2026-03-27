"""Verify bibliography entries against the 22K-row corpus.

Matches the 47 entries in bibliography/main.bib against
refined_works.csv by DOI (exact) then by title+year (fuzzy).

Produces:
- tables/bib_corpus_match.csv: per-entry match results
- Console summary: DOI matches, fuzzy matches, unmatched keys
- Reverse check: highly-cited corpus papers by bib authors not in bib
"""

import argparse
import os
import re

import bibtexparser
import pandas as pd
from rapidfuzz import fuzz
from utils import BASE_DIR, CATALOGS_DIR, get_logger, normalize_doi

log = get_logger("verify_bibliography")

# --- Paths ---
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(TABLES_DIR, exist_ok=True)

BIB_PATH = os.path.join(BASE_DIR, "bibliography", "main.bib")
CORPUS_PATH = os.path.join(CATALOGS_DIR, "refined_works.csv")
OUTPUT_PATH = os.path.join(TABLES_DIR, "bib_corpus_match.csv")

FUZZY_THRESHOLD = 85


def _safe_cited(val):
    """Safely convert cited_by_count to int string, handling NaN."""
    try:
        f = float(val)
        if pd.isna(f):
            return ""
        return str(int(f))
    except (ValueError, TypeError):
        return ""


def normalize_title_for_match(title):
    """Lowercase, strip braces/punctuation, collapse whitespace."""
    if not title:
        return ""
    t = title.lower()
    # Remove LaTeX braces and commands
    t = re.sub(r"[{}\\]", "", t)
    t = re.sub(r"<[^>]+>", "", t)  # strip HTML tags like <scp>
    t = re.sub(r"[^\w\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def extract_last_names(author_field):
    """Extract last names from a BibTeX author field (joined by 'and')."""
    if not author_field:
        return set()
    names = set()
    for part in author_field.split(" and "):
        part = part.strip()
        if not part:
            continue
        # Handle "Last, First" format
        if "," in part:
            last = part.split(",")[0].strip()
        else:
            # "First Last" — take last token (handle multi-word)
            tokens = part.split()
            last = tokens[-1] if tokens else part
        # Remove braces
        last = last.replace("{", "").replace("}", "")
        # Normalize accents to ASCII-ish for matching
        last = last.lower().strip()
        if last:
            names.add(last)
    return names


def parse_bib(path):
    """Parse .bib file and return list of dicts with key, authors, title, year, doi."""
    with open(path, encoding="utf-8") as f:
        bib_db = bibtexparser.load(f)

    entries = []
    for entry in bib_db.entries:
        bib_key = entry.get("ID", "")
        title = entry.get("title", "")
        year = entry.get("year", "")
        doi = normalize_doi(entry.get("doi", ""))
        authors = entry.get("author", "")
        entry_type = entry.get("ENTRYTYPE", "")
        entries.append({
            "bib_key": bib_key,
            "bib_title": title,
            "bib_year": int(year) if year.strip().isdigit() else None,
            "bib_doi": doi,
            "bib_authors": authors,
            "bib_type": entry_type,
            "bib_last_names": extract_last_names(authors),
        })
    return entries


def match_entries(bib_entries, corpus):
    """Match bib entries to corpus rows by DOI then fuzzy title+year."""
    # Build DOI lookup from corpus
    corpus_by_doi = {}
    for idx, row in corpus.iterrows():
        doi = normalize_doi(row.get("doi", ""))
        if doi:
            corpus_by_doi[doi] = row

    # Precompute normalized titles for fuzzy matching
    corpus_titles = []
    for idx, row in corpus.iterrows():
        corpus_titles.append((
            idx,
            normalize_title_for_match(str(row.get("title", ""))),
            row.get("year"),
            row,
        ))

    results = []
    for entry in bib_entries:
        match_type = "none"
        corpus_doi = ""
        corpus_title = ""
        corpus_cited_by = ""
        corpus_year = ""

        # Step 1: DOI match
        if entry["bib_doi"] and entry["bib_doi"] in corpus_by_doi:
            row = corpus_by_doi[entry["bib_doi"]]
            match_type = "doi"
            corpus_doi = normalize_doi(row.get("doi", ""))
            corpus_title = row.get("title", "")
            corpus_cited_by = row.get("cited_by_count", "")
            corpus_year = row.get("year", "")
        else:
            # Step 2: Fuzzy title+year match
            bib_norm = normalize_title_for_match(entry["bib_title"])
            if bib_norm:
                best_score = 0
                best_row = None
                for c_idx, c_title, c_year, c_row in corpus_titles:
                    # Year must match (within 1 year tolerance)
                    if entry["bib_year"] and c_year:
                        try:
                            if abs(int(entry["bib_year"]) - int(float(c_year))) > 1:
                                continue
                        except (ValueError, TypeError):
                            continue
                    score = fuzz.token_sort_ratio(bib_norm, c_title)
                    if score > best_score:
                        best_score = score
                        best_row = c_row
                if best_score >= FUZZY_THRESHOLD and best_row is not None:
                    match_type = "fuzzy"
                    corpus_doi = normalize_doi(best_row.get("doi", ""))
                    corpus_title = best_row.get("title", "")
                    corpus_cited_by = best_row.get("cited_by_count", "")
                    corpus_year = best_row.get("year", "")

        results.append({
            "bib_key": entry["bib_key"],
            "bib_type": entry["bib_type"],
            "bib_title": entry["bib_title"],
            "bib_year": entry["bib_year"],
            "bib_doi": entry["bib_doi"],
            "match_type": match_type,
            "corpus_doi": corpus_doi,
            "corpus_title": corpus_title,
            "corpus_year": corpus_year,
            "corpus_cited_by": corpus_cited_by,
        })

    return results


def reverse_check(bib_entries, corpus, cited_threshold=500):
    """Find highly-cited corpus papers by bib authors NOT in bibliography."""
    # Collect distinctive last names from bibliography.
    # Use only first/second authors (the key names) to reduce false positives.
    # Skip names that are too common as first names or too short.
    SKIP_NAMES = {
        "robert", "brown", "jessica", "martin", "peter", "david",
        "michael", "alan", "christian", "ann", "anna", "jane",
        "aaron", "ian", "ang", "kennedy", "victoria", "guy",
        "mazza", "john", "nick",
    }
    MIN_NAME_LENGTH = 5
    all_bib_names = set()
    for entry in bib_entries:
        # Only take first author (or first two for "X and Y" bib keys)
        authors = entry.get("bib_authors", "")
        parts = [p.strip() for p in authors.split(" and ") if p.strip()]
        # Extract last names from first 2 authors only
        for part in parts[:2]:
            if "," in part:
                last = part.split(",")[0].strip()
            else:
                tokens = part.split()
                last = tokens[-1] if tokens else part
            last = last.replace("{", "").replace("}", "").lower().strip()
            if last and len(last) >= MIN_NAME_LENGTH and last not in SKIP_NAMES:
                all_bib_names.add(last)

    # Collect all DOIs and normalized titles from bib (to exclude matched papers)
    bib_dois = {e["bib_doi"] for e in bib_entries if e["bib_doi"]}
    bib_titles_norm = {normalize_title_for_match(e["bib_title"]) for e in bib_entries}

    # Filter corpus to highly cited
    highly_cited = corpus[corpus["cited_by_count"] >= cited_threshold].copy()

    missing = []
    for _, row in highly_cited.iterrows():
        # Skip if already in bibliography
        rdoi = normalize_doi(row.get("doi", ""))
        if rdoi and rdoi in bib_dois:
            continue
        rtitle_norm = normalize_title_for_match(str(row.get("title", "")))
        if rtitle_norm in bib_titles_norm:
            continue

        # Check if any bib author last name appears as a word boundary in authors
        all_authors = str(row.get("all_authors", "")).lower()
        first_author = str(row.get("first_author", "")).lower()
        author_text = all_authors + " " + first_author

        for name in all_bib_names:
            # Use word boundary to avoid partial matches
            if re.search(r'\b' + re.escape(name) + r'\b', author_text):
                missing.append({
                    "corpus_title": row.get("title", ""),
                    "corpus_year": row.get("year", ""),
                    "corpus_doi": rdoi,
                    "corpus_cited_by": row.get("cited_by_count", ""),
                    "corpus_first_author": row.get("first_author", ""),
                    "matching_bib_name": name,
                })
                break  # one match is enough

    return missing


def main():
    log.info("=" * 70)
    log.info("Bibliography-Corpus Verification")
    log.info("=" * 70)

    # Parse bibliography
    bib_entries = parse_bib(BIB_PATH)
    log.info("Bibliography: %d entries from %s", len(bib_entries), BIB_PATH)

    # Load corpus
    corpus = pd.read_csv(CORPUS_PATH, low_memory=False)
    log.info("Corpus: %s rows from %s", f"{len(corpus):,}", CORPUS_PATH)

    # Match
    log.info("Matching...")
    results = match_entries(bib_entries, corpus)

    # Save
    df = pd.DataFrame(results)
    df.to_csv(OUTPUT_PATH, index=False, encoding="utf-8")
    log.info("Saved %d rows to %s", len(df), OUTPUT_PATH)

    # Summary
    doi_matches = [r for r in results if r["match_type"] == "doi"]
    fuzzy_matches = [r for r in results if r["match_type"] == "fuzzy"]
    unmatched = [r for r in results if r["match_type"] == "none"]

    log.info("--- Match Summary ---")
    log.info("  DOI matches:   %d", len(doi_matches))
    log.info("  Fuzzy matches: %d", len(fuzzy_matches))
    log.info("  Unmatched:     %d", len(unmatched))

    if doi_matches:
        log.info("  DOI-matched entries:")
        for r in sorted(doi_matches, key=lambda x: x["bib_key"]):
            cited = _safe_cited(r["corpus_cited_by"])
            cited_str = " (cited_by=%s)" % cited if cited else ""
            log.info("    %s%s", r['bib_key'], cited_str)

    if fuzzy_matches:
        log.info("  Fuzzy-matched entries:")
        for r in sorted(fuzzy_matches, key=lambda x: x["bib_key"]):
            cited = _safe_cited(r["corpus_cited_by"])
            cited_str = " (cited_by=%s)" % cited if cited else ""
            log.info("    %s%s", r['bib_key'], cited_str)

    if unmatched:
        log.info("  Unmatched entries (expected for books/grey lit):")
        for r in sorted(unmatched, key=lambda x: x["bib_key"]):
            log.info("    %s [%s] -- %s", r['bib_key'], r['bib_type'],
                     r['bib_title'][:80])

    # Reverse check
    log.info("--- Reverse Check: highly-cited corpus papers (cited_by > 500) ---")
    log.info("    by bibliography authors NOT in the bibliography")
    missing_papers = reverse_check(bib_entries, corpus, cited_threshold=500)
    if missing_papers:
        for p in sorted(missing_papers, key=lambda x: -float(x["corpus_cited_by"])):
            log.info("    [%d] %s (%d) -- %s",
                     int(float(p['corpus_cited_by'])),
                     p['corpus_first_author'],
                     int(float(p['corpus_year'])),
                     p['corpus_title'][:70])
            log.info("         matching bib author: %s, doi: %s",
                     p['matching_bib_name'], p['corpus_doi'])
    else:
        log.info("    (none found)")

    log.info("Done.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    main()
