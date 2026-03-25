"""Search and fetch stages for the syllabi collection pipeline.

Extracted from collect_syllabi.py to keep the main script under the
god-module 800-line threshold (see test_script_hygiene.py).

Harvest = web crawling + HTTP + PDF download.  No LLM calls here.

Public API (available from this module directly):
  FETCH_WORKERS, HOST_INTERVAL
  stage_search, stage_fetch
  _fetch_one
"""

import hashlib
import os
import re
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from urllib.parse import urlparse

from syllabi_config import SEARCH_QUERIES, SEED_URLS
from syllabi_io import append_jsonl, extract_pdf_text, load_jsonl
from utils import MAILTO, get_logger, polite_get

log = get_logger("syllabi_harvest")

FETCH_WORKERS = 100      # Global concurrency — different hosts in parallel
HOST_INTERVAL = 1.0      # Min seconds between requests to the same host


# ============================================================
# Stage 1: Search
# ============================================================

def stage_search(search_path, syllabi_dir, limit=0):
    """Discover candidate URLs via DuckDuckGo + seed list.

    Args:
        search_path: Path to write search_results.jsonl checkpoint.
        syllabi_dir: Directory to create if needed.
        limit: Max number of DuckDuckGo queries to run (0 = unlimited).
    """
    from ddgs import DDGS

    os.makedirs(syllabi_dir, exist_ok=True)

    # Load already-completed queries
    existing = load_jsonl(search_path)
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
        append_jsonl(new_seeds, search_path)
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
            }], search_path)
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
            append_jsonl(new_records, search_path)
            log.info("Found %d new URLs", len(new_records))
        else:
            # Write a marker so we don't re-run this query
            append_jsonl([{
                "url": "", "title": "", "snippet": "",
                "query": query, "language": lang,
                "source_tier": "search_empty",
            }], search_path)

        done_queries.add(query)
        queries_run += 1
        time.sleep(1.5)  # Be polite to DuckDuckGo

    # Summary
    all_results = load_jsonl(search_path)
    valid = [r for r in all_results if r["url"] and r["source_tier"] not in ("search_error", "search_empty")]
    log.info("Search complete: %d candidate URLs from %d queries",
             len(valid), len({r['query'] for r in all_results}))


# ============================================================
# Stage 2: Fetch
# ============================================================

def _fetch_one(url, pdf_dir):
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
            pdf_path = os.path.join(pdf_dir, pdf_name)
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


def stage_fetch(search_path, pages_path, pdf_dir):
    """Download page content for each candidate URL.

    Uses a thread pool for I/O parallelism across different hosts, with
    per-host rate limiting (max 1 request per HOST_INTERVAL seconds to
    the same hostname).  Checkpoint writes are serialized via a lock.

    Args:
        search_path: Path to search_results.jsonl.
        pages_path: Path to write pages.jsonl checkpoint.
        pdf_dir: Directory to save downloaded PDFs.
    """
    os.makedirs(pdf_dir, exist_ok=True)

    # Load search results
    search_results = load_jsonl(search_path)
    urls_to_fetch = [r for r in search_results
                     if r["url"] and r["source_tier"] not in ("search_error", "search_empty")]

    # Load already-fetched
    fetched = load_jsonl(pages_path)
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

            result = _fetch_one(url, pdf_dir)

            with host_time_lock:
                host_last_request[host] = time.monotonic()

        # Thread-safe checkpoint write
        with write_lock:
            append_jsonl([result], pages_path)
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
    all_pages = load_jsonl(pages_path)
    ok = [p for p in all_pages if p["text"] and not p["error"]]
    log.info("Fetch complete: %d/%d pages with text", len(ok), len(all_pages))
