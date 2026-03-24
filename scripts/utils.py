"""Shared utilities for the literature indexing pipeline."""

import gzip
import json
import logging
import os
import random
import re
import signal
import subprocess
import threading
import time

import pandas as pd
import requests
from dotenv import load_dotenv
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    SpinnerColumn,
    TaskProgressColumn,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)


# --- Logging ---

def get_logger(name=None):
    """Return a configured logger for pipeline scripts.

    First call installs a shared StreamHandler on the 'pipeline' root logger
    with elapsed-time timestamps.  Subsequent calls just return a child logger.

    Usage in scripts::

        from utils import get_logger
        log = get_logger("enrich_abstracts")
        log.info("Step 1: cross-source backfill (%d missing)", n)
    """
    root = logging.getLogger("pipeline")
    if not root.handlers:
        root.setLevel(logging.DEBUG)
        root.propagate = False  # prevent duplicates if DVC configures root logger
        handler = logging.StreamHandler()       # stderr, auto-flushes
        handler.setLevel(logging.DEBUG)
        formatter = logging.Formatter(
            fmt="%(asctime)s %(levelname)-7s %(message)s",
            datefmt="%H:%M:%S",
        )
        handler.setFormatter(formatter)
        root.addHandler(handler)
    if name:
        return root.getChild(name)
    return root


_utils_log = get_logger("utils")

# --- Paths ---

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Load .env from repo root (secrets like API keys live here, gitignored).
load_dotenv(os.path.join(BASE_DIR, ".env"))
CONFIG_DIR = os.path.join(BASE_DIR, "config")

# Data lives in <repo>/data/ (managed by DVC).
DATA_DIR = os.path.join(BASE_DIR, "data")
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

# Source provenance — boolean columns indicating which sources contributed each work.
# These replace the old pipe-separated `source` column for multi-source tracking.
SOURCE_NAMES = ["openalex", "istex", "bibcnrs", "scispsace", "grey", "teaching"]
FROM_COLS = [f"from_{s}" for s in SOURCE_NAMES]

REFS_COLUMNS = [
    "source_doi", "source_id", "ref_doi", "ref_title", "ref_first_author",
    "ref_year", "ref_journal", "ref_raw",
]

# --- Polite pool ---

MAILTO = "minh.ha-duong@cnrs.fr"
OPENALEX_API_KEY = os.environ.get("OPENALEX_API_KEY", "")

# Retry budgets — single source of truth for polite_get and retry_get defaults
POLITE_MAX_RETRIES = 3   # catalog scrapers (quick, many URLs)
RETRY_MAX_RETRIES = 5    # enrichment fetchers (heavy, fewer URLs)


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


def clean_doi(raw):
    """Extract a clean DOI (10.xxxx/...) from a raw string.

    Handles URL-prefixed DOIs from LLM extraction:
    - https://doi.org/10.xxx → 10.xxx
    - http://dx.doi.org/10.xxx → 10.xxx
    - https://doi.org/doi:10.xxx → 10.xxx
    - https://publisher.com/doi/full/10.xxx → 10.xxx
    - Already-clean 10.xxx → 10.xxx
    - Non-DOI URLs (SSRN, HDL) → ""
    - None / "" → ""
    """
    if not raw:
        return ""
    raw = str(raw).strip()
    if not raw:
        return ""
    # Extract the 10.xxxx/... DOI pattern from anywhere in the string
    m = re.search(r"(10\.\d{4,}[^\s]*)", raw)
    if m:
        return m.group(1).lower()
    return ""


def polite_get(url, params=None, headers=None, delay=0.2,
               max_retries=POLITE_MAX_RETRIES):
    """HTTP GET with polite delay, exponential backoff+jitter, retry on 429/5xx.

    Delegates to retry_get. All callers (OpenAlex, ISTEX, World Bank, syllabi)
    get POLITE_MAX_RETRIES retries with 5xx handling.
    """
    return retry_get(url, params=params, headers=headers, delay=delay,
                     max_retries=max_retries, timeout=30)


def retry_get(url, params=None, headers=None, delay=0.2,
              max_retries=RETRY_MAX_RETRIES,
              timeout=60, counters=None, backoff_base=2.0, jitter_max=1.0):
    """HTTP GET with bounded exponential backoff+jitter and optional counter tracking.

    Parameters
    ----------
    url:          Request URL.
    params:       Query parameters dict.
    headers:      HTTP headers dict.
    delay:        Base polite delay before each attempt (seconds).
    max_retries:  Maximum number of retry attempts for 429/5xx/timeout.
    timeout:      Per-request timeout in seconds.
    counters:     Optional dict to update with keys:
                  ``retries``, ``rate_limited``, ``server_errors``, ``client_errors``.
    backoff_base: Base for exponential backoff (seconds, default 2.0).
    jitter_max:   Maximum random jitter added to each backoff (seconds, default 1.0).

    Returns
    -------
    requests.Response on success.

    Raises
    ------
    RuntimeError after all retries are exhausted.
    """
    if params is None:
        params = {}
    if "mailto" not in params and "mailto" not in url:
        params["mailto"] = MAILTO
    if headers is None:
        headers = {}
    headers.setdefault("User-Agent", f"ClimateFinancePipeline/1.0 (mailto:{MAILTO})")
    if counters is None:
        counters = {}

    last_exc = None
    for attempt in range(max_retries):
        try:
            time.sleep(delay)
            resp = requests.get(url, params=params, headers=headers, timeout=timeout)
        except requests.exceptions.Timeout as exc:
            last_exc = exc
            counters["retries"] = counters.get("retries", 0) + 1
            backoff = min(backoff_base ** attempt + random.uniform(0, jitter_max), 60)
            _utils_log.warning("Timeout on attempt %d/%d, retrying in %.1fs...",
                               attempt + 1, max_retries, backoff)
            time.sleep(backoff)
            continue
        except requests.exceptions.RequestException as exc:
            last_exc = exc
            counters["retries"] = counters.get("retries", 0) + 1
            backoff = min(backoff_base ** attempt + random.uniform(0, jitter_max), 60)
            time.sleep(backoff)
            continue

        if resp.status_code == 429:
            counters["rate_limited"] = counters.get("rate_limited", 0) + 1
            counters["retries"] = counters.get("retries", 0) + 1
            if attempt == max_retries - 1:
                # Return the 429 response instead of raising — lets callers
                # inspect budget headers and degrade gracefully.
                _utils_log.warning("Rate limited (429) after %d attempts, returning response.", max_retries)
                return resp
            retry_after = min(int(resp.headers.get("Retry-After", backoff_base ** (attempt + 1))), 120)
            jitter = random.uniform(0, min(jitter_max * 2, 2))
            wait = retry_after + jitter
            _utils_log.warning("Rate limited (429), waiting %.1fs...", wait)
            time.sleep(wait)
            continue
        if resp.status_code >= 500:
            counters["server_errors"] = counters.get("server_errors", 0) + 1
            counters["retries"] = counters.get("retries", 0) + 1
            backoff = min(backoff_base ** attempt + random.uniform(0, jitter_max), 60)
            _utils_log.warning("Server error %d on attempt %d/%d, retrying in %.1fs...",
                               resp.status_code, attempt + 1, max_retries, backoff)
            time.sleep(backoff)
            last_exc = resp.status_code
            continue
        if resp.status_code >= 400:
            counters["client_errors"] = counters.get("client_errors", 0) + 1
            resp.raise_for_status()
        return resp

    raise RuntimeError(
        f"Failed after {max_retries} attempts: {url} "
        f"(last error: {last_exc})"
    )


def save_run_report(data, run_id, script_name):
    """Persist a structured run-summary dict as JSON in catalogs/run_reports/.

    Parameters
    ----------
    data:        Dict of counters / metadata to save.
    run_id:      Unique run identifier string (e.g. timestamp or ``--run-id`` value).
    script_name: Short script name used as filename prefix.

    Returns
    -------
    Path to the saved JSON file (str).
    """
    reports_dir = os.path.join(CATALOGS_DIR, "run_reports")
    os.makedirs(reports_dir, exist_ok=True)
    safe_run_id = re.sub(r"[^\w.-]", "_", run_id)
    filename = f"{script_name}__{safe_run_id}.json"
    path = os.path.join(reports_dir, filename)
    payload = {"script": script_name, "run_id": run_id, **data}
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    return path


def make_run_id():
    """Return a UTC timestamp string suitable for use as a run-id."""
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


_CLUSTER_LABELS_PATH = os.path.join(BASE_DIR, "content", "tables", "cluster_labels.json")


def load_cluster_labels(n_clusters=6):
    """Load cluster labels from cluster_labels.json.

    Returns dict with int keys: {0: "term1 / term2 / term3", ...}.
    Falls back to generic "Cluster N" labels with a warning.
    """
    import warnings

    if os.path.exists(_CLUSTER_LABELS_PATH):
        with open(_CLUSTER_LABELS_PATH) as f:
            raw = json.load(f)
        return {int(k): v for k, v in raw.items()}

    warnings.warn(
        f"cluster_labels.json not found at {_CLUSTER_LABELS_PATH}. "
        "Run: uv run python scripts/compute_clusters.py",
        stacklevel=2,
    )
    return {i: f"Cluster {i}" for i in range(n_clusters)}


# Embeddings live in a separate .npz rather than as columns in refined_works.csv:
# - Size: 384 floats × 30k rows as CSV text ≈ 500 MB vs. ~45 MB compressed binary
# - Incremental cache: stores keys + text hashes + model config so only new/changed
#   works are re-encoded on each run (~16 min full, seconds incremental)
# - Load speed: numpy reads the array in one shot; no parsing of 11M float strings
EMBEDDINGS_PATH = os.path.join(CATALOGS_DIR, "embeddings.npz")

# Incremental embedding cache lives in enrich_cache/ — NOT a DVC output.
# DVC deletes stage outputs before re-running; keeping the cache separate
# means re-runs skip already-computed vectors instead of starting from scratch.
EMBEDDINGS_CACHE_DIR = os.path.join(CATALOGS_DIR, "enrich_cache")
EMBEDDINGS_CACHE_PATH = os.path.join(EMBEDDINGS_CACHE_DIR, "embeddings_cache.npz")

# Phase 1 → Phase 2 aligned canonical artifacts (produced by corpus-align step).
# refined_embeddings.npz rows are 1:1 with refined_works.csv rows.
# refined_citations.csv source_doi values are a subset of refined_works.csv DOIs.
REFINED_WORKS_PATH = os.path.join(CATALOGS_DIR, "refined_works.csv")
REFINED_EMBEDDINGS_PATH = os.path.join(CATALOGS_DIR, "refined_embeddings.npz")
REFINED_CITATIONS_PATH = os.path.join(CATALOGS_DIR, "refined_citations.csv")


def work_key(row):
    """Stable key for a work: DOI preferred, then source_id, then title hash.

    Used by both enrich_embeddings.py and analyze_embeddings.py to align
    works with their embedding vectors. Must be identical across scripts.
    """
    import hashlib

    if pd.notna(row["doi"]):
        return str(row["doi"])
    if pd.notna(row["source_id"]):
        return str(row["source_id"])
    return "title:" + hashlib.md5(str(row["title"]).encode()).hexdigest()


def load_embeddings():
    """Load embedding vectors from the .npz cache.

    Returns the (N, 384) float32 array. Raises FileNotFoundError if missing.
    Also supports legacy .npy files for backwards compatibility.
    """
    import numpy as np

    if os.path.exists(EMBEDDINGS_PATH):
        return np.load(EMBEDDINGS_PATH)["vectors"]
    # Legacy fallback
    legacy = os.path.join(CATALOGS_DIR, "embeddings.npy")
    if os.path.exists(legacy):
        return np.load(legacy)
    raise FileNotFoundError(f"No embeddings found at {EMBEDDINGS_PATH}")


def load_refined_embeddings():
    """Load embedding vectors aligned 1:1 with refined_works.csv rows.

    Returns the (N, D) float32 array where N == len(refined_works.csv).
    Raises FileNotFoundError with a remediation hint if the file is missing.
    Run ``make corpus-align`` (or ``uv run python scripts/corpus_align.py``)
    to produce this file.
    """
    import numpy as np

    if not os.path.exists(REFINED_EMBEDDINGS_PATH):
        raise FileNotFoundError(
            f"refined_embeddings.npz not found at {REFINED_EMBEDDINGS_PATH}. "
            "Run: uv run python scripts/corpus_align.py"
        )
    return np.load(REFINED_EMBEDDINGS_PATH)["vectors"]


def load_refined_citations():
    """Load citation edges restricted to refined_works.csv source DOIs.

    Returns a DataFrame whose ``source_doi`` values are all members of
    ``normalize_doi(refined_works.csv.doi)``.
    Raises FileNotFoundError with a remediation hint if the file is missing.
    Run ``make corpus-align`` (or ``uv run python scripts/corpus_align.py``)
    to produce this file.
    """
    if not os.path.exists(REFINED_CITATIONS_PATH):
        raise FileNotFoundError(
            f"refined_citations.csv not found at {REFINED_CITATIONS_PATH}. "
            "Run: uv run python scripts/corpus_align.py"
        )
    return pd.read_csv(REFINED_CITATIONS_PATH, low_memory=False)


def load_analysis_corpus(core_only=False, with_embeddings=True,
                         cite_threshold=None, v1_only=False):
    """Load refined_works.csv with standard filtering + optional embeddings.

    Applies: year coercion, title-present filter, year in [year_min, year_max]
    (from config/analysis.yaml), optional core filtering (cited_by_count >= cite_threshold).

    If v1_only=True, restricts to rows with in_v1==1 (the v1.0-submission
    corpus). Use this for manuscript figures to ensure stability against
    corpus expansion.

    If cite_threshold is None, the value is read from config/analysis.yaml
    (clustering.cite_threshold) so there is a single source of truth.

    Returns (df, embeddings) where embeddings is None if with_embeddings=False.
    """
    import numpy as np

    cfg = load_analysis_config()
    if cite_threshold is None:
        cite_threshold = cfg["clustering"]["cite_threshold"]
    year_min = cfg["periodization"]["year_min"]
    year_max = cfg["periodization"]["year_max"]

    works = pd.read_csv(REFINED_WORKS_PATH)
    works["year"] = pd.to_numeric(works["year"], errors="coerce")

    has_title = works["title"].notna() & (works["title"].str.len() > 0)
    in_range = (works["year"] >= year_min) & (works["year"] <= year_max)
    keep_mask = has_title & in_range
    if v1_only:
        if "in_v1" not in works.columns:
            raise RuntimeError(
                "v1_only=True but 'in_v1' column missing from refined_works.csv. "
                "Re-run: uv run python scripts/corpus_filter.py --apply"
            )
        keep_mask = keep_mask & (works["in_v1"] == 1)
        _utils_log.info("v1_only: restricting to %d / %d rows",
                        keep_mask.sum(), len(works))
    keep_mask = keep_mask.values
    df = works[keep_mask].copy().reset_index(drop=True)

    embeddings = None
    if with_embeddings:
        all_embeddings = load_refined_embeddings()
        if len(all_embeddings) != len(works):
            raise RuntimeError(
                f"Embedding/refined_works row count mismatch "
                f"({len(all_embeddings)} vs {len(works)}). "
                "Re-run: uv run python scripts/corpus_align.py"
            )
        embeddings = all_embeddings[keep_mask]

    df["cited_by_count"] = pd.to_numeric(
        df["cited_by_count"], errors="coerce"
    ).fillna(0)

    if core_only:
        core_mask = df["cited_by_count"] >= cite_threshold
        core_indices = df.index[core_mask].values
        df = df.loc[core_mask].reset_index(drop=True)
        if embeddings is not None:
            embeddings = embeddings[core_indices]
            assert len(df) == len(embeddings), \
                "Embedding alignment error after core filtering"

    return df, embeddings


def load_collect_config():
    """Load config/corpus_collect.yaml (Phase 1 collection parameters).

    Returns dict with keys: year_min, year_max, queries.
    Raises FileNotFoundError if the config is missing.
    """
    import yaml

    path = os.path.join(CONFIG_DIR, "corpus_collect.yaml")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"corpus_collect.yaml not found at {path}. "
            "This file defines year bounds for API queries."
        )
    with open(path) as f:
        cfg = yaml.safe_load(f)
    if not isinstance(cfg.get("year_min"), int) or not isinstance(cfg.get("year_max"), int):
        raise ValueError("year_min and year_max must be integers in corpus_collect.yaml")
    if cfg["year_min"] > cfg["year_max"]:
        raise ValueError(
            f"year_min ({cfg['year_min']}) > year_max ({cfg['year_max']}) "
            "in corpus_collect.yaml"
        )
    return cfg


def load_analysis_config():
    """Load config/analysis.yaml (Phase 2 analysis parameters).

    Returns dict with keys: periodization, clustering.
    """
    import yaml

    path = os.path.join(CONFIG_DIR, "analysis.yaml")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"analysis.yaml not found at {path}. "
            "This file defines Phase 2 analysis parameters."
        )
    with open(path) as f:
        return yaml.safe_load(f)


def load_analysis_periods(config_dir=None):
    """Derive period tuples and labels from config/analysis.yaml.

    Returns (periods, labels) where:
      periods = [(1990, 2006), (2007, 2014), (2015, 2024)]
      labels  = ["1990\u20132006", "2007\u20132014", "2015\u20132024"]

    If config_dir is given, reads analysis.yaml (and optionally
    corpus_collect.yaml) from that directory instead of CONFIG_DIR.

    Emits a UserWarning if the analysis year range exceeds the collection
    range defined in corpus_collect.yaml. Skips the check gracefully if
    corpus_collect.yaml does not exist.
    """
    import warnings
    import yaml

    cdir = config_dir or CONFIG_DIR
    analysis_path = os.path.join(cdir, "analysis.yaml")
    with open(analysis_path) as f:
        cfg = yaml.safe_load(f)

    p = cfg["periodization"]
    year_min = p["year_min"]
    year_max = p["year_max"]
    breaks = p["breaks"]

    # Build period tuples: [year_min, break-1], [break, next_break-1], ..., [last_break, year_max]
    boundaries = [year_min] + breaks + [year_max + 1]
    periods = []
    labels = []
    for i in range(len(boundaries) - 1):
        start = boundaries[i]
        end = boundaries[i + 1] - 1
        periods.append((start, end))
        labels.append(f"{start}\u2013{end}")

    # Check against collection range if corpus_collect.yaml exists
    collect_path = os.path.join(cdir, "corpus_collect.yaml")
    if os.path.exists(collect_path):
        with open(collect_path) as f:
            collect_cfg = yaml.safe_load(f)
        c_min = collect_cfg.get("year_min")
        c_max = collect_cfg.get("year_max")
        msgs = []
        if c_min is not None and year_min < c_min:
            msgs.append(
                f"analysis year_min ({year_min}) < collection year_min ({c_min})"
            )
        if c_max is not None and year_max > c_max:
            msgs.append(
                f"analysis year_max ({year_max}) > collection year_max ({c_max})"
            )
        if msgs:
            warnings.warn(
                "Analysis range exceeds collection range: "
                + "; ".join(msgs),
                UserWarning,
                stacklevel=2,
            )

    return periods, labels


def save_csv(df, path):
    """Save DataFrame to CSV with UTF-8 encoding."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    _utils_log.info("Saved %d rows to %s", len(df), path)


def dedup_courses(grouped, course_col, overlap_threshold=0.8, min_shared=10):
    """Merge near-duplicate courses and recount n_courses.

    Two courses are considered duplicates if they share >= min_shared readings
    AND > overlap_threshold of the smaller course's readings.  This prevents
    false merges when courses share just 1-2 popular papers by coincidence.

    Modifies the grouped DataFrame in place: updates courses, institutions,
    and adds/updates n_courses.
    """
    from collections import defaultdict

    # Build course -> set of reading keys (row indices)
    course_readings = defaultdict(set)
    for idx, row in grouped.iterrows():
        courses = [c.strip() for c in row[course_col].split(" ; ")]
        for c in courses:
            if c:
                course_readings[c].add(idx)

    # Find courses that overlap significantly
    course_list = list(course_readings.keys())
    merged = {}  # course_name -> canonical_name
    for i, c1 in enumerate(course_list):
        if c1 in merged:
            continue
        for c2 in course_list[i + 1:]:
            if c2 in merged:
                continue
            s1, s2 = course_readings[c1], course_readings[c2]
            if not s1 or not s2:
                continue
            n_shared = len(s1 & s2)
            overlap = n_shared / min(len(s1), len(s2))
            if n_shared >= min_shared and overlap > overlap_threshold:
                canonical = c1 if len(c1) <= len(c2) else c2
                alias = c2 if canonical == c1 else c1
                merged[alias] = canonical
                _utils_log.info("Course dedup: '%s' -> '%s'",
                                alias[:50], canonical[:50])

    if not merged:
        grouped["n_courses"] = grouped[course_col].apply(
            lambda x: len(set(x.split(" ; "))) if x else 0)
        return grouped

    def apply_merge(courses_str):
        courses = [c.strip() for c in courses_str.split(" ; ")]
        deduped = []
        seen = set()
        for c in courses:
            canonical = merged.get(c, c)
            if canonical not in seen:
                deduped.append(canonical)
                seen.add(canonical)
        return " ; ".join(sorted(deduped))

    grouped[course_col] = grouped[course_col].apply(apply_merge)
    grouped["n_courses"] = grouped[course_col].apply(
        lambda x: len(set(x.split(" ; "))) if x else 0)

    _utils_log.info("Merged %d duplicate course names", len(merged))
    return grouped


def load_checkpoint(path):
    """Load records from a JSONL checkpoint file."""
    records = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        _utils_log.info("Loaded %d records from checkpoint %s", len(records), path)
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


# --- Progress monitoring ---

# Exit code for stuck-detection abort (EX_TEMPFAIL from sysexits.h)
EX_STUCK = 75


class WatchedProgress:
    """Rich progress bar with watchdog thread for stuck detection.

    Wraps ``rich.progress.Progress`` with:
    - Multi-task support, ETA column, throughput column
    - A daemon thread that checks each task's time-since-last-advance
    - If no advance for ``stuck_timeout`` seconds (default 300 = 5 min),
      fires ``notify-send``, calls ``flush_checkpoint``, and sets the
      ``on_stuck`` event (or raises SystemExit(75) if no event provided)
    - Registers a SIGTERM handler that flushes checkpoint before exit

    Parameters
    ----------
    stuck_timeout : float
        Seconds without progress before declaring stuck (default: 300).
    on_stuck : threading.Event | None
        If provided, set this event when stuck is detected instead of
        calling sys.exit(75). Useful for testing.
    flush_checkpoint : callable | None
        Called before exit on stuck detection or SIGTERM. Should save
        any in-progress work to disk.
    transient : bool
        If True, the progress display disappears after completion.
    disable : bool
        If True, disable the progress display (for non-TTY / CI).
    """

    def __init__(
        self,
        stuck_timeout: float = 300,
        on_stuck: threading.Event | None = None,
        flush_checkpoint: callable = None,
        transient: bool = False,
        disable: bool = False,
    ):
        self.stuck_timeout = stuck_timeout
        self.on_stuck = on_stuck
        self.flush_checkpoint = flush_checkpoint
        self._disable = disable

        self._progress = Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            MofNCompleteColumn(),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            transient=transient,
            disable=disable,
        )

        # Track last-advance time per task_id
        self._last_advance: dict[int, float] = {}
        self._lock = threading.Lock()
        self._stop_event = threading.Event()
        self._watchdog_thread: threading.Thread | None = None
        self._prev_sigterm = None

    def __enter__(self):
        self._progress.__enter__()
        self._install_sigterm_handler()
        self._start_watchdog()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._stop_event.set()
        if self._watchdog_thread is not None:
            self._watchdog_thread.join(timeout=2)
        self._restore_sigterm_handler()
        return self._progress.__exit__(exc_type, exc_val, exc_tb)

    def add_task(self, description: str, total: int = 100, **kwargs) -> int:
        """Add a new task to the progress display."""
        task_id = self._progress.add_task(description, total=total, **kwargs)
        with self._lock:
            self._last_advance[task_id] = time.monotonic()
        return task_id

    def advance(self, task_id: int, advance: float = 1):
        """Advance a task and reset its stuck timer."""
        self._progress.advance(task_id, advance)
        with self._lock:
            self._last_advance[task_id] = time.monotonic()

    def update(self, task_id: int, **kwargs):
        """Update task fields (description, total, etc.)."""
        self._progress.update(task_id, **kwargs)
        # If 'advance' or 'completed' changed, reset timer
        if "advance" in kwargs or "completed" in kwargs:
            with self._lock:
                self._last_advance[task_id] = time.monotonic()

    def _start_watchdog(self):
        """Launch daemon thread that polls for stuck tasks."""
        self._watchdog_thread = threading.Thread(
            target=self._watchdog_loop, daemon=True, name="progress-watchdog"
        )
        self._watchdog_thread.start()

    def _watchdog_loop(self):
        """Check every second if any task exceeded stuck_timeout."""
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=1.0)
            if self._stop_event.is_set():
                return
            now = time.monotonic()
            with self._lock:
                for task_id, last in self._last_advance.items():
                    if now - last > self.stuck_timeout:
                        self._handle_stuck(task_id)
                        return

    def _handle_stuck(self, task_id):
        """React to a stuck task: notify, flush, signal."""
        task = self._progress.tasks[task_id]
        msg = (
            f"Pipeline stuck: '{task.description}' has not advanced "
            f"for {self.stuck_timeout}s"
        )
        _utils_log.warning(msg)

        # Desktop notification (best-effort, ignore failures)
        try:
            subprocess.run(
                ["notify-send", "--urgency=critical", "Pipeline stuck", msg],
                check=False,
                timeout=5,
            )
        except FileNotFoundError:
            pass  # notify-send not installed

        # Flush checkpoint
        if self.flush_checkpoint is not None:
            try:
                self.flush_checkpoint()
            except Exception as exc:
                _utils_log.warning("Checkpoint flush failed: %s", exc)

        # Signal stuck
        if self.on_stuck is not None:
            self.on_stuck.set()
        else:
            raise SystemExit(EX_STUCK)

    def _install_sigterm_handler(self):
        """Intercept SIGTERM to flush checkpoint before exit."""
        try:
            self._prev_sigterm = signal.getsignal(signal.SIGTERM)
            signal.signal(signal.SIGTERM, self._sigterm_handler)
        except (OSError, ValueError):
            pass  # not main thread or signal not available

    def _restore_sigterm_handler(self):
        """Restore previous SIGTERM handler."""
        try:
            if self._prev_sigterm is not None:
                signal.signal(signal.SIGTERM, self._prev_sigterm)
        except (OSError, ValueError):
            pass

    def _sigterm_handler(self, signum, frame):
        """Flush checkpoint on SIGTERM, then re-raise."""
        _utils_log.info("SIGTERM received — flushing checkpoint before exit")
        if self.flush_checkpoint is not None:
            try:
                self.flush_checkpoint()
            except Exception as exc:
                _utils_log.warning("Checkpoint flush on SIGTERM failed: %s", exc)
        raise SystemExit(128 + signum)


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
    _utils_log.info("Saved → %s.png%s", os.path.basename(path_stem),
                     "" if no_pdf else " + .pdf")


# --- Enrichment priority ---

def compute_priority_scores(works_df: pd.DataFrame) -> pd.DataFrame:
    """Return works_df with a deterministic ``_priority`` score column and
    per-component ``_score_*`` columns (higher score = process first).

    Priority is based on:
    - ``_score_cited``   : raw ``cited_by_count`` (normalised: most-cited first)
    - ``_score_sources`` : ``source_count`` × 10  (multi-source works first)
    - ``_score_year``    : (year − 1990) × 0.01   (slight recency bonus)
    - ``_score_tiebreak``: stable MD5 hash of DOI  (fully deterministic)

    The function is pure: same input rows → same scores, regardless of row order.
    """
    import hashlib

    df = works_df.copy()

    cited = pd.to_numeric(df.get("cited_by_count", pd.Series(0, index=df.index)),
                          errors="coerce").fillna(0).clip(lower=0)

    sources = pd.to_numeric(df.get("source_count", pd.Series(1, index=df.index)),
                            errors="coerce").fillna(1).clip(lower=0)

    year = pd.to_numeric(df.get("year", pd.Series(1990, index=df.index)),
                         errors="coerce").fillna(1990)

    doi_str = df["doi"].fillna("").astype(str)
    tiebreak = doi_str.apply(
        lambda d: int(hashlib.md5(d.encode()).hexdigest(), 16) % 1_000_000 / 1_000_000
    )

    df["_score_cited"] = cited.values
    df["_score_sources"] = (sources * 10).values
    df["_score_year"] = ((year - 1990) * 0.01).values
    df["_score_tiebreak"] = tiebreak.values
    df["_priority"] = (
        df["_score_cited"] + df["_score_sources"] + df["_score_year"] + df["_score_tiebreak"]
    )

    return df


def sort_dois_by_priority(dois: list, works_df: pd.DataFrame) -> list:
    """Return *dois* sorted by descending priority score.

    DOIs absent from ``works_df`` are appended at the end (score = 0),
    preserving their relative insertion order for stability.

    Parameters
    ----------
    dois:      List of normalised DOI strings to sort.
    works_df:  Works DataFrame with at minimum a ``doi`` column.

    Returns
    -------
    Sorted list of DOIs (highest priority first).
    """
    scored = compute_priority_scores(works_df)
    doi_to_priority = dict(zip(
        scored["doi"].fillna("").astype(str),
        scored["_priority"],
    ))
    return sorted(dois, key=lambda d: doi_to_priority.get(d, -1), reverse=True)
