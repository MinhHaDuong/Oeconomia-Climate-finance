"""Shared utilities for the literature indexing pipeline."""

import gzip
import json
import os
import re
import time

import pandas as pd
import requests

# --- Paths ---

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.environ.get(
    "CLIMATE_FINANCE_DATA",
    os.path.expanduser("~/data/projets/Oeconomia-Climate-finance"),
)
CATALOGS_DIR = os.path.join(DATA_DIR, "catalogs")
EXPORTS_DIR = os.path.join(DATA_DIR, "exports")
RAW_DIR = os.path.join(DATA_DIR, "raw")
POOL_DIR = os.path.join(DATA_DIR, "pool")

# --- CSV schemas ---

WORKS_COLUMNS = [
    "source", "source_id", "doi", "title", "first_author", "all_authors",
    "year", "journal", "abstract", "language", "keywords", "categories",
    "cited_by_count", "affiliations",
]

REFS_COLUMNS = [
    "source_doi", "source_id", "ref_doi", "ref_title", "ref_first_author",
    "ref_year", "ref_journal", "ref_raw",
]

# --- Polite pool ---

MAILTO = "minh.haduong@cnrs.fr"


# --- Helpers ---

def normalize_doi(doi_raw):
    """Normalize a DOI: handle lists, strip URL prefix, lowercase, trim."""
    if doi_raw is None:
        return ""
    if isinstance(doi_raw, list):
        if not doi_raw:
            return ""
        doi_raw = doi_raw[0]
    doi = str(doi_raw).strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "http://dx.doi.org/",
                    "https://dx.doi.org/", "doi:"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
            break
    return doi.strip().lower()


def reconstruct_abstract(inverted_index):
    """Rebuild plain text from an OpenAlex abstract_inverted_index dict."""
    if not inverted_index:
        return ""
    word_positions = []
    for word, positions in inverted_index.items():
        for pos in positions:
            word_positions.append((pos, word))
    word_positions.sort()
    return " ".join(w for _, w in word_positions)


def normalize_title(title):
    """Normalize a title for fuzzy dedup: lowercase, strip punctuation, collapse spaces."""
    if not title:
        return ""
    t = title.lower()
    t = re.sub(r"[^\w\s]", "", t)
    t = re.sub(r"\s+", " ", t).strip()
    return t


def polite_get(url, params=None, headers=None, delay=0.2, max_retries=3):
    """HTTP GET with polite pool, delay, and retry on 429."""
    if params is None:
        params = {}
    if "mailto" not in params and "mailto" not in url:
        params["mailto"] = MAILTO
    if headers is None:
        headers = {}
    headers.setdefault("User-Agent", f"ClimateFinancePipeline/1.0 (mailto:{MAILTO})")

    for attempt in range(max_retries):
        time.sleep(delay)
        resp = requests.get(url, params=params, headers=headers, timeout=30)
        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", 2 ** (attempt + 1)))
            print(f"  Rate limited. Waiting {retry_after}s...")
            time.sleep(retry_after)
            continue
        resp.raise_for_status()
        return resp
    raise RuntimeError(f"Failed after {max_retries} retries: {url}")


def save_csv(df, path):
    """Save DataFrame to CSV with UTF-8 encoding."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    print(f"Saved {len(df)} rows to {path}")


def load_checkpoint(path):
    """Load records from a JSONL checkpoint file."""
    records = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        print(f"Loaded {len(records)} records from checkpoint {path}")
    return records


def append_checkpoint(records, path):
    """Append records to a JSONL checkpoint file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def delete_checkpoint(path):
    """Remove checkpoint file after successful completion."""
    if os.path.exists(path):
        os.remove(path)


# --- Pool helpers (append-only raw storage, gzipped JSONL) ---

def pool_path(source, slug):
    """Return path for a raw pool JSONL.gz file.

    Example: pool_path("openalex", "climate_finance")
      → ~/data/.../pool/openalex/climate_finance.jsonl.gz
    """
    d = os.path.join(POOL_DIR, source)
    os.makedirs(d, exist_ok=True)
    safe_slug = re.sub(r"[^\w\-]", "_", slug.lower())
    return os.path.join(d, f"{safe_slug}.jsonl.gz")


def append_to_pool(records, path):
    """Append raw API response dicts to a gzipped JSONL pool file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, "at", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_pool_ids(source, id_field="id"):
    """Scan all .jsonl.gz files in a source's pool dir, return set of IDs.

    Args:
        source: pool subdirectory name (e.g. "openalex")
        id_field: JSON field to extract as ID (default: "id")

    Returns:
        set of ID strings already in the pool
    """
    source_dir = os.path.join(POOL_DIR, source)
    ids = set()
    if not os.path.isdir(source_dir):
        return ids
    for fname in os.listdir(source_dir):
        if not fname.endswith(".jsonl.gz"):
            continue
        fpath = os.path.join(source_dir, fname)
        with gzip.open(fpath, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                    val = obj.get(id_field, "")
                    if val:
                        ids.add(str(val))
                except json.JSONDecodeError:
                    continue
    return ids


def load_pool_records(source):
    """Load all raw records from a source's pool directory.

    Returns:
        list of dicts (raw API responses)
    """
    source_dir = os.path.join(POOL_DIR, source)
    records = []
    if not os.path.isdir(source_dir):
        return records
    for fname in sorted(os.listdir(source_dir)):
        if not fname.endswith(".jsonl.gz"):
            continue
        fpath = os.path.join(source_dir, fname)
        with gzip.open(fpath, "rt", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        records.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue
    return records


def save_figure(fig, path_stem, no_pdf=False, dpi=150):
    """Save figure as PNG and optionally PDF.

    Produces byte-identical output across runs by stripping volatile
    metadata (Software version, creation timestamps).
    """
    _meta = {"Software": None, "Creation Time": None}
    fig.savefig(f"{path_stem}.png", dpi=dpi, bbox_inches="tight",
                metadata=_meta, pil_kwargs={"optimize": False})
    if not no_pdf:
        fig.savefig(f"{path_stem}.pdf", dpi=max(dpi, 300), bbox_inches="tight")
    print(f"Saved → {os.path.basename(path_stem)}.png" +
          ("" if no_pdf else " + .pdf"))
