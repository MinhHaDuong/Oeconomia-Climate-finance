"""Shared utilities for the literature indexing pipeline."""

import gzip
import json
import logging
import os
import random
import re
import time

import pandas as pd
import requests
from dotenv import load_dotenv


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
SOURCE_NAMES = ["openalex", "semanticscholar", "istex", "bibcnrs", "scispsace", "grey", "teaching"]
FROM_COLS = [f"from_{s}" for s in SOURCE_NAMES]

REFS_COLUMNS = [
    "source_doi", "source_id", "ref_doi", "ref_title", "ref_first_author",
    "ref_year", "ref_journal", "ref_raw",
]

# --- Polite pool ---

MAILTO = "minh.ha-duong@cnrs.fr"
OPENALEX_API_KEY = os.environ.get("OPENALEX_API_KEY", "")


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


def polite_get(url, params=None, headers=None, delay=0.2, max_retries=5):
    """HTTP GET with polite delay, exponential backoff+jitter, retry on 429/5xx.

    Delegates to retry_get. All callers (OpenAlex, ISTEX, World Bank, syllabi)
    now get 5 retries and 5xx handling — previously 3 retries, 429-only.
    """
    return retry_get(url, params=params, headers=headers, delay=delay,
                     max_retries=max_retries, timeout=30)


def retry_get(url, params=None, headers=None, delay=0.2, max_retries=5,
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


_CLUSTER_LABELS_PATH = os.path.join(CATALOGS_DIR, "cluster_labels.json")


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
        "Run: uv run python scripts/analyze_alluvial.py",
        stacklevel=2,
    )
    return {i: f"Cluster {i}" for i in range(n_clusters)}


# Embeddings live in a separate .npz rather than as columns in refined_works.csv:
# - Size: 384 floats × 30k rows as CSV text ≈ 500 MB vs. ~45 MB compressed binary
# - Incremental cache: stores keys + text hashes + model config so only new/changed
#   works are re-encoded on each run (~16 min full, seconds incremental)
# - Load speed: numpy reads the array in one shot; no parsing of 11M float strings
EMBEDDINGS_PATH = os.path.join(CATALOGS_DIR, "embeddings.npz")

# Phase 1 → Phase 2 aligned canonical artifacts (produced by corpus-align step).
# refined_embeddings.npz rows are 1:1 with refined_works.csv rows.
# refined_citations.csv source_doi values are a subset of refined_works.csv DOIs.
REFINED_WORKS_PATH = os.path.join(CATALOGS_DIR, "refined_works.csv")
REFINED_EMBEDDINGS_PATH = os.path.join(CATALOGS_DIR, "refined_embeddings.npz")
REFINED_CITATIONS_PATH = os.path.join(CATALOGS_DIR, "refined_citations.csv")


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


def load_analysis_corpus(core_only=False, with_embeddings=True, cite_threshold=50):
    """Load refined_works.csv with standard filtering + optional embeddings.

    Applies: year coercion, title-present filter, year in [1990, 2025],
    optional core filtering (cited_by_count >= cite_threshold).

    Returns (df, embeddings) where embeddings is None if with_embeddings=False.
    """
    import numpy as np

    works = pd.read_csv(REFINED_WORKS_PATH)
    works["year"] = pd.to_numeric(works["year"], errors="coerce")

    has_title = works["title"].notna() & (works["title"].str.len() > 0)
    in_range = (works["year"] >= 1990) & (works["year"] <= 2025)
    keep_mask = (has_title & in_range).values
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

    Returns dict with keys: year_min, year_max.
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
        return yaml.safe_load(f)


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


def save_csv(df, path):
    """Save DataFrame to CSV with UTF-8 encoding."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    df.to_csv(path, index=False, encoding="utf-8")
    _utils_log.info("Saved %d rows to %s", len(df), path)


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
