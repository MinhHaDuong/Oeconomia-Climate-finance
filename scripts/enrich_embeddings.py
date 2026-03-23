"""Encode corpus works into multilingual sentence embeddings.

Phase 1 enrichment step: produces embeddings.npz with vectors + metadata.
UMAP projection and clustering are Phase 2 (analyze_embeddings.py).

Method:
- Embed titles, abstracts, and keywords with a multilingual sentence-transformer
- Incremental caching: only new works are encoded (keyed by DOI/source_id)

Produces:
- data/catalogs/embeddings.npz: DVC output (vectors + metadata)
- data/catalogs/enrich_cache/embeddings_cache.npz: Incremental cache (survives DVC re-runs)
"""

import argparse
import os

# Suppress HuggingFace download/progress bars for clean nohup logs
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import numpy as np
import pandas as pd

from utils import (CATALOGS_DIR, EMBEDDINGS_CACHE_DIR, EMBEDDINGS_CACHE_PATH,
                   EMBEDDINGS_PATH, get_logger, load_analysis_config, work_key)

log = get_logger("enrich_embeddings")

# --- Configuration ---
MODEL_NAME = "paraphrase-multilingual-MiniLM-L12-v2"
TEXT_FIELDS = "title+abstract+keywords"
EMBEDDING_DIM = 384


def build_text(row):
    """Concatenate title, abstract, and keywords for embedding."""
    parts = [str(row["title"])]
    abstract = row.get("abstract")
    if pd.notna(abstract) and len(str(abstract)) > 20:
        parts.append(str(abstract))
    keywords = row.get("keywords")
    if pd.notna(keywords):
        parts.append(str(keywords).replace(";", ", "))
    return ". ".join(parts)


def text_hash(text):
    """Short hash of the text that was embedded, to detect content changes."""
    import hashlib
    return hashlib.md5(text.encode()).hexdigest()[:8]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--works-input",
        default=os.path.join(CATALOGS_DIR, "unified_works.csv"),
        help="Works CSV to embed (default: unified_works.csv)",
    )
    args = parser.parse_args()

    # Defer heavy imports so --help works without corpus group installed
    import torch
    from sentence_transformers import SentenceTransformer

    # --- Load data ---
    log.info("Loading works from %s...", args.works_input)
    works = pd.read_csv(args.works_input)

    # Filter: must have a title, year in range (from config)
    _cfg = load_analysis_config()
    _year_min = _cfg["periodization"]["year_min"]
    _year_max = _cfg["periodization"]["year_max"]
    has_title = works["title"].notna() & (works["title"].str.len() > 0)
    in_range = (works["year"] >= _year_min) & (works["year"] <= _year_max)
    df = works[has_title & in_range].copy().reset_index(drop=True)
    log.info("Works with titles (%d-%d): %d", _year_min, _year_max, len(df))

    # Build keys, text, and text hashes
    df["_key"] = df.apply(work_key, axis=1)
    df["_text"] = df.apply(build_text, axis=1)
    df["_thash"] = df["_text"].apply(text_hash)

    # --- Incremental embedding cache ---
    # Cache lives in enrich_cache/ (not a DVC output), so DVC re-runs
    # don't destroy already-computed vectors. The DVC output (EMBEDDINGS_PATH)
    # is written at the end as an ephemeral artifact.
    legacy_path = os.path.join(CATALOGS_DIR, "embeddings.npy")

    def _load_npz_cache(path):
        """Try to load cached embeddings from an .npz file.

        Returns (key_to_vec, key_to_hash) if model/fields match, else ({}, {}).
        """
        cache = np.load(path, allow_pickle=True)
        cached_model = str(cache["model"]) if "model" in cache.files else ""
        cached_fields = str(cache["text_fields"]) if "text_fields" in cache.files else ""
        if cached_model != MODEL_NAME or cached_fields != TEXT_FIELDS:
            log.info("Config changed (model: %r→%r, fields: %r→%r), full recompute",
                     cached_model, MODEL_NAME, cached_fields, TEXT_FIELDS)
            return {}, {}
        cached_keys = cache["keys"]
        cached_vecs = cache["vectors"]
        cached_hashes = cache["text_hashes"] if "text_hashes" in cache.files else None
        kvec = dict(zip(cached_keys, cached_vecs))
        khash = dict(zip(cached_keys, cached_hashes)) if cached_hashes is not None else {}
        return kvec, khash

    key_to_vec = {}   # key → vector
    key_to_hash = {}  # key → text hash (to detect content changes)
    if os.path.exists(EMBEDDINGS_CACHE_PATH):
        key_to_vec, key_to_hash = _load_npz_cache(EMBEDDINGS_CACHE_PATH)
        if key_to_vec:
            log.info("Loaded %d cached embeddings (model: %s, fields: %s)",
                     len(key_to_vec), MODEL_NAME, TEXT_FIELDS)
    elif os.path.exists(EMBEDDINGS_PATH):
        # Migration: old pattern stored cache in the DVC output itself
        key_to_vec, key_to_hash = _load_npz_cache(EMBEDDINGS_PATH)
        if key_to_vec:
            log.info("Migrated %d cached embeddings from DVC output → enrich_cache/",
                     len(key_to_vec))
    elif os.path.exists(legacy_path):
        log.info("Found legacy %s, will migrate to .npz (full recompute)", legacy_path)
    else:
        log.info("No embedding cache found, full computation")

    # A cached entry is valid only if key exists AND text hash matches
    keys = df["_key"].values
    thashes = df["_thash"].values
    hit_mask = np.array([
        k in key_to_vec and key_to_hash.get(k) == h
        for k, h in zip(keys, thashes)
    ])
    n_cached = int(hit_mask.sum())
    n_new = len(df) - n_cached
    n_stale = sum(1 for k in keys if k in key_to_vec) - n_cached
    if n_stale > 0:
        log.info("Embeddings: %d cached, %d stale, %d new", n_cached, n_stale, n_new - n_stale)
    else:
        log.info("Embeddings: %d cached, %d to compute", n_cached, n_new)

    # Encode only new works
    if n_new > 0:
        n_cpu = os.cpu_count() or 4
        torch.set_num_threads(n_cpu)
        log.info("Loading %s (%d threads)...", MODEL_NAME, n_cpu)
        model = SentenceTransformer(MODEL_NAME)

        new_texts = df.loc[~hit_mask, "_text"].tolist()
        log.info("Encoding %d texts...", n_new)
        new_vecs = model.encode(
            new_texts,
            batch_size=256,
            show_progress_bar=False,
            normalize_embeddings=True,
        )
    else:
        new_vecs = np.empty((0, EMBEDDING_DIM), dtype=np.float32)

    # Assemble full array in df order
    embeddings = np.empty((len(df), EMBEDDING_DIM), dtype=np.float32)
    if n_cached > 0:
        embeddings[hit_mask] = np.array([key_to_vec[k] for k in keys[hit_mask]])
    if n_new > 0:
        embeddings[~hit_mask] = new_vecs

    # Save incremental cache (survives DVC re-runs)
    os.makedirs(EMBEDDINGS_CACHE_DIR, exist_ok=True)
    cache_arrays = dict(
        vectors=embeddings,
        keys=keys,
        text_hashes=thashes,
        model=np.array(MODEL_NAME),
        text_fields=np.array(TEXT_FIELDS),
    )
    np.savez_compressed(EMBEDDINGS_CACHE_PATH, **cache_arrays)
    log.info("Saved %d embeddings cache → %s", len(embeddings), EMBEDDINGS_CACHE_PATH)

    # Save DVC output (ephemeral — may be deleted on next DVC repro)
    np.savez_compressed(EMBEDDINGS_PATH, **cache_arrays)
    log.info("Saved %d embeddings output → %s", len(embeddings), EMBEDDINGS_PATH)

    # Clean up legacy file
    if os.path.exists(legacy_path):
        os.remove(legacy_path)
        log.info("Removed legacy %s", legacy_path)

    log.info("Embedding shape: %s", embeddings.shape)


if __name__ == "__main__":
    main()
