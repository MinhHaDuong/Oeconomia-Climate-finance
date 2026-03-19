#!/usr/bin/env python3
"""Produce row-aligned Phase 1 → Phase 2 canonical artifacts.

Reads the Phase 1 cache files and produces two aligned outputs:

  refined_embeddings.npz
    Embedding vectors aligned 1:1 with refined_works.csv rows.
    refined_embeddings.npz[vectors][i] corresponds to refined_works.csv row i.

  refined_citations.csv
    Citation edges restricted to source_doi values in refined_works.csv.

These aligned files are the canonical Phase 2 contract inputs.  The full
``embeddings.npz`` and ``citations.csv`` caches remain as enrichment
internals and are NOT to be used directly by Phase 2 scripts.

Invariants enforced:
  - refined_embeddings.npz["vectors"].shape[0] == len(refined_works.csv)
  - All refined_citations.csv.source_doi ∈ normalize_doi(refined_works.csv.doi)

Usage:
    uv run python scripts/corpus_align.py [--run-id ID] [--dry-run]
"""

import argparse
import os
import sys
import time

import numpy as np
import pandas as pd

from utils import (
    CATALOGS_DIR, EMBEDDINGS_PATH, REFS_COLUMNS,
    REFINED_WORKS_PATH, REFINED_EMBEDDINGS_PATH, REFINED_CITATIONS_PATH,
    get_logger, normalize_doi, save_run_report, make_run_id,
)

log = get_logger("corpus_align")

CITATIONS_PATH = os.path.join(CATALOGS_DIR, "citations.csv")


def align_embeddings(refined_df, emb_path=None, dry_run=False):
    """Build refined_embeddings.npz aligned row-by-row with refined_df.

    Parameters
    ----------
    refined_df: DataFrame loaded from refined_works.csv (canonical row order).
    emb_path:   Path to embeddings.npz cache. Defaults to EMBEDDINGS_PATH.
    dry_run:    If True, skip file existence check (for testing).

    Matching key: doi (normalised), then source_id as fallback for works
    without a DOI.

    Returns
    -------
    tuple(np.ndarray, int, int)
        (vectors array of shape (N, D), n_matched, n_zero_fallback)
        n_zero_fallback: rows matched to zero-vector because embedding missing.
    """
    path = emb_path or EMBEDDINGS_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"embeddings.npz not found at {path}. "
            "Run: make corpus-enrich"
        )

    data = np.load(path, allow_pickle=True)
    vectors_all = data["vectors"]   # (M, D) full cache
    keys = data.get("keys", None)   # optional: array of DOIs/source_ids

    D = vectors_all.shape[1]
    N = len(refined_df)

    # Build key → row-index mapping for the full embedding cache
    if keys is not None:
        key_arr = np.array(keys, dtype=str)
        key_to_idx = {k: i for i, k in enumerate(key_arr)}
    else:
        # Fallback: no key array → cannot align, return zeros with warning
        log.warning("embeddings.npz has no 'keys' array; "
                    "cannot align -- all refined_embeddings will be zero vectors.")
        aligned = np.zeros((N, D), dtype=vectors_all.dtype)
        return aligned, 0, N

    # Map each refined work to its embedding row index
    doi_norm = refined_df["doi"].apply(normalize_doi)
    source_id = refined_df["source_id"].fillna("").astype(str)

    aligned = np.zeros((N, D), dtype=vectors_all.dtype)
    n_matched = 0
    n_zero_fallback = 0

    for i in range(N):
        idx = key_to_idx.get(doi_norm.iloc[i])
        if idx is None:
            idx = key_to_idx.get(source_id.iloc[i])
        if idx is not None:
            aligned[i] = vectors_all[idx]
            n_matched += 1
        else:
            n_zero_fallback += 1

    return aligned, n_matched, n_zero_fallback


def align_citations(refined_doi_set, cit_path=None, dry_run=False):
    """Filter citations.csv to rows whose source_doi is in refined_doi_set.

    Parameters
    ----------
    refined_doi_set: set of normalised DOIs in refined_works.csv.
    cit_path:        Path to citations.csv. Defaults to CITATIONS_PATH.

    Returns
    -------
    tuple(pd.DataFrame, int, int)
        (filtered DataFrame, total_rows_in, rows_kept)
    """
    path = cit_path or CITATIONS_PATH
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"citations.csv not found at {path}. "
            "Run: make citations"
        )

    citations = pd.read_csv(path, low_memory=False)
    total_in = len(citations)

    citations["_norm_doi"] = citations["source_doi"].apply(normalize_doi)
    mask = citations["_norm_doi"].isin(refined_doi_set)
    filtered = citations[mask].drop(columns=["_norm_doi"]).reset_index(drop=True)

    return filtered, total_in, len(filtered)


def main():
    parser = argparse.ArgumentParser(
        description="Align embeddings and citations to refined_works.csv row order"
    )
    parser.add_argument("--run-id", default=None,
                        help="Unique run identifier for the run report (default: timestamp)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Check inputs and print counts without writing outputs")
    parser.add_argument("--refined-works",
                        default=REFINED_WORKS_PATH,
                        help="Input refined_works.csv path")
    parser.add_argument("--embeddings",
                        default=EMBEDDINGS_PATH,
                        help="Input embeddings.npz path (full cache)")
    parser.add_argument("--citations",
                        default=CITATIONS_PATH,
                        help="Input citations.csv path (full graph)")
    parser.add_argument("--out-embeddings",
                        default=REFINED_EMBEDDINGS_PATH,
                        help="Output refined_embeddings.npz path")
    parser.add_argument("--out-citations",
                        default=REFINED_CITATIONS_PATH,
                        help="Output refined_citations.csv path")
    args = parser.parse_args()

    run_id = args.run_id or make_run_id()
    t0 = time.time()

    # ── Load refined works ────────────────────────────────────────────────
    if not os.path.exists(args.refined_works):
        log.error("refined_works.csv not found at %s. Run: make corpus-filter",
                  args.refined_works)
        sys.exit(1)

    refined_df = pd.read_csv(args.refined_works, dtype=str, keep_default_na=False)
    N = len(refined_df)
    log.info("Loaded %d rows from %s", N, args.refined_works)

    refined_doi_set = set(
        normalize_doi(d) for d in refined_df["doi"]
        if normalize_doi(d) not in ("", "nan", "none")
    )
    log.info("  Unique normalised DOIs: %d", len(refined_doi_set))

    # ── Align embeddings ─────────────────────────────────────────────────
    log.info("Aligning embeddings from %s ...", args.embeddings)
    aligned_vectors, n_matched, n_zero = align_embeddings(
        refined_df, emb_path=args.embeddings, dry_run=args.dry_run
    )
    log.info("  Shape: %s  (matched: %d, zero-fallback: %d)",
             aligned_vectors.shape, n_matched, n_zero)

    # Invariant check
    assert aligned_vectors.shape[0] == N, (
        f"BUG: aligned_vectors has {aligned_vectors.shape[0]} rows, "
        f"expected {N} (== len(refined_works.csv))"
    )

    if not args.dry_run:
        os.makedirs(os.path.dirname(args.out_embeddings) or ".", exist_ok=True)
        np.savez_compressed(args.out_embeddings, vectors=aligned_vectors)
        log.info("  Saved -> %s", args.out_embeddings)

    # ── Align citations ──────────────────────────────────────────────────
    log.info("Filtering citations from %s ...", args.citations)
    filtered_cit, total_cit_in, n_cit_kept = align_citations(
        refined_doi_set, cit_path=args.citations, dry_run=args.dry_run
    )
    log.info("  Total citation rows: %d", total_cit_in)
    log.info("  Kept (source_doi in refined): %d", n_cit_kept)
    log.info("  Dropped: %d", total_cit_in - n_cit_kept)

    if not args.dry_run:
        os.makedirs(os.path.dirname(args.out_citations) or ".", exist_ok=True)
        filtered_cit.to_csv(args.out_citations, index=False)
        log.info("  Saved -> %s", args.out_citations)

    elapsed = time.time() - t0
    log.info("Done in %.1fs", elapsed)

    if args.dry_run:
        log.info("Dry run -- no files written.")
        return

    counters = {
        "refined_works_rows": N,
        "refined_dois": len(refined_doi_set),
        "embedding_vectors_total": aligned_vectors.shape[0],
        "embedding_dim": aligned_vectors.shape[1],
        "embeddings_matched": n_matched,
        "embeddings_zero_fallback": n_zero,
        "citations_total_in": total_cit_in,
        "citations_kept": n_cit_kept,
        "citations_dropped": total_cit_in - n_cit_kept,
        "elapsed_seconds": round(elapsed, 1),
    }
    report_path = save_run_report(counters, run_id, "corpus_align")
    log.info("Run report: %s", report_path)


if __name__ == "__main__":
    main()
