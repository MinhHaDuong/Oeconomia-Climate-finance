"""Pool helpers for the literature indexing pipeline.

Append-only raw storage in gzipped JSONL files.

Extracted from utils.py — kept separate so that the core utils module
stays under the 800-line god-module threshold.

Exports
-------
pool_path        Return canonical path for a raw pool JSONL.gz file.
append_to_pool   Append raw API response dicts to a gzipped JSONL pool file.
load_pool_ids    Scan a source's pool dir and return the set of IDs already stored.
load_pool_records  Load all raw records from a source's pool directory.
"""

import gzip
import json
import os
import re

from utils import POOL_DIR


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
