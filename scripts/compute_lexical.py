"""Lexical validation of structural breaks via TF-IDF term shift analysis.

Reads:  refined_works.csv,
        tab_breakpoint_robustness.csv (to derive detected break years)
Writes: tab_lexical_tfidf.csv

Flags:
  --no-pdf  Accepted for interface compatibility; no-op (no figures generated)

Note: The lexical TF-IDF *figures* are produced by plot_fig_lexical_tfidf.py.
"""

import argparse
import os

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

from utils import BASE_DIR, CATALOGS_DIR

TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")
os.makedirs(TABLES_DIR, exist_ok=True)

# --- Args ---
parser = argparse.ArgumentParser(description="Compute lexical TF-IDF table at break years")
parser.add_argument("--no-pdf", action="store_true", help="No-op (no figures generated here)")
# parse_known_args: silently ignore flags forwarded by compute_alluvial.py shim
# (e.g. --core-only — the original code skipped lexical validation in core mode,
# so this script simply has no --core-only flag; the shim forwards it harmlessly)
args, _unknown = parser.parse_known_args()


# ============================================================
# Step 1: Load data and detected break years
# Note: each split script (breakpoints, clusters, lexical) loads refined_works.csv
# independently. When run via the compute_alluvial.py shim this means 3× I/O,
# but at ~30K rows the cost is negligible vs. the KMeans/TF-IDF compute time.
# ============================================================

print("Loading unified works...")
works = pd.read_csv(os.path.join(CATALOGS_DIR, "refined_works.csv"))
works["year"] = pd.to_numeric(works["year"], errors="coerce")

has_title = works["title"].notna() & (works["title"].str.len() > 0)
in_range = (works["year"] >= 1990) & (works["year"] <= 2025)
df = works[has_title & in_range].copy().reset_index(drop=True)
print(f"Works with titles (1990-2025): {len(df)}")

# Load detected break years from breakpoints table
robust_path = os.path.join(TABLES_DIR, "tab_breakpoint_robustness.csv")
try:
    robust_df = pd.read_csv(robust_path)
except FileNotFoundError:
    raise FileNotFoundError(
        f"Missing {robust_path}. Run compute_breakpoints.py first."
    ) from None
detected_breaks = sorted(robust_df["year"].tolist()[:3])
print(f"Detected break years (from tab_breakpoint_robustness.csv): {detected_breaks}")

main_break = detected_breaks[0] if detected_breaks else 2009


# ============================================================
# Step 2: TF-IDF comparison at main break year
# ============================================================

print(f"\n=== Lexical validation: TF-IDF at detected breakpoints ===")

mask_A = df["year"] < main_break
mask_B = (df["year"] >= main_break + 1) & (df["year"] <= main_break + 3)

texts_A = df.loc[mask_A, "abstract"].dropna().tolist()
texts_B = df.loc[mask_B, "abstract"].dropna().tolist()
n_A = len(texts_A)
n_B = len(texts_B)
print(f"Period A (before {main_break}): {n_A} abstracts")
print(f"Period B ({main_break+1}-{main_break+3}):   {n_B} abstracts")

if n_A >= 5 and n_B >= 5:
    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        min_df=3,
        max_df=0.9,
        sublinear_tf=True,
    )
    X = vectorizer.fit_transform(texts_A + texts_B)
    feature_names = np.array(vectorizer.get_feature_names_out())

    mean_A = np.asarray(X[:n_A].mean(axis=0)).flatten()
    mean_B = np.asarray(X[n_A:].mean(axis=0)).flatten()
    diff = mean_B - mean_A

    X_A = X[:n_A]
    X_B = X[n_A:]
    doc_freq_A = np.asarray((X_A > 0).sum(axis=0)).flatten()
    doc_freq_B = np.asarray((X_B > 0).sum(axis=0)).flatten()

    MIN_PERIOD_DF = 3
    EXTRA_STOPS = {"mid", "vol", "hope", "gives", "new", "use", "used", "using"}

    def is_clean_term(term):
        """Filter out noise: numbers, very short tokens, extra stop words."""
        tokens = term.split()
        if len(tokens) == 1 and len(tokens[0]) < 3:
            return False
        if all(t.isdigit() for t in tokens):
            return False
        if len(tokens) == 1 and tokens[0] in EXTRA_STOPS:
            return False
        return True

    valid_mask = np.zeros(len(feature_names), dtype=bool)
    for i, term in enumerate(feature_names):
        if not is_clean_term(term):
            continue
        if diff[i] < 0 and doc_freq_A[i] >= MIN_PERIOD_DF:
            valid_mask[i] = True
        elif diff[i] > 0 and doc_freq_B[i] >= MIN_PERIOD_DF:
            valid_mask[i] = True
        elif diff[i] == 0:
            valid_mask[i] = True

    n_filtered = (~valid_mask).sum()
    print(f"Denoising: filtered {n_filtered}/{len(feature_names)} terms "
          f"(min {MIN_PERIOD_DF} docs in enriched period, {len(EXTRA_STOPS)} extra stop words)")

    tfidf_df = pd.DataFrame({
        "term": feature_names,
        "mean_tfidf_before": mean_A,
        "mean_tfidf_after": mean_B,
        "diff": diff,
        "doc_freq_before": doc_freq_A.astype(int),
        "doc_freq_after": doc_freq_B.astype(int),
        "clean": valid_mask,
    }).sort_values("diff", ascending=False)
    tfidf_df.to_csv(os.path.join(TABLES_DIR, "tab_lexical_tfidf.csv"), index=False)
    print(f"\nSaved TF-IDF table → tables/tab_lexical_tfidf.csv "
          f"({valid_mask.sum()} clean / {len(tfidf_df)} total terms)")
    print("Run plot_fig_lexical_tfidf.py to generate the figures.")
else:
    print("WARNING: Too few abstracts for TF-IDF comparison.")

print("\nDone.")
