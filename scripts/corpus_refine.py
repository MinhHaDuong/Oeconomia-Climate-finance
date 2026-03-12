#!/usr/bin/env python3
"""Corpus refinement: flag noise -> verify flags -> filter.

Orchestrator that loads data, calls flag functions from refine_flags.py,
computes protection, verifies, and optionally applies the filter.

Reads:  data/catalogs/unified_works.csv, citations.csv, embeddings.npz
Writes: data/catalogs/refined_works.csv, data/catalogs/corpus_audit.csv

Usage:
    python scripts/corpus_refine.py              # flag + verify (dry run)
    python scripts/corpus_refine.py --apply      # flag + verify + apply filter
    python scripts/corpus_refine.py --skip-llm   # skip LLM scoring + audit
    python scripts/corpus_refine.py --cheap      # flags 1-3 only
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from refine_flags import (
    _load_config,
    compute_protection,
    flag_citation_isolated,
    flag_llm_irrelevant_streaming,
    flag_missing_metadata,
    flag_no_abstract,
    flag_semantic_outlier,
    flag_title_blacklist,
)
from utils import CATALOGS_DIR, EMBEDDINGS_PATH, normalize_doi, save_csv

# --- Paths ---
CITATIONS_PATH = os.path.join(CATALOGS_DIR, "citations.csv")

# Flag column names (order matters for merging)
FLAG_COLUMNS = [
    "missing_metadata", "no_abstract_irrelevant", "title_blacklist",
    "citation_isolated_old", "semantic_outlier", "llm_irrelevant",
]

CHECKPOINT_EVERY = 5


# ============================================================
# Apply gates
# ============================================================

def expected_flag_columns(args, has_embeddings):
    """Return the flag columns that should exist given CLI flags and data availability.

    Flags 1-3 and protection are always required.
    Flag 4 is required unless --skip-citation-flag.
    Flag 5 is required only if embeddings were successfully loaded.
    Flag 6 is required unless --skip-llm.
    """
    cols = ["missing_metadata", "no_abstract_irrelevant", "title_blacklist"]
    if not args.skip_citation_flag:
        cols.append("citation_isolated_old")
    if has_embeddings:
        cols.append("semantic_outlier")
    if not args.skip_llm:
        cols.append("llm_irrelevant")
    return cols


def check_apply_gates(df, args, has_embeddings):
    """Raise RuntimeError if the pipeline is incomplete for --apply."""
    expected = expected_flag_columns(args, has_embeddings)
    missing = [c for c in expected if c not in df.columns]
    if missing:
        raise RuntimeError(f"Cannot --apply: missing flag columns {missing}")
    if "protected" not in df.columns:
        raise RuntimeError("Cannot --apply: protection not computed.")


# ============================================================
# Merge flags into combined list column
# ============================================================

def merge_flags(df, flag_columns):
    """Build combined 'flags' list column from individual boolean flag columns."""
    result = [[] for _ in range(len(df))]
    for col in flag_columns:
        if col not in df.columns:
            continue
        for i in df.index[df[col].fillna(False)]:
            if col == "semantic_outlier" and "semantic_outlier_dist" in df.columns:
                dist = df.at[i, "semantic_outlier_dist"]
                if pd.notna(dist):
                    result[i].append(f"semantic_outlier:{dist:.3f}")
                else:
                    result[i].append("semantic_outlier")
            elif col == "missing_metadata":
                # Reconstruct detail string for backward compat
                parts = []
                title_s = str(df.at[i, "title"]) if pd.notna(df.at[i, "title"]) else ""
                author_s = str(df.at[i, "first_author"]) if pd.notna(df.at[i, "first_author"]) else ""
                year_s = str(df.at[i, "year"]) if pd.notna(df.at[i, "year"]) else ""
                if title_s.strip() in ("", "nan"):
                    parts.append("title")
                if author_s.strip() in ("", "nan"):
                    parts.append("author")
                if year_s.strip() in ("", "nan"):
                    parts.append("year")
                result[i].append(f"missing_metadata:{','.join(parts)}" if parts else "missing_metadata")
            else:
                result[i].append(col)
    return result


# ============================================================
# Verification (kept here for backward compat)
# ============================================================

def verify_blacklist(df, config):
    """Check that every noise term in corpus titles is caught by flag 3."""
    from refine_flags import _has_safe_words

    noise_title = config["noise_title"]
    safe_title = config["safe_title"]

    print("\n=== C1: Blacklist validation ===")
    all_ok = True
    for noise_term in noise_title:
        matches = df[df["title"].str.lower().str.contains(noise_term, na=False)]
        flagged = matches[matches["flags"].apply(
            lambda f: "title_blacklist" in f)]
        unflagged = matches[~matches.index.isin(flagged.index)]

        truly_missed = unflagged[~unflagged["title"].apply(
            lambda t: _has_safe_words(str(t), safe_title))]

        if len(truly_missed) > 0:
            print(f"  WARNING: '{noise_term}' -- {len(truly_missed)} missed:")
            for _, row in truly_missed.head(3).iterrows():
                print(f"    - {row['title'][:80]}")
            all_ok = False
        else:
            n_safe = len(unflagged)
            safe_note = f" ({n_safe} kept because of safe words)" if n_safe else ""
            print(f"  '{noise_term}': {len(matches)} total, "
                  f"{len(flagged)} flagged{safe_note}")

    if all_ok:
        print("  All blacklist terms properly caught.")
    return all_ok


def print_summary(df):
    """Print flagging summary."""
    print("\n=== Flagging summary ===")

    flagged = df[df["flags"].apply(len) > 0]
    protected_flagged = flagged[flagged["protected"]]
    removable = flagged[~flagged["protected"]]

    print(f"  Total papers: {len(df)}")
    print(f"  Flagged: {len(flagged)}")
    print(f"  Protected: {df['protected'].sum()}")
    print(f"  Protected + flagged (kept): {len(protected_flagged)}")
    print(f"  Removal candidates: {len(removable)}")

    # Per flag type
    flag_counts = {}
    for flags_list in df["flags"]:
        for f in flags_list:
            key = f.split(":")[0]
            flag_counts[key] = flag_counts.get(key, 0) + 1

    print(f"\n  Flag breakdown:")
    for key, count in sorted(flag_counts.items(), key=lambda x: -x[1]):
        print(f"    {key}: {count}")

    # Sample removals per flag type
    print(f"\n  Sample removal candidates (10 per flag type):")
    for flag_type in sorted(flag_counts.keys()):
        type_removable = removable[removable["flags"].apply(
            lambda f: any(flag_type in x for x in f))]
        if len(type_removable) > 0:
            print(f"\n  --- {flag_type} ({len(type_removable)} removable) ---")
            for _, row in type_removable.head(10).iterrows():
                yr = row.get("year", "?")
                cites = row.get("cited_by_count", 0)
                print(f"    [{yr}] (cit:{cites}) {str(row['title'])[:80]}")


# ============================================================
# Apply filter
# ============================================================

def apply_filter(df):
    """Remove flagged non-protected papers."""
    df["action"] = "keep"
    mask_remove = (df["flags"].apply(len) > 0) & (~df["protected"])
    df.loc[mask_remove, "action"] = "remove"

    n_remove = mask_remove.sum()
    n_keep = len(df) - n_remove
    print(f"\n=== Applying filter ===")
    print(f"  Removing: {n_remove}")
    print(f"  Keeping: {n_keep}")

    # Save audit
    audit_df = df[["doi", "title", "year", "cited_by_count", "source_count",
                    "protected", "protect_reason", "action"]].copy()
    audit_df["flags"] = df["flags"].apply(lambda f: "|".join(f) if f else "")
    audit_path = os.path.join(CATALOGS_DIR, "corpus_audit.csv")
    audit_df.to_csv(audit_path, index=False)
    print(f"  Saved audit -> {audit_path}")

    # Save refined corpus
    keep_df = df[df["action"] == "keep"].drop(
        columns=["flags", "protected", "protect_reason", "action", "doi_norm",
                 "missing_metadata", "no_abstract_irrelevant", "title_blacklist",
                 "citation_isolated_old", "semantic_outlier", "semantic_outlier_dist",
                 "llm_irrelevant"],
        errors="ignore")
    refined_path = os.path.join(CATALOGS_DIR, "refined_works.csv")
    save_csv(keep_df, refined_path)
    print(f"  Saved refined corpus -> {refined_path} ({len(keep_df)} papers)")

    return keep_df


def save_dry_run_audit(df):
    """Save audit CSV in dry-run mode."""
    audit_df = df[["doi", "title", "year", "cited_by_count"]].copy()
    audit_df["flags"] = df["flags"].apply(lambda f: "|".join(f) if f else "")
    audit_df["protected"] = df["protected"]
    audit_df["protect_reason"] = df["protect_reason"]
    flagged_mask = df["flags"].apply(len) > 0
    audit_df["action"] = "keep"
    audit_df.loc[flagged_mask & ~df["protected"], "action"] = "would_remove"
    audit_path = os.path.join(CATALOGS_DIR, "corpus_audit.csv")
    audit_df.to_csv(audit_path, index=False)
    print(f"  Saved dry-run audit -> {audit_path}")


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Corpus refinement: flag -> verify -> filter")
    parser.add_argument("--apply", action="store_true",
                        help="Apply filter (default: dry run, flag + verify only)")
    parser.add_argument("--skip-llm", action="store_true",
                        help="Skip LLM scoring + audit step")
    parser.add_argument("--skip-citation-flag", action="store_true",
                        help="Skip citation isolation flag")
    parser.add_argument("--cheap", action="store_true",
                        help="Cheap filter: only flags 1-3 (metadata, no-abstract, blacklist)")
    args = parser.parse_args()

    # --cheap implies skipping everything that needs external data
    if args.cheap:
        args.skip_llm = True
        args.skip_citation_flag = True

    # Load config
    config = _load_config()

    print("Loading data...")
    works_path = os.path.join(CATALOGS_DIR, "unified_works.csv")
    df = pd.read_csv(works_path)
    print(f"  Unified works: {len(df)}")

    # Normalize DOIs once (used by flags 4, 5, 6 and protection)
    df["doi_norm"] = df["doi"].apply(lambda x: normalize_doi(x) if pd.notna(x) else "")

    # Load citations (skip in cheap mode)
    citations_df = None
    if not args.cheap and os.path.exists(CITATIONS_PATH):
        citations_df = pd.read_csv(CITATIONS_PATH)
        citations_df["source_doi"] = citations_df["source_doi"].apply(
            lambda x: normalize_doi(x) if pd.notna(x) else "")
        citations_df["ref_doi"] = citations_df["ref_doi"].apply(
            lambda x: normalize_doi(x) if pd.notna(x) else "")
        print(f"  Citations: {len(citations_df)}")

    # Load embeddings (skip in cheap mode)
    embeddings = None
    emb_df = None
    has_embeddings = False
    if not args.cheap and os.path.exists(EMBEDDINGS_PATH):
        emb_df = df.copy()
        emb_df = emb_df[emb_df["abstract"].notna() & (emb_df["abstract"].str.len() > 50)]
        emb_df["year_num"] = pd.to_numeric(emb_df["year"], errors="coerce")
        emb_df = emb_df[(emb_df["year_num"] >= 1990) & (emb_df["year_num"] <= 2025)]
        emb_df = emb_df.reset_index(drop=True)

        cache = np.load(EMBEDDINGS_PATH, allow_pickle=True)
        embeddings = cache["vectors"] if "vectors" in cache.files else cache
        if len(embeddings) != len(emb_df):
            print(f"  WARNING: embedding size mismatch ({len(embeddings)} vs {len(emb_df)})")
            print(f"  Skipping semantic outlier detection.")
            embeddings = None
            emb_df = None
        else:
            has_embeddings = True
            print(f"  Embeddings: {len(embeddings)}")

    if args.cheap:
        print("\n=== CHEAP MODE: flags 1-3 only ===")

    # ---- Flags 1-3: always run, fast, no external deps ----
    print("\n=== Phase A: Flagging papers ===")
    df["missing_metadata"] = flag_missing_metadata(df, config)
    print(f"  Flag 1 (missing metadata): {df['missing_metadata'].sum()}")

    df["no_abstract_irrelevant"] = flag_no_abstract(df, config)
    print(f"  Flag 2 (no abstract + irrelevant title): {df['no_abstract_irrelevant'].sum()}")

    df["title_blacklist"] = flag_title_blacklist(df, config)
    print(f"  Flag 3 (title blacklist): {df['title_blacklist'].sum()}")

    # ---- Flag 4: citation isolation ----
    if args.skip_citation_flag:
        print("  Flag 4: skipped (--skip-citation-flag)")
    else:
        try:
            df["citation_isolated_old"] = flag_citation_isolated(
                df, config, citations_df=citations_df)
            print(f"  Flag 4 (citation isolated + old): {df['citation_isolated_old'].sum()}")
        except ValueError as e:
            print(f"  Flag 4 skipped: {e}")

    # ---- Flag 5: semantic outlier ----
    if has_embeddings:
        try:
            df["semantic_outlier"], df["semantic_outlier_dist"] = flag_semantic_outlier(
                df, config, embeddings=embeddings, emb_df=emb_df)
            print(f"  Flag 5 (semantic outlier): {df['semantic_outlier'].sum()}")
        except ValueError as e:
            print(f"  Flag 5 skipped: {e}")
            has_embeddings = False
    else:
        print("  Flag 5: skipped (no embeddings)")

    # ---- Flag 6: LLM relevance (streaming) ----
    if not args.skip_llm:
        print("  Computing LLM relevance scores...")
        prior_flags = [c for c in FLAG_COLUMNS[:5] if c in df.columns]
        already_flagged = df[prior_flags].any(axis=1) if prior_flags else pd.Series(False, index=df.index)
        for i, (batch_idx, partial) in enumerate(flag_llm_irrelevant_streaming(
                df, config, already_flagged=already_flagged), 1):
            df.loc[partial.index, "llm_irrelevant"] = partial
        if "llm_irrelevant" in df.columns:
            n_llm = df["llm_irrelevant"].fillna(False).sum()
            print(f"  Flag 6 (LLM irrelevant): {n_llm}")
        else:
            print("  Flag 6: no candidates scored")
    else:
        print("  Flag 6: skipped (--skip-llm)")

    # ---- Merge into combined flags list ----
    df["flags"] = merge_flags(df, FLAG_COLUMNS)

    # ---- Protection ----
    print("\n=== Phase B: Protecting key papers ===")
    df["protected"], df["protect_reason"] = compute_protection(
        df, config, citations_df=citations_df)
    print(f"  Protected papers: {df['protected'].sum()}")

    # ---- Verification ----
    print("\n=== Phase C: Verification ===")
    verify_blacklist(df, config)

    if not args.skip_llm:
        print("\n=== C2: LLM audit ===")
        print("  (Use scripts/qa_refine_audit.py for full audit)")
    else:
        print("\n=== C2: LLM audit SKIPPED (--skip-llm) ===")

    print_summary(df)

    # ---- Apply or dry run ----
    if args.apply:
        check_apply_gates(df, args, has_embeddings)
        apply_filter(df)
    else:
        print("\n=== DRY RUN: use --apply to actually filter ===")
        save_dry_run_audit(df)


if __name__ == "__main__":
    main()
