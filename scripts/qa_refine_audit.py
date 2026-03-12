#!/usr/bin/env python3
"""QA/Audit for corpus refinement: blacklist check + LLM audit + summary.

Reads a corpus_audit.csv (or any CSV with flags/titles) and runs verification.

Usage:
    python scripts/qa_refine_audit.py                           # uses default audit path
    python scripts/qa_refine_audit.py data/catalogs/corpus_audit.csv
"""

import argparse
import json
import os
import sys
import time

import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from refine_flags import _has_safe_words, _load_config
from utils import CATALOGS_DIR


def verify_blacklist(df, config):
    """Check that every noise term in corpus titles is caught."""
    noise_title = config["noise_title"]
    safe_title = config["safe_title"]

    print("\n=== Blacklist validation ===")
    all_ok = True

    # Parse flags: handle both list and pipe-delimited string
    def get_flags(row):
        flags = row.get("flags", "")
        if isinstance(flags, list):
            return flags
        return str(flags).split("|") if flags else []

    for noise_term in noise_title:
        matches = df[df["title"].str.lower().str.contains(noise_term, na=False)]
        flagged = matches[matches.apply(
            lambda row: "title_blacklist" in get_flags(row), axis=1)]
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


def llm_audit(df, config, n_sample=None):
    """LLM random-sample audit via OpenRouter."""
    import urllib.request

    audit_cfg = config.get("audit", {})
    model = audit_cfg.get("model", "google/gemma-2-27b-it")
    prompt_template = audit_cfg.get("prompt_template", "")
    if n_sample is None:
        n_sample = audit_cfg.get("sample_size", 50)

    api_key = os.environ.get("OPENROUTER_API_KEY", "")
    if not api_key:
        print("\n=== LLM audit SKIPPED (no OPENROUTER_API_KEY) ===")
        return None

    print(f"\n=== LLM audit ({n_sample} flagged + {n_sample} unflagged) ===")

    def get_flags_str(row):
        flags = row.get("flags", "")
        if isinstance(flags, list):
            return "|".join(flags)
        return str(flags) if flags else ""

    def is_flagged(row):
        return len(get_flags_str(row)) > 0

    flagged = df[df.apply(is_flagged, axis=1)]
    unflagged = df[~df.apply(is_flagged, axis=1)]

    n_flagged_sample = min(n_sample, len(flagged))
    flagged_sample = flagged.sample(n=n_flagged_sample, random_state=42)

    n_unflagged_sample = min(n_sample, len(unflagged))
    unflagged_sample = unflagged.sample(n=n_unflagged_sample, random_state=42)

    sample = pd.concat([flagged_sample, unflagged_sample])

    results = []
    for _, row in sample.iterrows():
        title = str(row.get("title", ""))[:200]
        abstract = str(row.get("abstract", ""))[:300]
        if abstract in ("", "nan"):
            abstract = "(no abstract)"

        prompt = prompt_template.format(title=title, abstract=abstract)

        body = json.dumps({
            "model": model,
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

        row_flagged = is_flagged(row)
        results.append({
            "doi": row.get("doi", ""),
            "title": title[:80],
            "flagged": row_flagged,
            "llm_relevant": is_relevant,
            "llm_answer": answer_text[:100],
            "flags": get_flags_str(row),
        })

        time.sleep(0.5)

    results_df = pd.DataFrame(results)

    # Compute error rates
    valid = results_df[results_df["llm_relevant"].notna()]
    flagged_valid = valid[valid["flagged"]]
    unflagged_valid = valid[~valid["flagged"]]

    type1 = flagged_valid[flagged_valid["llm_relevant"] == True]
    type1_rate = len(type1) / max(len(flagged_valid), 1)

    type2 = unflagged_valid[unflagged_valid["llm_relevant"] == False]
    type2_rate = len(type2) / max(len(unflagged_valid), 1)

    print(f"\n  Confusion matrix:")
    print(f"    Flagged + LLM says relevant (Type I):     "
          f"{len(type1)}/{len(flagged_valid)} = {type1_rate:.1%}")
    print(f"    Flagged + LLM says irrelevant:             "
          f"{len(flagged_valid) - len(type1)}/{len(flagged_valid)}")
    print(f"    Unflagged + LLM says irrelevant (Type II): "
          f"{len(type2)}/{len(unflagged_valid)} = {type2_rate:.1%}")
    print(f"    Unflagged + LLM says relevant:             "
          f"{len(unflagged_valid) - len(type2)}/{len(unflagged_valid)}")

    if type1_rate > 0.10:
        print(f"  *** WARNING: Type I error {type1_rate:.1%} > 10%")
    if type2_rate > 0.05:
        print(f"  *** WARNING: Type II error {type2_rate:.1%} > 5%")

    # Save results
    audit_path = os.path.join(CATALOGS_DIR, "llm_audit.csv")
    results_df.to_csv(audit_path, index=False)
    print(f"  Saved LLM audit -> {audit_path}")

    return {"type1_rate": type1_rate, "type2_rate": type2_rate}


def print_summary(df):
    """Print flagging summary from audit CSV."""
    print("\n=== Flagging summary ===")

    def get_flags_list(row):
        flags = row.get("flags", "")
        if isinstance(flags, list):
            return flags
        s = str(flags) if flags else ""
        return s.split("|") if s else []

    df["_flags_list"] = df.apply(get_flags_list, axis=1)
    flagged = df[df["_flags_list"].apply(len) > 0]

    has_protected = "protected" in df.columns
    if has_protected:
        protected_flagged = flagged[flagged["protected"].astype(bool)]
        removable = flagged[~flagged["protected"].astype(bool)]
    else:
        protected_flagged = pd.DataFrame()
        removable = flagged

    print(f"  Total papers: {len(df)}")
    print(f"  Flagged: {len(flagged)}")
    if has_protected:
        print(f"  Protected: {df['protected'].astype(bool).sum()}")
        print(f"  Protected + flagged (kept): {len(protected_flagged)}")
    print(f"  Removal candidates: {len(removable)}")

    # Per flag type
    flag_counts = {}
    for flags_list in df["_flags_list"]:
        for f in flags_list:
            key = f.split(":")[0]
            flag_counts[key] = flag_counts.get(key, 0) + 1

    print(f"\n  Flag breakdown:")
    for key, count in sorted(flag_counts.items(), key=lambda x: -x[1]):
        print(f"    {key}: {count}")

    df.drop(columns=["_flags_list"], inplace=True)


def main():
    parser = argparse.ArgumentParser(description="QA/Audit for corpus refinement")
    parser.add_argument("audit_csv", nargs="?",
                        default=os.path.join(CATALOGS_DIR, "corpus_audit.csv"),
                        help="Path to audit CSV")
    parser.add_argument("--skip-llm-audit", action="store_true",
                        help="Skip LLM audit, only run blacklist check + summary")
    args = parser.parse_args()

    config = _load_config()

    print(f"Loading {args.audit_csv}...")
    df = pd.read_csv(args.audit_csv)
    print(f"  {len(df)} papers")

    verify_blacklist(df, config)

    if not args.skip_llm_audit:
        llm_audit(df, config)

    print_summary(df)


if __name__ == "__main__":
    main()
