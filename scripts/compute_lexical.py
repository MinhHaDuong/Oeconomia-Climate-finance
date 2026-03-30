"""Lexical validation of structural breaks via TF-IDF term shift analysis.

Reads:  refined_works.csv,
        tab_breakpoint_robustness.csv (to derive detected break years)
Writes: tab_lexical_tfidf.csv (all break years + control years, with p-values)

Note: The lexical TF-IDF *figures* are produced by plot_fig_lexical_tfidf.py.

Exports (for import by plot_fig_lexical_tfidf.py):
  EXTRA_STOPS, MIN_PERIOD_DF, is_clean_term()
"""

import os

from utils import BASE_DIR, get_logger

log = get_logger("compute_lexical")

TABLES_DIR = os.path.join(BASE_DIR, "content", "tables")

# --- Shared lexical denoising constants (imported by plot_fig_lexical_tfidf.py) ---
MIN_PERIOD_DF = 3
EXTRA_STOPS = {"mid", "vol", "hope", "gives", "new", "use", "used", "using"}

# Control years appended after detected breaks
CONTROL_YEARS = [2015, 2021]


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


if __name__ == "__main__":
    import argparse

    import numpy as np
    import pandas as pd
    from sklearn.feature_extraction.text import TfidfVectorizer
    from utils import load_analysis_corpus

    os.makedirs(TABLES_DIR, exist_ok=True)

    # --- Args ---
    parser = argparse.ArgumentParser(description="Compute lexical TF-IDF table at break years")
    parser.add_argument("--core-only", action="store_true",
                        help="Not supported (lexical analysis uses full corpus). Prints warning.")
    args = parser.parse_args()

    if args.core_only:
        log.warning("--core-only is not supported by compute_lexical.py "
                    "(lexical analysis uses the full corpus). Flag ignored.")

    # ============================================================
    # Step 1: Load data and detected break years
    # ============================================================

    df, _ = load_analysis_corpus(with_embeddings=False)
    log.info("Loaded %d works", len(df))

    # Load detected break years from breakpoints table
    robust_path = os.path.join(TABLES_DIR, "tab_breakpoint_robustness.csv")
    try:
        robust_df = pd.read_csv(robust_path)
    except FileNotFoundError:
        raise FileNotFoundError(
            f"Missing {robust_path}. Run compute_breakpoints.py first."
        ) from None
    detected_breaks = sorted(robust_df["year"].tolist()[:3])
    log.info("Detected break years (from tab_breakpoint_robustness.csv): %s", detected_breaks)

    # All years to compute: detected breaks + control years
    break_years = sorted(set(detected_breaks) | {yr for yr in CONTROL_YEARS})
    log.info("Computing TF-IDF for years: %s", break_years)

    # ============================================================
    # Step 2: TF-IDF comparison at each break year
    # ============================================================

    N_PERM = 1000
    WINDOW_AFTER = 3
    all_rows = []

    for break_year in break_years:
        log.info("=== Lexical validation: TF-IDF at %d ===", break_year)

        mask_A = df["year"] < break_year
        mask_B = (df["year"] >= break_year + 1) & (df["year"] <= break_year + WINDOW_AFTER)

        texts_A = df.loc[mask_A, "abstract"].dropna().tolist()
        texts_B = df.loc[mask_B, "abstract"].dropna().tolist()
        n_A = len(texts_A)
        n_B = len(texts_B)
        log.info("Period A (before %d): %d abstracts", break_year, n_A)
        log.info("Period B (%d-%d):   %d abstracts", break_year + 1, break_year + WINDOW_AFTER, n_B)

        if n_A < 5 or n_B < 5:
            log.warning("Too few abstracts for %d, skipping.", break_year)
            continue

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
        log.info("Denoising: filtered %d/%d terms "
                 "(min %d docs in enriched period, %d extra stop words)",
                 n_filtered, len(feature_names), MIN_PERIOD_DF, len(EXTRA_STOPS))

        # Permutation test for significance thresholds
        rng = np.random.RandomState(42)
        max_abs_diffs = np.zeros(N_PERM)
        n_total = n_A + n_B
        for p in range(N_PERM):
            perm = rng.permutation(n_total)
            perm_A = np.asarray(X[perm[:n_A]].mean(axis=0)).flatten()
            perm_B = np.asarray(X[perm[n_A:]].mean(axis=0)).flatten()
            max_abs_diffs[p] = np.max(np.abs(perm_B - perm_A))
        sig_95 = float(np.percentile(max_abs_diffs, 95))
        sig_99 = float(np.percentile(max_abs_diffs, 99))
        log.info("Permutation test (%d perm): |DTFIDF| threshold "
                 "p<0.05=%.4f, p<0.01=%.4f", N_PERM, sig_95, sig_99)

        tfidf_df = pd.DataFrame({
            "break_year": break_year,
            "term": feature_names,
            "mean_tfidf_before": mean_A,
            "mean_tfidf_after": mean_B,
            "diff": diff,
            "doc_freq_before": doc_freq_A.astype(int),
            "doc_freq_after": doc_freq_B.astype(int),
            "clean": valid_mask,
            "n_before": n_A,
            "n_after": n_B,
            "sig_95": sig_95,
            "sig_99": sig_99,
        })
        all_rows.append(tfidf_df)
        log.info("  %d clean / %d total terms", valid_mask.sum(), len(tfidf_df))

    # ============================================================
    # Step 3: Concatenate and save
    # ============================================================

    if all_rows:
        result = pd.concat(all_rows, ignore_index=True)
        out_path = os.path.join(TABLES_DIR, "tab_lexical_tfidf.csv")
        result.to_csv(out_path, index=False)
        years_saved = sorted(result["break_year"].unique())
        log.info("Saved TF-IDF table -> tables/tab_lexical_tfidf.csv "
                 "(%d rows, break years: %s)", len(result), years_saved)
        log.info("Run plot_fig_lexical_tfidf.py to generate the figures.")
    else:
        log.warning("No break years had enough abstracts for TF-IDF comparison.")

    log.info("Done.")
