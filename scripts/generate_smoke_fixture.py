#!/usr/bin/env python3
"""Generate a tiny smoke fixture from the full corpus.

Samples 100 rows from refined_works.csv (stratified by source provenance
to preserve diversity), plus matching embeddings and citations.

Usage:
    uv run python scripts/generate_smoke_fixture.py

Reads from data/catalogs/ (full corpus), writes to tests/fixtures/smoke/.
Run from the repo root after `dvc pull` to regenerate.
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd

from utils import get_logger

log = get_logger("generate_smoke_fixture")

# Paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
# Allow override via env var (useful when running from a worktree without data)
_data_override = os.environ.get("CLIMATE_FINANCE_DATA")
CATALOGS = _data_override or os.path.join(BASE_DIR, "data", "catalogs")
FIXTURE_DIR = os.path.join(BASE_DIR, "tests", "fixtures", "smoke")

N_SAMPLE = 100
SEED = 42


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=FIXTURE_DIR,
                        help="Output directory for fixture files")
    args = parser.parse_args()

    out_dir = args.output
    os.makedirs(out_dir, exist_ok=True)

    # ── Load full corpus ──────────────────────────────────────
    log.info("Loading refined_works.csv...")
    df = pd.read_csv(os.path.join(CATALOGS, "refined_works.csv"))
    log.info("Full corpus: %d rows, %d columns", len(df), len(df.columns))

    # ── Stratified sample ─────────────────────────────────────
    rng = np.random.default_rng(SEED)

    # Ensure we get some high-cited papers (for core-only tests)
    df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0)
    core_mask = df["cited_by_count"] >= 50

    # Reserve 20 core papers, 80 from the rest
    n_core = min(20, core_mask.sum())
    n_rest = N_SAMPLE - n_core

    core_idx = rng.choice(df.index[core_mask], size=n_core, replace=False)
    rest_pool = df.index[~df.index.isin(core_idx)]
    rest_idx = rng.choice(rest_pool, size=min(n_rest, len(rest_pool)), replace=False)

    sample_idx = np.sort(np.concatenate([core_idx, rest_idx]))
    sample = df.iloc[sample_idx].reset_index(drop=True)
    log.info("Sample: %d rows (%d core, %d rest)", len(sample), n_core, len(rest_idx))

    # Truncate abstracts to save space (keep first 200 chars)
    if "abstract" in sample.columns:
        sample["abstract"] = sample["abstract"].fillna("").str[:200]

    # ── Write refined_works.csv ───────────────────────────────
    works_path = os.path.join(out_dir, "refined_works.csv")
    sample.to_csv(works_path, index=False)
    log.info("Wrote %s (%s bytes)", works_path, f"{os.path.getsize(works_path):,}")

    # ── Aligned embeddings ────────────────────────────────────
    log.info("Loading refined_embeddings.npz...")
    all_emb = np.load(os.path.join(CATALOGS, "refined_embeddings.npz"))["vectors"]
    log.info("Full embeddings: %s", all_emb.shape)

    sample_emb = all_emb[sample_idx]
    emb_path = os.path.join(out_dir, "refined_embeddings.npz")
    np.savez_compressed(emb_path, vectors=sample_emb)
    log.info("Wrote %s (%s bytes)", emb_path, f"{os.path.getsize(emb_path):,}")

    # ── Citations (subset to sampled DOIs) ────────────────────
    log.info("Loading refined_citations.csv...")
    cit = pd.read_csv(os.path.join(CATALOGS, "refined_citations.csv"),
                       dtype=str, keep_default_na=False)
    log.info("Full citations: %d rows", len(cit))

    sample_dois = set(sample["doi"].dropna().str.lower())
    cit_subset = cit[cit["source_doi"].str.lower().isin(sample_dois)]
    # Cap citations to keep fixture under 1 MB — keep first N edges per source
    if len(cit_subset) > 2000:
        cit_subset = (
            cit_subset.groupby("source_doi", sort=False)
            .head(30)
            .reset_index(drop=True)
        )
    cit_path = os.path.join(out_dir, "refined_citations.csv")
    cit_subset.to_csv(cit_path, index=False)
    log.info("Wrote %s (%s bytes)", cit_path, f"{os.path.getsize(cit_path):,}")

    # ── Summary ───────────────────────────────────────────────
    total = sum(
        os.path.getsize(os.path.join(out_dir, f))
        for f in os.listdir(out_dir)
        if not f.startswith(".")
    )
    log.info("Total fixture size: %s bytes (%d KB)", f"{total:,}", total // 1024)
    if total > 1_000_000:
        log.error("Fixture exceeds 1 MB target!")
        sys.exit(1)


if __name__ == "__main__":
    main()
