"""I/O utilities for the literature indexing pipeline.

Covers all external I/O: HTTP requests with retry, CSV persistence,
checkpoint files, pool storage (gzipped JSONL), run reports, figure saving,
and teaching-data helpers (dedup_courses).

Exports
-------
MAILTO, POLITE_MAX_RETRIES, RETRY_MAX_RETRIES
    Constants used by HTTP helpers.
polite_get
    HTTP GET with polite delay and automatic retry (catalog scrapers).
retry_get
    HTTP GET with bounded exponential backoff (enrichment scripts).
save_csv
    Save a DataFrame to CSV with UTF-8 encoding.
save_run_report
    Persist a run-summary dict as JSON in catalogs/run_reports/.
make_run_id
    Return a UTC timestamp string suitable for use as a run-id.
load_checkpoint, append_checkpoint, delete_checkpoint
    JSONL checkpoint helpers for resumable enrichment runs.
pool_path, append_to_pool, load_pool_ids, load_pool_records
    Append-only raw pool storage in gzipped JSONL files.
save_figure
    Save a matplotlib figure as PNG (+ optional PDF), byte-reproducible.
dedup_courses
    Merge near-duplicate courses in a teaching-readings DataFrame.
"""

import gzip
import json
import logging
import os
import random
import re
import time
from typing import TYPE_CHECKING, Any

import pandas as pd
import requests  # type: ignore[import-untyped]

if TYPE_CHECKING:
    from matplotlib.figure import Figure

_log = logging.getLogger("pipeline.io")

# ---------------------------------------------------------------------------
# HTTP constants (single source of truth)
# ---------------------------------------------------------------------------

MAILTO = "minh.ha-duong@cnrs.fr"
OPENALEX_API_KEY = os.environ.get("OPENALEX_API_KEY", "")

# Retry budgets — single source of truth for polite_get and retry_get defaults
POLITE_MAX_RETRIES = 3   # catalog scrapers (quick, many URLs)
RETRY_MAX_RETRIES = 5    # enrichment fetchers (heavy, fewer URLs)


# ---------------------------------------------------------------------------
# HTTP helpers
# ---------------------------------------------------------------------------

def polite_get(url: str, params: dict[str, Any] | None = None,
               headers: dict[str, str] | None = None, delay: float = 0.2,
               max_retries: int = POLITE_MAX_RETRIES) -> requests.Response:
    """HTTP GET with polite delay, exponential backoff+jitter, retry on 429/5xx.

    Delegates to retry_get. All callers (OpenAlex, ISTEX, World Bank, syllabi)
    get POLITE_MAX_RETRIES retries with 5xx handling.
    """
    return retry_get(url, params=params, headers=headers, delay=delay,
                     max_retries=max_retries, timeout=30)


def retry_get(url: str, params: dict[str, Any] | None = None,
              headers: dict[str, str] | None = None, delay: float = 0.2,
              max_retries: int = RETRY_MAX_RETRIES,
              timeout: float = 60, counters: dict[str, int] | None = None,
              backoff_base: float = 2.0, jitter_max: float = 1.0) -> requests.Response:
    """HTTP GET with bounded exponential backoff+jitter and optional counter tracking.

    Parameters
    ----------
    url : str
        Request URL.
    params : dict, optional
        Query parameters.
    headers : dict, optional
        HTTP headers.
    delay : float
        Base polite delay before each attempt (seconds).
    max_retries : int
        Maximum retry attempts for 429/5xx/timeout.
    timeout : float
        Per-request timeout in seconds.
    counters : dict, optional
        Mutable dict updated with keys ``retries``, ``rate_limited``,
        ``server_errors``, ``client_errors``.
    backoff_base : float
        Base for exponential backoff (seconds).
    jitter_max : float
        Maximum random jitter added to each backoff (seconds).

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
            _log.warning("Timeout on attempt %d/%d, retrying in %.1fs...",
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
                _log.warning("Rate limited (429) after %d attempts, returning response.",
                             max_retries)
                return resp
            retry_after = min(
                int(resp.headers.get("Retry-After", backoff_base ** (attempt + 1))), 120
            )
            jitter = random.uniform(0, min(jitter_max * 2, 2))
            wait = retry_after + jitter
            _log.warning("Rate limited (429), waiting %.1fs...", wait)
            time.sleep(wait)
            continue
        if resp.status_code >= 500:
            counters["server_errors"] = counters.get("server_errors", 0) + 1
            counters["retries"] = counters.get("retries", 0) + 1
            backoff = min(backoff_base ** attempt + random.uniform(0, jitter_max), 60)
            _log.warning("Server error %d on attempt %d/%d, retrying in %.1fs...",
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


# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

def save_csv(df: pd.DataFrame, path: str) -> None:
    """Save DataFrame to CSV with UTF-8 encoding (atomic write-then-rename)."""
    import tempfile

    target_dir = os.path.dirname(path) or "."
    os.makedirs(target_dir, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=target_dir, suffix=".tmp")
    try:
        os.close(fd)
        df.to_csv(tmp_path, index=False, encoding="utf-8")
        os.replace(tmp_path, path)
    except BaseException:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise
    _log.info("Saved %d rows to %s", len(df), path)


# ---------------------------------------------------------------------------
# Run reports
# ---------------------------------------------------------------------------

def save_run_report(data: dict[str, Any], run_id: str, script_name: str) -> str:
    """Persist a structured run-summary dict as JSON in catalogs/run_reports/.

    Parameters
    ----------
    data : dict
        Counters / metadata to save.
    run_id : str
        Unique run identifier (e.g. timestamp or ``--run-id`` value).
    script_name : str
        Short script name used as filename prefix.

    Returns
    -------
    Path to the saved JSON file (str).

    """
    from pipeline_loaders import CATALOGS_DIR  # avoid circular import

    reports_dir = os.path.join(CATALOGS_DIR, "run_reports")
    os.makedirs(reports_dir, exist_ok=True)
    safe_run_id = re.sub(r"[^\w.-]", "_", run_id)
    filename = f"{script_name}__{safe_run_id}.json"
    path = os.path.join(reports_dir, filename)
    payload = {"script": script_name, "run_id": run_id, **data}
    with open(path, "w") as f:
        json.dump(payload, f, indent=2, default=str)
    return path


def make_run_id() -> str:
    """Return a UTC timestamp string suitable for use as a run-id."""
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())


# ---------------------------------------------------------------------------
# Checkpoint helpers (resumable enrichment)
# ---------------------------------------------------------------------------

def load_checkpoint(path: str) -> list[dict[str, Any]]:
    """Load records from a JSONL checkpoint file."""
    records = []
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    records.append(json.loads(line))
        _log.info("Loaded %d records from checkpoint %s", len(records), path)
    return records


def append_checkpoint(records: list[dict[str, Any]], path: str) -> None:
    """Append records to a JSONL checkpoint file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def delete_checkpoint(path: str) -> None:
    """Remove checkpoint file after successful completion."""
    if os.path.exists(path):
        os.remove(path)


# ---------------------------------------------------------------------------
# Pool helpers (append-only raw storage, gzipped JSONL)
# ---------------------------------------------------------------------------

def pool_path(source: str, slug: str) -> str:
    """Return path for a raw pool JSONL.gz file.

    Example: pool_path("openalex", "climate_finance")
      → ~/data/.../pool/openalex/climate_finance.jsonl.gz
    """
    from pipeline_loaders import POOL_DIR  # avoid circular import

    d = os.path.join(POOL_DIR, source)
    os.makedirs(d, exist_ok=True)
    safe_slug = re.sub(r"[^\w\-]", "_", slug.lower())
    return os.path.join(d, f"{safe_slug}.jsonl.gz")


def append_to_pool(records: list[dict[str, Any]], path: str) -> None:
    """Append raw API response dicts to a gzipped JSONL pool file."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with gzip.open(path, "at", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def load_pool_ids(source: str, id_field: str = "id") -> set[str]:
    """Scan all .jsonl.gz files in a source's pool dir, return set of IDs.

    Args:
        source: pool subdirectory name (e.g. "openalex")
        id_field: JSON field to extract as ID (default: "id")

    Returns:
        set of ID strings already in the pool

    """
    from pipeline_loaders import POOL_DIR  # avoid circular import

    source_dir = os.path.join(POOL_DIR, source)
    ids: set[str] = set()
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


def load_pool_records(source: str) -> list[dict[str, Any]]:
    """Load all raw records from a source's pool directory.

    Returns:
        list of dicts (raw API responses)

    """
    from pipeline_loaders import POOL_DIR  # avoid circular import

    source_dir = os.path.join(POOL_DIR, source)
    records: list[dict[str, Any]] = []
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


# ---------------------------------------------------------------------------
# Figure saving
# ---------------------------------------------------------------------------

def save_figure(fig: "Figure", path_stem: str, no_pdf: bool = False, dpi: int = 150) -> None:
    """Save figure as PNG and optionally PDF.

    Produces byte-identical output across runs by stripping volatile
    metadata (Software version, creation timestamps).
    """
    import os as _os
    _meta = {"Software": None, "Creation Time": None}
    fig.savefig(f"{path_stem}.png", dpi=dpi, bbox_inches="tight",
                metadata=_meta, pil_kwargs={"optimize": False})
    if not no_pdf:
        fig.savefig(f"{path_stem}.pdf", dpi=max(dpi, 300), bbox_inches="tight")
    _log.info("Saved → %s.png%s", _os.path.basename(path_stem),
              "" if no_pdf else " + .pdf")


# ---------------------------------------------------------------------------
# Teaching-data helpers
# ---------------------------------------------------------------------------

def dedup_courses(grouped: pd.DataFrame, course_col: str, overlap_threshold: float = 0.8, min_shared: int = 10) -> pd.DataFrame:
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
                _log.info("Course dedup: '%s' -> '%s'",
                          alias[:50], canonical[:50])

    if not merged:
        grouped["n_courses"] = grouped[course_col].apply(
            lambda x: len(set(x.split(" ; "))) if x else 0)
        return grouped

    def apply_merge(courses_str: str) -> str:
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

    _log.info("Merged %d duplicate course names", len(merged))
    return grouped
