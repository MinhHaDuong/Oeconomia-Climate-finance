"""Testing the two-communities hypothesis: efficiency vs. accountability.

Method:
- Define efficiency and accountability pole vocabularies
- Compute pole centroids in embedding space
- Project all papers onto efficiency↔accountability axis
- Test bimodality (GMM BIC, dip test if available, KDE)
- Validate with TF-IDF and keyword co-occurrence

Produces:
- figures/fig_bimodality.pdf: KDE of embedding scores by period
- figures/fig_bimodality_lexical.pdf: TF-IDF version (appendix)
- figures/fig_bimodality_keywords.pdf: Keyword scatter (appendix)
- tables/tab_bimodality.csv: Dip test p-values, GMM BIC, pole paper counts
- tables/tab_pole_papers.csv: Per-paper score and pole assignment
- tables/tab_axis_detection.csv: Unsupervised TF-IDF components and alignment to pole axis
"""

import argparse
import os
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import gaussian_kde
from sklearn.decomposition import PCA, TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.mixture import GaussianMixture

from utils import (BASE_DIR, CATALOGS_DIR, get_logger, load_refined_embeddings,
                   save_figure)

log = get_logger("analyze_bimodality")

parser = argparse.ArgumentParser(description="Bimodality analysis (Fig 5)")
parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation (PNG only)")
parser.add_argument("--core-only", action="store_true",
                    help="Restrict to core papers (cited_by_count >= 50)")
args = parser.parse_args()

warnings.filterwarnings("ignore", category=FutureWarning)

# --- Paths ---
FIGURES_DIR = os.path.join(BASE_DIR, "content", "figures")
TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)


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

# Three-act periods
PERIODS = {
    "1990–2006": (1990, 2006),
    "2007–2014": (2007, 2014),
    "2015–2025": (2015, 2025),
}
PERIOD_COLORS = {"1990–2006": "#8da0cb", "2007–2014": "#fc8d62", "2015–2025": "#66c2a5"}


# --- Load data + embeddings ---
log.info("Loading data...")
works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
works["year"] = pd.to_numeric(works["year"], errors="coerce")

has_title = works["title"].notna() & (works["title"].str.len() > 0)
in_range = (works["year"] >= 1990) & (works["year"] <= 2025)
df = works[has_title & in_range].copy().reset_index(drop=True)

embeddings = load_refined_embeddings()[(has_title & in_range).values]
assert len(embeddings) == len(df), f"Embedding size mismatch: {len(embeddings)} vs {len(df)}"
log.info("Loaded %d papers with embeddings (%dD)", len(df), embeddings.shape[1])

# Core filtering: keep only highly-cited papers
CITE_THRESHOLD = 50
df["cited_by_count"] = pd.to_numeric(df["cited_by_count"], errors="coerce").fillna(0)
if args.core_only:
    core_mask = df["cited_by_count"] >= CITE_THRESHOLD
    core_indices = df.index[core_mask].values
    df = df.loc[core_mask].reset_index(drop=True)
    embeddings = embeddings[core_indices]
    log.info("Core-only mode: %d papers (cited_by_count >= %d)", len(df), CITE_THRESHOLD)
    assert len(df) == len(embeddings), "Embedding alignment error after core filtering"

# Output naming: use "_core" suffix for figures and "b" prefix for tables in core mode
if args.core_only:
    FIG5A = "fig_bimodality_core"
    FIG5B = "fig_bimodality_lexical_core"
    FIG5C = "fig_bimodality_keywords_core"
    TAB5_BIM = "tab_bimodality_core.csv"
    TAB5_AXIS = "tab_axis_detection_core.csv"
    TAB5_POLE = "tab_pole_papers_core.csv"
else:
    FIG5A = "fig_bimodality"
    FIG5B = "fig_bimodality_lexical"
    FIG5C = "fig_bimodality_keywords"
    TAB5_BIM = "tab_bimodality.csv"
    TAB5_AXIS = "tab_axis_detection.csv"
    TAB5_POLE = "tab_pole_papers.csv"

df["abstract_lower"] = df["abstract"].str.lower()
df["year"] = df["year"].astype(int)


# ============================================================
# Step 1: Identify pole papers from abstracts
# ============================================================

def count_pole_terms(text, terms):
    """Count how many terms from a set appear in text."""
    if pd.isna(text):
        return 0
    text = str(text).lower()
    return sum(1 for t in terms if t in text)


df["eff_count"] = df["abstract_lower"].apply(lambda t: count_pole_terms(t, EFFICIENCY_TERMS))
df["acc_count"] = df["abstract_lower"].apply(lambda t: count_pole_terms(t, ACCOUNTABILITY_TERMS))

eff_mask = df["eff_count"] >= 2
acc_mask = df["acc_count"] >= 2

n_eff = eff_mask.sum()
n_acc = acc_mask.sum()
n_both = (eff_mask & acc_mask).sum()
log.info("Pole papers: %d efficiency, %d accountability, %d both", n_eff, n_acc, n_both)


# ============================================================
# Step 2: Compute pole centroids in embedding space
# ============================================================

centroid_eff = embeddings[eff_mask].mean(axis=0)
centroid_acc = embeddings[acc_mask].mean(axis=0)

# Axis vector (efficiency - accountability), normalized
axis = centroid_eff - centroid_acc
axis = axis / np.linalg.norm(axis)

# Explained variance: what fraction of total variance lies along this axis?
projections = embeddings @ axis
total_var = np.var(embeddings, axis=0).sum()
axis_var = np.var(projections)
explained_frac = axis_var / total_var
log.info("Axis explains %.1f%% of total embedding variance", explained_frac * 100)


# ============================================================
# Step 3: Project all papers onto the axis
# ============================================================

df["axis_score"] = projections
# Center scores so 0 = midpoint
df["axis_score"] = df["axis_score"] - df["axis_score"].median()


# ============================================================
# Step 4: Bimodality tests
# ============================================================

scores = df["axis_score"].values

# GMM: 1 vs 2 components
gmm1 = GaussianMixture(n_components=1, random_state=42).fit(scores.reshape(-1, 1))
gmm2 = GaussianMixture(n_components=2, random_state=42).fit(scores.reshape(-1, 1))
bic1 = gmm1.bic(scores.reshape(-1, 1))
bic2 = gmm2.bic(scores.reshape(-1, 1))
delta_bic = bic1 - bic2  # positive = 2-component is better

log.info("GMM BIC: 1-component=%.0f, 2-component=%.0f, dBIC=%.0f", bic1, bic2, delta_bic)
if delta_bic > 10:
    log.info("-> Strong evidence for bimodality (dBIC > 10)")
elif delta_bic > 0:
    log.info("-> Weak evidence for bimodality")
else:
    log.info("-> Unimodal (1-component preferred)")

# Dip test (optional)
dip_pvalue = None
try:
    import diptest
    dip_stat, dip_pvalue = diptest.diptest(scores)
    log.info("Hartigan's dip test: statistic=%.4f, p=%.4f", dip_stat, dip_pvalue)
    if dip_pvalue < 0.05:
        log.info("-> Reject unimodality (p < 0.05)")
    else:
        log.info("-> Cannot reject unimodality")
except ImportError:
    log.info("diptest package not available, skipping Hartigan's dip test")

# Per-period bimodality
period_stats = []
for period_label, (y_start, y_end) in PERIODS.items():
    pmask = (df["year"] >= y_start) & (df["year"] <= y_end)
    pscores = df.loc[pmask, "axis_score"].values
    if len(pscores) < 20:
        period_stats.append({"period": period_label, "n": len(pscores),
                             "delta_bic": None, "dip_p": None})
        continue

    g1 = GaussianMixture(n_components=1, random_state=42).fit(pscores.reshape(-1, 1))
    g2 = GaussianMixture(n_components=2, random_state=42).fit(pscores.reshape(-1, 1))
    dbic = g1.bic(pscores.reshape(-1, 1)) - g2.bic(pscores.reshape(-1, 1))

    dp = None
    if dip_pvalue is not None:
        try:
            _, dp = diptest.diptest(pscores)
        except Exception:
            pass

    period_stats.append({"period": period_label, "n": len(pscores),
                         "delta_bic": dbic, "dip_p": dp})
    log.info("%s (n=%d): dBIC=%.0f%s", period_label, len(pscores), dbic,
             (", dip p=%.4f" % dp) if dp is not None else "")


# ============================================================
# Step 5: Figure 5 — KDE of embedding scores by period
# ============================================================

sns.set_style("whitegrid")
fig, axes = plt.subplots(1, 3, figsize=(14, 4), sharey=True)

for ax, (period_label, (y_start, y_end)) in zip(axes, PERIODS.items()):
    pmask = (df["year"] >= y_start) & (df["year"] <= y_end)
    pscores = df.loc[pmask, "axis_score"].values

    if len(pscores) < 10:
        ax.set_title(f"{period_label}\n(n={len(pscores)}, too few)")
        continue

    # KDE
    kde = gaussian_kde(pscores, bw_method=0.15)
    x = np.linspace(pscores.min() - 0.5, pscores.max() + 0.5, 500)
    y = kde(x)

    ax.fill_between(x, y, alpha=0.3, color=PERIOD_COLORS[period_label])
    ax.plot(x, y, color=PERIOD_COLORS[period_label], linewidth=2)

    # GMM components overlay
    if len(pscores) >= 20:
        g2 = GaussianMixture(n_components=2, random_state=42).fit(pscores.reshape(-1, 1))
        means = g2.means_.flatten()
        stds = np.sqrt(g2.covariances_.flatten())
        weights = g2.weights_

        for i in range(2):
            comp = weights[i] * gaussian_kde(
                np.random.RandomState(42).normal(means[i], stds[i], 10000),
                bw_method=0.15
            )(x)
            ax.plot(x, comp, "--", color="grey", alpha=0.5, linewidth=1)

    ax.axvline(0, color="black", linestyle=":", alpha=0.3)
    ax.set_title(f"{period_label}\n(n={len(pscores):,})", fontsize=11)
    ax.set_xlabel("← Accountability          Efficiency →", fontsize=9)

axes[0].set_ylabel("Density", fontsize=11)

fig.suptitle(
    "Distribution of papers along the efficiency–accountability axis",
    fontsize=13, y=1.02,
)
plt.tight_layout()
save_figure(fig, os.path.join(FIGURES_DIR, FIG5A), no_pdf=args.no_pdf)
log.info("(%s)", FIG5A)
plt.close()


# ============================================================
# Step 6: TF-IDF axis (Method B — lexical validation)
# ============================================================

log.info("=== Method B: TF-IDF lexical axis ===")

# Fit TF-IDF on all abstracts
abstracts = df["abstract"].fillna("").tolist()
tfidf = TfidfVectorizer(
    max_features=10000,
    ngram_range=(1, 2),
    sublinear_tf=True,
    stop_words="english",
)
X_tfidf = tfidf.fit_transform(abstracts)
log.info("TF-IDF matrix: %s", X_tfidf.shape)

# Compute mean TF-IDF for each pole
eff_tfidf = X_tfidf[eff_mask.values].mean(axis=0).A1
acc_tfidf = X_tfidf[acc_mask.values].mean(axis=0).A1

# Lexical axis
lex_axis = eff_tfidf - acc_tfidf
lex_axis = lex_axis / np.linalg.norm(lex_axis)

# Project all papers
lex_scores = X_tfidf.dot(lex_axis)
df["lex_score"] = lex_scores - np.median(lex_scores)

# Bimodality on lexical axis
lex_vals = df["lex_score"].values
lg1 = GaussianMixture(n_components=1, random_state=42).fit(lex_vals.reshape(-1, 1))
lg2 = GaussianMixture(n_components=2, random_state=42).fit(lex_vals.reshape(-1, 1))
lex_dbic = lg1.bic(lex_vals.reshape(-1, 1)) - lg2.bic(lex_vals.reshape(-1, 1))
log.info("Lexical dBIC: %.0f", lex_dbic)

# Lexical figure
fig, axes = plt.subplots(1, 3, figsize=(14, 4), sharey=True)

for ax, (period_label, (y_start, y_end)) in zip(axes, PERIODS.items()):
    pmask = (df["year"] >= y_start) & (df["year"] <= y_end)
    pscores = df.loc[pmask, "lex_score"].values

    if len(pscores) < 10:
        ax.set_title(f"{period_label}\n(n={len(pscores)}, too few)")
        continue

    kde = gaussian_kde(pscores, bw_method=0.15)
    x = np.linspace(np.percentile(pscores, 1), np.percentile(pscores, 99), 500)
    y = kde(x)

    ax.fill_between(x, y, alpha=0.3, color=PERIOD_COLORS[period_label])
    ax.plot(x, y, color=PERIOD_COLORS[period_label], linewidth=2)
    ax.axvline(0, color="black", linestyle=":", alpha=0.3)
    ax.set_title(f"{period_label}\n(n={len(pscores):,})", fontsize=11)
    ax.set_xlabel("← Accountability          Efficiency →", fontsize=9)

axes[0].set_ylabel("Density", fontsize=11)
fig.suptitle(
    "Distribution along the efficiency–accountability axis (TF-IDF lexical)",
    fontsize=13, y=1.02,
)
plt.tight_layout()
save_figure(fig, os.path.join(FIGURES_DIR, FIG5B), no_pdf=args.no_pdf)
log.info("(%s)", FIG5B)
plt.close()

# Agreement check
corr = np.corrcoef(df["axis_score"].values, df["lex_score"].values)[0, 1]
log.info("Correlation between embedding and TF-IDF axis scores: r=%.3f", corr)


# ============================================================
# Step 6b: Unsupervised main-axis detection (TF-IDF SVD)
# ============================================================

log.info("=== Unsupervised axis detection (TF-IDF SVD) ===")

n_components = min(5, max(2, X_tfidf.shape[1] - 1))
svd = TruncatedSVD(n_components=n_components, random_state=42)
svd_scores = svd.fit_transform(X_tfidf)
explained = svd.explained_variance_ratio_

component_rows = []
feature_names = np.array(tfidf.get_feature_names_out())

best_idx = None
best_abs_corr = -1
best_corr = None
best_dbic = None

for comp_idx in range(n_components):
    comp_scores = svd_scores[:, comp_idx]
    comp_scores = comp_scores - np.median(comp_scores)

    comp_corr = np.corrcoef(comp_scores, df["axis_score"].values)[0, 1]
    comp_abs_corr = abs(comp_corr)

    cg1 = GaussianMixture(n_components=1, random_state=42).fit(comp_scores.reshape(-1, 1))
    cg2 = GaussianMixture(n_components=2, random_state=42).fit(comp_scores.reshape(-1, 1))
    comp_dbic = cg1.bic(comp_scores.reshape(-1, 1)) - cg2.bic(comp_scores.reshape(-1, 1))

    weights = svd.components_[comp_idx]
    top_pos_idx = np.argsort(weights)[-10:][::-1]
    top_neg_idx = np.argsort(weights)[:10]
    top_pos_terms = "; ".join(feature_names[top_pos_idx])
    top_neg_terms = "; ".join(feature_names[top_neg_idx])

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
        best_abs_corr = comp_abs_corr
        best_corr = comp_corr
        best_idx = comp_idx
        best_dbic = comp_dbic

main_axis_label = f"PC{best_idx + 1}"
log.info(
    "Main unsupervised component aligned with efficiency<->accountability axis: "
    "%s (r=%.3f, dBIC=%.0f)", main_axis_label, best_corr, best_dbic
)


# ============================================================
# Step 6c: Unsupervised main-axis detection (Embedding PCA)
# ============================================================

from sklearn.decomposition import PCA

log.info("=== Unsupervised axis detection (Embedding PCA) ===")

n_emb_components = 10
pca = PCA(n_components=n_emb_components, random_state=42)
pca_scores = pca.fit_transform(embeddings)
pca_explained = pca.explained_variance_ratio_

emb_component_rows = []
emb_best_idx = None
emb_best_abs_corr = -1
emb_best_corr = None
emb_best_dbic = None

for comp_idx in range(n_emb_components):
    comp_scores = pca_scores[:, comp_idx]
    comp_scores_centered = comp_scores - np.median(comp_scores)

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
        emb_best_abs_corr = comp_abs_corr
        emb_best_corr = comp_corr
        emb_best_idx = comp_idx
        emb_best_dbic = comp_dbic

emb_main_label = f"emb_PC{emb_best_idx + 1}"
log.info(
    "Best embedding PCA component aligned with seed axis: "
    "%s (r=%+.3f, explains %.1f%% of embedding variance, dBIC=%.0f)",
    emb_main_label, emb_best_corr, pca_explained[emb_best_idx] * 100, emb_best_dbic
)
log.info("Seed axis explains %.1f%% of embedding variance (for comparison)",
         explained_frac * 100)
log.info("Top 10 embedding PCs explain %.1f%% total", pca_explained.sum() * 100)


# ============================================================
# Step 7: Keyword co-occurrence scatter (Method C)
# ============================================================

log.info("=== Method C: Keyword co-occurrence ===")

fig, ax = plt.subplots(figsize=(7, 6))

for period_label, (y_start, y_end) in PERIODS.items():
    pmask = (df["year"] >= y_start) & (df["year"] <= y_end)
    pdata = df[pmask]
    ax.scatter(
        pdata["eff_count"], pdata["acc_count"],
        alpha=0.15, s=15, color=PERIOD_COLORS[period_label],
        label=f"{period_label} (n={len(pdata):,})",
    )

ax.set_xlabel("Efficiency keyword count", fontsize=11)
ax.set_ylabel("Accountability keyword count", fontsize=11)
ax.set_title("Keyword co-occurrence: efficiency vs. accountability terms", fontsize=12)
ax.legend(fontsize=9, framealpha=0.9)

# Add marginal histograms as insets
from mpl_toolkits.axes_grid1 import make_axes_locatable
divider = make_axes_locatable(ax)
ax_histx = divider.append_axes("top", 0.8, pad=0.1, sharex=ax)
ax_histy = divider.append_axes("right", 0.8, pad=0.1, sharey=ax)

ax_histx.hist(df["eff_count"], bins=range(0, df["eff_count"].max() + 2),
              color="#4C72B0", alpha=0.7, edgecolor="white")
ax_histy.hist(df["acc_count"], bins=range(0, df["acc_count"].max() + 2),
              orientation="horizontal", color="#C44E52", alpha=0.7, edgecolor="white")

ax_histx.tick_params(labelbottom=False)
ax_histy.tick_params(labelleft=False)

save_figure(fig, os.path.join(FIGURES_DIR, FIG5C), no_pdf=args.no_pdf)
log.info("(%s)", FIG5C)
plt.close()


# ============================================================
# Step 7b: Embedding PCA — axis detection
# ============================================================

log.info("=== Embedding PCA: axis detection ===")

n_emb_components = 5
pca = PCA(n_components=n_emb_components, random_state=42)
pca_scores = pca.fit_transform(embeddings)

# Cosine similarity of each PC direction with the seed eff/acc axis
axis_rows = []
feature_names = np.array(tfidf.get_feature_names_out())

# Densify TF-IDF once for correlation computation
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

    # Compute top terms for this embedding PC via TF-IDF correlation
    comp_scores_vec = pca_scores[:, comp_idx]
    scores_centered = comp_scores_vec - comp_scores_vec.mean()
    scores_norm = np.sqrt((scores_centered ** 2).sum())
    denom = scores_norm * X_col_norms
    corrs = (X_centered.T @ scores_centered) / (denom + 1e-10)

    top_pos_idx = np.argsort(corrs)[-10:][::-1]
    top_neg_idx = np.argsort(corrs)[:10]
    pos_terms = "; ".join(feature_names[j] for j in top_pos_idx)
    neg_terms = "; ".join(feature_names[j] for j in top_neg_idx)

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

# Also add the seed axis itself as a reference row
axis_rows.append({
    "component": "seed_eff_acc",
    "variance_explained": explained_frac,
    "cosine_with_seed_axis": 1.0,
    "top_positive_terms": "; ".join(sorted(EFFICIENCY_TERMS)[:10]),
    "top_negative_terms": "; ".join(sorted(ACCOUNTABILITY_TERMS)[:10]),
})

axis_detection = pd.DataFrame(axis_rows)
axis_detection.to_csv(os.path.join(TABLES_DIR, TAB5_AXIS), index=False)
log.info("Saved -> tables/%s", TAB5_AXIS)


# ============================================================
# Step 8: Save tables
# ============================================================

# Summary table
summary_rows = [{
    "method": "embedding",
    "n_papers": len(df),
    "n_efficiency_pole": n_eff,
    "n_accountability_pole": n_acc,
    "n_both_poles": n_both,
    "bic_1comp": bic1,
    "bic_2comp": bic2,
    "delta_bic": delta_bic,
    "dip_pvalue": dip_pvalue,
    "explained_variance": explained_frac,
    "embedding_lexical_corr": corr,
}, {
    "method": "tfidf_lexical",
    "n_papers": len(df),
    "n_efficiency_pole": n_eff,
    "n_accountability_pole": n_acc,
    "n_both_poles": n_both,
    "bic_1comp": lg1.bic(lex_vals.reshape(-1, 1)),
    "bic_2comp": lg2.bic(lex_vals.reshape(-1, 1)),
    "delta_bic": lex_dbic,
    "dip_pvalue": None,
    "explained_variance": None,
    "embedding_lexical_corr": corr,
}, {
    "method": f"unsupervised_{main_axis_label}",
    "n_papers": len(df),
    "n_efficiency_pole": n_eff,
    "n_accountability_pole": n_acc,
    "n_both_poles": n_both,
    "bic_1comp": None,
    "bic_2comp": None,
    "delta_bic": best_dbic,
    "dip_pvalue": None,
    "explained_variance": explained[best_idx],
    "embedding_lexical_corr": best_corr,
}]

# Add per-period stats
for ps in period_stats:
    summary_rows.append({
        "method": f"embedding_{ps['period']}",
        "n_papers": ps["n"],
        "delta_bic": ps["delta_bic"],
        "dip_pvalue": ps["dip_p"],
    })

tab5 = pd.DataFrame(summary_rows)
tab5.to_csv(os.path.join(TABLES_DIR, TAB5_BIM), index=False)
log.info("Saved -> tables/%s", TAB5_BIM)

# Combine TF-IDF SVD and embedding PCA rows
all_axis_rows = component_rows + emb_component_rows
axis_tab = pd.DataFrame(all_axis_rows).sort_values("component")
axis_tab.to_csv(os.path.join(TABLES_DIR, "tab_axis_detection.csv"), index=False)
log.info("Saved -> tables/tab_axis_detection.csv")

# Per-paper scores
pole_papers = df[["doi", "title", "year", "axis_score", "lex_score",
                   "eff_count", "acc_count"]].copy()
pole_papers["pole_assignment"] = np.where(
    df["axis_score"] > 0, "efficiency",
    np.where(df["axis_score"] < 0, "accountability", "neutral")
)
pole_papers.to_csv(os.path.join(TABLES_DIR, TAB5_POLE), index=False)
log.info("Saved -> tables/%s (%d papers)", TAB5_POLE, len(pole_papers))

log.info("Done.")
