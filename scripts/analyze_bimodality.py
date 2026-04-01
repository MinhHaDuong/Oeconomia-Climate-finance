"""Testing the two-communities hypothesis: efficiency vs. accountability.

Method:
- Define efficiency and accountability pole vocabularies
- Compute pole centroids in embedding space
- Project all papers onto efficiency↔accountability axis
- Test bimodality (GMM BIC, dip test if available, KDE)
- Validate with TF-IDF and keyword co-occurrence

Produces:
- tables/tab_bimodality.csv: Dip test p-values, GMM BIC, pole paper counts
- tables/tab_pole_papers.csv: Per-paper score and pole assignment
- tables/tab_axis_detection.csv: Unsupervised TF-IDF components and alignment to pole axis

Usage:
    uv run python scripts/analyze_bimodality.py --output content/tables/tab_bimodality.csv
    uv run python scripts/analyze_bimodality.py --output content/tables/tab_bimodality_core.csv --core-only
"""

import argparse
import os
import warnings

import numpy as np
import pandas as pd
from sklearn.decomposition import PCA, TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.mixture import GaussianMixture
from script_io_args import parse_io_args, validate_io
from utils import (
    BASE_DIR,
    CATALOGS_DIR,
    get_logger,
    load_analysis_config,
    load_analysis_periods,
    load_refined_embeddings,
)

log = get_logger("analyze_bimodality")

warnings.filterwarnings("ignore", category=FutureWarning)


# --- Pole vocabularies ---
EFFICIENCY_TERMS = {
    "leverage", "de-risking", "mobilisation", "mobilization",
    "blended finance", "private finance", "green bond",
    "crowding-in", "bankable", "risk-adjusted", "financial instrument",
    "de-risk", "leveraging", "green bonds", "private sector",
}

ACCOUNTABILITY_TERMS = {
    "additionality", "over-reporting", "climate justice",
    "loss and damage", "grant-equivalent", "double counting",
    "accountability", "equity", "concessional", "oda",
    "grant equivalent", "overreporting", "climate debt",
}

def _tfidf_svd_detection(X_tfidf, tfidf, df):
    """Step 5b: Unsupervised main-axis detection via TF-IDF SVD."""
    log.info("=== Unsupervised axis detection (TF-IDF SVD) ===")
    n_components = min(5, max(2, X_tfidf.shape[1] - 1))
    svd = TruncatedSVD(n_components=n_components, random_state=42)
    svd_scores = svd.fit_transform(X_tfidf)
    explained = svd.explained_variance_ratio_
    feature_names = np.array(tfidf.get_feature_names_out())

    component_rows = []
    best_idx, best_abs_corr, best_corr, best_dbic = None, -1, None, None

    for comp_idx in range(n_components):
        comp_scores = svd_scores[:, comp_idx] - np.median(svd_scores[:, comp_idx])
        comp_corr = np.corrcoef(comp_scores, df["axis_score"].values)[0, 1]
        comp_abs_corr = abs(comp_corr)
        cg1 = GaussianMixture(n_components=1, random_state=42).fit(comp_scores.reshape(-1, 1))
        cg2 = GaussianMixture(n_components=2, random_state=42).fit(comp_scores.reshape(-1, 1))
        comp_dbic = cg1.bic(comp_scores.reshape(-1, 1)) - cg2.bic(comp_scores.reshape(-1, 1))
        weights = svd.components_[comp_idx]
        top_pos_terms = "; ".join(feature_names[np.argsort(weights)[-10:][::-1]])
        top_neg_terms = "; ".join(feature_names[np.argsort(weights)[:10]])
        component_rows.append({
            "component": f"PC{comp_idx + 1}",
            "explained_variance_ratio": explained[comp_idx],
            "corr_with_embedding_axis": comp_corr,
            "abs_corr_with_embedding_axis": comp_abs_corr,
            "delta_bic": comp_dbic,
            "top_positive_terms": top_pos_terms,
            "top_negative_terms": top_neg_terms,
        })
        if comp_abs_corr > best_abs_corr:
            best_abs_corr, best_corr, best_idx, best_dbic = (
                comp_abs_corr, comp_corr, comp_idx, comp_dbic
            )

    main_axis_label = f"PC{best_idx + 1}"
    log.info("Main unsupervised component: %s (r=%.3f, dBIC=%.0f)",
             main_axis_label, best_corr, best_dbic)
    return component_rows, main_axis_label, best_corr, best_dbic, best_idx, explained


def _embedding_pca_detection(embeddings, df, explained_frac):
    """Step 5c: Unsupervised main-axis detection via Embedding PCA."""
    log.info("=== Unsupervised axis detection (Embedding PCA) ===")
    n_emb_components = 10
    pca = PCA(n_components=n_emb_components, random_state=42)
    pca_scores = pca.fit_transform(embeddings)
    pca_explained = pca.explained_variance_ratio_

    emb_component_rows = []
    emb_best_idx, emb_best_abs_corr, emb_best_corr, emb_best_dbic = None, -1, None, None

    for comp_idx in range(n_emb_components):
        comp_scores_centered = pca_scores[:, comp_idx] - np.median(pca_scores[:, comp_idx])
        comp_corr = np.corrcoef(comp_scores_centered, df["axis_score"].values)[0, 1]
        comp_abs_corr = abs(comp_corr)
        cg1 = GaussianMixture(n_components=1, random_state=42).fit(comp_scores_centered.reshape(-1, 1))
        cg2 = GaussianMixture(n_components=2, random_state=42).fit(comp_scores_centered.reshape(-1, 1))
        comp_dbic = cg1.bic(comp_scores_centered.reshape(-1, 1)) - cg2.bic(comp_scores_centered.reshape(-1, 1))
        emb_component_rows.append({
            "component": f"emb_PC{comp_idx + 1}",
            "explained_variance_ratio": pca_explained[comp_idx],
            "corr_with_embedding_axis": comp_corr,
            "abs_corr_with_embedding_axis": comp_abs_corr,
            "delta_bic": comp_dbic,
        })
        log.info("emb_PC%d: var=%.3f, r=%+.3f, dBIC=%.0f",
                 comp_idx + 1, pca_explained[comp_idx], comp_corr, comp_dbic)
        if comp_abs_corr > emb_best_abs_corr:
            emb_best_abs_corr, emb_best_corr, emb_best_idx, emb_best_dbic = (
                comp_abs_corr, comp_corr, comp_idx, comp_dbic
            )

    log.info("Best embedding PCA: emb_PC%d (r=%+.3f, %.1f%% var, dBIC=%.0f)",
             emb_best_idx + 1, emb_best_corr, pca_explained[emb_best_idx] * 100, emb_best_dbic)
    log.info("Seed axis explains %.1f%% of embedding variance (for comparison)",
             explained_frac * 100)
    log.info("Top 10 embedding PCs explain %.1f%% total", pca_explained.sum() * 100)
    return emb_component_rows


def _load_bimodality_data(core_only):
    """Load refined works and embeddings, optionally filtering to core subset."""
    log.info("Loading data...")
    _cfg = load_analysis_config()
    _year_min = _cfg["periodization"]["year_min"]
    _year_max = _cfg["periodization"]["year_max"]

    works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
    works["year"] = pd.to_numeric(works["year"], errors="coerce")

    has_title = works["title"].notna() & (works["title"].str.len() > 0)
    in_range = (works["year"] >= _year_min) & (works["year"] <= _year_max)
    df = works[has_title & in_range].copy().reset_index(drop=True)

    embeddings = load_refined_embeddings()[(has_title & in_range).values]
    assert len(embeddings) == len(df), f"Embedding size mismatch: {len(embeddings)} vs {len(df)}"
    log.info("Loaded %d papers with embeddings (%dD)", len(df), embeddings.shape[1])

    cite_threshold = _cfg["clustering"]["cite_threshold"]
    df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0)
    if core_only:
        core_mask = df["cited_by_count"] >= cite_threshold
        core_indices = df.index[core_mask].values
        df = df.loc[core_mask].reset_index(drop=True)
        embeddings = embeddings[core_indices]
        log.info("Core-only mode: %d papers (cited_by_count >= %d)", len(df), cite_threshold)
        assert len(df) == len(embeddings), "Embedding alignment error after core filtering"

    df["abstract_lower"] = df["abstract"].str.lower()
    df["year"] = df["year"].astype(int)
    return df, embeddings


def _save_all_tables(*, df, n_eff, n_acc, n_both, bic1, bic2, delta_bic,
                     dip_pvalue, explained_frac, corr, lg1, lg2, lex_vals,
                     lex_dbic, main_axis_label, best_corr, best_dbic,
                     best_idx, explained, period_stats, component_rows,
                     emb_component_rows, output_path,
                     out_dir, tab_axis, tab_pole):
    """Step 7: Save all output tables (bimodality summary, axis detection, pole papers)."""
    summary_rows = [{
        "method": "embedding",
        "n_papers": len(df),
        "n_efficiency_pole": n_eff,
        "n_accountability_pole": n_acc,
        "n_both_poles": n_both,
        "bic_1comp": bic1, "bic_2comp": bic2, "delta_bic": delta_bic,
        "dip_pvalue": dip_pvalue, "explained_variance": explained_frac,
        "embedding_lexical_corr": corr,
    }, {
        "method": "tfidf_lexical",
        "n_papers": len(df),
        "n_efficiency_pole": n_eff,
        "n_accountability_pole": n_acc,
        "n_both_poles": n_both,
        "bic_1comp": lg1.bic(lex_vals.reshape(-1, 1)),
        "bic_2comp": lg2.bic(lex_vals.reshape(-1, 1)),
        "delta_bic": lex_dbic, "dip_pvalue": None,
        "explained_variance": None, "embedding_lexical_corr": corr,
    }, {
        "method": f"unsupervised_{main_axis_label}",
        "n_papers": len(df),
        "n_efficiency_pole": n_eff,
        "n_accountability_pole": n_acc,
        "n_both_poles": n_both,
        "bic_1comp": None, "bic_2comp": None,
        "delta_bic": best_dbic, "dip_pvalue": None,
        "explained_variance": explained[best_idx],
        "embedding_lexical_corr": best_corr,
    }]
    for ps in period_stats:
        summary_rows.append({
            "method": f"embedding_{ps['period']}",
            "n_papers": ps["n"],
            "delta_bic": ps["delta_bic"],
            "dip_pvalue": ps["dip_p"],
        })

    tab5 = pd.DataFrame(summary_rows)
    for col in ["bic_1comp", "bic_2comp", "delta_bic"]:
        if col in tab5.columns:
            tab5[col] = pd.to_numeric(tab5[col], errors="coerce").round(0).astype("Int64")
    for col in ["explained_variance", "embedding_lexical_corr", "dip_pvalue"]:
        if col in tab5.columns:
            tab5[col] = pd.to_numeric(tab5[col], errors="coerce").round(4)
    tab5.to_csv(output_path, index=False)
    log.info("Saved -> %s", output_path)

    # Combined axis detection table
    all_axis_rows = component_rows + emb_component_rows
    axis_tab = pd.DataFrame(all_axis_rows).sort_values("component")
    for col in ["explained_variance_ratio", "corr_with_embedding_axis",
                "abs_corr_with_embedding_axis"]:
        if col in axis_tab.columns:
            axis_tab[col] = axis_tab[col].round(4)
    if "delta_bic" in axis_tab.columns:
        axis_tab["delta_bic"] = axis_tab["delta_bic"].round(0).astype("Int64")
    axis_path = os.path.join(out_dir, tab_axis) if out_dir else tab_axis
    axis_tab.to_csv(axis_path, index=False)
    log.info("Saved -> %s", axis_path)

    # Per-paper scores
    pole_papers = df[["doi", "title", "year", "axis_score", "lex_score",
                       "eff_count", "acc_count"]].copy()
    pole_papers["axis_score"] = pole_papers["axis_score"].round(4)
    pole_papers["lex_score"] = pole_papers["lex_score"].round(4)
    pole_papers["pole_assignment"] = np.where(
        df["axis_score"] > 0, "efficiency",
        np.where(df["axis_score"] < 0, "accountability", "neutral")
    )
    pole_path = os.path.join(out_dir, tab_pole) if out_dir else tab_pole
    pole_papers.to_csv(pole_path, index=False)
    log.info("Saved -> %s (%d papers)", pole_path, len(pole_papers))


def _build_axis_detection_table(embeddings, axis, explained_frac, tfidf, X_tfidf):
    """Step 6: Build axis detection table from Embedding PCA."""
    log.info("=== Embedding PCA: axis detection ===")
    n_emb_components = 5
    pca = PCA(n_components=n_emb_components, random_state=42)
    pca_scores = pca.fit_transform(embeddings)

    axis_rows = []
    feature_names = np.array(tfidf.get_feature_names_out())

    X_dense = X_tfidf.toarray() if hasattr(X_tfidf, 'toarray') else X_tfidf
    X_col_means = X_dense.mean(axis=0)
    X_centered = X_dense - X_col_means
    X_col_norms = np.sqrt((X_centered ** 2).sum(axis=0) + 1e-10)

    for comp_idx in range(n_emb_components):
        pc_direction = pca.components_[comp_idx]
        cos_sim = np.dot(pc_direction, axis) / (
            np.linalg.norm(pc_direction) * np.linalg.norm(axis) + 1e-10
        )
        var_explained = pca.explained_variance_ratio_[comp_idx]

        comp_scores_vec = pca_scores[:, comp_idx]
        scores_centered = comp_scores_vec - comp_scores_vec.mean()
        scores_norm = np.sqrt((scores_centered ** 2).sum())
        denom = scores_norm * X_col_norms
        corrs = (X_centered.T @ scores_centered) / (denom + 1e-10)

        pos_terms = "; ".join(feature_names[j] for j in np.argsort(corrs)[-10:][::-1])
        neg_terms = "; ".join(feature_names[j] for j in np.argsort(corrs)[:10])

        log.info("PC%d: var=%.3f, cos(seed axis)=%.3f", comp_idx + 1, var_explained, cos_sim)
        log.info("  + %s", pos_terms)
        log.info("  - %s", neg_terms)

        axis_rows.append({
            "component": f"emb_PC{comp_idx+1}",
            "variance_explained": var_explained,
            "cosine_with_seed_axis": cos_sim,
            "top_positive_terms": pos_terms,
            "top_negative_terms": neg_terms,
        })

    axis_rows.append({
        "component": "seed_eff_acc",
        "variance_explained": explained_frac,
        "cosine_with_seed_axis": 1.0,
        "top_positive_terms": "; ".join(sorted(EFFICIENCY_TERMS)[:10]),
        "top_negative_terms": "; ".join(sorted(ACCOUNTABILITY_TERMS)[:10]),
    })

    result = pd.DataFrame(axis_rows)
    for col in ["variance_explained", "cosine_with_seed_axis"]:
        if col in result.columns:
            result[col] = result[col].round(4)
    return result


def _identify_pole_papers(df):
    """Step 1: Tag papers by pole-term frequency in abstracts."""
    df["eff_count"] = df["abstract_lower"].apply(lambda t: _count_pole_terms(t, EFFICIENCY_TERMS))
    df["acc_count"] = df["abstract_lower"].apply(lambda t: _count_pole_terms(t, ACCOUNTABILITY_TERMS))
    eff_mask = df["eff_count"] >= 2
    acc_mask = df["acc_count"] >= 2
    log.info("Pole papers: %d efficiency, %d accountability, %d both",
             eff_mask.sum(), acc_mask.sum(), (eff_mask & acc_mask).sum())
    return eff_mask, acc_mask


def _compute_seed_axis(embeddings, eff_mask, acc_mask):
    """Step 2–3: Build efficiency↔accountability axis from pole centroids."""
    if eff_mask.sum() == 0 or acc_mask.sum() == 0:
        log.warning("Too few pole papers (eff=%d, acc=%d). Exiting.", eff_mask.sum(), acc_mask.sum())
        raise SystemExit(0)
    axis = embeddings[eff_mask].mean(axis=0) - embeddings[acc_mask].mean(axis=0)
    norm = np.linalg.norm(axis)
    if norm < 1e-10:
        log.warning("Pole centroids are identical -- axis has zero norm. Exiting.")
        raise SystemExit(0)
    axis = axis / norm
    projections = embeddings @ axis
    explained_frac = np.var(projections) / np.var(embeddings, axis=0).sum()
    log.info("Axis explains %.1f%% of total embedding variance", explained_frac * 100)
    return axis, projections, explained_frac


def _gmm_delta_bic(scores):
    """Fit 1- and 2-component GMMs, return (bic1, bic2, delta_bic)."""
    col = scores.reshape(-1, 1)
    g1 = GaussianMixture(n_components=1, random_state=42).fit(col)
    g2 = GaussianMixture(n_components=2, random_state=42).fit(col)
    return g1.bic(col), g2.bic(col), g1.bic(col) - g2.bic(col)


def _test_bimodality(df, periods):
    """Step 4: GMM BIC + optional dip test, overall and per-period."""
    scores = df["axis_score"].values
    bic1, bic2, delta_bic = _gmm_delta_bic(scores)
    log.info("GMM BIC: 1-component=%.0f, 2-component=%.0f, dBIC=%.0f", bic1, bic2, delta_bic)

    dip_pvalue = None
    try:
        import diptest
        dip_stat, dip_pvalue = diptest.diptest(scores)
        log.info("Hartigan's dip test: statistic=%.4f, p=%.4f", dip_stat, dip_pvalue)
    except ImportError:
        log.info("diptest package not available, skipping Hartigan's dip test")

    period_stats = []
    for period_label, (y_start, y_end) in periods.items():
        pmask = (df["year"] >= y_start) & (df["year"] <= y_end)
        pscores = df.loc[pmask, "axis_score"].values
        if len(pscores) < 20:
            period_stats.append({"period": period_label, "n": len(pscores),
                                 "delta_bic": None, "dip_p": None})
            continue
        _, _, dbic = _gmm_delta_bic(pscores)
        dp = None
        if dip_pvalue is not None:
            try:
                _, dp = diptest.diptest(pscores)
            except (ValueError, RuntimeError):
                pass
        period_stats.append({"period": period_label, "n": len(pscores),
                             "delta_bic": dbic, "dip_p": dp})
        log.info("%s (n=%d): dBIC=%.0f%s", period_label, len(pscores), dbic,
                 (", dip p=%.4f" % dp) if dp is not None else "")

    return bic1, bic2, delta_bic, dip_pvalue, period_stats


def _compute_tfidf_axis(df, eff_mask, acc_mask):
    """Step 5: Build TF-IDF lexical axis and correlate with embedding axis."""
    log.info("=== Method B: TF-IDF lexical axis ===")
    abstracts = df["abstract"].fillna("").tolist()
    tfidf = TfidfVectorizer(
        max_features=10000, ngram_range=(1, 2),
        sublinear_tf=True, stop_words="english",
    )
    X_tfidf = tfidf.fit_transform(abstracts)
    log.info("TF-IDF matrix: %s", X_tfidf.shape)

    lex_axis = X_tfidf[eff_mask.values].mean(axis=0).A1 - X_tfidf[acc_mask.values].mean(axis=0).A1
    lex_norm = np.linalg.norm(lex_axis)
    if lex_norm < 1e-10 or np.any(np.isnan(lex_axis)):
        log.warning("Lexical axis degenerate (norm=%.2e or NaN). Skipping.", lex_norm)
        df["lex_score"] = 0.0
    else:
        lex_axis = lex_axis / lex_norm
        lex_scores = X_tfidf.dot(lex_axis)
        df["lex_score"] = lex_scores - np.median(lex_scores)

    lex_vals = df["lex_score"].values
    lg1 = GaussianMixture(n_components=1, random_state=42).fit(lex_vals.reshape(-1, 1))
    lg2 = GaussianMixture(n_components=2, random_state=42).fit(lex_vals.reshape(-1, 1))
    lex_dbic = lg1.bic(lex_vals.reshape(-1, 1)) - lg2.bic(lex_vals.reshape(-1, 1))
    corr = np.corrcoef(df["axis_score"].values, lex_vals)[0, 1]
    log.info("Lexical dBIC: %.0f, correlation with embedding axis: r=%.3f", lex_dbic, corr)
    return tfidf, X_tfidf, lg1, lg2, lex_vals, lex_dbic, corr


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output)

    parser = argparse.ArgumentParser(description="Bimodality analysis (tables only)")
    parser.add_argument("--core-only", action="store_true",
                        help="Restrict to core papers (cited_by_count >= 50)")
    args = parser.parse_args(extra)

    out_dir = os.path.dirname(io_args.output)
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    out_stem = os.path.splitext(os.path.basename(io_args.output))[0]
    suffix = out_stem.replace("tab_bimodality", "")
    tab_axis = f"tab_axis_detection{suffix}.csv"
    tab_pole = f"tab_pole_papers{suffix}.csv"

    _period_tuples, _period_labels = load_analysis_periods()
    periods = dict(zip(_period_labels, _period_tuples))

    df, embeddings = _load_bimodality_data(args.core_only)
    eff_mask, acc_mask = _identify_pole_papers(df)
    axis, projections, explained_frac = _compute_seed_axis(embeddings, eff_mask, acc_mask)

    df["axis_score"] = projections - np.median(projections)

    bic1, bic2, delta_bic, dip_pvalue, period_stats = _test_bimodality(df, periods)
    tfidf, X_tfidf, lg1, lg2, lex_vals, lex_dbic, corr = _compute_tfidf_axis(df, eff_mask, acc_mask)

    component_rows, main_axis_label, best_corr, best_dbic, best_idx, explained = \
        _tfidf_svd_detection(X_tfidf, tfidf, df)
    emb_component_rows = _embedding_pca_detection(embeddings, df, explained_frac)
    _build_axis_detection_table(embeddings, axis, explained_frac, tfidf, X_tfidf)

    _save_all_tables(
        df=df, n_eff=eff_mask.sum(), n_acc=acc_mask.sum(),
        n_both=(eff_mask & acc_mask).sum(),
        bic1=bic1, bic2=bic2, delta_bic=delta_bic, dip_pvalue=dip_pvalue,
        explained_frac=explained_frac, corr=corr, lg1=lg1, lg2=lg2,
        lex_vals=lex_vals, lex_dbic=lex_dbic,
        main_axis_label=main_axis_label, best_corr=best_corr,
        best_dbic=best_dbic, best_idx=best_idx, explained=explained,
        period_stats=period_stats, component_rows=component_rows,
        emb_component_rows=emb_component_rows,
        output_path=io_args.output, out_dir=out_dir,
        tab_axis=tab_axis, tab_pole=tab_pole,
    )
    log.info("Done.")


def _count_pole_terms(text, terms):
    """Count how many terms from a set appear in text."""
    if pd.isna(text):
        return 0
    text = str(text).lower()
    return sum(1 for t in terms if t in text)


if __name__ == "__main__":
    main()
