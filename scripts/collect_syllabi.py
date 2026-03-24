#!/usr/bin/env python3
"""Collect climate finance course reading lists from universities worldwide.

Five-stage pipeline:
  1. search   — Discover candidate URLs via DuckDuckGo + seed list
  2. fetch    — Download page content (HTML/PDF)
  3. classify — LLM classifies pages as syllabi or not
  4. extract  — LLM extracts bibliographic references
  5. normalize — Deduplicate + enrich via CrossRef (cached)

Each stage reads the previous stage's output and writes JSONL checkpoints.
Interruptible: re-run any stage to resume from checkpoint.

Usage:
    python scripts/collect_syllabi.py --stage search [--limit N]
    python scripts/collect_syllabi.py --stage fetch
    python scripts/collect_syllabi.py --stage classify
    python scripts/collect_syllabi.py --stage extract
    python scripts/collect_syllabi.py --stage normalize
"""

import argparse
import hashlib
import json
import os
import re
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urlparse

import pandas as pd

from syllabi_config import SEARCH_QUERIES, SEED_URLS
from utils import (BASE_DIR, DATA_DIR, MAILTO, clean_doi, dedup_courses,
                   get_logger, normalize_title, polite_get, save_csv)

log = get_logger("collect_syllabi")

# --- Constants ---
# No text truncation — make_chunks() handles splitting for LLM calls.
# Tested: 20K chunks cause 0 extractions with gemma-2-27b-it on dense
# bibliographies (Harvard FECS). 8K works. Model-dependent — recalibrate
# if switching models (see #289).
CHUNK_SIZE = 8000       # ~2K tokens per chunk — proven to work with gemma-2-27b-it
CHUNK_OVERLAP = 500     # Overlap between chunks to avoid splitting references at boundaries
MAX_TEXT_CHARS = 500000 # Skip pages over 500K chars (misclassified books/reports, not syllabi)

# --- Paths ---
SYLLABI_DIR = os.path.join(DATA_DIR, "syllabi")
PDF_DIR = os.path.join(SYLLABI_DIR, "pdfs")
SEARCH_PATH = os.path.join(SYLLABI_DIR, "search_results.jsonl")
PAGES_PATH = os.path.join(SYLLABI_DIR, "pages.jsonl")
CLASSIFIED_PATH = os.path.join(SYLLABI_DIR, "classified.jsonl")
REFERENCES_PATH = os.path.join(SYLLABI_DIR, "raw_references.jsonl")
OUTPUT_CSV = os.path.join(SYLLABI_DIR, "reading_lists.csv")


# ============================================================
# Helpers
# ============================================================

_clean_doi = clean_doi  # Alias for backward compatibility with tests


def load_jsonl(path):
    """Load all records from a JSONL file."""
    records = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
    return records


_jsonl_lock = threading.Lock()


def append_jsonl(records, path):
    """Append records to a JSONL file (thread-safe)."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with _jsonl_lock, open(path, "a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def extract_pdf_text(pdf_path, page_cap=50):
    """Extract text from a PDF using pdfplumber's extract_text().

    Table extraction (extract_tables) was removed because it duplicates
    reading list text as pipe-separated rows alongside the normal body text,
    confusing the LLM in overlapping chunks. pdfplumber's extract_text()
    already captures table content in most PDFs.
    """
    import pdfplumber

    text_parts = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages[:page_cap]:
            t = page.extract_text()
            if t:
                text_parts.append(t)
    return "\n\n".join(text_parts)


def make_chunks(text, chunk_size=CHUNK_SIZE, overlap=None):
    """Split text into overlapping chunks for LLM extraction.

    Overlap prevents references from being split across chunk boundaries.
    """
    if overlap is None:
        overlap = CHUNK_OVERLAP
    if overlap >= chunk_size:
        raise ValueError(f"overlap ({overlap}) must be < chunk_size ({chunk_size})")
    chunks = []
    start = 0
    while start < len(text):
        end = start + chunk_size
        chunks.append(text[start:end])
        start = end - overlap  # Step back by overlap amount
        if start + overlap >= len(text):
            break  # Last chunk captured everything
    return chunks


def llm_call(prompt, model="openrouter/google/gemma-2-27b-it", max_tokens=2000):
    """Call LLM via litellm. Model string encodes the provider.

    Examples:
        ollama/qwen3.5:27b          → routes to local Ollama
        openrouter/google/gemma-2-27b-it → routes to OpenRouter

    litellm reads OPENROUTER_API_KEY from env automatically.
    """
    import litellm

    # Prepend /no_think for Qwen models on Ollama to suppress chain-of-thought
    actual_prompt = prompt
    if model.startswith("ollama/") and "qwen" in model.lower():
        actual_prompt = "/no_think\n" + prompt

    try:
        response = litellm.completion(
            model=model,
            messages=[{"role": "user", "content": actual_prompt}],
            max_tokens=max_tokens,
            temperature=0,
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        log.error("LLM error (%s): %s", model, e)
        return None


def extract_json_from_text(text):
    """Extract the first JSON object or array from LLM response text."""
    if not text:
        return None
    # Try to find JSON block in markdown code fence
    m = re.search(r"```(?:json)?\s*\n?([\s\S]*?)\n?```", text)
    if m:
        text = m.group(1)
    # Try to parse the whole thing
    text = text.strip()
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        idx_start = text.find(start_char)
        idx_end = text.rfind(end_char)
        if idx_start != -1 and idx_end > idx_start:
            candidate = text[idx_start:idx_end + 1]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    return None


# ============================================================
# Stage 1: Search
# ============================================================

def stage_search(limit=0):
    """Discover candidate URLs via DuckDuckGo + seed list."""
    from ddgs import DDGS

    os.makedirs(SYLLABI_DIR, exist_ok=True)

    # Load already-completed queries
    existing = load_jsonl(SEARCH_PATH)
    done_queries = {r.get("query", "") for r in existing}
    seen_urls = {r["url"] for r in existing}

    log.info("Search: %d results already collected, %d queries done",
             len(existing), len(done_queries))

    # Add seed URLs first
    new_seeds = []
    for seed in SEED_URLS:
        if seed["url"] not in seen_urls:
            rec = {
                "url": seed["url"],
                "title": seed["title"],
                "snippet": "",
                "query": "__seed__",
                "language": seed["language"],
                "source_tier": seed["source_tier"],
            }
            new_seeds.append(rec)
            seen_urls.add(seed["url"])

    if new_seeds:
        append_jsonl(new_seeds, SEARCH_PATH)
        log.info("Added %d seed URLs", len(new_seeds))

    # DuckDuckGo searches
    ddgs = DDGS()
    queries_run = 0

    for topic, suffix, lang in SEARCH_QUERIES:
        query = f'"{topic}" {suffix}' if suffix else topic

        if query in done_queries:
            continue

        if limit and queries_run >= limit:
            log.info("Reached query limit (%d), stopping.", limit)
            break

        log.info("Searching: %s [%s]", query, lang)
        try:
            results = ddgs.text(query, max_results=30)
        except Exception as e:
            log.error("Search error for %s: %s", query, e)
            # Mark query as done to avoid retrying on resume
            append_jsonl([{
                "url": "", "title": f"ERROR: {e}", "snippet": "",
                "query": query, "language": lang,
                "source_tier": "search_error",
            }], SEARCH_PATH)
            done_queries.add(query)
            queries_run += 1
            time.sleep(2)
            continue

        new_records = []
        for r in (results or []):
            url = r.get("href", r.get("link", ""))
            if not url or url in seen_urls:
                continue
            seen_urls.add(url)
            new_records.append({
                "url": url,
                "title": r.get("title", ""),
                "snippet": r.get("body", ""),
                "query": query,
                "language": lang,
                "source_tier": "search",
            })

        if new_records:
            append_jsonl(new_records, SEARCH_PATH)
            log.info("Found %d new URLs", len(new_records))
        else:
            # Write a marker so we don't re-run this query
            append_jsonl([{
                "url": "", "title": "", "snippet": "",
                "query": query, "language": lang,
                "source_tier": "search_empty",
            }], SEARCH_PATH)

        done_queries.add(query)
        queries_run += 1
        time.sleep(1.5)  # Be polite to DuckDuckGo

    # Summary
    all_results = load_jsonl(SEARCH_PATH)
    valid = [r for r in all_results if r["url"] and r["source_tier"] not in ("search_error", "search_empty")]
    log.info("Search complete: %d candidate URLs from %d queries",
             len(valid), len({r['query'] for r in all_results}))


# ============================================================
# Stage 2: Fetch
# ============================================================

FETCH_WORKERS = 100      # Global concurrency — different hosts in parallel
HOST_INTERVAL = 1.0      # Min seconds between requests to the same host


def _fetch_one(url):
    """Fetch a single URL and return a page record dict.

    Handles both HTML and PDF responses.  Pure function (no file I/O for
    the checkpoint — caller writes the result).
    """
    from bs4 import BeautifulSoup

    page_rec = {
        "url": url,
        "content_type": "",
        "text": "",
        "fetch_date": datetime.now(timezone.utc).isoformat(),
        "http_status": 0,
        "error": "",
    }

    try:
        headers = {"User-Agent": f"ClimateFinancePipeline/1.0 (mailto:{MAILTO})"}
        resp = polite_get(url, headers=headers, delay=0.5)
        ct = resp.headers.get("Content-Type", "")
        page_rec["http_status"] = resp.status_code
        page_rec["content_type"] = ct

        if "pdf" in ct.lower() or url.lower().endswith(".pdf"):
            base = re.sub(r'[^\w\-.]', '_', url.split("/")[-1] or "page")
            if base.lower().endswith(".pdf"):
                base = base[:-4]
            url_hash = hashlib.md5(url.encode()).hexdigest()[:8]
            pdf_name = f"{base}_{url_hash}.pdf"
            pdf_path = os.path.join(PDF_DIR, pdf_name)
            with open(pdf_path, "wb") as f:
                f.write(resp.content)

            try:
                page_rec["text"] = extract_pdf_text(pdf_path)
                page_rec["content_type"] = "application/pdf"
            except Exception as e:
                page_rec["error"] = f"PDF parse error: {e}"
                log.warning("PDF parse error: %s", e)
        else:
            soup = BeautifulSoup(resp.text, "html.parser")
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            page_rec["text"] = text
            page_rec["content_type"] = "text/html"

    except Exception as e:
        page_rec["error"] = str(e)
        log.error("Fetch error for %s: %s", url, e)

    return page_rec


def stage_fetch():
    """Download page content for each candidate URL.

    Uses a thread pool for I/O parallelism across different hosts, with
    per-host rate limiting (max 1 request per HOST_INTERVAL seconds to
    the same hostname).  Checkpoint writes are serialized via a lock.
    """
    os.makedirs(PDF_DIR, exist_ok=True)

    # Load search results
    search_results = load_jsonl(SEARCH_PATH)
    urls_to_fetch = [r for r in search_results
                     if r["url"] and r["source_tier"] not in ("search_error", "search_empty")]

    # Load already-fetched
    fetched = load_jsonl(PAGES_PATH)
    done_urls = {r["url"] for r in fetched}

    pending = [r for r in urls_to_fetch if r["url"] not in done_urls]
    log.info("Fetch: %d already done, %d pending", len(done_urls), len(pending))

    if not pending:
        return

    # Group pending URLs by host for rate limiting and logging
    host_counts = defaultdict(int)
    for rec in pending:
        host = urlparse(rec["url"]).hostname or "unknown"
        host_counts[host] += 1

    # Pre-create per-host locks before spawning threads (avoids defaultdict race)
    host_locks = {host: threading.Lock() for host in host_counts}
    host_last_request = {}  # hostname → monotonic timestamp
    host_time_lock = threading.Lock()  # protects host_last_request reads/writes

    # Checkpoint write lock — serializes appends to pages.jsonl
    write_lock = threading.Lock()
    completed = [0]  # mutable counter for progress logging

    def rate_limited_fetch(url):
        """Fetch url, respecting per-host rate limit."""
        host = urlparse(url).hostname or "unknown"

        # Acquire per-host lock so only one thread hits this host at a time
        with host_locks[host]:
            # Enforce minimum interval since last request to this host
            with host_time_lock:
                last = host_last_request.get(host, 0)
                now = time.monotonic()
                wait = HOST_INTERVAL - (now - last)
            if wait > 0:
                time.sleep(wait)

            result = _fetch_one(url)

            with host_time_lock:
                host_last_request[host] = time.monotonic()

        # Thread-safe checkpoint write
        with write_lock:
            append_jsonl([result], PAGES_PATH)
            completed[0] += 1
            log.info("[%d/%d] %s", completed[0], len(pending), url[:80])

        return result
    n_hosts = len(host_counts)
    max_per_host = max(host_counts.values())
    log.info("Fetching from %d hosts (max %d URLs/host), %d workers",
             n_hosts, max_per_host, FETCH_WORKERS)

    with ThreadPoolExecutor(max_workers=FETCH_WORKERS) as pool:
        futures = {pool.submit(rate_limited_fetch, rec["url"]): rec
                   for rec in pending}
        for future in as_completed(futures):
            # Propagate exceptions for visibility (already logged inside)
            try:
                future.result()
            except Exception as e:
                url = futures[future]["url"]
                log.error("Unhandled error fetching %s: %s", url[:80], e)

    # Summary
    all_pages = load_jsonl(PAGES_PATH)
    ok = [p for p in all_pages if p["text"] and not p["error"]]
    log.info("Fetch complete: %d/%d pages with text", len(ok), len(all_pages))


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


def stage_classify():
    """LLM classifies fetched pages as syllabi or not."""
    classify_model = os.environ.get(
        "CLASSIFY_MODEL", "openrouter/google/gemma-2-27b-it"
    )

    pages = load_jsonl(PAGES_PATH)
    pages_with_text = [p for p in pages if p.get("text") and not p.get("error")]

    classified = load_jsonl(CLASSIFIED_PATH)
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

        append_jsonl([rec], CLASSIFIED_PATH)

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(classify_one, p) for p in pending]
        for f in as_completed(futures):
            f.result()  # raise exceptions

    # Summary
    all_classified = load_jsonl(CLASSIFIED_PATH)
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


def stage_extract():
    """LLM extracts bibliographic references from confirmed syllabi."""
    extract_model = os.environ.get(
        "EXTRACT_MODEL", "openrouter/google/gemma-2-27b-it"
    )

    classified = load_jsonl(CLASSIFIED_PATH)
    syllabi = [c for c in classified if c["is_syllabus"] and c["has_reading_list"]]

    # Load full page text for these URLs
    pages = load_jsonl(PAGES_PATH)
    page_by_url = {p["url"]: p for p in pages}

    extracted = load_jsonl(REFERENCES_PATH)
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
                         REFERENCES_PATH)
            with counter_lock:
                counter["done"] += 1
                log.info("[%d/%d] %s -- no text, skipping",
                         counter["done"], len(pending), url[:60])
            return
        if len(text) > MAX_TEXT_CHARS:
            append_jsonl([{"url": url, "references": [], "error": f"too_large_{len(text)}_chars"}],
                         REFERENCES_PATH)
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
        append_jsonl([rec], REFERENCES_PATH)
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
    all_extracted = load_jsonl(REFERENCES_PATH)
    total = sum(r.get("n_refs", 0) for r in all_extracted)
    log.info("Extract complete: %d total references from %d syllabi",
             total, len(all_extracted))


# ============================================================
# Stage 5: Normalize
# ============================================================

EXTRACT_CACHE_PATH = os.path.join(BASE_DIR, "enrich_cache", "extract_cache.jsonl")

CROSSREF_CACHE_PATH = os.path.join(SYLLABI_DIR, "crossref_cache.jsonl")
_crossref_cache = None


def _load_crossref_cache():
    """Load title→DOI cache from disk (once)."""
    global _crossref_cache
    if _crossref_cache is not None:
        return _crossref_cache
    _crossref_cache = {}
    for rec in load_jsonl(CROSSREF_CACHE_PATH):
        _crossref_cache[rec["title_norm"]] = rec.get("doi", "")
    log.info("CrossRef cache: %d entries loaded", len(_crossref_cache))
    return _crossref_cache


def _save_crossref_cache_entry(title_norm, doi):
    """Append one lookup result to the cache file."""
    _crossref_cache[title_norm] = doi
    append_jsonl([{"title_norm": title_norm, "doi": doi}], CROSSREF_CACHE_PATH)


def crossref_lookup(title, authors=""):
    """Look up a DOI on CrossRef by title. Cached to avoid redundant queries."""
    cache = _load_crossref_cache()
    tnorm = normalize_title(title)
    if tnorm in cache:
        return cache[tnorm]

    query = title
    authors = str(authors) if authors and authors == authors else ""
    if authors:
        first_author = authors.split(",")[0].split(";")[0].strip()
        if first_author:
            query = f"{first_author} {title}"

    try:
        resp = polite_get(
            "https://api.crossref.org/works",
            params={"query": query[:200], "rows": 1},
            delay=0.3,
        )
        data = resp.json()
        items = data.get("message", {}).get("items", [])
        if items:
            item = items[0]
            cr_title = " ".join(item.get("title", []))
            if normalize_title(cr_title) == normalize_title(title):
                doi = item.get("DOI", "")
                _save_crossref_cache_entry(tnorm, doi)
                return doi
            t1_words = set(normalize_title(title).split())
            t2_words = set(normalize_title(cr_title).split())
            if t1_words and t2_words:
                overlap = len(t1_words & t2_words) / max(len(t1_words), 1)
                if overlap > 0.7:
                    doi = item.get("DOI", "")
                    _save_crossref_cache_entry(tnorm, doi)
                    return doi
    except Exception as e:
        log.warning("CrossRef error: %s", e)
    _save_crossref_cache_entry(tnorm, "")
    return ""


def stage_normalize():
    """Deduplicate and enrich references via CrossRef (cached)."""
    extracted = load_jsonl(REFERENCES_PATH)

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
                "doi": _clean_doi(ref.get("doi")),
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
        year = df.at[idx, "year"]
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

    save_csv(grouped, OUTPUT_CSV)

    log.info("Normalize complete:")
    log.info("Unique references: %d", len(grouped))
    log.info("With DOI: %d", (grouped['doi'] != '').sum())
    log.info("Most assigned (top 10):")
    for _, row in grouped.head(10).iterrows():
        log.info("[%d courses] %s", row['n_courses'], row['title'][:70])


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Collect climate finance course reading lists")
    parser.add_argument("--stage", required=True,
                        choices=["search", "fetch", "classify", "extract", "normalize"],
                        help="Pipeline stage to run")
    parser.add_argument("--limit", type=int, default=0,
                        help="Limit number of queries (search) or items to process")
    args = parser.parse_args()

    os.makedirs(SYLLABI_DIR, exist_ok=True)

    if args.stage == "search":
        stage_search(limit=args.limit)
    elif args.stage == "fetch":
        stage_fetch()
    elif args.stage == "classify":
        stage_classify()
    elif args.stage == "extract":
        stage_extract()
    elif args.stage == "normalize":
        stage_normalize()


if __name__ == "__main__":
    main()
