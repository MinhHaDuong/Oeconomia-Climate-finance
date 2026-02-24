#!/usr/bin/env python3
"""Corpus refinement: flag noise → verify flags → filter.

Phase A: Flag papers (missing metadata, no abstract, title blacklist,
         citation isolation + age, semantic outlier)
Phase B: Protect key papers (high citations, multi-source, cited in corpus)
Phase C: Verify flags (blacklist validation, LLM random-sample audit)
Phase D: Apply filter (only after verification)

Reads:  data/catalogs/unified_works.csv, citations.csv, embeddings.npy
Writes: data/catalogs/refined_works.csv, data/catalogs/corpus_audit.csv

Usage:
    python scripts/corpus_refine.py              # flag + verify (dry run)
    python scripts/corpus_refine.py --apply      # flag + verify + apply filter
    python scripts/corpus_refine.py --skip-llm   # skip LLM audit step
"""

import argparse
import os
import re
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from utils import BASE_DIR, CATALOGS_DIR, normalize_doi, save_csv

# --- Paths ---
EMBEDDINGS_PATH = os.path.join(CATALOGS_DIR, "embeddings.npy")
CITATIONS_PATH = os.path.join(CATALOGS_DIR, "citations.csv")

# --- Title blacklist ---
NOISE_TITLE = [
    "blockchain", "cryptocurrency", "bitcoin", "ethereum", "nft",
    "deep learning", "neural network", "gpt", "large language model",
    "llm", "metaverse", "virtual reality", "chatgpt", "generative ai",
]

SAFE_TITLE = [
    "climate", "carbon", "emission", "energy", "green", "environment",
    "sustainable", "adaptation", "mitigation", "renewable", "finance",
    "fund", "investment", "development", "aid", "cdm", "kyoto", "gef",
    "paris agreement", "unfccc", "cop", "redd",
]

# --- Concept groups for abstract relevance ---
CONCEPT_GROUPS = {
    "climate": {"climate", "emission", "greenhouse", "warming", "carbon",
                "mitigation", "adaptation", "ghg", "co2", "ipcc"},
    "finance": {"finance", "fund", "investment", "cost", "market", "aid",
                "grant", "loan", "subsidy", "fiscal", "monetary", "budget",
                "bond", "bank", "insurance"},
    "development": {"development", "developing", "country", "nation",
                    "capacity", "transfer", "poverty", "oda", "governance"},
    "environment": {"environment", "energy", "renewable", "sustainable",
                    "conservation", "ecology", "biodiversity", "forest",
                    "pollution", "resource"},
}
MIN_GROUPS = 2


def text_has_concept_groups(text, min_groups=MIN_GROUPS):
    """Check if text mentions at least min_groups concept groups."""
    if not text:
        return False
    words = set(re.findall(r'[a-z]{3,}', text.lower()))
    groups_hit = sum(1 for gw in CONCEPT_GROUPS.values() if words & gw)
    return groups_hit >= min_groups


def title_matches_blacklist(title):
    """Check if title matches noise blacklist but not safe words."""
    if not title:
        return False
    t = title.lower()
    has_noise = any(n in t for n in NOISE_TITLE)
    has_safe = any(s in t for s in SAFE_TITLE)
    return has_noise and not has_safe


def title_has_safe_words(title):
    """Check if title contains any safe/relevant words."""
    if not title:
        return False
    t = title.lower()
    return any(s in t for s in SAFE_TITLE)


# ============================================================
# Phase A: Flag papers
# ============================================================

def flag_papers(df, citations_df, embeddings, emb_df):
    """Apply all flagging rules. Returns df with 'flags' column (list of str)."""
    n = len(df)
    flags = [[] for _ in range(n)]

    # Flag 1: Missing metadata
    for i, row in df.iterrows():
        missing = []
        if pd.isna(row["title"]) or str(row["title"]).strip() in ("", "nan"):
            missing.append("title")
        if pd.isna(row["first_author"]) or str(row["first_author"]).strip() in ("", "nan"):
            missing.append("author")
        if pd.isna(row["year"]) or str(row["year"]).strip() in ("", "nan"):
            missing.append("year")
        if missing:
            flags[i].append(f"missing_metadata:{','.join(missing)}")

    n_flag1 = sum(1 for f in flags if any("missing_metadata" in x for x in f))
    print(f"  Flag 1 (missing metadata): {n_flag1}")

    # Flag 2: No abstract + title without safe words
    for i, row in df.iterrows():
        abstract = str(row.get("abstract", ""))
        has_abstract = pd.notna(row.get("abstract")) and len(abstract.strip()) > 50
        if not has_abstract:
            title = str(row.get("title", ""))
            if not title_has_safe_words(title):
                flags[i].append("no_abstract_irrelevant")

    n_flag2 = sum(1 for f in flags if "no_abstract_irrelevant" in f)
    print(f"  Flag 2 (no abstract + irrelevant title): {n_flag2}")

    # Flag 3: Title blacklist
    for i, row in df.iterrows():
        title = str(row.get("title", ""))
        if title_matches_blacklist(title):
            flags[i].append("title_blacklist")

    n_flag3 = sum(1 for f in flags if "title_blacklist" in f)
    print(f"  Flag 3 (title blacklist): {n_flag3}")

    # Flag 4: Citation isolation + age (year <= 2019, no internal citations)
    print("  Computing citation isolation...")
    df["doi_norm"] = df["doi"].apply(lambda x: normalize_doi(x) if pd.notna(x) else "")
    cited_dois = set()
    citing_dois = set()
    if citations_df is not None and len(citations_df) > 0:
        cited_dois = set(citations_df["ref_doi"].dropna())
        citing_dois = set(citations_df["source_doi"].dropna())

    corpus_dois = set(df["doi_norm"])
    for i, row in df.iterrows():
        yr = pd.to_numeric(row.get("year"), errors="coerce")
        if pd.isna(yr) or yr > 2019:
            continue
        doi = row["doi_norm"]
        if not doi:
            continue
        is_cited = doi in cited_dois
        is_citing = doi in citing_dois
        if not is_cited and not is_citing:
            flags[i].append("citation_isolated_old")

    n_flag4 = sum(1 for f in flags if "citation_isolated_old" in f)
    print(f"  Flag 4 (citation isolated + old): {n_flag4}")

    # Flag 5: Semantic outlier (>2σ from centroid)
    if embeddings is not None and emb_df is not None:
        print("  Computing semantic outliers...")
        centroid = embeddings.mean(axis=0)
        # Cosine distance from centroid
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1
        normed = embeddings / norms
        centroid_normed = centroid / max(np.linalg.norm(centroid), 1e-10)
        cos_sim = normed @ centroid_normed
        cos_dist = 1 - cos_sim

        mean_dist = cos_dist.mean()
        std_dist = cos_dist.std()
        threshold = mean_dist + 2 * std_dist

        # Map embedding rows to df rows via DOI
        emb_doi_to_dist = {}
        for j, row in emb_df.iterrows():
            doi = normalize_doi(row["doi"]) if pd.notna(row["doi"]) else ""
            if doi and j < len(cos_dist):
                emb_doi_to_dist[doi] = cos_dist[j]

        for i, row in df.iterrows():
            doi = row["doi_norm"]
            if doi in emb_doi_to_dist:
                if emb_doi_to_dist[doi] > threshold:
                    flags[i].append(f"semantic_outlier:{emb_doi_to_dist[doi]:.3f}")

        n_flag5 = sum(1 for f in flags if any("semantic_outlier" in x for x in f))
        print(f"  Flag 5 (semantic outlier >2σ): {n_flag5} "
              f"(threshold: {threshold:.3f}, mean: {mean_dist:.3f}, std: {std_dist:.3f})")
    else:
        print("  Flag 5: skipped (no embeddings)")

    df["flags"] = flags
    return df


# ============================================================
# Phase B: Protect key papers
# ============================================================

def protect_papers(df, citations_df):
    """Mark papers as protected. Returns df with 'protected' and 'protect_reason' columns."""
    protect = [False] * len(df)
    reasons = [""] * len(df)

    for i, row in df.iterrows():
        r = []
        # High citations
        cites = pd.to_numeric(row.get("cited_by_count"), errors="coerce")
        if pd.notna(cites) and cites >= 50:
            r.append(f"cited_by={int(cites)}")

        # Multi-source
        sc = pd.to_numeric(row.get("source_count"), errors="coerce")
        if pd.notna(sc) and sc >= 2:
            r.append(f"multi_source={int(sc)}")

        # Cited by other corpus papers
        doi = row.get("doi_norm", "")
        if doi and citations_df is not None:
            if doi in set(citations_df["ref_doi"].dropna()):
                r.append("cited_in_corpus")

        if r:
            protect[i] = True
            reasons[i] = "; ".join(r)

    df["protected"] = protect
    df["protect_reason"] = reasons

    n_protected = sum(protect)
    print(f"\n  Protected papers: {n_protected}")
    return df


# ============================================================
# Phase C: Verify flags
# ============================================================

def verify_blacklist(df):
    """C1: Check that every NOISE_TITLE term in corpus titles is caught."""
    print("\n=== C1: Blacklist validation ===")
    all_ok = True
    for noise_term in NOISE_TITLE:
        matches = df[df["title"].str.lower().str.contains(noise_term, na=False)]
        flagged = matches[matches["flags"].apply(
            lambda f: "title_blacklist" in f)]
        unflagged = matches[~matches.index.isin(flagged.index)]

        # Unflagged ones should have safe words (that's why they weren't caught)
        truly_missed = unflagged[~unflagged["title"].apply(
            lambda t: title_has_safe_words(str(t)))]

        if len(truly_missed) > 0:
            print(f"  WARNING: '{noise_term}' — {len(truly_missed)} missed:")
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


def llm_audit(df, n_sample=50):
    """C2: LLM random-sample audit via OpenRouter."""
    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("\n=== C2: LLM audit SKIPPED (no OPENROUTER_API_KEY) ===")
        return None

    print(f"\n=== C2: LLM audit ({n_sample} flagged + {n_sample} unflagged) ===")

    import json
    import urllib.request

    flagged = df[df["flags"].apply(len) > 0]
    unflagged = df[df["flags"].apply(len) == 0]

    # Stratified sample of flagged papers
    n_flagged_sample = min(n_sample, len(flagged))
    flagged_sample = flagged.sample(n=n_flagged_sample, random_state=42)

    # Random sample of unflagged papers
    n_unflagged_sample = min(n_sample, len(unflagged))
    unflagged_sample = unflagged.sample(n=n_unflagged_sample, random_state=42)

    sample = pd.concat([flagged_sample, unflagged_sample])

    prompt_template = (
        "Is this academic paper about climate finance, climate policy, carbon markets, "
        "environmental economics, or green investment? Answer YES or NO with one "
        "sentence justification.\n\n"
        "Title: {title}\n"
        "Abstract: {abstract}\n"
    )

    results = []
    for idx, row in sample.iterrows():
        title = str(row.get("title", ""))[:200]
        abstract = str(row.get("abstract", ""))[:300]
        if abstract in ("", "nan"):
            abstract = "(no abstract)"

        prompt = prompt_template.format(title=title, abstract=abstract)

        body = json.dumps({
            "model": "google/gemini-flash-1.5-8b",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 100,
            "temperature": 0,
        }).encode()

        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/chat/completions",
            data=body,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )

        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                result = json.loads(resp.read())
            answer_text = result["choices"][0]["message"]["content"].strip()
            is_relevant = answer_text.upper().startswith("YES")
        except Exception as e:
            print(f"  LLM error for '{title[:50]}': {e}")
            answer_text = f"ERROR: {e}"
            is_relevant = None

        is_flagged = len(row["flags"]) > 0
        results.append({
            "doi": row.get("doi_norm", ""),
            "title": title[:80],
            "flagged": is_flagged,
            "llm_relevant": is_relevant,
            "llm_answer": answer_text[:100],
            "flags": "|".join(row["flags"]) if row["flags"] else "",
        })

        # Rate limit
        time.sleep(0.5)

    results_df = pd.DataFrame(results)

    # Compute error rates
    valid = results_df[results_df["llm_relevant"].notna()]
    flagged_valid = valid[valid["flagged"]]
    unflagged_valid = valid[~valid["flagged"]]

    # Type I: flagged but LLM says relevant (false positive)
    type1 = flagged_valid[flagged_valid["llm_relevant"] == True]
    type1_rate = len(type1) / max(len(flagged_valid), 1)

    # Type II: unflagged but LLM says not relevant (false negative)
    type2 = unflagged_valid[unflagged_valid["llm_relevant"] == False]
    type2_rate = len(type2) / max(len(unflagged_valid), 1)

    print(f"\n  Confusion matrix:")
    print(f"    Flagged + LLM says relevant (Type I):     {len(type1)}/{len(flagged_valid)} = {type1_rate:.1%}")
    print(f"    Flagged + LLM says irrelevant:             {len(flagged_valid) - len(type1)}/{len(flagged_valid)}")
    print(f"    Unflagged + LLM says irrelevant (Type II): {len(type2)}/{len(unflagged_valid)} = {type2_rate:.1%}")
    print(f"    Unflagged + LLM says relevant:             {len(unflagged_valid) - len(type2)}/{len(unflagged_valid)}")

    if type1_rate > 0.10:
        print(f"  *** WARNING: Type I error {type1_rate:.1%} > 10% — filter may be too aggressive")
        print(f"  Flagged papers LLM considers relevant:")
        for _, row in type1.iterrows():
            print(f"    [{row['flags']}] {row['title']}")

    if type2_rate > 0.05:
        print(f"  *** WARNING: Type II error {type2_rate:.1%} > 5% — filter may be too lenient")
        print(f"  Unflagged papers LLM considers irrelevant:")
        for _, row in type2.iterrows():
            print(f"    {row['title']}")

    # Save LLM audit results
    audit_path = os.path.join(CATALOGS_DIR, "llm_audit.csv")
    results_df.to_csv(audit_path, index=False)
    print(f"  Saved LLM audit → {audit_path}")

    return {"type1_rate": type1_rate, "type2_rate": type2_rate}


def print_summary(df):
    """C3: Print flagging summary."""
    print("\n=== C3: Flagging summary ===")

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
# Phase D: Apply filter
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
    print(f"  Saved audit → {audit_path}")

    # Save refined corpus
    keep_df = df[df["action"] == "keep"].drop(
        columns=["flags", "protected", "protect_reason", "action", "doi_norm"],
        errors="ignore")
    refined_path = os.path.join(CATALOGS_DIR, "refined_works.csv")
    save_csv(keep_df, refined_path)
    print(f"  Saved refined corpus → {refined_path} ({len(keep_df)} papers)")

    return keep_df


# ============================================================
# Main
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Corpus refinement: flag → verify → filter")
    parser.add_argument("--apply", action="store_true",
                        help="Apply filter (default: dry run, flag + verify only)")
    parser.add_argument("--skip-llm", action="store_true",
                        help="Skip LLM audit step")
    args = parser.parse_args()

    print("Loading data...")
    works_path = os.path.join(CATALOGS_DIR, "unified_works.csv")
    df = pd.read_csv(works_path)
    print(f"  Unified works: {len(df)}")

    # Load citations
    citations_df = None
    if os.path.exists(CITATIONS_PATH):
        citations_df = pd.read_csv(CITATIONS_PATH)
        citations_df["source_doi"] = citations_df["source_doi"].apply(
            lambda x: normalize_doi(x) if pd.notna(x) else "")
        citations_df["ref_doi"] = citations_df["ref_doi"].apply(
            lambda x: normalize_doi(x) if pd.notna(x) else "")
        print(f"  Citations: {len(citations_df)}")

    # Load embeddings (if available)
    embeddings = None
    emb_df = None
    if os.path.exists(EMBEDDINGS_PATH):
        # Embeddings correspond to works with abstracts in 1990-2025
        emb_df = df.copy()
        emb_df = emb_df[emb_df["abstract"].notna() & (emb_df["abstract"].str.len() > 50)]
        emb_df["year_num"] = pd.to_numeric(emb_df["year"], errors="coerce")
        emb_df = emb_df[(emb_df["year_num"] >= 1990) & (emb_df["year_num"] <= 2025)]
        emb_df = emb_df.reset_index(drop=True)

        embeddings = np.load(EMBEDDINGS_PATH)
        if len(embeddings) != len(emb_df):
            print(f"  WARNING: embedding size mismatch ({len(embeddings)} vs {len(emb_df)})")
            print(f"  Skipping semantic outlier detection.")
            embeddings = None
            emb_df = None
        else:
            print(f"  Embeddings: {len(embeddings)}")

    # Phase A: Flag
    print("\n=== Phase A: Flagging papers ===")
    df = flag_papers(df, citations_df, embeddings, emb_df)

    # Phase B: Protect
    print("\n=== Phase B: Protecting key papers ===")
    df = protect_papers(df, citations_df)

    # Phase C: Verify
    print("\n=== Phase C: Verification ===")
    verify_blacklist(df)

    if not args.skip_llm:
        llm_result = llm_audit(df)
    else:
        print("\n=== C2: LLM audit SKIPPED (--skip-llm) ===")

    print_summary(df)

    # Phase D: Apply (only with --apply flag)
    if args.apply:
        apply_filter(df)
    else:
        print("\n=== DRY RUN: use --apply to actually filter ===")
        # Still save audit for review
        audit_df = df[["doi", "title", "year", "cited_by_count"]].copy()
        audit_df["flags"] = df["flags"].apply(lambda f: "|".join(f) if f else "")
        audit_df["protected"] = df["protected"]
        audit_df["protect_reason"] = df["protect_reason"]
        flagged_mask = df["flags"].apply(len) > 0
        audit_df["action"] = "keep"
        audit_df.loc[flagged_mask & ~df["protected"], "action"] = "would_remove"
        audit_path = os.path.join(CATALOGS_DIR, "corpus_audit.csv")
        audit_df.to_csv(audit_path, index=False)
        print(f"  Saved dry-run audit → {audit_path}")


if __name__ == "__main__":
    main()
