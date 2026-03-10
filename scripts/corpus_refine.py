#!/usr/bin/env python3
"""Corpus refinement: flag noise → verify flags → filter.

Phase A: Flag papers (missing metadata, no abstract, title blacklist,
         citation isolation + age, semantic outlier)
Phase B: Protect key papers (high citations, multi-source, cited in corpus)
Phase C: Verify flags (blacklist validation, LLM random-sample audit)
Phase D: Apply filter (only after verification)

Reads:  data/catalogs/unified_works.csv, citations.csv, embeddings.npz
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
from utils import BASE_DIR, CATALOGS_DIR, EMBEDDINGS_PATH, normalize_doi, save_csv

# --- Paths ---
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
    # French
    "climat", "financ", "carbone", "durable",
    # German
    "klima", "finanz",
    # Spanish/Portuguese
    "climátic", "financ",
    # Chinese
    "气候", "金融", "碳", "绿色",
    # Japanese
    "グリーン", "ファイナンス", "気候",
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
# Flag 6: LLM relevance scoring with cache
# ============================================================

LLM_CACHE_PATH = os.path.join(CATALOGS_DIR, "llm_relevance_cache.csv")


def load_llm_relevance_cache():
    """Load cached LLM relevance scores {doi: bool}."""
    cache = {}
    if os.path.exists(LLM_CACHE_PATH):
        df = pd.read_csv(LLM_CACHE_PATH, dtype=str, keep_default_na=False)
        for _, row in df.iterrows():
            cache[row["doi"]] = row["relevant"].lower() == "true"
    return cache


def save_llm_relevance_cache(cache):
    """Save LLM relevance cache to CSV."""
    rows = [{"doi": doi, "relevant": str(rel)} for doi, rel in cache.items()]
    pd.DataFrame(rows).to_csv(LLM_CACHE_PATH, index=False)


def score_relevance_llm(df_subset, batch_size=15):
    """Score papers for climate finance relevance via LLM.

    Sends batched prompts to OpenRouter. Returns {doi: bool}.
    """
    import json
    import urllib.request

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("    WARNING: no OPENROUTER_API_KEY, skipping LLM scoring")
        return {}

    results = {}
    rows = list(df_subset.itertuples())

    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]

        # Build batch prompt
        papers = []
        dois = []
        for j, row in enumerate(batch):
            title = str(getattr(row, "title", ""))[:150]
            abstract = str(getattr(row, "abstract", ""))[:250]
            doi = getattr(row, "doi_norm", "")
            dois.append(doi)
            papers.append(f"{j+1}. Title: {title}\n   Abstract: {abstract}")

        prompt = (
            "For each paper below, determine if it is about climate finance, "
            "climate policy economics, carbon markets, green investment, "
            "or environmental finance for developing countries.\n"
            "Answer with ONLY a JSON object mapping paper numbers to true/false.\n"
            "Example: {\"1\": true, \"2\": false, \"3\": true}\n\n"
            + "\n\n".join(papers)
        )

        body = json.dumps({
            "model": "google/gemini-2.5-flash",
            "messages": [{"role": "user", "content": prompt}],
            "max_tokens": 200,
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
            with urllib.request.urlopen(req, timeout=60) as resp:
                result = json.loads(resp.read())
            answer = result["choices"][0]["message"]["content"].strip()
            # Parse JSON from response (handle markdown code blocks)
            answer = re.sub(r"```json?\s*", "", answer)
            answer = re.sub(r"```", "", answer)
            scores = json.loads(answer)

            for j, doi in enumerate(dois):
                key = str(j + 1)
                if key in scores and doi:
                    results[doi] = bool(scores[key])
        except Exception as e:
            print(f"    LLM batch error: {e}")

        time.sleep(1.0)
        print(f"    Scored {min(i + batch_size, len(rows))}/{len(rows)}",
              end="\r")

    print()
    return results


# ============================================================
# Phase A: Flag papers
# ============================================================

def flag_papers(df, citations_df, embeddings, emb_df,
                skip_citation_flag=False, skip_llm_relevance=False):
    """Apply all flagging rules (vectorized). Returns df with 'flags' column."""
    n = len(df)
    flags = [[] for _ in range(n)]

    # Precompute normalized DOIs early (used by flags 4 & 5)
    df["doi_norm"] = df["doi"].apply(lambda x: normalize_doi(x) if pd.notna(x) else "")

    # Flag 1: Missing metadata (vectorized)
    # Papers missing title are always flagged. Papers missing only author/year
    # are only flagged if the title also lacks safe words (to preserve grey
    # literature and policy documents that are genuinely relevant).
    title_s = df["title"].fillna("").astype(str).str.strip()
    author_s = df["first_author"].fillna("").astype(str).str.strip()
    year_s = df["year"].fillna("").astype(str).str.strip()
    miss_title = (title_s == "") | (title_s == "nan")
    miss_author = (author_s == "") | (author_s == "nan")
    miss_year = (year_s == "") | (year_s == "nan")

    title_lower = title_s.str.lower()
    safe_pattern = "|".join(re.escape(s) for s in SAFE_TITLE)
    title_has_safe = title_lower.str.contains(safe_pattern, na=False)

    # Missing title → always flag; missing author/year → only if title lacks safe words
    flag1_mask = miss_title | ((miss_author | miss_year) & ~title_has_safe)

    for i in flag1_mask[flag1_mask].index:
        parts = []
        if miss_title[i]: parts.append("title")
        if miss_author[i]: parts.append("author")
        if miss_year[i]: parts.append("year")
        flags[i].append(f"missing_metadata:{','.join(parts)}")

    print(f"  Flag 1 (missing metadata): {flag1_mask.sum()} "
          f"(title: {miss_title.sum()}, author-only: {(miss_author & ~miss_title).sum()}, "
          f"year-only: {(miss_year & ~miss_title & ~miss_author).sum()}, "
          f"saved by safe title: {((miss_author | miss_year) & ~miss_title & title_has_safe).sum()})")

    # Flag 2: No abstract + title without safe words (vectorized)
    abstract_s = df["abstract"].fillna("").astype(str).str.strip()
    has_abstract = abstract_s.str.len() > 50
    flag2_mask = ~has_abstract & ~title_has_safe

    for i in flag2_mask[flag2_mask].index:
        flags[i].append("no_abstract_irrelevant")

    print(f"  Flag 2 (no abstract + irrelevant title): {flag2_mask.sum()}")

    # Flag 3: Title blacklist (vectorized)
    noise_pattern = "|".join(re.escape(n) for n in NOISE_TITLE)
    title_has_noise = title_lower.str.contains(noise_pattern, na=False)
    flag3_mask = title_has_noise & ~title_has_safe

    for i in flag3_mask[flag3_mask].index:
        flags[i].append("title_blacklist")

    print(f"  Flag 3 (title blacklist): {flag3_mask.sum()}")

    # Flag 4: Citation isolation + age (vectorized)
    if skip_citation_flag:
        print("  Flag 4: skipped (--skip-citation-flag)")
    else:
        print("  Computing citation isolation...")
        cited_dois = set()
        citing_dois = set()
        if citations_df is not None and len(citations_df) > 0:
            cited_dois = set(citations_df["ref_doi"].dropna())
            citing_dois = set(citations_df["source_doi"].dropna())

        year_num = pd.to_numeric(df["year"], errors="coerce")
        is_old = year_num.notna() & (year_num <= 2019)
        has_doi = df["doi_norm"] != ""
        is_cited = df["doi_norm"].isin(cited_dois)
        is_citing = df["doi_norm"].isin(citing_dois)
        flag4_mask = is_old & has_doi & ~is_cited & ~is_citing

        for i in flag4_mask[flag4_mask].index:
            flags[i].append("citation_isolated_old")

        print(f"  Flag 4 (citation isolated + old): {flag4_mask.sum()}")

    # Flag 5: Semantic outlier (>2σ from centroid)
    if embeddings is not None and emb_df is not None:
        print("  Computing semantic outliers...")
        centroid = embeddings.mean(axis=0)
        norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
        norms[norms == 0] = 1
        normed = embeddings / norms
        centroid_normed = centroid / max(np.linalg.norm(centroid), 1e-10)
        cos_sim = normed @ centroid_normed
        cos_dist = 1 - cos_sim

        mean_dist = cos_dist.mean()
        std_dist = cos_dist.std()
        threshold = mean_dist + 2 * std_dist

        # Build DOI → distance mapping (vectorized)
        emb_dois = emb_df["doi"].apply(
            lambda x: normalize_doi(x) if pd.notna(x) else "")
        emb_doi_to_dist = dict(zip(emb_dois, cos_dist))
        emb_doi_to_dist.pop("", None)

        # Map to main df
        outlier_dists = df["doi_norm"].map(emb_doi_to_dist)
        flag5_mask = outlier_dists.notna() & (outlier_dists > threshold)

        for i in flag5_mask[flag5_mask].index:
            flags[i].append(f"semantic_outlier:{outlier_dists[i]:.3f}")

        print(f"  Flag 5 (semantic outlier >2σ): {flag5_mask.sum()} "
              f"(threshold: {threshold:.3f}, mean: {mean_dist:.3f}, std: {std_dist:.3f})")
    else:
        print("  Flag 5: skipped (no embeddings)")

    # Flag 6: LLM relevance (for papers with low concept-group coverage)
    if not skip_llm_relevance:
        print("  Computing LLM relevance scores...")
        # Identify candidates: papers with abstract but < 2 concept groups hit
        has_text = abstract_s.str.len() > 50
        low_concept = ~df["title"].fillna("").apply(
            lambda t: text_has_concept_groups(str(t), min_groups=2)
        ) & ~abstract_s.apply(
            lambda a: text_has_concept_groups(str(a), min_groups=2)
        )
        candidates_mask = has_text & low_concept
        # Don't re-flag already-flagged papers
        already_flagged = pd.Series([len(f) > 0 for f in flags], index=df.index)
        candidates_mask = candidates_mask & ~already_flagged

        n_candidates = candidates_mask.sum()
        if n_candidates > 0:
            cache = load_llm_relevance_cache()
            candidates = df[candidates_mask]
            uncached = candidates[~candidates["doi_norm"].isin(cache)]
            print(f"    Candidates: {n_candidates} "
                  f"(cached: {n_candidates - len(uncached)}, "
                  f"to score: {len(uncached)})")

            if len(uncached) > 0:
                new_scores = score_relevance_llm(uncached)
                cache.update(new_scores)
                save_llm_relevance_cache(cache)

            # Flag papers scored as irrelevant
            n_flag6 = 0
            for i in candidates_mask[candidates_mask].index:
                doi = df.at[i, "doi_norm"]
                if doi in cache and not cache[doi]:
                    flags[i].append("llm_irrelevant")
                    n_flag6 += 1
            print(f"  Flag 6 (LLM irrelevant): {n_flag6}")
        else:
            print("  Flag 6: no candidates (all papers pass concept-group check)")
    else:
        print("  Flag 6: skipped (--skip-llm)")

    df["flags"] = flags
    return df


# ============================================================
# Phase B: Protect key papers
# ============================================================

def load_teaching_canon():
    """Load teaching canon DOIs (papers used in 2+ syllabi)."""
    canon_path = os.path.join(CATALOGS_DIR, "teaching_canon.csv")
    if not os.path.exists(canon_path):
        return set()
    canon_df = pd.read_csv(canon_path, dtype=str, keep_default_na=False)
    canon_df = canon_df[pd.to_numeric(canon_df["teaching_count"], errors="coerce") >= 2]
    dois = set()
    for d in canon_df["doi"]:
        nd = normalize_doi(d)
        if nd:
            dois.add(nd)
    return dois


def protect_papers(df, citations_df):
    """Mark papers as protected (vectorized)."""
    cites = pd.to_numeric(df["cited_by_count"], errors="coerce")
    sc = pd.to_numeric(df["source_count"], errors="coerce")

    high_cites = cites.notna() & (cites >= 50)
    multi_src = sc.notna() & (sc >= 2)

    ref_dois = set()
    if citations_df is not None:
        ref_dois = set(citations_df["ref_doi"].dropna())
    cited_in_corpus = df["doi_norm"].isin(ref_dois) & (df["doi_norm"] != "")

    # Teaching canon protection: papers in 2+ syllabi
    teaching_dois = load_teaching_canon()
    in_teaching_canon = df["doi_norm"].isin(teaching_dois) & (df["doi_norm"] != "")
    if in_teaching_canon.any():
        print(f"  Teaching canon papers: {in_teaching_canon.sum()}")

    protected = high_cites | multi_src | cited_in_corpus | in_teaching_canon

    # Build reason strings
    reasons = [""] * len(df)
    for i in protected[protected].index:
        r = []
        if high_cites[i]:
            r.append(f"cited_by={int(cites[i])}")
        if multi_src[i]:
            r.append(f"multi_source={int(sc[i])}")
        if cited_in_corpus[i]:
            r.append("cited_in_corpus")
        if in_teaching_canon[i]:
            r.append("teaching_canon")
        reasons[i] = "; ".join(r)

    df["protected"] = protected
    df["protect_reason"] = reasons

    print(f"\n  Protected papers: {protected.sum()}")
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
            "model": "google/gemma-2-27b-it",
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
    parser.add_argument("--skip-citation-flag", action="store_true",
                        help="Skip citation isolation flag (use when citations are stale)")
    parser.add_argument("--cheap", action="store_true",
                        help="Cheap filter: only flags 1-3 (metadata, no-abstract, blacklist). "
                             "Use before enrichment to remove obvious junk.")
    args = parser.parse_args()

    # --cheap implies skipping everything that needs external data
    if args.cheap:
        args.skip_llm = True
        args.skip_citation_flag = True

    print("Loading data...")
    works_path = os.path.join(CATALOGS_DIR, "unified_works.csv")
    df = pd.read_csv(works_path)
    print(f"  Unified works: {len(df)}")

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
    if not args.cheap and os.path.exists(EMBEDDINGS_PATH):
        # Embeddings correspond to works with abstracts in 1990-2025
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
            print(f"  Embeddings: {len(embeddings)}")

    if args.cheap:
        print("\n=== CHEAP MODE: flags 1-3 only ===")

    # Phase A: Flag
    print("\n=== Phase A: Flagging papers ===")
    df = flag_papers(df, citations_df, embeddings, emb_df,
                     skip_citation_flag=args.skip_citation_flag,
                     skip_llm_relevance=args.skip_llm)

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
