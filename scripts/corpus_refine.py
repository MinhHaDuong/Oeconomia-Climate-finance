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

def apply_filter(df, output_path=None, audit_path=None):
    """Remove flagged non-protected papers."""
    if output_path is None:
        output_path = os.path.join(CATALOGS_DIR, "refined_works.csv")
    if audit_path is None:
        audit_path = os.path.join(CATALOGS_DIR, "corpus_audit.csv")

    # Re-evaluate flags if we have individual columns (boolean) rather than list
    flag_cols_present = [c for c in FLAG_COLUMNS if c in df.columns]
    if "flags" not in df.columns or df["flags"].apply(
            lambda x: isinstance(x, str)).any():
        # Reconstruct flags from boolean columns or parse string repr
        import ast
        if "flags" in df.columns:
            df["flags"] = df["flags"].apply(
                lambda x: ast.literal_eval(x) if isinstance(x, str) else (x or []))
        else:
            df["flags"] = merge_flags(df, FLAG_COLUMNS)

    df["action"] = "keep"
    mask_remove = (df["flags"].apply(len) > 0) & (~df["protected"].fillna(False))
    df.loc[mask_remove, "action"] = "remove"

    n_remove = mask_remove.sum()
    n_keep = len(df) - n_remove
    print(f"\n=== Applying filter ===")
    print(f"  Removing: {n_remove}")
    print(f"  Keeping: {n_keep}")

    # Save audit
    audit_df = df[["doi", "title", "year", "cited_by_count", "source_count",
                    "protected", "protect_reason", "action"]].copy()
    audit_df["flags"] = df["flags"].apply(lambda f: "|".join(f) if isinstance(f, list) else str(f))
    audit_df.to_csv(audit_path, index=False)
    print(f"  Saved audit -> {audit_path}")

    # Save refined corpus
    keep_df = df[df["action"] == "keep"].drop(
        columns=["flags", "protected", "protect_reason", "action",
                 "missing_metadata", "no_abstract_irrelevant", "title_blacklist",
                 "citation_isolated_old", "semantic_outlier", "semantic_outlier_dist",
                 "llm_irrelevant"],
        errors="ignore")

    # Deduplicate on normalized DOI (enrichment steps can reintroduce duplicates
    # from source JSONs; this is the final quality gate).
    #
    # Step 1: clear placeholder DOIs shared by grey-literature records — these are
    # fake DOIs assigned to multiple distinct grey-lit documents and should not be
    # used as identifiers.
    if "doi_norm" in keep_df.columns and "from_grey" in keep_df.columns:
        grey_doi_counts = keep_df.loc[
            keep_df["from_grey"].fillna(0).astype(bool) & (keep_df["doi_norm"] != ""),
            "doi_norm"
        ].value_counts()
        shared_grey_dois = set(grey_doi_counts[grey_doi_counts > 1].index)
        if shared_grey_dois:
            mask_fake = keep_df["doi_norm"].isin(shared_grey_dois) & \
                        keep_df["from_grey"].fillna(0).astype(bool)
            keep_df.loc[mask_fake, "doi"] = ""
            keep_df.loc[mask_fake, "doi_norm"] = ""
            print(f"  Cleared {mask_fake.sum()} fake placeholder DOIs "
                  f"({len(shared_grey_dois)} shared grey-lit DOIs)")

    # Step 2: deduplicate on normalized DOI, keeping the record with the highest
    # cited_by_count (OpenAlex sometimes indexes the same paper under two IDs).
    if "doi_norm" in keep_df.columns:
        n_before = len(keep_df)
        keep_df["_cite_sort"] = pd.to_numeric(
            keep_df["cited_by_count"], errors="coerce").fillna(0)
        has_doi_mask = keep_df["doi_norm"] != ""
        no_doi_df = keep_df[~has_doi_mask]
        with_doi_df = keep_df[has_doi_mask].sort_values(
            "_cite_sort", ascending=False
        ).drop_duplicates(subset=["doi_norm"], keep="first")
        keep_df = pd.concat([with_doi_df, no_doi_df], ignore_index=True).drop(
            columns=["_cite_sort"])
        n_dropped = n_before - len(keep_df)
        if n_dropped:
            print(f"  Dropped {n_dropped} duplicate-DOI records "
                  f"(kept highest cited_by_count per DOI)")

    keep_df = keep_df.drop(columns=["doi_norm"], errors="ignore")
    save_csv(keep_df, output_path)
    print(f"  Saved refined corpus -> {output_path} ({len(keep_df)} papers)")

    return keep_df


def save_extended(df, output_path):
    """Save extended_works.csv — all rows, with flag/protection columns added."""
    # Mark would-remove candidates (for audit visibility, but keep all rows)
    flag_cols_present = [c for c in FLAG_COLUMNS if c in df.columns]
    if "flags" not in df.columns:
        df["flags"] = merge_flags(df, FLAG_COLUMNS)

    flagged = df["flags"].apply(len) > 0
    protected = df["protected"].fillna(False)
    df["action"] = "keep"
    df.loc[flagged & ~protected, "action"] = "would_remove"

    save_csv(df, output_path)
    n_would_remove = (df["action"] == "would_remove").sum()
    print(f"  Saved extended corpus -> {output_path} "
          f"({len(df)} rows, {n_would_remove} would-remove candidates)")


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
# Shared data loading
# ============================================================

def load_input_works(works_path):
    """Load works CSV and normalise DOIs."""
    df = pd.read_csv(works_path)
    print(f"  Loaded: {len(df)} rows from {works_path}")
    df["doi_norm"] = df["doi"].apply(lambda x: normalize_doi(x) if pd.notna(x) else "")
    return df


def load_citations(cheap=False):
    if cheap or not os.path.exists(CITATIONS_PATH):
        return None
    citations_df = pd.read_csv(CITATIONS_PATH)
    citations_df["source_doi"] = citations_df["source_doi"].apply(
        lambda x: normalize_doi(x) if pd.notna(x) else "")
    citations_df["ref_doi"] = citations_df["ref_doi"].apply(
        lambda x: normalize_doi(x) if pd.notna(x) else "")
    print(f"  Citations: {len(citations_df)}")
    return citations_df


def load_embeddings(df, cheap=False):
    """Return (embeddings, emb_df, has_embeddings)."""
    if cheap or not os.path.exists(EMBEDDINGS_PATH):
        return None, None, False
    emb_df = df.copy()
    emb_df = emb_df[emb_df["abstract"].notna() & (emb_df["abstract"].str.len() > 50)]
    emb_df["year_num"] = pd.to_numeric(emb_df["year"], errors="coerce")
    emb_df = emb_df[(emb_df["year_num"] >= 1990) & (emb_df["year_num"] <= 2025)]
    emb_df = emb_df.reset_index(drop=True)
    cache = np.load(EMBEDDINGS_PATH, allow_pickle=True)
    embeddings = cache["vectors"] if "vectors" in cache.files else cache
    if len(embeddings) != len(emb_df):
        print(f"  WARNING: embedding size mismatch ({len(embeddings)} vs {len(emb_df)}), skipping.")
        return None, None, False
    print(f"  Embeddings: {len(embeddings)}")
    return embeddings, emb_df, True


def run_flagging(df, args, config, citations_df, embeddings, emb_df, has_embeddings):
    """Run all flags + protection + verification. Returns df with flag columns."""
    cheap = getattr(args, "cheap", False)

    if cheap:
        print("\n=== CHEAP MODE: flags 1-3 only ===")

    print("\n=== Phase A: Flagging papers ===")
    df["missing_metadata"] = flag_missing_metadata(df, config)
    print(f"  Flag 1 (missing metadata): {df['missing_metadata'].sum()}")

    df["no_abstract_irrelevant"] = flag_no_abstract(df, config)
    print(f"  Flag 2 (no abstract + irrelevant title): {df['no_abstract_irrelevant'].sum()}")

    df["title_blacklist"] = flag_title_blacklist(df, config)
    print(f"  Flag 3 (title blacklist): {df['title_blacklist'].sum()}")

    if getattr(args, "skip_citation_flag", False):
        print("  Flag 4: skipped (--skip-citation-flag)")
    else:
        try:
            df["citation_isolated_old"] = flag_citation_isolated(
                df, config, citations_df=citations_df)
            print(f"  Flag 4 (citation isolated + old): {df['citation_isolated_old'].sum()}")
        except ValueError as e:
            print(f"  Flag 4 skipped: {e}")

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

    skip_llm = getattr(args, "skip_llm", False)
    if not skip_llm:
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

    df["flags"] = merge_flags(df, FLAG_COLUMNS)

    print("\n=== Phase B: Protecting key papers ===")
    df["protected"], df["protect_reason"] = compute_protection(
        df, config, citations_df=citations_df)
    print(f"  Protected papers: {df['protected'].sum()}")

    print("\n=== Phase C: Verification ===")
    verify_blacklist(df, config)

    if not skip_llm:
        print("\n=== C2: LLM audit ===")
        print("  (Use scripts/qa_refine_audit.py for full audit)")
    else:
        print("\n=== C2: LLM audit SKIPPED (--skip-llm) ===")

    print_summary(df)
    return df, has_embeddings


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Corpus refinement: flag → verify → extend → filter",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Modes:\n"
            "  --extend  Phase 1c: annotate enriched_works.csv → extended_works.csv (no row removal)\n"
            "  --filter  Phase 1d: apply policy extended_works.csv → refined_works.csv\n"
            "  --apply   Compat: full pipeline on unified_works.csv → refined_works.csv\n"
            "  (no flag) Dry run: flag + verify, write audit only"
        ),
    )
    parser.add_argument("--extend", action="store_true",
                        help="Phase 1c: compute flags/protection, write extended_works.csv (no filtering)")
    parser.add_argument("--filter", action="store_true",
                        help="Phase 1d: read extended_works.csv, apply policy, write refined_works.csv")
    parser.add_argument("--apply", action="store_true",
                        help="Compat alias: full flag+filter pipeline (unified → refined)")
    parser.add_argument("--works-input", default=None,
                        help=("Input works CSV. Defaults: "
                              "--extend=enriched_works.csv, "
                              "--filter=extended_works.csv, "
                              "--apply=unified_works.csv"))
    parser.add_argument("--works-output", default=None,
                        help=("Output works CSV. Defaults: "
                              "--extend=extended_works.csv, "
                              "--filter/--apply=refined_works.csv"))
    parser.add_argument("--skip-llm", action="store_true",
                        help="Skip LLM scoring + audit step")
    parser.add_argument("--skip-citation-flag", action="store_true",
                        help="Skip citation isolation flag")
    parser.add_argument("--cheap", action="store_true",
                        help="Cheap filter: only flags 1-3 (metadata, no-abstract, blacklist)")
    args = parser.parse_args()

    if args.cheap:
        args.skip_llm = True
        args.skip_citation_flag = True

    # ── Resolve defaults ───────────────────────────────────────────────────
    if args.extend:
        default_input = os.path.join(CATALOGS_DIR, "enriched_works.csv")
        default_output = os.path.join(CATALOGS_DIR, "extended_works.csv")
    elif args.filter:
        default_input = os.path.join(CATALOGS_DIR, "extended_works.csv")
        default_output = os.path.join(CATALOGS_DIR, "refined_works.csv")
    else:  # --apply or dry-run (backward compat)
        default_input = os.path.join(CATALOGS_DIR, "unified_works.csv")
        default_output = os.path.join(CATALOGS_DIR, "refined_works.csv")

    works_input = args.works_input or default_input
    works_output = args.works_output or default_output

    # ── Filter mode: read existing extended artifact, apply policy ─────────
    if args.filter:
        print(f"=== FILTER MODE: {works_input} → {works_output} ===")
        df = pd.read_csv(works_input)
        print(f"  Loaded: {len(df)} rows from {works_input}")
        audit_path = os.path.join(os.path.dirname(works_output), "corpus_audit.csv")
        apply_filter(df, output_path=works_output, audit_path=audit_path)
        return

    # ── Extend / apply modes: run flagging pipeline ────────────────────────
    mode_label = "EXTEND" if args.extend else ("APPLY" if args.apply else "DRY RUN")
    print(f"=== {mode_label} MODE: {works_input} → {works_output} ===")

    config = _load_config()
    print("Loading data...")
    df = load_input_works(works_input)
    citations_df = load_citations(cheap=getattr(args, "cheap", False))
    embeddings, emb_df, has_embeddings = load_embeddings(
        df, cheap=getattr(args, "cheap", False))

    df, has_embeddings = run_flagging(
        df, args, config, citations_df, embeddings, emb_df, has_embeddings)

    if args.extend:
        save_extended(df, works_output)
    elif args.apply:
        check_apply_gates(df, args, has_embeddings)
        audit_path = os.path.join(os.path.dirname(works_output), "corpus_audit.csv")
        apply_filter(df, output_path=works_output, audit_path=audit_path)
    else:
        print("\n=== DRY RUN: use --extend / --filter / --apply to write output ===")
        save_dry_run_audit(df)


if __name__ == "__main__":
    main()

