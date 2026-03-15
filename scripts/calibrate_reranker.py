#!/usr/bin/env python3
"""Calibrate a cross-encoder reranker for corpus relevance scoring (Flag 6).

Uses corpus signals (teaching canon, citations, multi-source provenance,
existing flags) as weak labels to:
  A. Search for the best query among generated candidates (AUC-ranked)
  B. Analyze score distributions and find a natural threshold
  C. Export boundary cases for human review (--hitl)

Usage:
    uv run python scripts/calibrate_reranker.py                    # full calibration
    uv run python scripts/calibrate_reranker.py --hitl             # export boundary cases
    uv run python scripts/calibrate_reranker.py --model OTHER      # try a different model
    uv run python scripts/calibrate_reranker.py --queries-only     # skip scoring, just show generated queries
"""

import argparse
import itertools
import os
import sys
import time

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.dirname(__file__))
from refine_flags import _load_config, flag_missing_metadata, flag_no_abstract, flag_title_blacklist
from utils import CATALOGS_DIR, normalize_doi

# Paths
REFINED_PATH = os.path.join(CATALOGS_DIR, "refined_works.csv")
ENRICHED_PATH = os.path.join(CATALOGS_DIR, "enriched_works.csv")


CITATIONS_PATH = os.path.join(CATALOGS_DIR, "citations.csv")
LLM_CACHE_PATH = os.path.join(CATALOGS_DIR, "llm_relevance_cache.csv")

DEFAULT_MODEL = "BAAI/bge-reranker-v2-m3"


def load_data():
    """Load works + teaching DOIs (from from_teaching column) + citation DOIs."""
    # Prefer enriched (has all papers including flagged ones)
    path = ENRICHED_PATH if os.path.exists(ENRICHED_PATH) else REFINED_PATH
    df = pd.read_csv(path)
    df["doi_norm"] = df["doi"].apply(lambda x: normalize_doi(x) if pd.notna(x) else "")
    print(f"Loaded {len(df)} works from {os.path.basename(path)}")

    # Teaching works via from_teaching column
    from_teaching = pd.to_numeric(df.get("from_teaching", 0), errors="coerce").fillna(0) == 1
    teaching_dois = set(df.loc[from_teaching, "doi_norm"]) - {""}
    print(f"Teaching works (from_teaching=1): {len(teaching_dois)} DOIs")

    # Citation target DOIs (papers cited by others in corpus)
    cited_dois = set()
    if os.path.exists(CITATIONS_PATH):
        cit = pd.read_csv(CITATIONS_PATH, usecols=["ref_doi"], dtype=str)
        cited_dois = {normalize_doi(d) for d in cit["ref_doi"].dropna() if normalize_doi(d)}
        print(f"Cited-in-corpus DOIs: {len(cited_dois)}")

    # LLM cache (for comparison, not ground truth)
    llm_cache = {}
    if os.path.exists(LLM_CACHE_PATH):
        cache_df = pd.read_csv(LLM_CACHE_PATH, dtype=str, keep_default_na=False)
        for _, row in cache_df.iterrows():
            llm_cache[row["doi"]] = row["relevant"].lower() == "true"
        print(f"LLM cache: {len(llm_cache)} entries")

    return df, teaching_dois, cited_dois, llm_cache


def build_weak_labels(df, config, teaching_dois, cited_dois):
    """Build weak positive/negative labels from corpus signals.

    Positive: teaching canon OR cited >= 50 OR source_count >= 3
    Negative: flagged by flags 1-3 (metadata, no abstract, blacklist)
    """
    doi_norm = df["doi_norm"]

    # Positive signals
    in_teaching = doi_norm.isin(teaching_dois) & (doi_norm != "")
    cited = pd.to_numeric(df["cited_by_count"], errors="coerce")
    high_cited = cited.notna() & (cited >= 50)
    sc = pd.to_numeric(df["source_count"], errors="coerce")
    multi_source = sc.notna() & (sc >= 3)

    positive = in_teaching | high_cited | multi_source

    # Negative signals (flags 1-3)
    flag1 = flag_missing_metadata(df, config)
    flag2 = flag_no_abstract(df, config)
    flag3 = flag_title_blacklist(df, config)
    negative = flag1 | flag2 | flag3

    # Exclude overlap
    negative = negative & ~positive

    print(f"\nWeak labels: {positive.sum()} positive, {negative.sum()} negative, "
          f"{len(df) - positive.sum() - negative.sum()} unlabeled")

    return positive, negative


def generate_queries():
    """Generate candidate queries for reranker calibration."""
    domains = [
        "history of economic thought on climate finance",
        "economics of climate finance",
        "climate finance policy and governance",
        "climate finance measurement and accounting",
        "climate policy economics and carbon markets",
    ]

    topics = [
        "climate finance",
        "climate finance and green investment",
        "carbon markets and environmental finance",
        "climate finance for developing countries",
        "climate policy and financial mechanisms",
    ]

    # Template-based queries
    templates = [
        "{domain}",
        "Relevance for {domain}",
        "{topic}: economic analysis, measurement, and governance",
        "{topic}",
    ]

    queries = set()
    for domain in domains:
        for tmpl in templates:
            queries.add(tmpl.format(domain=domain, topic=domain))
    for topic in topics:
        for tmpl in templates:
            queries.add(tmpl.format(domain=topic, topic=topic))

    # Keyword-based queries (combinations of key terms)
    core_terms = [
        "climate finance", "carbon market", "green bond", "climate policy",
        "environmental finance", "climate investment", "adaptation finance",
        "mitigation finance", "climate fund", "carbon pricing",
        "UNFCCC", "Paris Agreement", "climate economics",
        "development finance", "climate risk", "green investment",
    ]

    # 2-term combinations (skip 3-term to keep query count manageable on CPU)
    for combo in itertools.combinations(core_terms[:12], 2):
        queries.add(", ".join(combo))

    # The prompt from the existing LLM config
    queries.add(
        "climate finance, climate policy economics, carbon markets, "
        "green investment, environmental finance for developing countries"
    )

    # Domain-specific scholarly queries
    queries.add(
        "How economists shaped climate finance through quantification, "
        "measurement, and policy design"
    )
    queries.add(
        "Economic analysis of climate finance flows, carbon markets, "
        "and international climate policy"
    )
    queries.add(
        "Scholarly research on climate finance, UNFCCC financial mechanisms, "
        "and green investment"
    )

    queries = sorted(queries)
    print(f"Generated {len(queries)} candidate queries")
    return queries


def score_papers(model, query, texts, batch_size=64):
    """Score (query, text) pairs with cross-encoder. Returns numpy array of floats."""
    pairs = [(query, t) for t in texts]
    scores = model.predict(pairs, batch_size=batch_size, show_progress_bar=False)
    return np.array(scores, dtype=np.float32)


def compute_auc(scores, labels):
    """Compute ROC AUC without sklearn dependency."""
    pos = scores[labels]
    neg = scores[~labels]
    if len(pos) == 0 or len(neg) == 0:
        return 0.5
    # Mann-Whitney U statistic
    n_pos, n_neg = len(pos), len(neg)
    u = 0.0
    for p in pos:
        u += (neg < p).sum() + 0.5 * (neg == p).sum()
    return u / (n_pos * n_neg)


def calibrate(args):
    """Main calibration workflow."""
    config = _load_config()
    df, teaching_dois, cited_dois, llm_cache = load_data()
    positive, negative = build_weak_labels(df, config, teaching_dois, cited_dois)

    # Build calibration sample: all positive + all negative papers
    labeled_mask = positive | negative
    labels = positive[labeled_mask].values  # True = relevant
    cal_df = df[labeled_mask].reset_index(drop=True)

    # Build text for each paper
    title_max = 200
    abstract_max = 500
    texts = []
    for _, row in cal_df.iterrows():
        title = str(row["title"] if pd.notna(row.get("title")) else "")[:title_max]
        abstract = str(row["abstract"] if pd.notna(row.get("abstract")) else "")[:abstract_max]
        texts.append(f"{title}. {abstract}" if abstract else title)

    print(f"\nCalibration sample: {len(cal_df)} papers "
          f"({labels.sum()} positive, {(~labels).sum()} negative)")

    queries = generate_queries()
    if args.queries_only:
        print("\n=== Generated queries ===")
        for i, q in enumerate(queries, 1):
            print(f"  {i:3d}. {q}")
        return

    # Load model — auto-detect GPU
    import torch
    from sentence_transformers import CrossEncoder

    model_name = args.model or DEFAULT_MODEL
    device = args.device
    if device == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    if device == "cpu":
        n_cpu = os.cpu_count() or 4
        torch.set_num_threads(n_cpu)
        print(f"\nLoading reranker: {model_name} ({n_cpu} CPU threads)...")
    else:
        gpu_name = torch.cuda.get_device_name(0)
        print(f"\nLoading reranker: {model_name} (GPU: {gpu_name})...")
    t0 = time.time()
    reranker = CrossEncoder(model_name, device=device)
    print(f"  Model loaded in {time.time() - t0:.1f}s")

    # Subsample for query search: keep it small for CPU speed
    # Target: ~100 pos + ~100 neg = 200 papers (manageable with 220 queries)
    rng = np.random.default_rng(42)
    pos_idx = np.where(labels)[0]
    neg_idx = np.where(~labels)[0]
    n_pos_sample = min(len(pos_idx), 100)
    n_neg_sample = min(len(neg_idx), 100)
    pos_sample = rng.choice(pos_idx, size=n_pos_sample, replace=False)
    neg_sample = rng.choice(neg_idx, size=n_neg_sample, replace=False)
    sample_idx = np.sort(np.concatenate([pos_sample, neg_sample]))
    sample_texts = [texts[i] for i in sample_idx]
    sample_labels = labels[sample_idx]
    print(f"  Query search sample: {len(sample_idx)} papers "
          f"({sample_labels.sum()} pos, {(~sample_labels).sum()} neg)")

    # Phase D: Search for best query
    print(f"\n=== Query search ({len(queries)} candidates) ===")
    results = []
    t0 = time.time()
    for i, query in enumerate(queries):
        scores = score_papers(reranker, query, sample_texts)
        auc = compute_auc(scores, sample_labels)
        results.append((auc, query, scores))
        if (i + 1) % 20 == 0:
            elapsed = time.time() - t0
            rate = (i + 1) / elapsed
            eta = (len(queries) - i - 1) / rate
            print(f"  {i+1}/{len(queries)} queries scored "
                  f"({elapsed:.0f}s elapsed, ~{eta:.0f}s remaining)")

    results.sort(key=lambda x: -x[0])
    elapsed = time.time() - t0
    print(f"\n  Done in {elapsed:.0f}s ({len(queries)/elapsed:.1f} queries/s)")

    print(f"\n=== Top 10 queries by AUC ===")
    for rank, (auc, query, _) in enumerate(results[:10], 1):
        print(f"  {rank:2d}. AUC={auc:.4f}  {query[:80]}")

    print(f"\n=== Bottom 5 queries ===")
    for auc, query, _ in results[-5:]:
        print(f"      AUC={auc:.4f}  {query[:80]}")

    # Use the best query, score ALL calibration papers
    best_auc, best_query, _ = results[0]
    print(f"\n=== Best query (AUC={best_auc:.4f}) ===")
    print(f"  {best_query}")

    print(f"\nScoring full calibration set with best query...")
    all_scores = score_papers(reranker, best_query, texts)

    # Score distribution analysis
    pos_scores = all_scores[labels]
    neg_scores = all_scores[~labels]
    print(f"\n=== Score distributions ===")
    print(f"  Positive: mean={pos_scores.mean():.3f}, "
          f"median={np.median(pos_scores):.3f}, "
          f"std={pos_scores.std():.3f}, "
          f"[{pos_scores.min():.3f}, {pos_scores.max():.3f}]")
    print(f"  Negative: mean={neg_scores.mean():.3f}, "
          f"median={np.median(neg_scores):.3f}, "
          f"std={neg_scores.std():.3f}, "
          f"[{neg_scores.min():.3f}, {neg_scores.max():.3f}]")

    # Find optimal threshold (Youden's J)
    thresholds = np.linspace(all_scores.min(), all_scores.max(), 200)
    best_j = -1
    best_thresh = 0
    for t in thresholds:
        tp = (pos_scores >= t).sum()
        tn = (neg_scores < t).sum()
        tpr = tp / max(len(pos_scores), 1)
        tnr = tn / max(len(neg_scores), 1)
        j = tpr + tnr - 1
        if j > best_j:
            best_j = j
            best_thresh = t

    tp = (pos_scores >= best_thresh).sum()
    fn = (pos_scores < best_thresh).sum()
    tn = (neg_scores < best_thresh).sum()
    fp = (neg_scores >= best_thresh).sum()
    precision = tp / max(tp + fp, 1)
    recall = tp / max(tp + fn, 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-10)

    print(f"\n=== Optimal threshold (Youden's J = {best_j:.3f}) ===")
    print(f"  Threshold: {best_thresh:.4f}")
    print(f"  Precision: {precision:.3f}  Recall: {recall:.3f}  F1: {f1:.3f}")
    print(f"  TP={tp}  FN={fn}  FP={fp}  TN={tn}")

    # Compare with LLM cache
    if llm_cache:
        agree = 0
        disagree = 0
        for i, (_, row) in enumerate(cal_df.iterrows()):
            doi = normalize_doi(row["doi"]) if pd.notna(row.get("doi")) else ""
            if doi in llm_cache:
                reranker_relevant = all_scores[i] >= best_thresh
                if reranker_relevant == llm_cache[doi]:
                    agree += 1
                else:
                    disagree += 1
        total = agree + disagree
        if total > 0:
            print(f"\n=== LLM cache comparison ===")
            print(f"  Overlap: {total} papers")
            print(f"  Agreement: {agree}/{total} ({100*agree/total:.1f}%)")

    # Save calibration results
    out_path = os.path.join(CATALOGS_DIR, "reranker_calibration.csv")
    cal_df["reranker_score"] = all_scores
    cal_df["weak_label"] = labels
    cal_df[["doi", "title", "year", "cited_by_count", "source_count",
            "reranker_score", "weak_label"]].to_csv(out_path, index=False)
    print(f"\nSaved calibration data -> {out_path}")

    # Save recommended config
    print(f"\n=== Recommended config for corpus_refine.yaml ===")
    print(f"  reranker_model: {model_name}")
    print(f"  reranker_query: >")
    print(f"    {best_query}")
    print(f"  reranker_threshold: {best_thresh:.4f}")
    print(f"  reranker_batch_size: 64")

    # HITL export
    if args.hitl:
        export_hitl(cal_df, all_scores, best_thresh)


def export_hitl(cal_df, scores, threshold, n_samples=100):
    """Export papers near the threshold for human review."""
    distances = np.abs(scores - threshold)
    boundary_idx = np.argsort(distances)[:n_samples]

    hitl_df = cal_df.iloc[boundary_idx][
        ["doi", "title", "year", "abstract", "cited_by_count", "source_count"]
    ].copy()
    hitl_df["reranker_score"] = scores[boundary_idx]
    hitl_df["reranker_relevant"] = scores[boundary_idx] >= threshold
    hitl_df["weak_label"] = cal_df["weak_label"].iloc[boundary_idx].values
    hitl_df["human_label"] = ""  # to be filled by reviewer

    out_path = os.path.join(CATALOGS_DIR, "reranker_hitl_review.csv")
    hitl_df.to_csv(out_path, index=False)
    print(f"\n=== HITL export ===")
    print(f"  Exported {len(hitl_df)} boundary cases -> {out_path}")
    print(f"  Score range: [{scores[boundary_idx].min():.4f}, "
          f"{scores[boundary_idx].max():.4f}]")
    print(f"  Fill the 'human_label' column with True/False and re-run.")


def main():
    parser = argparse.ArgumentParser(
        description="Calibrate cross-encoder reranker for Flag 6 relevance scoring")
    parser.add_argument("--model", default=None,
                        help=f"Reranker model name (default: {DEFAULT_MODEL})")
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda"],
                        help="Device for inference (default: auto-detect)")
    parser.add_argument("--hitl", action="store_true",
                        help="Export boundary cases for human review")
    parser.add_argument("--queries-only", action="store_true",
                        help="Only print generated queries, don't score")
    parser.add_argument("--no-pdf", action="store_true",
                        help="(ignored, for pipeline compat)")
    args = parser.parse_args()
    calibrate(args)


if __name__ == "__main__":
    main()
