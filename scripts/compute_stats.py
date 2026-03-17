"""Compute corpus statistics and write _variables.yml for Quarto.

Reads pipeline outputs (CSVs, NPZ, JSON) and produces a YAML file of
pre-formatted statistics that Quarto injects via {{< var key >}} shortcodes.

Usage:
    uv run python scripts/compute_stats.py
"""

import json
import os
import sys
import warnings

import numpy as np
import pandas as pd

from utils import BASE_DIR, CATALOGS_DIR, DATA_DIR, get_logger, load_analysis_periods

log = get_logger("compute_stats")

TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
OUTPUT_PATH = os.path.join(BASE_DIR, "_variables.yml")

MISSING = "[MISSING]"


# ── Helpers ──────────────────────────────────────────────────

def _int(value):
    """Format integer with comma thousands separator."""
    return f"{int(round(value)):,}"


def _pct(value, decimals=1):
    """Format percentage (0–100 scale) with fixed decimals."""
    return f"{value:.{decimals}f}"


def _signed_int(value):
    """Format integer with minus sign (not hyphen) for negatives."""
    v = int(round(value))
    if v < 0:
        return f"\u2212{abs(v):,}"  # Unicode minus
    return f"{v:,}"


def _read_csv(filename, directory=TABLES_DIR):
    """Read CSV, returning None with a warning if missing."""
    path = os.path.join(directory, filename)
    if not os.path.isfile(path):
        warnings.warn(f"Missing: {path}")
        return None
    return pd.read_csv(path)


def _read_json(filename, directory=TABLES_DIR):
    """Read JSON, returning None with a warning if missing."""
    path = os.path.join(directory, filename)
    if not os.path.isfile(path):
        warnings.warn(f"Missing: {path}")
        return None
    with open(path) as f:
        return json.load(f)


# ── Collectors ───────────────────────────────────────────────

def corpus_stats(v):
    """Corpus size, language, multi-source from refined_works.csv."""
    path = os.path.join(CATALOGS_DIR, "refined_works.csv")
    if not os.path.isfile(path):
        warnings.warn(f"Missing: {path}")
        return
    df = pd.read_csv(path)
    n = len(df)
    v["corpus_total"] = _int(n)
    v["corpus_total_approx"] = _int(round(n, -3))

    # Core subset
    if "cited_by_count" in df.columns:
        threshold = 50
        core = df[df["cited_by_count"] >= threshold]
        v["corpus_core"] = _int(len(core))
        v["corpus_core_threshold"] = str(threshold)

    # Multi-source
    if "source_count" in df.columns:
        multi = (df["source_count"] >= 2).sum()
        v["corpus_multi_source"] = _int(multi)
        v["corpus_multi_source_pct"] = _pct(100 * multi / n)

    # Language
    if "language" in df.columns:
        lang = df["language"].fillna("unknown")
        en_count = lang.str.lower().isin(["en", "english"]).sum()
        v["lang_english_pct"] = _pct(100 * en_count / n)

    # Sources count (from tab_corpus_sources.csv)
    sources = _read_csv("tab_corpus_sources.csv")
    if sources is not None:
        # Exclude the TOTAL row
        n_sources = len(sources[~sources.iloc[:, 0].str.contains("TOTAL", case=False, na=False)])
        v["corpus_sources"] = str(n_sources)


def embedding_stats(v):
    """Embedding count and dimensions from embeddings.npz."""
    from utils import EMBEDDINGS_PATH
    if not os.path.isfile(EMBEDDINGS_PATH):
        warnings.warn(f"Missing: {EMBEDDINGS_PATH}")
        return
    data = np.load(EMBEDDINGS_PATH)
    vectors = data["vectors"]
    v["corpus_with_embeddings"] = _int(vectors.shape[0])
    v["emb_dimensions"] = str(vectors.shape[1])


def _bimodality_period_keys():
    """Build (csv_label, var_key) pairs from config for bimodality lookups.

    csv_label: matches the 'method' column written by analyze_bimodality.py
               (e.g. "embedding_1990–2006")
    var_key:   Quarto variable suffix (e.g. "pre2007", "2007_2014", "post2015")
    """
    _period_tuples, _period_labels = load_analysis_periods()
    pairs = []
    for i, label in enumerate(_period_labels):
        csv_label = f"embedding_{label}"
        lo, hi = _period_tuples[i]
        if i == 0:
            key = f"pre{hi + 1}"
        elif i == len(_period_labels) - 1:
            key = f"post{lo}"
        else:
            key = f"{lo}_{hi}"
        pairs.append((csv_label, key))
    return pairs


def bimodality_stats(v):
    """Bimodality results from tab_bimodality.csv and tab_bimodality_core.csv."""
    df = _read_csv("tab_bimodality.csv")
    if df is None:
        return

    # Full corpus — embedding row
    emb = df[df["method"] == "embedding"]
    if not emb.empty:
        row = emb.iloc[0]
        v["bim_n_efficiency"] = _int(row["n_efficiency_pole"])
        v["bim_n_accountability"] = _int(row["n_accountability_pole"])
        v["bim_n_overlap"] = _int(row["n_both_poles"])
        v["bim_dbic_embedding"] = _signed_int(row["delta_bic"])
        v["bim_bic1"] = _signed_int(row["bic_1comp"])
        v["bim_bic2"] = _signed_int(row["bic_2comp"])
        v["bim_corr"] = f"{row['embedding_lexical_corr']:.2f}"
        v["bim_var_pct"] = _pct(100 * row["explained_variance"])

    # Full corpus — TF-IDF row
    tfidf = df[df["method"] == "tfidf_lexical"]
    if not tfidf.empty:
        v["bim_dbic_tfidf"] = _signed_int(tfidf.iloc[0]["delta_bic"])

    # Per-period rows
    for label, key in _bimodality_period_keys():
        period = df[df["method"] == label]
        if not period.empty:
            row = period.iloc[0]
            v[f"bim_dbic_{key}"] = _signed_int(row["delta_bic"])
            v[f"bim_n_{key}"] = _int(row["n_papers"])

    # Core
    core = _read_csv("tab_bimodality_core.csv")
    if core is None:
        return
    emb_core = core[core["method"] == "embedding"]
    if not emb_core.empty:
        row = emb_core.iloc[0]
        v["bim_core_dbic_embedding"] = _signed_int(row["delta_bic"])
        v["bim_core_n_efficiency"] = _int(row["n_efficiency_pole"])
        v["bim_core_n_accountability"] = _int(row["n_accountability_pole"])
    tfidf_core = core[core["method"] == "tfidf_lexical"]
    if not tfidf_core.empty:
        v["bim_core_dbic_tfidf"] = _signed_int(tfidf_core.iloc[0]["delta_bic"])

    # Core per-period
    for label, key in _bimodality_period_keys():
        period = core[core["method"] == label]
        if not period.empty:
            v[f"bim_core_dbic_{key}"] = _signed_int(period.iloc[0]["delta_bic"])


def pca_stats(v):
    """PCA axis detection from tab_axis_detection.csv."""
    df = _read_csv("tab_axis_detection.csv")
    if df is None:
        return

    for _, row in df.iterrows():
        comp = row["component"]
        if comp == "emb_PC1":
            v["pca_emb_pc1_var_pct"] = _pct(100 * row["explained_variance_ratio"])
        elif comp == "emb_PC2":
            v["pca_emb_pc2_var_pct"] = _pct(100 * row["explained_variance_ratio"])
            v["pca_emb_pc2_cosine"] = f"{row['corr_with_embedding_axis']:.3f}"
            v["pca_emb_pc2_dbic"] = _signed_int(row["delta_bic"])
        elif comp == "emb_PC4":
            v["pca_emb_pc4_var_pct"] = _pct(100 * row["explained_variance_ratio"])
            cosine = row["corr_with_embedding_axis"]
            if cosine < 0:
                v["pca_emb_pc4_cosine"] = f"\u2212{abs(cosine):.3f}"
            else:
                v["pca_emb_pc4_cosine"] = f"{cosine:.3f}"
            v["pca_emb_pc4_dbic"] = _signed_int(row["delta_bic"])

    # Core — tab_axis_detection_core.csv has different columns (no delta_bic)
    # The core max ΔBIC comes from tab_bimodality_core.csv instead


def citation_stats(v):
    """Citation graph coverage from qa_citations_report.json + citations.csv."""
    report = _read_json("qa_citations_report.json")
    if report is not None:
        c = report["corpus"]
        v["cite_total_dois"] = _int(c["total_dois"])
        v["cite_crossref_rows"] = _int(c["total_citation_rows"])

    # Read actual citations.csv for current totals (post-OpenAlex)
    cite_path = os.path.join(CATALOGS_DIR, "citations.csv")
    if os.path.isfile(cite_path):
        # Read just the header + count rows efficiently
        cite_df = pd.read_csv(cite_path, usecols=["source_doi", "ref_doi"])
        v["cite_total_rows"] = _int(len(cite_df))
        doi_ref_rows = cite_df["ref_doi"].notna().sum()
        v["cite_doi_ref_rows"] = _int(doi_ref_rows)
        v["cite_doi_ref_pct"] = _pct(100 * doi_ref_rows / len(cite_df), 0)

        fetched = cite_df["source_doi"].nunique()
        v["cite_fetched_dois"] = _int(fetched)

        if "cite_total_dois" in v:
            total_dois = int(v["cite_total_dois"].replace(",", ""))
            v["cite_coverage_pct"] = _pct(100 * fetched / total_dois, 0)
            v["cite_never_fetched"] = _int(total_dois - fetched)


# ── Write YAML ───────────────────────────────────────────────

def write_yaml(v, path):
    """Write variables dict as a YAML file with all values quoted."""
    lines = ["# Auto-generated by scripts/compute_stats.py — do not edit\n"]
    for key in sorted(v.keys()):
        val = v[key]
        # Quote all values to prevent YAML type coercion
        escaped = val.replace('"', '\\"')
        lines.append(f'{key}: "{escaped}"')
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    log.info("Wrote %d variables to %s", len(v), path)


# ── Main ─────────────────────────────────────────────────────

def main():
    v = {}
    corpus_stats(v)
    embedding_stats(v)
    bimodality_stats(v)
    pca_stats(v)
    citation_stats(v)

    # Static constants (single source of truth)
    v["emb_model"] = "paraphrase-multilingual-MiniLM-L12-v2"

    write_yaml(v, OUTPUT_PATH)

    # Summary
    missing = [k for k, val in v.items() if val == MISSING]
    if missing:
        log.warning("%d variables set to %s: %s", len(missing), MISSING, missing)


if __name__ == "__main__":
    main()
