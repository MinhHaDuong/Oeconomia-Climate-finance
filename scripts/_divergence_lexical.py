"""Lexical divergence: implementation functions (L1-L3).

Private module -- no main, no argparse. Called by compute_divergence.py.

Methods:
  L1  JS divergence on TF-IDF distributions (sliding window)
  L2  Novelty / Transience / Resonance (Barron et al. 2018)
  L3  Burst detection (z-score term frequency, Kleinberg-style)

"""

import numpy as np
import pandas as pd
from pipeline_loaders import load_analysis_corpus
from scipy.spatial.distance import jensenshannon
from scipy.stats import entropy
from sklearn.feature_extraction.text import TfidfVectorizer
from utils import get_logger

log = get_logger("_divergence_lexical")


# ── Data loading ───────────────────────────────────────────────────────────


def load_lexical_data(input_path):
    """Load works with non-null abstracts.

    Parameters
    ----------
    input_path : str | list[str] | None
        Path to refined_works.csv (used by tests).

    """
    if isinstance(input_path, list):
        input_path = input_path[0] if input_path else None

    if input_path:
        df = pd.read_csv(
            input_path, usecols=["year", "abstract"], dtype={"year": "Int64"}
        )
    else:
        df, _ = load_analysis_corpus(with_embeddings=False)

    df = df.dropna(subset=["abstract", "year"]).copy()
    df["year"] = df["year"].astype(int)
    log.info(
        "Loaded %d works with abstracts (years %d–%d)",
        len(df),
        df["year"].min(),
        df["year"].max(),
    )
    return df


# ── Shared helpers ─────────────────────────────────────────────────────────


def _smooth_distribution(v, eps=1e-10):
    """Add epsilon smoothing and normalize to a probability distribution."""
    v = np.asarray(v, dtype=float).copy()
    v = v + eps
    total = v.sum()
    if total > 0:
        v = v / total
    return v


from _divergence_io import get_min_papers as _get_min_papers

# ── L1: JS divergence on TF-IDF distributions ────────────────────────────


def compute_l1_js(df, cfg):
    """JS divergence between TF-IDF of before/after windows per year.

    Returns DataFrame with columns: year, window, hyperparams, value
    """
    div_cfg = cfg["divergence"]
    lex_cfg = div_cfg["lexical"]

    windows = div_cfg["windows"]
    min_papers = _get_min_papers(len(df), cfg)
    tfidf_max_features = lex_cfg["tfidf_max_features"]
    tfidf_min_df = lex_cfg["tfidf_min_df"]

    log.info("=== L1: JS divergence on TF-IDF ===")
    years = sorted(df["year"].unique())
    all_texts = df["abstract"].tolist()

    # Fit one global vectorizer to get consistent vocabulary
    vec = TfidfVectorizer(
        stop_words="english",
        max_features=tfidf_max_features,
        min_df=min(tfidf_min_df, max(1, len(all_texts) - 1)),
        sublinear_tf=True,
    )
    vec.fit(all_texts)

    equal_n = div_cfg.get("equal_n", False)
    seed = div_cfg.get("random_seed", 42)
    rng = np.random.RandomState(seed) if equal_n else None

    rows = []
    for w in windows:
        log.info("  L1 window=%d", w)
        for y in years:
            mask_before = (df["year"] >= y - w) & (df["year"] <= y)
            mask_after = (df["year"] >= y + 1) & (df["year"] <= y + 1 + w)

            texts_before = df.loc[mask_before, "abstract"].tolist()
            texts_after = df.loc[mask_after, "abstract"].tolist()

            if len(texts_before) < min_papers or len(texts_after) < min_papers:
                continue

            if equal_n and len(texts_before) != len(texts_after):
                from _divergence_io import subsample_equal_n

                result = subsample_equal_n(texts_before, texts_after, min_papers, rng)
                if result is None:
                    continue
                texts_before, texts_after = result

            X_before = vec.transform(texts_before)
            X_after = vec.transform(texts_after)

            # Aggregate: mean TF-IDF per window
            agg_before = np.asarray(X_before.mean(axis=0)).flatten()
            agg_after = np.asarray(X_after.mean(axis=0)).flatten()

            # Smooth to valid probability distributions
            p = _smooth_distribution(agg_before)
            q = _smooth_distribution(agg_after)

            js = float(jensenshannon(p, q))
            rows.append(
                {
                    "year": y,
                    "window": str(w),
                    "hyperparams": f"w={w}",
                    "value": js,
                }
            )

    log.info("  L1: %d data points", len(rows))
    return pd.DataFrame(rows)


# ── L2: Novelty / Transience / Resonance ──────────────────────────────────


def compute_l2_novelty(df, cfg):
    """Novelty, transience, resonance per year from KL divergence.

    Returns DataFrame with columns: year, window, hyperparams, value
    """
    div_cfg = cfg["divergence"]
    lex_cfg = div_cfg["lexical"]

    l2_windows = lex_cfg["L2_novelty"]["windows"]
    min_papers = _get_min_papers(len(df), cfg)
    tfidf_max_features = lex_cfg["tfidf_max_features"]
    tfidf_min_df = lex_cfg["tfidf_min_df"]

    log.info("=== L2: Novelty / Transience / Resonance ===")
    years = sorted(df["year"].unique())
    all_texts = df["abstract"].tolist()

    # Fit global vectorizer
    vec = TfidfVectorizer(
        stop_words="english",
        max_features=tfidf_max_features,
        min_df=min(tfidf_min_df, max(1, len(all_texts) - 1)),
        sublinear_tf=True,
    )
    X_all = vec.fit_transform(all_texts)
    doc_years = df["year"].values

    rows = []
    for w in l2_windows:
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

            if past_mask.sum() < min_papers or future_mask.sum() < min_papers:
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

            for metric, val in [
                ("novelty", mean_novelty),
                ("transience", mean_transience),
                ("resonance", mean_resonance),
            ]:
                rows.append(
                    {
                        "year": y,
                        "window": str(w),
                        "hyperparams": f"w={w},metric={metric}",
                        "value": val,
                    }
                )

    log.info("  L2: %d data points", len(rows))
    return pd.DataFrame(rows)


# ── L3: Burst detection ───────────────────────────────────────────────────


def compute_l3_bursts(df, cfg):
    """Count terms in burst (z > threshold) per year.

    Returns DataFrame with columns: year, window, hyperparams, value
    """
    div_cfg = cfg["divergence"]
    lex_cfg = div_cfg["lexical"]

    n_top_terms = lex_cfg["L3_bursts"]["top_n_terms"]
    z_threshold = lex_cfg["L3_bursts"]["z_threshold"]
    tfidf_max_features = lex_cfg["tfidf_max_features"]
    tfidf_min_df = lex_cfg["tfidf_min_df"]

    log.info("=== L3: Burst detection (z-score) ===")
    years = sorted(df["year"].unique())
    all_texts = df["abstract"].tolist()

    # Fit TF-IDF to get vocabulary, then use raw term counts per year
    vec = TfidfVectorizer(
        stop_words="english",
        max_features=tfidf_max_features,
        min_df=min(tfidf_min_df, max(1, len(all_texts) - 1)),
        sublinear_tf=False,  # raw TF for burst detection
        use_idf=False,
        norm=None,
    )
    X_all = vec.fit_transform(all_texts)
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
        n_burst = int((z_matrix[i] > z_threshold).sum())
        rows.append(
            {
                "year": y,
                "window": "0",
                "hyperparams": f"top={n_top_terms},z_thresh={z_threshold}",
                "value": n_burst,
            }
        )

    log.info("  L3: %d data points", len(rows))
    return pd.DataFrame(rows)
