"""Lexical divergence methods for structural break detection.

Three cluster-free continuous methods operating on abstract text:

- **L1**: JS divergence on TF-IDF distributions (sliding window)
- **L2**: Novelty / Transience / Resonance (Barron et al. 2018)
- **L3**: Burst detection (z-score term frequency, Kleinberg-style)

After computing all series, applies PELT break detection (ruptures).

Reads:  refined_works.csv
Writes: long-format CSV with columns: year, method, window, hyperparams, value

Usage:
    python3 scripts/compute_divergence_lexical.py \
        --output content/tables/tab_lexical_divergence.csv
"""

import os
import warnings

import numpy as np
import pandas as pd
import ruptures
from scipy.spatial.distance import jensenshannon
from scipy.stats import entropy
from sklearn.feature_extraction.text import TfidfVectorizer

from script_io_args import parse_io_args, validate_io
from utils import CATALOGS_DIR, get_logger

log = get_logger("compute_divergence_lexical")

warnings.filterwarnings("ignore", category=FutureWarning)

# ---------------------------------------------------------------------------
# TF-IDF parameters
# ---------------------------------------------------------------------------
MAX_FEATURES = 5000
MIN_DF = 3
MIN_PAPERS_PER_WINDOW = 3

# PELT parameters
PELT_PENALTIES = [1, 3, 5]
PELT_MIN_SIZE = 2
PELT_JUMP = 1


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _load_corpus(input_path=None):
    """Load refined_works.csv, keep only rows with non-null abstracts."""
    csv_path = input_path or os.path.join(CATALOGS_DIR, "refined_works.csv")
    df = pd.read_csv(csv_path, usecols=["year", "abstract"],
                     dtype={"year": "Int64"})
    df = df.dropna(subset=["abstract", "year"]).copy()
    df["year"] = df["year"].astype(int)
    log.info("Loaded %d works with abstracts (years %d-%d)",
             len(df), df["year"].min(), df["year"].max())
    return df


def _fit_tfidf(texts):
    """Fit TF-IDF vectorizer on a list of texts. Returns (matrix, vectorizer)."""
    vec = TfidfVectorizer(
        stop_words="english",
        max_features=MAX_FEATURES,
        min_df=min(MIN_DF, max(1, len(texts) - 1)),
        sublinear_tf=True,
    )
    X = vec.fit_transform(texts)
    return X, vec


def _smooth_distribution(v, eps=1e-10):
    """Add epsilon smoothing and normalize to a probability distribution."""
    v = np.asarray(v, dtype=float).copy()
    v = v + eps
    total = v.sum()
    if total > 0:
        v = v / total
    return v


# ---------------------------------------------------------------------------
# L1: JS divergence on TF-IDF distributions
# ---------------------------------------------------------------------------

def compute_l1(df, windows=(2, 3, 4, 5)):
    """JS divergence between TF-IDF of before/after windows per year."""
    log.info("=== L1: JS divergence on TF-IDF ===")
    years = sorted(df["year"].unique())
    all_texts = df["abstract"].tolist()

    # Fit one global vectorizer to get consistent vocabulary
    vec = TfidfVectorizer(
        stop_words="english",
        max_features=MAX_FEATURES,
        min_df=min(MIN_DF, max(1, len(all_texts) - 1)),
        sublinear_tf=True,
    )
    vec.fit(all_texts)

    rows = []
    for w in windows:
        log.info("  L1 window=%d", w)
        for y in years:
            mask_before = (df["year"] >= y - w) & (df["year"] <= y)
            mask_after = (df["year"] >= y + 1) & (df["year"] <= y + 1 + w)

            texts_before = df.loc[mask_before, "abstract"].tolist()
            texts_after = df.loc[mask_after, "abstract"].tolist()

            if (len(texts_before) < MIN_PAPERS_PER_WINDOW or
                    len(texts_after) < MIN_PAPERS_PER_WINDOW):
                continue

            X_before = vec.transform(texts_before)
            X_after = vec.transform(texts_after)

            # Aggregate: mean TF-IDF per window
            agg_before = np.asarray(X_before.mean(axis=0)).flatten()
            agg_after = np.asarray(X_after.mean(axis=0)).flatten()

            # Smooth to valid probability distributions
            p = _smooth_distribution(agg_before)
            q = _smooth_distribution(agg_after)

            js = float(jensenshannon(p, q))
            rows.append({
                "year": y,
                "method": "L1",
                "window": w,
                "hyperparams": f"w={w}",
                "value": js,
            })

    log.info("  L1: %d data points", len(rows))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# L2: Novelty / Transience / Resonance (Barron et al. 2018)
# ---------------------------------------------------------------------------

def compute_l2(df, windows=(3, 5)):
    """Novelty, transience, resonance per year from KL divergence."""
    log.info("=== L2: Novelty / Transience / Resonance ===")
    years = sorted(df["year"].unique())
    all_texts = df["abstract"].tolist()

    # Fit global vectorizer
    vec = TfidfVectorizer(
        stop_words="english",
        max_features=MAX_FEATURES,
        min_df=min(MIN_DF, max(1, len(all_texts) - 1)),
        sublinear_tf=True,
    )
    X_all = vec.fit_transform(all_texts)
    # Map each document index to its year
    doc_years = df["year"].values

    rows = []
    for w in windows:
        log.info("  L2 window=%d", w)
        for y in years:
            # Documents in this year
            year_mask = doc_years == y
            if year_mask.sum() == 0:
                continue

            # Past: [y-w, y-1]
            past_mask = (doc_years >= y - w) & (doc_years <= y - 1)
            # Future: [y+1, y+w]
            future_mask = (doc_years >= y + 1) & (doc_years <= y + w)

            if (past_mask.sum() < MIN_PAPERS_PER_WINDOW or
                    future_mask.sum() < MIN_PAPERS_PER_WINDOW):
                continue

            # Aggregate past and future TF-IDF
            past_agg = _smooth_distribution(
                np.asarray(X_all[past_mask].mean(axis=0)).flatten()
            )
            future_agg = _smooth_distribution(
                np.asarray(X_all[future_mask].mean(axis=0)).flatten()
            )

            # Per-document novelty and transience
            year_indices = np.where(year_mask)[0]
            novelties = []
            transiences = []

            for idx in year_indices:
                doc_vec = _smooth_distribution(
                    np.asarray(X_all[idx].todense()).flatten()
                )
                # KL(doc || past) = novelty
                nov = float(entropy(doc_vec, past_agg))
                # KL(doc || future) = transience
                trans = float(entropy(doc_vec, future_agg))

                # Clip extreme values (sparse docs can produce very large KL)
                nov = min(nov, 50.0)
                trans = min(trans, 50.0)

                novelties.append(nov)
                transiences.append(trans)

            mean_novelty = float(np.mean(novelties))
            mean_transience = float(np.mean(transiences))
            mean_resonance = mean_novelty - mean_transience

            for metric, val in [("novelty", mean_novelty),
                                ("transience", mean_transience),
                                ("resonance", mean_resonance)]:
                rows.append({
                    "year": y,
                    "method": "L2",
                    "window": w,
                    "hyperparams": f"w={w},metric={metric}",
                    "value": val,
                })

    log.info("  L2: %d data points", len(rows))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# L3: Burst detection (z-score term frequency, Kleinberg-style)
# ---------------------------------------------------------------------------

def compute_l3(df, n_top_terms=100):
    """Count terms in burst (z > 2) per year based on z-scored term frequency."""
    log.info("=== L3: Burst detection (z-score) ===")
    years = sorted(df["year"].unique())
    all_texts = df["abstract"].tolist()

    # Fit TF-IDF to get vocabulary, then use raw term counts per year
    vec = TfidfVectorizer(
        stop_words="english",
        max_features=MAX_FEATURES,
        min_df=min(MIN_DF, max(1, len(all_texts) - 1)),
        sublinear_tf=False,  # raw TF for burst detection
        use_idf=False,
        norm=None,
    )
    X_all = vec.fit_transform(all_texts)
    feature_names = vec.get_feature_names_out()
    doc_years = df["year"].values

    # Corpus-wide term frequency: sum over all docs, then pick top N
    corpus_freq = np.asarray(X_all.sum(axis=0)).flatten()
    top_indices = np.argsort(corpus_freq)[-n_top_terms:]

    # Per-year term frequency for top terms
    year_tf = {}
    for y in years:
        mask = doc_years == y
        if mask.sum() == 0:
            year_tf[y] = np.zeros(len(top_indices))
            continue
        # Normalize by number of docs in the year
        n_docs = mask.sum()
        tf = np.asarray(X_all[mask][:, top_indices].sum(axis=0)).flatten()
        year_tf[y] = tf / n_docs

    # Build matrix: rows=years, cols=top terms
    tf_matrix = np.array([year_tf[y] for y in years])

    # Z-score each term across years
    with np.errstate(divide="ignore", invalid="ignore"):
        means = tf_matrix.mean(axis=0)
        stds = tf_matrix.std(axis=0)
        z_matrix = np.where(stds > 0, (tf_matrix - means) / stds, 0.0)

    rows = []
    for i, y in enumerate(years):
        n_burst = int((z_matrix[i] > 2).sum())
        rows.append({
            "year": y,
            "method": "L3",
            "window": 0,
            "hyperparams": f"top={n_top_terms},z_thresh=2",
            "value": n_burst,
        })

    log.info("  L3: %d data points", len(rows))
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# PELT break detection
# ---------------------------------------------------------------------------

def detect_breaks_pelt(series_df, penalties=None):
    """Apply PELT to each (method, hyperparams) series.

    Returns a DataFrame with columns: method, window, hyperparams, penalty, break_year.
    """
    if penalties is None:
        penalties = PELT_PENALTIES

    results = []
    groups = series_df.groupby(["method", "hyperparams"])

    for (method, hp), grp in groups:
        grp = grp.sort_values("year")
        signal = grp["value"].values.astype(float)
        years = grp["year"].values

        if len(signal) < PELT_MIN_SIZE * 2:
            continue

        for pen in penalties:
            try:
                algo = ruptures.Pelt(
                    model="l2", min_size=PELT_MIN_SIZE, jump=PELT_JUMP
                )
                bkps = algo.fit(signal).predict(pen=pen)
                # ruptures returns indices (1-based end points); last is len(signal)
                bkps = [b for b in bkps if b < len(signal)]
                for b in bkps:
                    results.append({
                        "method": method,
                        "window": grp["window"].iloc[0],
                        "hyperparams": hp,
                        "penalty": pen,
                        "break_year": int(years[b]),
                    })
            except Exception as exc:
                log.warning("PELT failed for %s %s pen=%d: %s",
                            method, hp, pen, exc)

    return pd.DataFrame(results)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    io_args, _extra = parse_io_args()
    validate_io(output=io_args.output)

    input_path = io_args.input[0] if io_args.input else None
    df = _load_corpus(input_path)

    # Compute all three methods
    l1 = compute_l1(df)
    l2 = compute_l2(df)
    l3 = compute_l3(df)

    # Combine
    combined = pd.concat([l1, l2, l3], ignore_index=True)
    log.info("Combined: %d rows across %d methods",
             len(combined), combined["method"].nunique())

    # Detect breaks
    breaks = detect_breaks_pelt(combined)
    if len(breaks) > 0:
        log.info("PELT detected %d breaks:", len(breaks))
        for _, row in breaks.iterrows():
            log.info("  %s %s pen=%d -> year %d",
                     row["method"], row["hyperparams"],
                     row["penalty"], row["break_year"])
    else:
        log.info("PELT detected no breaks (expected with sparse smoke data)")

    # Save series
    os.makedirs(os.path.dirname(io_args.output) or ".", exist_ok=True)
    combined.to_csv(io_args.output, index=False)
    log.info("Saved divergence series -> %s (%d rows)", io_args.output,
             len(combined))

    # Save breaks alongside
    breaks_path = io_args.output.replace(".csv", "_breaks.csv")
    breaks.to_csv(breaks_path, index=False)
    log.info("Saved PELT breaks -> %s (%d rows)", breaks_path, len(breaks))

    log.info("Done.")


if __name__ == "__main__":
    main()
