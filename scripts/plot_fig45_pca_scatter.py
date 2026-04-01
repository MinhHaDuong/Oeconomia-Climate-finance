"""PCA scatter plots: year x score for bimodal embedding axes.

Two modes:
  --supervised : Project onto the efficiency<->accountability seed axis
                 (pole centroids from keyword matching, as in analyze_bimodality.py).
                 Produces a single-panel figure. Recommended with --core-only.
  (default)    : Unsupervised PCA, one panel per PC with DBIC > 200.
                 Best on full corpus (3 qualifying PCs). Good for appendix.

Produces:
- figures/fig_pca_scatter*.{png,pdf}: Scatter plot(s)

Usage:
    uv run python scripts/plot_fig45_pca_scatter.py --output content/figures/fig_pca_scatter.png [--pdf]
    uv run python scripts/plot_fig45_pca_scatter.py --output content/figures/fig_pca_scatter.png \
        --input refined_works.csv refined_embeddings.npz [--core-only] [--supervised] [--pdf]
"""

import argparse
import os
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from sklearn.decomposition import PCA
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
    save_figure,
)

log = get_logger("plot_fig45_pca_scatter")

warnings.filterwarnings("ignore", category=FutureWarning)

# Pole vocabularies (same as analyze_bimodality.py)
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


def _count_pole_terms(text, terms):
    """Count how many pole terms appear in text."""
    if pd.isna(text):
        return 0
    text = str(text).lower()
    return sum(1 for t in terms if t in text)


def _compute_supervised_axes(df, embeddings):
    """Compute supervised seed axis from pole paper centroids."""
    log.info("--- Supervised mode: efficiency/accountability seed axis ---")

    df["eff_count"] = df["abstract_lower"].apply(
        lambda t: _count_pole_terms(t, EFFICIENCY_TERMS))
    df["acc_count"] = df["abstract_lower"].apply(
        lambda t: _count_pole_terms(t, ACCOUNTABILITY_TERMS))

    eff_mask = df["eff_count"] >= 2
    acc_mask = df["acc_count"] >= 2
    n_eff, n_acc = eff_mask.sum(), acc_mask.sum()
    log.info("Pole papers: %d efficiency, %d accountability", n_eff, n_acc)

    centroid_eff = embeddings[eff_mask].mean(axis=0)
    centroid_acc = embeddings[acc_mask].mean(axis=0)
    axis_vec = centroid_eff - centroid_acc
    axis_vec = axis_vec / np.linalg.norm(axis_vec)

    projections = embeddings @ axis_vec
    total_var = np.var(embeddings, axis=0).sum()
    explained_frac = np.var(projections) / total_var
    log.info("Seed axis explains %.1f%% of total variance",
             explained_frac * 100)

    proj_col = projections.reshape(-1, 1)
    gmm1 = GaussianMixture(n_components=1, random_state=42).fit(proj_col)
    gmm2 = GaussianMixture(n_components=2, random_state=42).fit(proj_col)
    dbic = gmm1.bic(proj_col) - gmm2.bic(proj_col)
    log.info("Seed axis DBIC = %.0f", dbic)

    return [{
        "component": "seed",
        "scores": projections,
        "variance_explained": explained_frac,
        "delta_bic": dbic,
        "bic_1comp": gmm1.bic(proj_col),
        "bic_2comp": gmm2.bic(proj_col),
        "top_positive_terms": "leverage, blended finance, private sector",
        "top_negative_terms": "additionality, climate justice, accountability",
        "label": "Efficiency \u2194 Accountability",
        "n_efficiency": n_eff,
        "n_accountability": n_acc,
    }]


def _compute_unsupervised_axes(df, embeddings, n_components, dbic_threshold):
    """Run PCA + bimodality filtering to find qualifying axes."""
    log.info("Running PCA (n_components=%d)...", n_components)
    pca = PCA(n_components=n_components, random_state=42)
    pca_scores = pca.fit_transform(embeddings)

    log.info("Variance explained by first %d PCs:", n_components)
    for i, v in enumerate(pca.explained_variance_ratio_):
        log.info("  PC%d: %.1f%%", i + 1, v * 100)
    log.info("  Total: %.1f%%", pca.explained_variance_ratio_.sum() * 100)

    axes_info = []
    log.info("Bimodality test (DBIC threshold = %d):", dbic_threshold)
    for i in range(n_components):
        scores = pca_scores[:, i].reshape(-1, 1)
        gmm1 = GaussianMixture(n_components=1, random_state=42).fit(scores)
        gmm2 = GaussianMixture(n_components=2, random_state=42).fit(scores)
        dbic = gmm1.bic(scores) - gmm2.bic(scores)

        tag = " ***" if dbic > dbic_threshold else ""
        log.info("  PC%d: DBIC = %.0f%s", i + 1, dbic, tag)

        if dbic > dbic_threshold:
            axes_info.append({
                "component": i + 1,
                "scores": pca_scores[:, i],
                "variance_explained": pca.explained_variance_ratio_[i],
                "delta_bic": dbic,
                "bic_1comp": gmm1.bic(scores),
                "bic_2comp": gmm2.bic(scores),
            })

    if not axes_info:
        return axes_info

    log.info(
        "%d qualifying PC(s): %s",
        len(axes_info),
        ", ".join("PC%d" % a["component"] for a in axes_info),
    )

    # TF-IDF term labels for unsupervised PCs
    _label_axes_tfidf(df, axes_info)
    return axes_info


def _label_axes_tfidf(df, axes_info):
    """Assign TF-IDF term labels to unsupervised PC axes."""
    log.info("Fitting TF-IDF for term labelling...")
    abstracts = df["abstract"].fillna("").tolist()
    tfidf_vec = TfidfVectorizer(
        max_features=10000, ngram_range=(1, 2),
        sublinear_tf=True, stop_words="english",
    )
    X_tfidf = tfidf_vec.fit_transform(abstracts)
    feature_names = np.array(tfidf_vec.get_feature_names_out())

    for ax_info in axes_info:
        scores = ax_info["scores"]
        scores_centered = scores - scores.mean()
        scores_std = scores.std()
        if scores_std == 0:
            ax_info["top_positive_terms"] = ""
            ax_info["top_negative_terms"] = ""
            continue

        n = len(scores)
        col_means = np.asarray(X_tfidf.mean(axis=0)).flatten()
        xtz = np.asarray(X_tfidf.T.dot(scores_centered)).flatten()
        col_stds = np.sqrt(
            np.asarray(X_tfidf.multiply(X_tfidf).mean(axis=0)).flatten()
            - col_means ** 2)
        col_stds[col_stds == 0] = 1e-10
        correlations = xtz / (n * col_stds * scores_std)

        top_pos = feature_names[np.argsort(correlations)[-5:][::-1]].tolist()
        top_neg = feature_names[np.argsort(correlations)[:5]].tolist()
        ax_info["top_positive_terms"] = ", ".join(top_pos)
        ax_info["top_negative_terms"] = ", ".join(top_neg)
        ax_info["label"] = f"PC{ax_info['component']}"

        log.info("  PC%d (+): %s", ax_info["component"], ", ".join(top_pos))
        log.info("  PC%d (-): %s", ax_info["component"], ", ".join(top_neg))


def _render_scatter(df, axes_info, periods, period_colors, cite_threshold,
                    supervised, core_only, out_stem, pdf):
    """Render scatter plot panels and save figure."""
    sns.set_style("whitegrid")
    n_panels = len(axes_info)
    fig_width = max(8, min(6 * n_panels, 24))
    fig, plot_axes = plt.subplots(
        1, n_panels, figsize=(fig_width, 6), sharey=False, squeeze=False,
    )
    plot_axes = plot_axes.flatten()
    rng = np.random.RandomState(42)

    for ax, ax_info in zip(plot_axes, axes_info):
        _render_panel(ax, ax_info, df, periods, period_colors,
                      cite_threshold, supervised, rng)

    core_label = " (core, cited \u2265 50)" if core_only else ""
    if supervised:
        fig.suptitle(
            f"Efficiency \u2194 Accountability axis over time{core_label}",
            fontsize=13, y=1.02)
    else:
        fig.suptitle(
            f"PCA bimodal axes: paper distribution over time{core_label}",
            fontsize=13, y=1.02)
    plt.tight_layout()
    save_figure(fig, out_stem, pdf=pdf)
    plt.close()


def _render_panel(ax, ax_info, df, periods, period_colors,
                  cite_threshold, supervised, rng):
    """Render a single scatter panel."""
    scores = ax_info["scores"]
    var_pct = ax_info["variance_explained"]
    dbic = ax_info["delta_bic"]

    for period_label, (y_start, y_end) in periods.items():
        ax.axvspan(y_start - 0.5, y_end + 0.5,
                   alpha=0.08, color=period_colors[period_label], zorder=0)

    trend_mask = (df["year"] >= 2000) & (df["year"] <= 2023)
    trend_years = df.loc[trend_mask, "year"].values.astype(float)
    trend_scores = scores[trend_mask.values]
    slope, intercept = np.polyfit(trend_years, trend_scores, 1)
    x_line = np.array([2000, 2023])
    ax.plot(x_line, slope * x_line + intercept,
            color="black", linewidth=1.2, linestyle="--",
            alpha=0.5, zorder=1)

    for period_label, (y_start, y_end) in periods.items():
        pmask = (df["year"] >= y_start) & (df["year"] <= y_end)
        pscores = scores[pmask.values]
        cite_vals = df.loc[pmask, "cited_by_count"].values
        sizes = 8 + 3 * np.sqrt(cite_vals / max(cite_threshold, 1))
        jitter = rng.uniform(-0.3, 0.3, size=pmask.sum())
        ax.scatter(
            df.loc[pmask, "year"].values + jitter, pscores,
            s=sizes, alpha=0.7, color=period_colors[period_label],
            edgecolors="none", label=period_label, zorder=2,
        )

    _add_pole_labels(ax, ax_info, supervised)
    _format_panel(ax, ax_info, var_pct, dbic, supervised)


def _add_pole_labels(ax, ax_info, supervised):
    """Add pole term labels to a scatter panel."""
    pos_terms = ax_info.get("top_positive_terms", "")
    neg_terms = ax_info.get("top_negative_terms", "")
    bbox_kw = dict(boxstyle="round,pad=0.3", facecolor="white",
                   edgecolor="grey", alpha=0.8)
    if pos_terms:
        top3 = ", ".join(pos_terms.split(", ")[:3])
        label_plus = "(+) Efficiency" if supervised else f"(+) {top3}"
        ax.text(0.97, 0.97, label_plus,
                transform=ax.transAxes, fontsize=7, ha="right", va="top",
                style="italic", color="#333333", bbox=bbox_kw)
    if neg_terms:
        top3 = ", ".join(neg_terms.split(", ")[:3])
        label_minus = (
            "(-) Accountability" if supervised else f"(-) {top3}"
        )
        ax.text(0.97, 0.03, label_minus,
                transform=ax.transAxes, fontsize=7, ha="right", va="bottom",
                style="italic", color="#333333", bbox=bbox_kw)


def _format_panel(ax, ax_info, var_pct, dbic, supervised):
    """Set titles, labels, and ticks on a scatter panel."""
    if supervised:
        ax.set_title(
            f"Efficiency \u2194 Accountability "
            f"({var_pct:.1%} var, \u0394BIC={dbic:.0f})", fontsize=11)
        ax.set_ylabel(
            "Score (efficiency \u2192 / \u2190 accountability)",
            fontsize=10)
    else:
        ax.set_title(
            f"PC{ax_info['component']} ({var_pct:.1%} var, "
            f"\u0394BIC={dbic:.0f})", fontsize=11)
        ax.set_ylabel(f"PC{ax_info['component']} score", fontsize=10)
    ax.set_xlabel("Year", fontsize=10)
    ax.set_xlim(1999.5, 2023.5)
    ax.set_ylim(-0.5, 0.5)

    tick_years = sorted(set(list(range(2000, 2024, 5)) + [2007]))
    tick_labels = []
    for y in tick_years:
        if y == 2007:
            tick_labels.append("2007\n(Bali)")
        elif y == 2015:
            tick_labels.append("2015\n(Paris)")
        else:
            tick_labels.append(str(y))
    ax.set_xticks(tick_years)
    ax.set_xticklabels(tick_labels)


def main():
    io_args, extra = parse_io_args()
    validate_io(output=io_args.output, inputs=io_args.input)

    parser = argparse.ArgumentParser(
        description="PCA scatter plots (Figs 4 & 5)")
    parser.add_argument("--pdf", action="store_true",
                        help="Also save PDF output")
    parser.add_argument("--core-only", action="store_true",
                        help="Restrict to core papers (cited_by_count >= 50)")
    parser.add_argument("--supervised", action="store_true",
                        help="Use supervised seed axis instead of PCA")
    args = parser.parse_args(extra)

    out_stem = os.path.splitext(io_args.output)[0]
    out_dir = os.path.dirname(io_args.output)
    os.makedirs(out_dir or ".", exist_ok=True)

    works_path = (
        io_args.input[0] if io_args.input
        else os.path.join(CATALOGS_DIR, "refined_works.csv")
    )
    emb_path = (
        io_args.input[1] if io_args.input and len(io_args.input) >= 2
        else None
    )

    _cfg = load_analysis_config()
    cite_threshold = _cfg["clustering"]["cite_threshold"]
    _period_tuples, _period_labels = load_analysis_periods()
    periods = dict(zip(_period_labels, _period_tuples))
    period_colors = dict(zip(
        _period_labels, ["#8da0cb", "#fc8d62", "#66c2a5"]))

    # --- Load data + embeddings ---
    log.info("Loading data...")
    _year_min = _cfg["periodization"]["year_min"]
    _year_max = _cfg["periodization"]["year_max"]

    works = pd.read_csv(works_path)
    works["year"] = pd.to_numeric(works["year"], errors="coerce")
    has_title = works["title"].notna() & (works["title"].str.len() > 0)
    in_range = (works["year"] >= _year_min) & (works["year"] <= _year_max)
    df = works[has_title & in_range].copy().reset_index(drop=True)

    if emb_path is not None:
        all_embeddings = np.load(emb_path)["vectors"]
    else:
        all_embeddings = load_refined_embeddings()
    embeddings = all_embeddings[(has_title & in_range).values]
    assert len(embeddings) == len(df), (
        f"Embedding size mismatch: {len(embeddings)} vs {len(df)}")
    log.info("Loaded %d papers with embeddings (%dD)",
             len(df), embeddings.shape[1])

    df["cited_by_count"] = pd.to_numeric(
        df["cited_by_count"], errors="coerce").fillna(0)
    if args.core_only:
        core_mask = df["cited_by_count"] >= cite_threshold
        core_indices = df.index[core_mask].values
        df = df.loc[core_mask].reset_index(drop=True)
        embeddings = embeddings[core_indices]
        log.info("Core subset: %d papers (cited_by_count >= %d)",
                 len(df), cite_threshold)

    df["year"] = df["year"].astype(int)
    df["abstract_lower"] = df["abstract"].str.lower()

    # --- Compute axes ---
    if args.supervised:
        axes_info = _compute_supervised_axes(df, embeddings)
    else:
        axes_info = _compute_unsupervised_axes(
            df, embeddings, n_components=10, dbic_threshold=200)
        if not axes_info:
            log.info("No PCs passed the bimodality threshold. Exiting.")
            open(io_args.output, "w").close()
            raise SystemExit(0)

    # --- Scatter plot ---
    _render_scatter(df, axes_info, periods, period_colors,
                    cite_threshold, args.supervised, args.core_only,
                    out_stem, args.pdf)

    log.info("Done.")


if __name__ == "__main__":
    main()
