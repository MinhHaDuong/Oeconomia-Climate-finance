"""Flag functions and protection for corpus filtering.

Each flag function takes (df, config, **kwargs) and returns pd.Series[bool].
The orchestrator (corpus_filter.py) calls each directly — no registry, no loop.
Exceptions signal genuine errors; the orchestrator catches them.

Flag 6 (LLM relevance) lives in filter_flags_llm.py — re-exported here for
backward compatibility with corpus_filter.py and calibrate_reranker.py.
"""

import os
import re

import numpy as np
import pandas as pd
import yaml
from utils import CATALOGS_DIR, CONFIG_DIR, get_logger, normalize_doi_safe

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
# Flag 6: LLM relevance (delegated to filter_flags_llm.py)
# ============================================================

# Re-export for backward compatibility — corpus_filter.py and tests import from here
from filter_flags_llm import (  # noqa: E402, F401
    _cache_key,
    flag_llm_irrelevant,
    flag_llm_irrelevant_streaming,
)


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
