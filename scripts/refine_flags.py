"""Flag functions and protection for corpus refinement.

Each flag function takes (df, config, **kwargs) and returns pd.Series[bool].
The orchestrator (corpus_refine.py) calls each directly — no registry, no loop.
Exceptions signal genuine errors; the orchestrator catches them.
"""

import hashlib
import json
import os
import re
import time

import numpy as np
import pandas as pd
import yaml

import sys

sys.path.insert(0, os.path.dirname(__file__))
from utils import CATALOGS_DIR, CONFIG_DIR, normalize_doi


# ============================================================
# Config loading
# ============================================================

def _load_config(path=None):
    """Load config from YAML. Defaults to config/corpus_refine.yaml."""
    if path is None:
        path = os.path.join(CONFIG_DIR, "corpus_refine.yaml")
    with open(path) as f:
        return yaml.safe_load(f)


# ============================================================
# Private helpers
# ============================================================

def _has_safe_words(title, safe_words):
    """Check if title contains any safe/relevant words."""
    if not title:
        return False
    t = title.lower()
    return any(s in t for s in safe_words)


def _text_has_concept_groups(text, groups, min_groups):
    """Check if text mentions at least min_groups concept groups."""
    if not text:
        return False
    words = set(re.findall(r'[a-z]{3,}', text.lower()))
    groups_hit = sum(1 for gw in groups.values() if words & set(gw))
    return groups_hit >= min_groups


def _load_teaching_canon(config):
    """Load teaching canon DOIs (papers used in N+ syllabi)."""
    min_count = config.get("protection", {}).get("min_teaching_count", 2)
    canon_path = os.path.join(CATALOGS_DIR, "teaching_canon.csv")
    if not os.path.exists(canon_path):
        return set()
    canon_df = pd.read_csv(canon_path, dtype=str, keep_default_na=False)
    canon_df = canon_df[
        pd.to_numeric(canon_df["teaching_count"], errors="coerce") >= min_count
    ]
    dois = set()
    for d in canon_df["doi"]:
        nd = normalize_doi(d)
        if nd:
            dois.add(nd)
    return dois


# ============================================================
# Flag 1: Missing metadata
# ============================================================

def flag_missing_metadata(df, config):
    """Flag papers with missing title/author/year (rescued by safe title words).

    Returns pd.Series[bool] aligned with df.index.
    """
    safe_words = config["safe_title"]

    title_s = df["title"].fillna("").astype(str).str.strip()
    author_s = df["first_author"].fillna("").astype(str).str.strip()
    year_s = df["year"].fillna("").astype(str).str.strip()

    miss_title = (title_s == "") | (title_s == "nan")
    miss_author = (author_s == "") | (author_s == "nan")
    miss_year = (year_s == "") | (year_s == "nan")

    title_lower = title_s.str.lower()
    safe_pattern = "|".join(re.escape(s) for s in safe_words)
    title_has_safe = title_lower.str.contains(safe_pattern, na=False)

    # Missing title -> always flag; missing author/year -> only if title lacks safe words
    mask = miss_title | ((miss_author | miss_year) & ~title_has_safe)
    return mask


# ============================================================
# Flag 2: No abstract + irrelevant title
# ============================================================

def flag_no_abstract(df, config):
    """Flag papers with no/short abstract and no safe words in title.

    Returns pd.Series[bool] aligned with df.index.
    """
    safe_words = config["safe_title"]

    title_lower = df["title"].fillna("").astype(str).str.strip().str.lower()
    safe_pattern = "|".join(re.escape(s) for s in safe_words)
    title_has_safe = title_lower.str.contains(safe_pattern, na=False)

    abstract_s = df["abstract"].fillna("").astype(str).str.strip()
    has_abstract = abstract_s.str.len() > 50

    return ~has_abstract & ~title_has_safe


# ============================================================
# Flag 3: Title blacklist
# ============================================================

def flag_title_blacklist(df, config):
    """Flag papers whose title matches noise words but not safe words,
    or whose title exactly matches journal front/back matter.

    Returns pd.Series[bool] aligned with df.index.
    """
    noise_words = config["noise_title"]
    safe_words = config["safe_title"]

    title_lower = df["title"].fillna("").astype(str).str.strip().str.lower()
    noise_pattern = "|".join(re.escape(n) for n in noise_words)
    safe_pattern = "|".join(re.escape(s) for s in safe_words)

    title_has_noise = title_lower.str.contains(noise_pattern, na=False)
    title_has_safe = title_lower.str.contains(safe_pattern, na=False)

    noise_match = title_has_noise & ~title_has_safe

    # Exact-match titles (journal front/back matter)
    exact_noise = config.get("noise_title_exact", [])
    if exact_noise:
        exact_set = {t.lower().strip() for t in exact_noise}
        exact_match = title_lower.isin(exact_set)
        noise_match = noise_match | exact_match

    return noise_match


# ============================================================
# Flag 4: Citation isolation
# ============================================================

def flag_citation_isolated(df, config, *, citations_df):
    """Flag old papers with DOI that are neither cited nor citing in the corpus.

    Returns pd.Series[bool] aligned with df.index.
    Raises ValueError if citations_df is None.
    """
    if citations_df is None:
        raise ValueError("citations_df is required for citation isolation flag")

    max_year = config["citation_isolation"]["max_year"]

    # Ensure doi_norm exists
    if "doi_norm" not in df.columns:
        doi_norm = df["doi"].apply(lambda x: normalize_doi(x) if pd.notna(x) else "")
    else:
        doi_norm = df["doi_norm"]

    cited_dois = set()
    citing_dois = set()
    if len(citations_df) > 0:
        cited_dois = set(citations_df["ref_doi"].dropna())
        citing_dois = set(citations_df["source_doi"].dropna())

    year_num = pd.to_numeric(df["year"], errors="coerce")
    is_old = year_num.notna() & (year_num <= max_year)
    has_doi = doi_norm != ""
    is_cited = doi_norm.isin(cited_dois)
    is_citing = doi_norm.isin(citing_dois)

    return is_old & has_doi & ~is_cited & ~is_citing


# ============================================================
# Flag 5: Semantic outlier
# ============================================================

def flag_semantic_outlier(df, config, *, embeddings, emb_df):
    """Flag papers whose embedding is >sigma*std from centroid.

    Returns (pd.Series[bool], pd.Series[float]) aligned with df.index.
    Raises ValueError if embeddings or emb_df is None or size mismatch.
    """
    if embeddings is None or emb_df is None:
        raise ValueError("embeddings and emb_df are required for semantic outlier flag")

    if len(embeddings) != len(emb_df):
        raise ValueError(
            f"embedding size mismatch ({len(embeddings)} vs {len(emb_df)})"
        )

    sigma = config["semantic_outlier"]["sigma"]

    # Ensure doi_norm exists
    if "doi_norm" not in df.columns:
        doi_norm = df["doi"].apply(lambda x: normalize_doi(x) if pd.notna(x) else "")
    else:
        doi_norm = df["doi_norm"]

    centroid = embeddings.mean(axis=0)
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    norms[norms == 0] = 1
    normed = embeddings / norms
    centroid_normed = centroid / max(np.linalg.norm(centroid), 1e-10)
    cos_sim = normed @ centroid_normed
    cos_dist = 1 - cos_sim

    mean_dist = cos_dist.mean()
    std_dist = cos_dist.std()
    threshold = mean_dist + sigma * std_dist

    # Build DOI -> distance mapping
    emb_dois = emb_df["doi"].apply(
        lambda x: normalize_doi(x) if pd.notna(x) else ""
    )
    emb_doi_to_dist = dict(zip(emb_dois, cos_dist))
    emb_doi_to_dist.pop("", None)

    # Map to main df
    outlier_dists = doi_norm.map(emb_doi_to_dist)
    flag_mask = outlier_dists.notna() & (outlier_dists > threshold)

    return flag_mask, outlier_dists


# ============================================================
# Flag 6: LLM relevance
# ============================================================

LLM_CACHE_PATH = os.path.join(CATALOGS_DIR, "llm_relevance_cache.csv")


def _cache_key(config):
    """Hash of backend + model + query/prompt for cache invalidation."""
    llm = config["llm_relevance"]
    backend = llm["backend"]
    if backend == "reranker":
        model = llm["reranker_model"]
        # Don't include threshold — score cache is reusable across thresholds
        blob = f"{backend}:{model}\n{llm['reranker_query']}"
    elif backend == "ollama":
        model = llm["ollama_model"]
        blob = f"{backend}:{model}\n{llm['prompt_template']}"
    else:
        model = llm["openrouter_model"]
        blob = f"{backend}:{model}\n{llm['prompt_template']}"
    return hashlib.sha256(blob.encode()).hexdigest()[:12]


def _load_llm_cache(config):
    """Load cached relevance scores, filtering by config hash.

    Returns dict: {doi: value} where value is float (reranker score) or bool (LLM).
    """
    cache = {}
    current_hash = _cache_key(config)
    if os.path.exists(LLM_CACHE_PATH):
        cache_df = pd.read_csv(LLM_CACHE_PATH, dtype=str, keep_default_na=False)
        for _, row in cache_df.iterrows():
            row_hash = row.get("config_hash", "")
            if row_hash == "" or row_hash == current_hash:
                # Reranker stores float scores; LLM stores bool
                score_str = row.get("score", "")
                if score_str != "":
                    cache[row["doi"]] = float(score_str)
                else:
                    cache[row["doi"]] = row["relevant"].lower() == "true"
    return cache


def _save_llm_cache(cache, config):
    """Save relevance cache to CSV with config hash.

    Supports both float scores (reranker) and bool (LLM) values.
    """
    current_hash = _cache_key(config)
    rows = []
    for doi, val in cache.items():
        if isinstance(val, float):
            rows.append({"doi": doi, "relevant": str(val >= 0),
                         "score": f"{val:.6f}", "config_hash": current_hash})
        else:
            rows.append({"doi": doi, "relevant": str(val),
                         "score": "", "config_hash": current_hash})
    pd.DataFrame(rows).to_csv(LLM_CACHE_PATH, index=False)


def _llm_call(prompt, backend, api_key, model):
    """Send prompt to LLM backend. Returns parsed response text."""
    import urllib.request

    if backend == "ollama":
        body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
            "options": {"temperature": 0},
        }).encode()
        url = os.environ.get("OLLAMA_URL", "http://localhost:11434")
        req = urllib.request.Request(
            f"{url}/api/chat",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read())
        return result["message"]["content"].strip()
    else:
        # OpenRouter
        body = json.dumps({
            "model": model,
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
        with urllib.request.urlopen(req, timeout=60) as resp:
            result = json.loads(resp.read())
        return result["choices"][0]["message"]["content"].strip()


def _is_relevant(cache_val, threshold):
    """Check if a cached value indicates relevance.

    For reranker: float score >= threshold means relevant.
    For LLM: bool True means relevant.
    """
    if isinstance(cache_val, float):
        return cache_val >= threshold
    return bool(cache_val)


def _identify_candidates(df, config, already_flagged):
    """Identify Flag 6 candidates: have abstract, low concept groups, not already flagged.

    Returns (candidates_mask, doi_norm).
    """
    concept_groups = {k: set(v) for k, v in config["concept_groups"].items()}
    min_groups = config["min_concept_groups"]

    if "doi_norm" not in df.columns:
        doi_norm = df["doi"].apply(lambda x: normalize_doi(x) if pd.notna(x) else "")
    else:
        doi_norm = df["doi_norm"]

    abstract_s = df["abstract"].fillna("").astype(str).str.strip()
    has_text = abstract_s.str.len() > 50

    title_s = df["title"].fillna("").astype(str)
    low_concept_title = ~title_s.apply(
        lambda t: _text_has_concept_groups(str(t), concept_groups, min_groups)
    )
    low_concept_abstract = ~abstract_s.apply(
        lambda a: _text_has_concept_groups(str(a), concept_groups, min_groups)
    )
    candidates_mask = has_text & low_concept_title & low_concept_abstract & ~already_flagged
    return candidates_mask, doi_norm


def _reranker_streaming(df, config, *, already_flagged):
    """Score papers with a local cross-encoder reranker. Yields (indices, partial_series)."""
    import torch
    from sentence_transformers import CrossEncoder

    llm_cfg = config["llm_relevance"]
    candidates_mask, doi_norm = _identify_candidates(df, config, already_flagged)

    n_candidates = candidates_mask.sum()
    if n_candidates == 0:
        print("  Flag 6: no candidates (all papers pass concept-group check)")
        return

    model_name = llm_cfg["reranker_model"]
    query = llm_cfg["reranker_query"]
    threshold = float(llm_cfg.get("reranker_threshold", 0.5))
    batch_size = int(llm_cfg.get("reranker_batch_size", 64))
    title_max = llm_cfg.get("title_max_chars", 150)
    abstract_max = llm_cfg.get("abstract_max_chars", 250)

    cache = _load_llm_cache(config)
    candidate_indices = df.index[candidates_mask].tolist()

    uncached_indices = [
        i for i in candidate_indices
        if doi_norm.at[i] not in cache or doi_norm.at[i] == ""
    ]
    cached_count = n_candidates - len(uncached_indices)
    print(f"    Candidates: {n_candidates} "
          f"(cached: {cached_count}, to score: {len(uncached_indices)})")

    # Yield cached results
    if cached_count > 0:
        cached_results = pd.Series(False, index=df.index[candidates_mask], dtype=bool)
        for i in candidate_indices:
            d = doi_norm.at[i]
            if d in cache:
                cached_results.at[i] = not _is_relevant(cache[d], threshold)
        yield candidate_indices, cached_results

    if not uncached_indices:
        return

    # Load model
    n_cpu = os.cpu_count() or 4
    torch.set_num_threads(n_cpu)
    print(f"    Loading reranker: {model_name} ({n_cpu} threads)...")
    t0 = time.time()
    reranker = CrossEncoder(model_name)
    print(f"    Model loaded in {time.time() - t0:.1f}s")

    # Score in batches
    total_batches = (len(uncached_indices) + batch_size - 1) // batch_size
    for batch_num in range(0, len(uncached_indices), batch_size):
        batch_idx = uncached_indices[batch_num:batch_num + batch_size]
        current_batch = batch_num // batch_size + 1

        texts = []
        dois = []
        for idx in batch_idx:
            title = str(df.at[idx, "title"] if pd.notna(df.at[idx, "title"]) else "")[:title_max]
            abstract = str(df.at[idx, "abstract"] if pd.notna(df.at[idx, "abstract"]) else "")[:abstract_max]
            texts.append(f"{title}. {abstract}" if abstract else title)
            dois.append(doi_norm.at[idx])

        pairs = [(query, t) for t in texts]
        scores = reranker.predict(pairs, batch_size=len(pairs), show_progress_bar=False)

        for doi, score in zip(dois, scores):
            if doi:
                cache[doi] = float(score)

        _save_llm_cache(cache, config)

        partial = pd.Series(False, index=pd.Index(batch_idx), dtype=bool)
        for idx_val, doi in zip(batch_idx, dois):
            if doi in cache:
                partial.at[idx_val] = not _is_relevant(cache[doi], threshold)
        yield batch_idx, partial

        if current_batch < total_batches:
            print(f"    batch {current_batch}/{total_batches}")


def flag_llm_irrelevant_streaming(df, config, *, already_flagged):
    """Yield (batch_indices, partial_series) for Flag 6 scoring.

    Dispatches to reranker or LLM backend based on config.
    Candidates: papers with abstract, <min_groups concept groups, not already flagged.
    Uses persistent DOI-keyed cache with config hash.
    """
    llm_cfg = config["llm_relevance"]
    backend = llm_cfg["backend"]

    if backend == "reranker":
        yield from _reranker_streaming(df, config, already_flagged=already_flagged)
        return

    # LLM backends (openrouter / ollama)
    candidates_mask, doi_norm = _identify_candidates(df, config, already_flagged)

    n_candidates = candidates_mask.sum()
    if n_candidates == 0:
        print("  Flag 6: no candidates (all papers pass concept-group check)")
        return

    if backend == "ollama":
        model = llm_cfg["ollama_model"]
        api_key = ""
        batch_size = llm_cfg.get("ollama_batch_size", 5)
    else:
        api_key = os.environ.get("OPENROUTER_API_KEY", "")
        model = llm_cfg["openrouter_model"]
        batch_size = llm_cfg.get("batch_size", 15)
        if not api_key:
            print("    WARNING: no OPENROUTER_API_KEY, skipping LLM scoring")
            return

    title_max = llm_cfg.get("title_max_chars", 150)
    abstract_max = llm_cfg.get("abstract_max_chars", 250)
    max_errors = llm_cfg.get("max_consecutive_errors", 3)

    cache = _load_llm_cache(config)
    candidate_indices = df.index[candidates_mask].tolist()

    uncached_indices = [
        i for i in candidate_indices
        if doi_norm.at[i] not in cache or doi_norm.at[i] == ""
    ]
    cached_count = n_candidates - len(uncached_indices)
    print(f"    Candidates: {n_candidates} "
          f"(cached: {cached_count}, to score: {len(uncached_indices)})")

    # Yield cached results first
    if cached_count > 0:
        cached_results = pd.Series(False, index=df.index[candidates_mask], dtype=bool)
        for i in candidate_indices:
            d = doi_norm.at[i]
            if d in cache:
                cached_results.at[i] = not _is_relevant(cache[d], 0)
        yield candidate_indices, cached_results

    # Score uncached in batches
    retries_left = max_errors
    total_batches = (len(uncached_indices) + batch_size - 1) // batch_size

    for batch_num in range(0, len(uncached_indices), batch_size):
        batch_idx = uncached_indices[batch_num:batch_num + batch_size]
        current_batch = batch_num // batch_size + 1

        papers = []
        dois = []
        for j, idx in enumerate(batch_idx):
            title = str(df.at[idx, "title"] if pd.notna(df.at[idx, "title"]) else "")[:title_max]
            abstract = str(df.at[idx, "abstract"] if pd.notna(df.at[idx, "abstract"]) else "")[:abstract_max]
            doi = doi_norm.at[idx]
            dois.append(doi)
            papers.append(f"{j+1}. Title: {title}\n   Abstract: {abstract}")

        prompt = llm_cfg["prompt_template"] + "\n\n".join(papers)

        try:
            answer = _llm_call(prompt, backend, api_key, model)
            answer = re.sub(r"```json?\s*", "", answer)
            answer = re.sub(r"```", "", answer)
            scores = json.loads(answer)

            for j, doi in enumerate(dois):
                key = str(j + 1)
                if key in scores and doi:
                    cache[doi] = bool(scores[key])
            retries_left = max_errors
        except Exception as e:
            print(f"    LLM batch error: {e}")
            retries_left -= 1
            if retries_left <= 0:
                print("    Too many consecutive errors, stopping LLM scoring")
                _save_llm_cache(cache, config)
                break

        _save_llm_cache(cache, config)

        partial = pd.Series(False, index=pd.Index(batch_idx), dtype=bool)
        for idx_val, doi in zip(batch_idx, dois):
            if doi in cache:
                partial.at[idx_val] = not _is_relevant(cache[doi], 0)
        yield batch_idx, partial

        remaining = len(uncached_indices) - (batch_num + len(batch_idx))
        if current_batch < total_batches and remaining > 0:
            print(f"    batch {current_batch}/{total_batches} "
                  f"({remaining} candidates remaining)")

        time.sleep(1.0 if backend == "openrouter" else 0.1)


def flag_llm_irrelevant(df, config, *, already_flagged):
    """Score papers via LLM, return pd.Series[bool] (True = irrelevant).

    Wraps flag_llm_irrelevant_streaming() by consuming the full generator.
    """
    result = pd.Series(False, index=df.index, dtype=bool)
    for batch_idx, partial in flag_llm_irrelevant_streaming(
            df, config, already_flagged=already_flagged):
        result.loc[partial.index] = partial
    return result


# ============================================================
# Protection
# ============================================================

def compute_protection(df, config, *, citations_df):
    """Mark papers as protected based on citations, sources, teaching canon.

    Returns (pd.Series[bool], pd.Series[str]) for (protected, protect_reason).
    """
    prot_cfg = config["protection"]
    min_cited_by = prot_cfg["min_cited_by"]
    min_source_count = prot_cfg["min_source_count"]

    cites = pd.to_numeric(df["cited_by_count"], errors="coerce")
    sc = pd.to_numeric(df["source_count"], errors="coerce")

    high_cites = cites.notna() & (cites >= min_cited_by)
    multi_src = sc.notna() & (sc >= min_source_count)

    # Ensure doi_norm exists
    if "doi_norm" not in df.columns:
        doi_norm = df["doi"].apply(lambda x: normalize_doi(x) if pd.notna(x) else "")
    else:
        doi_norm = df["doi_norm"]

    ref_dois = set()
    if citations_df is not None:
        ref_dois = set(citations_df["ref_doi"].dropna())
    cited_in_corpus = doi_norm.isin(ref_dois) & (doi_norm != "")

    teaching_dois = _load_teaching_canon(config)
    in_teaching_canon = doi_norm.isin(teaching_dois) & (doi_norm != "")

    protected = high_cites | multi_src | cited_in_corpus | in_teaching_canon

    # Build reason strings
    reasons = pd.Series("", index=df.index)
    for i in protected[protected].index:
        r = []
        if high_cites.at[i]:
            r.append(f"cited_by={int(cites.at[i])}")
        if multi_src.at[i]:
            r.append(f"multi_source={int(sc.at[i])}")
        if cited_in_corpus.at[i]:
            r.append("cited_in_corpus")
        if in_teaching_canon.at[i]:
            r.append("teaching_canon")
        reasons.at[i] = "; ".join(r)

    return protected, reasons
