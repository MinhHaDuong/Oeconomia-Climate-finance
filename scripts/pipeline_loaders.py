"""Configuration and data loaders for the literature indexing pipeline.

Owns all path constants and provides functions to load config YAMLs,
corpus DataFrames, embeddings, and citation edges.

Exports
-------
BASE_DIR, CONFIG_DIR, DATA_DIR, CATALOGS_DIR, EXPORTS_DIR, RAW_DIR, POOL_DIR
    Canonical project-level path constants.
EMBEDDINGS_PATH, EMBEDDINGS_CACHE_DIR, EMBEDDINGS_CACHE_PATH
    Paths to embeddings artifacts.
REFINED_WORKS_PATH, REFINED_EMBEDDINGS_PATH, REFINED_CITATIONS_PATH
    Phase 1 → Phase 2 contract artifacts.
load_collect_config
    Load config/corpus_collect.yaml (Phase 1 collection parameters).
load_analysis_config
    Load config/analysis.yaml (Phase 2 analysis parameters).
load_analysis_periods
    Derive period tuples and labels from config/analysis.yaml.
load_cluster_labels
    Load cluster_labels.json with fallback to generic labels.
work_key
    Stable key for a work: DOI preferred, then source_id, then title hash.
load_embeddings
    Load embedding vectors from the .npz cache (legacy path).
load_refined_embeddings
    Load embedding vectors aligned 1:1 with refined_works.csv.
load_refined_citations
    Load citation edges restricted to refined_works.csv source DOIs.
load_analysis_corpus
    Load refined_works.csv with standard filtering + optional embeddings.
"""

import json
import logging
import os

import pandas as pd
from dotenv import load_dotenv

_log = logging.getLogger("pipeline.loaders")

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

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

_CLUSTER_LABELS_PATH = os.path.join(BASE_DIR, "content", "tables", "cluster_labels.json")


# ---------------------------------------------------------------------------
# Config loaders
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Corpus / embeddings / citations loaders
# ---------------------------------------------------------------------------

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
        _log.info("v1_only: restricting to %d / %d rows",
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
