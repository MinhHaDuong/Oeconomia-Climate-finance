"""Flag functions and protection for corpus filtering.

Each flag function takes (df, config, **kwargs) and returns pd.Series[bool].
The orchestrator (corpus_filter.py) calls each directly — no registry, no loop.
Exceptions signal genuine errors; the orchestrator catches them.
"""

import hashlib
import json
import os
import re
import time

# Suppress HuggingFace download/progress bars for clean nohup logs
os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")

import numpy as np
import pandas as pd
import yaml

from utils import CATALOGS_DIR, CONFIG_DIR, get_logger, normalize_doi, normalize_doi_safe

log = get_logger("filter_flags")


# ============================================================
# Config loading
# ============================================================

def _load_config(path=None):
    """Load config from YAML. Defaults to config/corpus_filter.yaml."""
    if path is None:
        path = os.path.join(CONFIG_DIR, "corpus_filter.yaml")
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


def _is_from_teaching(df):
    """Return boolean mask for works originating from teaching sources.

    Uses the from_teaching column set by catalog_merge.py during deduplication.
    """
    if "from_teaching" not in df.columns:
        return pd.Series(False, index=df.index)
    return pd.to_numeric(df["from_teaching"], errors="coerce").fillna(0) == 1


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
        doi_norm = df["doi"].apply(normalize_doi_safe)
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
        doi_norm = df["doi"].apply(normalize_doi_safe)
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
    emb_dois = emb_df["doi"].apply(normalize_doi_safe)
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


def _llm_call(prompt, model):
    """Send prompt to LLM via litellm. Model string encodes the provider.

    Examples:
        ollama/qwen3.5:27b          → routes to local Ollama
        openrouter/google/gemma-2-27b-it → routes to OpenRouter

    litellm reads OPENROUTER_API_KEY from env automatically.
    """
    import litellm

    response = litellm.completion(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        max_tokens=200,
        temperature=0,
    )
    return response.choices[0].message.content.strip()


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
        doi_norm = df["doi"].apply(normalize_doi_safe)
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


def _load_reranker_model(llm_cfg):
    """Load a CrossEncoder reranker model with auto-detected device and logging.

    Returns (reranker, device) tuple.
    """
    import torch
    from sentence_transformers import CrossEncoder

    model_name = llm_cfg["reranker_model"]
    device_cfg = llm_cfg.get("reranker_device", "auto")
    if device_cfg == "auto":
        device = "cuda" if torch.cuda.is_available() else "cpu"
    else:
        device = device_cfg

    if device == "cpu":
        n_cpu = os.cpu_count() or 4
        torch.set_num_threads(n_cpu)
        log.info("    Loading reranker: %s (%d CPU threads)...", model_name, n_cpu)
    else:
        gpu_name = torch.cuda.get_device_name(0)
        log.info("    Loading reranker: %s (GPU: %s)...", model_name, gpu_name)

    t0 = time.time()
    reranker = CrossEncoder(model_name, device=device)
    log.info("    Model loaded in %.1fs", time.time() - t0)
    return reranker


def _score_batch(batch_idx, df, doi_norm, query, title_max, abstract_max, reranker):
    """Build text pairs for a batch and return (dois, scores) arrays.

    Pairs each paper's title+abstract against the reranker query.
    """
    texts = []
    dois = []
    for idx in batch_idx:
        title = str(df.at[idx, "title"] if pd.notna(df.at[idx, "title"]) else "")[:title_max]
        abstract = str(df.at[idx, "abstract"] if pd.notna(df.at[idx, "abstract"]) else "")[:abstract_max]
        texts.append(f"{title}. {abstract}" if abstract else title)
        dois.append(doi_norm.at[idx])

    pairs = [(query, t) for t in texts]
    scores = reranker.predict(pairs, batch_size=len(pairs), show_progress_bar=False)
    return dois, scores


def _yield_cached_results(priority_indices, doi_norm, cache, threshold, candidates_mask, df):
    """Yield a partial series of flag decisions for already-cached candidate indices.

    Returns a generator that yields (priority_indices, cached_results) if any cached.
    """
    cached_results = pd.Series(False, index=df.index[candidates_mask], dtype=bool)
    for i in priority_indices:
        d = doi_norm.at[i]
        if d in cache:
            cached_results.at[i] = not _is_relevant(cache[d], threshold)
    yield priority_indices, cached_results


def _reranker_streaming(df, config, *, already_flagged):
    """Score ALL papers with a cross-encoder reranker, prioritized by heuristic.

    Priority 1: concept-group failures (most likely to be flagged) — yields results
    Priority 2: remaining papers (expected to mostly pass) — scores cached for future use

    Cache is checkpointed after each batch, so interrupting preserves progress.
    Yields (indices, partial_series) for Flag 6 candidates only.
    """
    try:
        import torch  # noqa: F401
    except ImportError:
        log.warning("Flag 6 skipped: torch/sentence-transformers not installed")
        return

    llm_cfg = config["llm_relevance"]
    candidates_mask, doi_norm = _identify_candidates(df, config, already_flagged)

    query = llm_cfg["reranker_query"]
    threshold = float(llm_cfg.get("reranker_threshold", 0.5))
    batch_size = int(llm_cfg.get("reranker_batch_size", 64))
    title_max = llm_cfg.get("title_max_chars", 150)
    abstract_max = llm_cfg.get("abstract_max_chars", 250)

    cache = _load_llm_cache(config)

    # All papers with text worth scoring
    abstract_s = df["abstract"].fillna("").astype(str).str.strip()
    has_text = abstract_s.str.len() > 50
    scoreable = has_text & ~already_flagged

    # Priority 1: concept-group failures (Flag 6 candidates)
    priority1_indices = df.index[candidates_mask].tolist()
    # Priority 2: papers that pass concept-group check (background scoring)
    priority2_indices = df.index[scoreable & ~candidates_mask].tolist()

    def uncached(indices):
        return [i for i in indices
                if doi_norm.at[i] not in cache or doi_norm.at[i] == ""]

    p1_uncached = uncached(priority1_indices)
    p2_uncached = uncached(priority2_indices)
    p1_cached = len(priority1_indices) - len(p1_uncached)
    p2_cached = len(priority2_indices) - len(p2_uncached)

    log.info("    Priority 1 (concept-group failures): %d (cached: %d, to score: %d)",
             len(priority1_indices), p1_cached, len(p1_uncached))
    log.info("    Priority 2 (background scoring): %d (cached: %d, to score: %d)",
             len(priority2_indices), p2_cached, len(p2_uncached))

    if p1_cached > 0:
        yield from _yield_cached_results(
            priority1_indices, doi_norm, cache, threshold, candidates_mask, df
        )

    all_uncached = p1_uncached + p2_uncached
    if not all_uncached:
        return

    reranker = _load_reranker_model(llm_cfg)

    max_batches = int(llm_cfg.get("reranker_max_batches", 0))  # 0 = unlimited
    p1_boundary = len(p1_uncached)
    p1_set = set(p1_uncached)
    total_batches = (len(all_uncached) + batch_size - 1) // batch_size
    if max_batches > 0:
        effective_batches = min(max_batches, total_batches)
        log.info("    Limited to %d/%d batches (%d papers)",
                 effective_batches, total_batches, effective_batches * batch_size)

    for batch_start in range(0, len(all_uncached), batch_size):
        batch_idx = all_uncached[batch_start:batch_start + batch_size]
        current_batch = batch_start // batch_size + 1

        dois, scores = _score_batch(
            batch_idx, df, doi_norm, query, title_max, abstract_max, reranker
        )
        for doi, score in zip(dois, scores):
            if doi:
                cache[doi] = float(score)
        _save_llm_cache(cache, config)

        p1_in_batch = [i for i in batch_idx if i in p1_set]
        if p1_in_batch:
            partial = pd.Series(False, index=pd.Index(p1_in_batch), dtype=bool)
            for idx_val in p1_in_batch:
                d = doi_norm.at[idx_val]
                if d in cache:
                    partial.at[idx_val] = not _is_relevant(cache[d], threshold)
            yield p1_in_batch, partial

        phase = "P1" if batch_start < p1_boundary else "P2"
        if current_batch < total_batches:
            log.info("    [%s] batch %d/%d", phase, current_batch, total_batches)

        if max_batches > 0 and current_batch >= max_batches:
            log.info("    Stopped after %d batches (reranker_max_batches)", max_batches)
            break


def _resolve_llm_model(llm_cfg, backend):
    """Build provider-prefixed model string from config or env override.

    New-style: REFINE_MODEL env var takes precedence.
    Legacy: backend + ollama_model/openrouter_model keys.
    Returns (model_string, batch_size).
    """
    model = os.environ.get("REFINE_MODEL", "")
    if not model:
        if backend == "ollama":
            model = f"ollama/{llm_cfg['ollama_model']}"
        else:
            model = f"openrouter/{llm_cfg['openrouter_model']}"
    batch_size = (
        llm_cfg.get("ollama_batch_size", 5)
        if backend == "ollama"
        else llm_cfg.get("batch_size", 15)
    )
    return model, batch_size


def _score_llm_batch(batch_idx, df, doi_norm, llm_cfg, model, title_max, abstract_max):
    """Build prompt and call the LLM for one batch.

    Returns (dois, scores_dict) where scores_dict maps "1"-indexed keys to bool.
    Raises on parse error so the caller can manage retries.
    """
    papers = []
    dois = []
    for j, idx in enumerate(batch_idx):
        title = str(df.at[idx, "title"] if pd.notna(df.at[idx, "title"]) else "")[:title_max]
        abstract = str(df.at[idx, "abstract"] if pd.notna(df.at[idx, "abstract"]) else "")[:abstract_max]
        doi = doi_norm.at[idx]
        dois.append(doi)
        papers.append(f"{j+1}. Title: {title}\n   Abstract: {abstract}")

    prompt = llm_cfg["prompt_template"] + "\n\n".join(papers)
    answer = _llm_call(prompt, model)
    answer = re.sub(r"```json?\s*", "", answer)
    answer = re.sub(r"```", "", answer)
    scores = json.loads(answer)
    return dois, scores


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
        log.info("  Flag 6: no candidates (all papers pass concept-group check)")
        return

    model, batch_size = _resolve_llm_model(llm_cfg, backend)
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
    log.info("    Candidates: %d (cached: %d, to score: %d)",
             n_candidates, cached_count, len(uncached_indices))

    if cached_count > 0:
        yield from _yield_cached_results(
            candidate_indices, doi_norm, cache, 0, candidates_mask, df
        )

    retries_left = max_errors
    total_batches = (len(uncached_indices) + batch_size - 1) // batch_size

    for batch_num in range(0, len(uncached_indices), batch_size):
        batch_idx = uncached_indices[batch_num:batch_num + batch_size]
        current_batch = batch_num // batch_size + 1

        try:
            dois, scores = _score_llm_batch(
                batch_idx, df, doi_norm, llm_cfg, model, title_max, abstract_max
            )
            for j, doi in enumerate(dois):
                key = str(j + 1)
                if key in scores and doi:
                    cache[doi] = bool(scores[key])
            retries_left = max_errors
        except Exception as e:
            log.error("    LLM batch error: %s", e)
            retries_left -= 1
            if retries_left <= 0:
                log.error("    Too many consecutive errors, stopping LLM scoring")
                _save_llm_cache(cache, config)
                break
            dois = [doi_norm.at[i] for i in batch_idx]

        _save_llm_cache(cache, config)

        partial = pd.Series(False, index=pd.Index(batch_idx), dtype=bool)
        for idx_val, doi in zip(batch_idx, dois):
            if doi in cache:
                partial.at[idx_val] = not _is_relevant(cache[doi], 0)
        yield batch_idx, partial

        remaining = len(uncached_indices) - (batch_num + len(batch_idx))
        if current_batch < total_batches and remaining > 0:
            log.info("    batch %d/%d (%d candidates remaining)",
                     current_batch, total_batches, remaining)

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
        doi_norm = df["doi"].apply(normalize_doi_safe)
    else:
        doi_norm = df["doi_norm"]

    ref_dois = set()
    if citations_df is not None:
        ref_dois = set(citations_df["ref_doi"].dropna())
    cited_in_corpus = doi_norm.isin(ref_dois) & (doi_norm != "")

    in_teaching = _is_from_teaching(df)

    protected = high_cites | multi_src | cited_in_corpus | in_teaching

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
        if in_teaching.at[i]:
            r.append("from_teaching")
        reasons.at[i] = "; ".join(r)

    return protected, reasons
