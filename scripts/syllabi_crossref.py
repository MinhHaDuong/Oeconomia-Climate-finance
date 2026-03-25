"""CrossRef DOI lookup cache for the syllabi normalization stage.

Extracted from collect_syllabi.py to keep the main script under the
god-module 800-line threshold (see test_script_hygiene.py).

Public API (all re-exported by collect_syllabi.py):
  CROSSREF_CACHE_PATH
  _load_crossref_cache, _save_crossref_cache_entry, crossref_lookup
"""

import os

from syllabi_io import append_jsonl, load_jsonl
from utils import DATA_DIR, get_logger, normalize_title, polite_get

log = get_logger("syllabi_crossref")

# --- Paths ---
_SYLLABI_DIR = os.path.join(DATA_DIR, "syllabi")
CROSSREF_CACHE_PATH = os.path.join(_SYLLABI_DIR, "crossref_cache.jsonl")
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
