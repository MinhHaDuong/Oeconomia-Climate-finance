"""Classify, extract and normalize stages for the syllabi pipeline.

Extracted from collect_syllabi.py to keep the main script under the
god-module 800-line threshold (see test_script_hygiene.py).

Process = LLM calls + text parsing + DOI resolution.  No HTTP crawling here.

Public API (available from this module directly):
  CLASSIFY_PROMPT, EXTRACT_PROMPT
  EXTRACT_CACHE_PATH
  _extract_cache_key, _load_extract_cache, _save_extract_cache_entry
  stage_classify, stage_extract, stage_normalize

Re-exported by collect_syllabi.py (noqa F401):
  EXTRACT_PROMPT, EXTRACT_CACHE_PATH
  _extract_cache_key, _extract_cache_lock, _load_extract_cache, _save_extract_cache_entry
"""

import hashlib
import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

import pandas as pd

from syllabi_crossref import crossref_lookup
from syllabi_io import (MAX_TEXT_CHARS, append_jsonl, extract_json_from_text,
                        load_jsonl, llm_call, make_chunks)
from utils import BASE_DIR, DATA_DIR, clean_doi, dedup_courses, get_logger, normalize_title, save_csv

log = get_logger("syllabi_process")

EXTRACT_CACHE_PATH = os.path.join(BASE_DIR, "enrich_cache", "extract_cache.jsonl")

# ============================================================
# Stage 3: Classify
# ============================================================

CLASSIFY_PROMPT = """You are classifying web pages. Given the text below, determine if this is a university course syllabus or reading list related to climate finance, green finance, sustainable finance, carbon markets, or environmental economics.

Respond with ONLY a JSON object (no other text):
{{"is_syllabus": true/false, "course_name": "...", "institution": "...", "country": "...", "language": "...", "has_reading_list": true/false}}

If it is not a syllabus, set course_name/institution/country to empty strings.

TEXT (first 2000 chars):
{text}
"""


def stage_classify(pages_path, classified_path):
    """LLM classifies fetched pages as syllabi or not.

    Args:
        pages_path: Path to pages.jsonl (input).
        classified_path: Path to classified.jsonl checkpoint (output).
    """
    classify_model = os.environ.get(
        "CLASSIFY_MODEL", "openrouter/google/gemma-2-27b-it"
    )

    pages = load_jsonl(pages_path)
    pages_with_text = [p for p in pages if p.get("text") and not p.get("error")]

    classified = load_jsonl(classified_path)
    done_urls = {r["url"] for r in classified}

    pending = [p for p in pages_with_text if p["url"] not in done_urls]
    # Ollama: limit concurrency to avoid GPU contention; OpenRouter: go wide
    max_workers = 2 if classify_model.startswith("ollama/") else 20
    log.info("Classify: %d already done, %d pending, %d workers (model=%s)",
             len(done_urls), len(pending), max_workers, classify_model)

    counter = {"done": 0}
    counter_lock = threading.Lock()

    def classify_one(page):
        url = page["url"]
        text_snippet = page["text"][:2000]

        prompt = CLASSIFY_PROMPT.format(text=text_snippet)
        response = llm_call(prompt, model=classify_model)

        rec = {
            "url": url,
            "is_syllabus": False,
            "course_name": "",
            "institution": "",
            "country": "",
            "language": "",
            "has_reading_list": False,
            "llm_raw": (response or "")[:500],
        }

        parsed = extract_json_from_text(response)
        if parsed and isinstance(parsed, dict):
            rec["is_syllabus"] = bool(parsed.get("is_syllabus", False))
            rec["course_name"] = str(parsed.get("course_name", ""))
            rec["institution"] = str(parsed.get("institution", ""))
            rec["country"] = str(parsed.get("country", ""))
            rec["language"] = str(parsed.get("language", ""))
            rec["has_reading_list"] = bool(parsed.get("has_reading_list", False))

        status = "SYLLABUS" if rec["is_syllabus"] else "skip"
        reading = "+refs" if rec["has_reading_list"] else ""
        with counter_lock:
            counter["done"] += 1
            log.info("[%d/%d] %s -> %s%s | %s | %s",
                     counter["done"], len(pending), url[:60],
                     status, reading, rec['institution'], rec['course_name'])

        append_jsonl([rec], classified_path)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(classify_one, p) for p in pending]
        for f in as_completed(futures):
            f.result()  # raise exceptions

    # Summary
    all_classified = load_jsonl(classified_path)
    syllabi = [c for c in all_classified if c["is_syllabus"]]
    with_refs = [c for c in syllabi if c["has_reading_list"]]
    log.info("Classify complete: %d syllabi identified, %d with reading lists",
             len(syllabi), len(with_refs))

    if syllabi:
        countries = {}
        for s in syllabi:
            c = s.get("country", "unknown") or "unknown"
            countries[c] = countries.get(c, 0) + 1
        log.info("Countries: %s", ", ".join(
            f"{c}: {n}" for c, n in sorted(countries.items(), key=lambda x: -x[1])))


# ============================================================
# Stage 4: Extract
# ============================================================

def _extract_cache_key(text: str, model: str) -> str:
    """Build cache key from page text hash and model name."""
    return f"{hashlib.sha256(text.encode()).hexdigest()}:{model}"


def _load_extract_cache(path: str) -> dict:
    """Load extract cache from JSONL file. Returns dict mapping key → refs."""
    cache = {}
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    cache[rec["key"]] = rec["references"]
    return cache


_extract_cache_lock = threading.Lock()


def _save_extract_cache_entry(key: str, refs: list, path: str) -> None:
    """Append one extraction result to the cache JSONL file (thread-safe)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with _extract_cache_lock:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps({"key": key, "references": refs}, ensure_ascii=False) + "\n")


EXTRACT_PROMPT = """Extract ALL bibliographic references (reading list, required readings, recommended readings, bibliography) from this course syllabus text.

Return ONLY a JSON array of references (no other text). Each reference:
[{{"title": "...", "authors": "...", "year": 2020, "journal_or_publisher": "...", "doi": null, "type": "article"}}]

Valid types: "article", "book", "chapter", "report", "other"
If year is unknown, use null. If DOI is unknown, use null.

SYLLABUS TEXT:
{text}
"""


def stage_extract(pages_path, classified_path, references_path):
    """LLM extracts bibliographic references from confirmed syllabi.

    Args:
        pages_path: Path to pages.jsonl (input).
        classified_path: Path to classified.jsonl (input).
        references_path: Path to raw_references.jsonl checkpoint (output).
    """
    extract_model = os.environ.get(
        "EXTRACT_MODEL", "openrouter/google/gemma-2-27b-it"
    )

    classified = load_jsonl(classified_path)
    syllabi = [c for c in classified if c["is_syllabus"] and c["has_reading_list"]]

    # Load full page text for these URLs
    pages = load_jsonl(pages_path)
    page_by_url = {p["url"]: p for p in pages}

    extracted = load_jsonl(references_path)
    done_urls = {r["url"] for r in extracted}

    pending = [s for s in syllabi if s["url"] not in done_urls]
    max_workers = 2 if extract_model.startswith("ollama/") else 10
    log.info("Extract: %d already done, %d pending, %d workers (model=%s)",
             len(done_urls), len(pending), max_workers, extract_model)

    # Load extract cache (survives DVC re-runs via enrich_cache/ pattern)
    extract_cache = _load_extract_cache(EXTRACT_CACHE_PATH)
    log.info("Extract cache: %d entries loaded", len(extract_cache))

    total_refs_lock = threading.Lock()
    total_refs = [0]
    counter = {"done": 0}
    counter_lock = threading.Lock()

    def extract_one(syllabus):
        url = syllabus["url"]
        page = page_by_url.get(url, {})
        text = page.get("text", "")
        if not text:
            append_jsonl([{"url": url, "references": [], "error": "no_text"}],
                         references_path)
            with counter_lock:
                counter["done"] += 1
                log.info("[%d/%d] %s -- no text, skipping",
                         counter["done"], len(pending), url[:60])
            return
        if len(text) > MAX_TEXT_CHARS:
            append_jsonl([{"url": url, "references": [], "error": f"too_large_{len(text)}_chars"}],
                         references_path)
            with counter_lock:
                counter["done"] += 1
                log.warning("[%d/%d] %s -- %d chars, skipping (likely not a syllabus)",
                            counter["done"], len(pending), url[:60], len(text))
            return

        # Pass 1: regex DOI extraction — catches all explicit DOIs in text.
        # Essential: LLM (gemma-2-27b-it) only extracts ~24% of DOIs visible
        # in PDF text (tested on Harvard FECS: 22/92). Regex catches 100%.
        # The LLM is still needed for title-only references without DOIs.
        regex_dois = set()
        for m in re.finditer(r'(10\.\d{4,}/[^\s,);]+)', text):
            doi = clean_doi(m.group(1).rstrip('.'))
            if doi:
                regex_dois.add(doi)

        # Pass 2: LLM extraction — gets title/author/year + refs without DOIs
        # Uses per-chunk cache to avoid redundant LLM calls across runs.
        all_refs = []
        chunks = make_chunks(text)

        for chunk in chunks:
            cache_key = _extract_cache_key(chunk, extract_model)
            if cache_key in extract_cache:
                all_refs.extend(extract_cache[cache_key])
                continue

            prompt = EXTRACT_PROMPT.format(text=chunk)
            response = llm_call(prompt, model=extract_model, max_tokens=4000)

            chunk_refs = []
            parsed = extract_json_from_text(response)
            if parsed and isinstance(parsed, list):
                chunk_refs = parsed
            elif parsed and isinstance(parsed, dict):
                chunk_refs = [parsed]

            # Cache the result for this chunk+model combination
            _save_extract_cache_entry(cache_key, chunk_refs, EXTRACT_CACHE_PATH)
            extract_cache[cache_key] = chunk_refs
            all_refs.extend(chunk_refs)

        # Merge: add regex DOIs not found by LLM
        llm_dois = {clean_doi(r.get("doi", "")) for r in all_refs if r.get("doi")}
        for doi in regex_dois - llm_dois:
            all_refs.append({"title": "", "authors": "", "year": None,
                             "doi": doi, "type": "other"})

        # Deduplicate within this syllabus by DOI or normalized title
        seen_keys = set()
        unique_refs = []
        for ref in all_refs:
            if not isinstance(ref, dict):
                continue
            doi = clean_doi(ref.get("doi", ""))
            key = doi if doi else normalize_title(ref.get("title", ""))
            if key and key not in seen_keys:
                seen_keys.add(key)
                unique_refs.append(ref)

        rec = {
            "url": url,
            "course_name": syllabus["course_name"],
            "institution": syllabus["institution"],
            "country": syllabus["country"],
            "language": syllabus["language"],
            "references": unique_refs,
            "n_refs": len(unique_refs),
            "error": "",
        }
        append_jsonl([rec], references_path)
        with total_refs_lock:
            total_refs[0] += len(unique_refs)
        with counter_lock:
            counter["done"] += 1
            log.info("[%d/%d] %s (%s) -> %d refs",
                     counter["done"], len(pending),
                     syllabus['course_name'], syllabus['institution'],
                     len(unique_refs))

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(extract_one, s) for s in pending]
        for f in as_completed(futures):
            f.result()  # raise exceptions

    # Summary
    all_extracted = load_jsonl(references_path)
    total = sum(r.get("n_refs", 0) for r in all_extracted)
    log.info("Extract complete: %d total references from %d syllabi",
             total, len(all_extracted))


# ============================================================
# Stage 5: Normalize
# ============================================================

def stage_normalize(references_path, output_csv):
    """Deduplicate and enrich references via CrossRef (cached).

    Args:
        references_path: Path to raw_references.jsonl (input).
        output_csv: Path to write reading_lists.csv (output).
    """
    extracted = load_jsonl(references_path)

    # Flatten all references with course metadata
    flat = []
    for rec in extracted:
        for ref in rec.get("references", []):
            if not isinstance(ref, dict):
                continue
            flat.append({
                "title": ref.get("title", ""),
                "authors": ref.get("authors", ""),
                "year": ref.get("year"),
                "journal_or_publisher": ref.get("journal_or_publisher", ""),
                "doi": clean_doi(ref.get("doi")),
                "type": ref.get("type", "other"),
                "course_name": rec.get("course_name", ""),
                "institution": rec.get("institution", ""),
                "country": rec.get("country", ""),
            })

    log.info("Normalize: %d raw references from %d syllabi", len(flat), len(extracted))

    if not flat:
        log.info("No references to normalize.")
        return

    df = pd.DataFrame(flat)
    df["title_norm"] = df["title"].apply(normalize_title)

    # DOI lookup: CrossRef primary, OpenAlex fallback.
    # CrossRef is better for bibliographic title matching (~33% hit rate).
    # OpenAlex search= queries title+abstract+fulltext, which returns wrong
    # matches for short titles. Tried: appending author to OpenAlex search
    # (broke results), year filter (excluded correct matches with date
    # mismatch). Title-only search with similarity threshold works best.
    # CrossRef cached in JSONL (append-only), OpenAlex via find_doi() cache.
    no_doi = df[df["doi"] == ""]
    log.info("%d references without DOIs, looking up on CrossRef...", len(no_doi))

    lookup_count = 0
    for idx in no_doi.index:
        title = df.at[idx, "title"]
        authors = df.at[idx, "authors"]
        if not title or len(title) < 10:
            continue

        doi = crossref_lookup(title, authors)
        if doi:
            df.at[idx, "doi"] = doi.lower()
            lookup_count += 1
            log.info("Found DOI: %s <- %s", doi, title[:60])

        # Progress
        if (idx + 1) % 50 == 0:
            log.info("... %d/%d looked up, %d DOIs found",
                     idx + 1, len(no_doi), lookup_count)

    log.info("CrossRef: found %d DOIs", lookup_count)

    # Pass 2: OpenAlex fallback for remaining no-DOI refs
    from enrich_dois import find_doi
    still_no_doi = df[df["doi"] == ""]
    oa_count = 0
    for idx in still_no_doi.index:
        title = df.at[idx, "title"]
        if not title or len(title) < 10:
            continue
        doi = find_doi(title)
        if doi:
            df.at[idx, "doi"] = doi.lower()
            oa_count += 1
            log.info("Found DOI (OpenAlex): %s <- %s", doi, title[:60])
    if oa_count:
        log.info("OpenAlex fallback: found %d additional DOIs", oa_count)

    # Deduplicate: group by DOI (if available) or normalized title
    df["dedup_key"] = df.apply(
        lambda r: r["doi"] if r["doi"] else r["title_norm"], axis=1)

    grouped = df.groupby("dedup_key").agg({
        "doi": "first",
        "title": "first",
        "authors": "first",
        "year": "first",
        "journal_or_publisher": "first",
        "type": "first",
        "course_name": lambda x: " ; ".join(sorted(set(x))),
        "institution": lambda x: " ; ".join(sorted(set(x))),
        "country": lambda x: " ; ".join(sorted(set(x))),
    }).reset_index(drop=True)

    # Deduplicate near-identical courses before counting.
    # Some courses appear under multiple institution names (e.g., co-organized
    # MOOCs). We detect these by reading overlap: if two courses share >80%
    # of their readings, they are the same course and should count as one.
    grouped = dedup_courses(grouped, "course_name")

    # Sort by number of courses (most assigned first)
    grouped = grouped.sort_values("n_courses", ascending=False).reset_index(drop=True)

    # Rename columns for clarity
    grouped = grouped.rename(columns={
        "course_name": "courses",
        "institution": "institutions",
        "country": "countries",
    })

    # Optionally cross-reference with existing corpus
    corpus_path = os.path.join(DATA_DIR, "catalogs", "refined_works.csv")
    if os.path.exists(corpus_path):
        corpus = pd.read_csv(corpus_path)
        corpus_titles = set(corpus["title"].dropna().apply(normalize_title))
        corpus_dois = set(corpus["doi"].dropna().str.lower())

        grouped["in_corpus"] = grouped.apply(
            lambda r: (r["doi"] and r["doi"] in corpus_dois) or
                      (normalize_title(r["title"]) in corpus_titles),
            axis=1,
        )
        n_in = grouped["in_corpus"].sum()
        log.info("%d/%d references found in existing corpus", n_in, len(grouped))
    else:
        grouped["in_corpus"] = False

    save_csv(grouped, output_csv)

    log.info("Normalize complete:")
    log.info("Unique references: %d", len(grouped))
    log.info("With DOI: %d", (grouped['doi'] != '').sum())
    log.info("Most assigned (top 10):")
    for _, row in grouped.head(10).iterrows():
        log.info("[%d courses] %s", row['n_courses'], row['title'][:70])
