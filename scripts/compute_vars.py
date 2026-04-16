"""Compute corpus statistics and write per-document vars files for Quarto.

Reads pipeline outputs (CSVs, NPZ, JSON) and produces one YAML file per
Quarto document, each containing only the variables that document uses.
Quarto injects them via {{< meta key >}} shortcodes.

Usage:
    uv run python scripts/compute_vars.py
"""

import json
import os
import sys
import warnings

import numpy as np
import pandas as pd
from script_io_args import parse_io_args, validate_io
from utils import (
    BASE_DIR,
    CATALOGS_DIR,
    SOURCE_NAMES,
    get_logger,
    load_analysis_periods,
)

log = get_logger("compute_vars")

TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
CONTENT_DIR = os.path.join(BASE_DIR, "content")

# Which variables each document uses (direct + {{< include >}}'d files).
# Each document gets a sibling -vars.yml containing only its variables.
DOC_VARS = {
    # "manuscript" is pinned to v1.0 values — not auto-generated.
    # Edit content/manuscript-vars.yml manually if needed.
    "technical-report": [
        # direct: corpus_sources, corpus_total
        # includes: bimodality-analysis, citation-quality, core-vs-full,
        #   corpus-construction, corpus-enrichment, corpus-filtering,
        #   pca-scatter, structural-breaks, alluvial-diagram
        "bim_bic1",
        "bim_bic2",
        "bim_core_dbic_embedding",
        "bim_core_dbic_tfidf",
        "bim_core_n_accountability",
        "bim_core_n_efficiency",
        "bim_corr",
        "bim_dbic_2007_2014",
        "bim_dbic_embedding",
        "bim_dbic_post2015",
        "bim_dbic_pre2007",
        "bim_dbic_tfidf",
        "bim_n_2007_2014",
        "bim_n_accountability",
        "bim_n_efficiency",
        "bim_n_overlap",
        "bim_n_post2015",
        "bim_n_pre2007",
        "bim_var_pct",
        "cite_refined_rows",
        "cite_refined_sources",
        "corpus_core",
        "corpus_core_threshold",
        "corpus_sources",
        "corpus_total",
        "corpus_with_embeddings",
        "analysis_corpus_n",
        "emb_dimensions",
        "pca_emb_pc2_cosine",
        "pca_emb_pc2_dbic",
        "pca_emb_pc2_var_pct",
        "pca_emb_pc4_cosine",
        "pca_emb_pc4_dbic",
        "pca_emb_pc4_var_pct",
    ],
    "data-paper": [
        # direct + includes: corpus-construction, corpus-filtering,
        #   embedding-generation
        "cite_coverage_core_pct",
        "cite_refined_coverage_pct",
        "cite_refined_rows",
        "cite_total_rows",
        "corpus_core",
        "corpus_core_threshold",
        "corpus_multi_source",
        "corpus_multi_source_pct",
        "corpus_raw",
        "corpus_removal_pct",
        "corpus_sources",
        "corpus_total",
        "corpus_with_embeddings",
        "emb_dimensions",
        "filter_citation_isolated",
        "filter_flagged",
        "filter_llm_irrelevant",
        "filter_missing_metadata",
        "filter_net_removals",
        "filter_no_abstract",
        "filter_protected",
        "filter_title_blacklist",
        "lang_english_pct",
        "openalex_pct",
    ],
    "companion-paper": [
        # direct + includes: bimodality-analysis, core-vs-full,
        #   embedding-generation, pca-scatter, structural-breaks,
        #   alluvial-diagram
        "bim_bic1",
        "bim_bic2",
        "bim_core_dbic_embedding",
        "bim_core_dbic_tfidf",
        "bim_core_n_accountability",
        "bim_core_n_efficiency",
        "bim_corr",
        "bim_dbic_2007_2014",
        "bim_dbic_embedding",
        "bim_dbic_post2015",
        "bim_dbic_pre2007",
        "bim_dbic_tfidf",
        "bim_n_2007_2014",
        "bim_n_accountability",
        "bim_n_efficiency",
        "bim_n_overlap",
        "bim_n_post2015",
        "bim_n_pre2007",
        "bim_var_pct",
        "corpus_core",
        "corpus_core_threshold",
        "corpus_sources",
        "corpus_total",
        "corpus_total_approx",
        "corpus_with_embeddings",
        "analysis_corpus_n",
        "emb_dimensions",
        "lang_english_pct",
        "pca_emb_pc1_var_pct",
        "pca_emb_pc2_cosine",
        "pca_emb_pc2_dbic",
        "pca_emb_pc2_var_pct",
        "pca_emb_pc4_cosine",
        "pca_emb_pc4_dbic",
        "pca_emb_pc4_var_pct",
    ],
}

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

    v["corpus_sources"] = str(len(SOURCE_NAMES))

    # OpenAlex share of refined works
    if "from_openalex" in df.columns:
        oa_pct = 100 * df["from_openalex"].sum() / n
        v["openalex_pct"] = _pct(oa_pct)

    # Raw (pre-filter) count from unified_works.csv
    unified_path = os.path.join(CATALOGS_DIR, "unified_works.csv")
    if os.path.isfile(unified_path):
        unified_n = len(pd.read_csv(unified_path, usecols=["source"]))
        v["corpus_raw"] = _int(unified_n)
        v["corpus_removal_pct"] = _pct(100 * (unified_n - n) / unified_n)


def filter_stats(v):
    """Flag counts from corpus_audit.csv for the data paper."""
    audit_path = os.path.join(CATALOGS_DIR, "corpus_audit.csv")
    if not os.path.isfile(audit_path):
        warnings.warn(f"Missing: {audit_path}")
        return
    audit = pd.read_csv(audit_path, usecols=["action", "flags", "protected"])

    # Flagged = non-empty flags column
    flagged_mask = audit["flags"].fillna("").str.strip() != ""
    v["filter_flagged"] = _int(flagged_mask.sum())

    # Per-flag counts (non-exclusive, pipe-separated)
    all_flags = audit["flags"].dropna().str.split("|").explode().str.strip()
    all_flags = all_flags[all_flags != ""]
    counts = all_flags.value_counts()

    v["filter_citation_isolated"] = _int(counts.get("citation_isolated_old", 0))
    v["filter_llm_irrelevant"] = _int(counts.get("llm_irrelevant", 0))
    v["filter_no_abstract"] = _int(counts.get("no_abstract_irrelevant", 0))
    v["filter_title_blacklist"] = _int(counts.get("title_blacklist", 0))
    # missing_metadata has sub-types (missing_metadata:title, etc.)
    missing = counts.filter(like="missing_metadata").sum()
    v["filter_missing_metadata"] = _int(int(missing))

    # Flagged but kept = protected from removal
    flagged_kept = (flagged_mask & (audit["action"] == "keep")).sum()
    v["filter_protected"] = _int(flagged_kept)

    # Net removals
    v["filter_net_removals"] = _int((audit["action"] == "remove").sum())


def embedding_stats(v):
    """Embedding count and dimensions from embeddings.npz."""
    from utils import EMBEDDINGS_PATH, REFINED_EMBEDDINGS_PATH

    if not os.path.isfile(EMBEDDINGS_PATH):
        warnings.warn(f"Missing: {EMBEDDINGS_PATH}")
        return
    data = np.load(EMBEDDINGS_PATH)
    vectors = data["vectors"]
    v["corpus_with_embeddings"] = _int(vectors.shape[0])
    v["emb_dimensions"] = str(vectors.shape[1])
    # Analysis corpus: refined works with non-zero embeddings
    if os.path.isfile(REFINED_EMBEDDINGS_PATH):
        ref_data = np.load(REFINED_EMBEDDINGS_PATH)
        ref_vectors = ref_data["vectors"]
        nonzero = int(np.any(ref_vectors != 0, axis=1).sum())
        v["analysis_corpus_n"] = _int(nonzero)


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
        cite_df = pd.read_csv(cite_path)[["source_doi", "ref_doi"]]
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

    # Refined (corpus-internal) citations from refined_citations.csv
    from utils import REFINED_CITATIONS_PATH, REFINED_WORKS_PATH, normalize_doi

    if os.path.isfile(REFINED_CITATIONS_PATH):
        ref_cite_df = pd.read_csv(REFINED_CITATIONS_PATH)[["source_doi"]]
        v["cite_refined_rows"] = _int(len(ref_cite_df))
        v["cite_refined_sources"] = _int(ref_cite_df["source_doi"].nunique())

        # Coverage: % of refined DOIs that appear as citation sources
        if os.path.isfile(REFINED_WORKS_PATH):
            refined_df = pd.read_csv(
                REFINED_WORKS_PATH, usecols=["doi", "cited_by_count"]
            )
            refined_dois = {normalize_doi(d) for d in refined_df["doi"].dropna()} - {""}
            source_dois = {normalize_doi(d) for d in ref_cite_df["source_doi"].dropna()}
            covered = len(source_dois & refined_dois)
            if refined_dois:
                v["cite_refined_coverage_pct"] = str(
                    round(100 * covered / len(refined_dois))
                )
            # Core coverage (cited >= 50)
            core_mask = refined_df["cited_by_count"].fillna(0).astype(int) >= 50
            core_dois = {
                normalize_doi(d) for d in refined_df.loc[core_mask, "doi"].dropna()
            } - {""}
            if core_dois:
                core_covered = len(source_dois & core_dois)
                v["cite_coverage_core_pct"] = str(
                    round(100 * core_covered / len(core_dois))
                )


# ── Write YAML ───────────────────────────────────────────────


def write_yaml(v, path):
    """Write variables dict as a YAML file with all values quoted."""
    lines = ["# Auto-generated by scripts/compute_vars.py — do not edit\n"]
    for key in sorted(v.keys()):
        val = v[key]
        # Quote all values to prevent YAML type coercion
        escaped = val.replace('"', '\\"')
        lines.append(f'{key}: "{escaped}"')
    with open(path, "w") as f:
        f.write("\n".join(lines) + "\n")
    log.info("Wrote %d variables to %s", len(v), path)


# ── Main ─────────────────────────────────────────────────────


def main(output_dir):
    v = {}
    corpus_stats(v)
    embedding_stats(v)
    bimodality_stats(v)
    pca_stats(v)
    citation_stats(v)
    filter_stats(v)

    # Write per-document vars files
    all_missing = []
    for doc_name, keys in DOC_VARS.items():
        doc_v = {k: v[k] for k in keys if k in v}
        missing = [k for k in keys if k not in v]
        if missing:
            log.warning("%s: %d variables missing: %s", doc_name, len(missing), missing)
            all_missing.extend(f"{doc_name}:{k}" for k in missing)
        path = os.path.join(output_dir, f"{doc_name}-vars.yml")
        write_yaml(doc_v, path)

    if all_missing:
        log.error(
            "Aborting: %d variables could not be computed. "
            "Rendering would produce ?meta:X placeholders.",
            len(all_missing),
        )
        sys.exit(1)


if __name__ == "__main__":
    io_args, _extra = parse_io_args()
    validate_io(output=io_args.output)
    # --output receives the primary output path (first vars file);
    # all sibling vars files are co-produced in the same directory.
    main(os.path.dirname(io_args.output))
