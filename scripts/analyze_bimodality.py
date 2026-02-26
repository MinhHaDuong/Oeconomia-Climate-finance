"""Testing the two-communities hypothesis: efficiency vs. accountability.

Method:
- Define efficiency and accountability pole vocabularies
- Compute pole centroids in embedding space
- Project all papers onto efficiency↔accountability axis
- Test bimodality (GMM BIC, dip test if available, KDE)
- Validate with TF-IDF and keyword co-occurrence

Produces:
- figures/fig5_bimodality.pdf: KDE of embedding scores by period
- figures/fig5_bimodality_lexical.pdf: TF-IDF version (appendix)
- figures/fig5_bimodality_keywords.pdf: Keyword scatter (appendix)
- tables/tab5_bimodality.csv: Dip test p-values, GMM BIC, pole paper counts
- tables/tab5_pole_papers.csv: Per-paper score and pole assignment
"""

import argparse
import os
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
from scipy.stats import gaussian_kde
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.mixture import GaussianMixture

from utils import BASE_DIR, CATALOGS_DIR, save_figure

parser = argparse.ArgumentParser(description="Bimodality analysis (Fig 5)")
parser.add_argument("--no-pdf", action="store_true", help="Skip PDF generation (PNG only)")
args = parser.parse_args()

warnings.filterwarnings("ignore", category=FutureWarning)

# --- Paths ---
FIGURES_DIR = os.path.join(BASE_DIR, "figures")
TABLES_DIR = os.path.join(BASE_DIR, "tables")
os.makedirs(FIGURES_DIR, exist_ok=True)
os.makedirs(TABLES_DIR, exist_ok=True)

EMBEDDINGS_PATH = os.path.join(CATALOGS_DIR, "embeddings.npy")

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
print("Loading data...")
works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
works["year"] = pd.to_numeric(works["year"], errors="coerce")

has_abstract = works["abstract"].notna() & (works["abstract"].str.len() > 50)
in_range = (works["year"] >= 1990) & (works["year"] <= 2025)
df = works[has_abstract & in_range].copy().reset_index(drop=True)

embeddings = np.load(EMBEDDINGS_PATH)
assert len(embeddings) == len(df), f"Embedding size mismatch: {len(embeddings)} vs {len(df)}"
print(f"Loaded {len(df)} papers with embeddings ({embeddings.shape[1]}D)")

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
print(f"\nPole papers: {n_eff} efficiency, {n_acc} accountability, {n_both} both")


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
print(f"Axis explains {explained_frac:.1%} of total embedding variance")


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

print(f"\nGMM BIC: 1-component={bic1:.0f}, 2-component={bic2:.0f}, ΔBIC={delta_bic:.0f}")
if delta_bic > 10:
    print("  → Strong evidence for bimodality (ΔBIC > 10)")
elif delta_bic > 0:
    print("  → Weak evidence for bimodality")
else:
    print("  → Unimodal (1-component preferred)")

# Dip test (optional)
dip_pvalue = None
try:
    import diptest
    dip_stat, dip_pvalue = diptest.diptest(scores)
    print(f"Hartigan's dip test: statistic={dip_stat:.4f}, p={dip_pvalue:.4f}")
    if dip_pvalue < 0.05:
        print("  → Reject unimodality (p < 0.05)")
    else:
        print("  → Cannot reject unimodality")
except ImportError:
    print("diptest package not available, skipping Hartigan's dip test")

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
    print(f"  {period_label} (n={len(pscores)}): ΔBIC={dbic:.0f}" +
          (f", dip p={dp:.4f}" if dp is not None else ""))


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
save_figure(fig, os.path.join(FIGURES_DIR, "fig5a_bimodality"), no_pdf=args.no_pdf)
print(f"  (Figure 5a)")
plt.close()


# ============================================================
# Step 6: TF-IDF axis (Method B — lexical validation)
# ============================================================

print("\n=== Method B: TF-IDF lexical axis ===")

# Fit TF-IDF on all abstracts
abstracts = df["abstract"].fillna("").tolist()
tfidf = TfidfVectorizer(
    max_features=10000,
    ngram_range=(1, 2),
    sublinear_tf=True,
    stop_words="english",
)
X_tfidf = tfidf.fit_transform(abstracts)
print(f"TF-IDF matrix: {X_tfidf.shape}")

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
print(f"Lexical ΔBIC: {lex_dbic:.0f}")

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
save_figure(fig, os.path.join(FIGURES_DIR, "fig5b_bimodality_lexical"), no_pdf=args.no_pdf)
print(f"  (Figure 5b)")
plt.close()

# Agreement check
corr = np.corrcoef(df["axis_score"].values, df["lex_score"].values)[0, 1]
print(f"Correlation between embedding and TF-IDF axis scores: r={corr:.3f}")


# ============================================================
# Step 7: Keyword co-occurrence scatter (Method C)
# ============================================================

print("\n=== Method C: Keyword co-occurrence ===")

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

save_figure(fig, os.path.join(FIGURES_DIR, "fig5c_bimodality_keywords"), no_pdf=args.no_pdf)
print(f"  (Figure 5c)")
plt.close()


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
tab5.to_csv(os.path.join(TABLES_DIR, "tab5_bimodality.csv"), index=False)
print(f"\nSaved → tables/tab5_bimodality.csv")

# Per-paper scores
pole_papers = df[["doi", "title", "year", "axis_score", "lex_score",
                   "eff_count", "acc_count"]].copy()
pole_papers["pole_assignment"] = np.where(
    df["axis_score"] > 0, "efficiency",
    np.where(df["axis_score"] < 0, "accountability", "neutral")
)
pole_papers.to_csv(os.path.join(TABLES_DIR, "tab5_pole_papers.csv"), index=False)
print(f"Saved → tables/tab5_pole_papers.csv ({len(pole_papers)} papers)")

print("\nDone.")
