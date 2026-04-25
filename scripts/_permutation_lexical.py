"""Permutation null model drivers for lexical methods (L1, L2, L3).

Private module — no main, no argparse.  Called by compute_null_model.py.

L1 — Jensen-Shannon divergence on TF-IDF (precomputed sparse permutation)
L2 — Novelty / Transience / Resonance (Barron et al. 2018)
    Past/future pool-shuffle: pool past and future texts; for each permutation
    randomly assign pool docs into buckets of size |past| and |future| and
    recompute resonance of the fixed year-y docs against the shuffled LMs.

L3 — Burst detection (z-score term frequency, Kleinberg-style)
    Document-shuffle permutation: shuffle document-year assignments while
    preserving per-year document counts.  Recompute burst counts from scratch
    in each permutation.  The null ribbon is in raw burst-count units,
    matching the observed statistic.
"""

import numpy as np
import pandas as pd
from _permutation_io import _nan_row, _result_row
from utils import get_logger

log = get_logger("_permutation_lexical")


def _count_bursts(year_labels, X_all, top_indices, years, z_threshold):
    """Count burst terms per year given a (possibly permuted) year-label array.

    Parameters
    ----------
    year_labels : np.ndarray of int, shape (n_docs,)
        Year assigned to each document (may be permuted).
    X_all : scipy sparse matrix, shape (n_docs, n_features)
        Raw TF matrix for the entire corpus.
    top_indices : np.ndarray of int
        Column indices of the top-N terms by corpus frequency.
    years : list[int]
        Sorted list of years to compute counts for.
    z_threshold : float
        Z-score threshold for declaring a term as bursting.

    Returns
    -------
    np.ndarray of int, shape (n_years,)
        Number of bursting terms for each year.

    """
    n_years = len(years)
    year_to_idx = {y: i for i, y in enumerate(years)}

    # Per-year mean term frequency for top terms
    tf_matrix = np.zeros((n_years, len(top_indices)))
    for i, y in enumerate(years):
        mask = year_labels == y
        n_docs = mask.sum()
        if n_docs == 0:
            continue
        tf = np.asarray(X_all[mask][:, top_indices].sum(axis=0)).flatten()
        tf_matrix[i] = tf / n_docs

    # Z-score each term across years
    means = tf_matrix.mean(axis=0)
    stds = tf_matrix.std(axis=0)
    with np.errstate(divide="ignore", invalid="ignore"):
        z_matrix = np.where(stds > 0, (tf_matrix - means) / stds, 0.0)

    return (z_matrix > z_threshold).sum(axis=1).astype(int)


def run_l3_permutations(div_df, cfg):
    """Document-shuffle permutation null model for L3 (term burst counts).

    L3 emits one value per year (window="0"): the count of terms whose
    per-year TF z-score exceeds a threshold.  The null model shuffles
    document-year assignments (preserving per-year document counts) and
    recomputes burst counts from scratch in each permutation.

    The observed value is read directly from div_df["value"] (raw burst
    counts as produced by compute_l3_bursts).  The null ribbon is in the
    same raw-count units.

    Parameters
    ----------
    div_df : pd.DataFrame
        Rows from tab_div_L3.csv with columns year, window, value.
    cfg : dict
        Analysis config (reads divergence.random_seed,
        divergence.permutation.n_perm, and divergence.lexical.L3_bursts).

    Returns
    -------
    pd.DataFrame matching NullModelSchema with window="0".

    """
    from _divergence_lexical import load_lexical_data
    from sklearn.feature_extraction.text import TfidfVectorizer

    div_cfg = cfg["divergence"]
    lex_cfg = div_cfg["lexical"]
    n_perm = div_cfg["permutation"]["n_perm"]
    seed = div_cfg["random_seed"]
    rng = np.random.RandomState(seed)

    n_top_terms = lex_cfg["L3_bursts"]["top_n_terms"]
    z_threshold = lex_cfg["L3_bursts"]["z_threshold"]
    tfidf_max_features = lex_cfg["tfidf_max_features"]
    tfidf_min_df = lex_cfg["tfidf_min_df"]

    df = load_lexical_data(None)
    doc_years = df["year"].values
    all_texts = df["abstract"].tolist()

    # Fit TF-IDF (raw TF, no IDF) — same settings as compute_l3_bursts
    vec = TfidfVectorizer(
        stop_words="english",
        max_features=tfidf_max_features,
        min_df=min(tfidf_min_df, max(1, len(all_texts) - 1)),
        sublinear_tf=False,
        use_idf=False,
        norm=None,
    )
    X_all = vec.fit_transform(all_texts)

    # Corpus-wide frequency → top N terms (invariant under permutation)
    corpus_freq = np.asarray(X_all.sum(axis=0)).flatten()
    top_indices = np.argsort(corpus_freq)[-n_top_terms:]

    years = sorted(div_df["year"].unique())
    observed_values = np.array(
        [div_df.loc[div_df["year"] == y, "value"].iloc[0] for y in years]
    )

    # Per-year document counts (preserved during shuffle)
    year_counts = {y: int((doc_years == y).sum()) for y in years}

    # Permutation loop: shuffle document-year assignments within the corpus
    perm_matrix = np.empty((n_perm, len(years)))
    for i in range(n_perm):
        shuffled_years = rng.permutation(doc_years)
        perm_matrix[i] = _count_bursts(
            shuffled_years, X_all, top_indices, years, z_threshold
        )

    null_mean = np.mean(perm_matrix, axis=0)
    null_std = np.std(perm_matrix, axis=0)

    rows = []
    for j, y in enumerate(years):
        obs = float(observed_values[j])
        nm = float(null_mean[j])
        ns = float(null_std[j])
        if ns > 0:
            z = (obs - nm) / ns
        else:
            z = 0.0
        p = float(np.mean(perm_matrix[:, j] >= obs))
        rows.append(_result_row(y, "0", obs, nm, ns, z, p))
        log.info(
            "  year=%d obs=%.1f null_mean=%.2f z=%.2f p=%.3f [L3]", y, obs, nm, z, p
        )

    return pd.DataFrame(rows)


def run_l2_permutations(div_df, cfg):
    """Past/future pool-shuffle null model for L2 (Novelty-Transience Resonance).

    L2 computes per-document KL divergence against a past language model
    (novelty) and a future language model (transience). The statistic is
    mean_resonance = mean_novelty - mean_transience for year-y docs.

    Null model: pool the past and future texts; for each permutation,
    randomly assign pool docs into buckets of size |past| and |future|;
    recompute resonance of the fixed year-y docs against these shuffled
    language models.

    Parameters
    ----------
    div_df : pd.DataFrame
        Rows from tab_div_L2.csv. May have three rows per (year, window) for
        novelty/transience/resonance; unique (year, window) pairs are used.
    cfg : dict
        Analysis config.

    Returns
    -------
    pd.DataFrame matching NullModelSchema, one row per (year, window).

    """
    from _divergence_io import _make_window_rngs, get_min_papers
    from _divergence_lexical import _smooth_distribution, load_lexical_data
    from scipy.stats import entropy
    from sklearn.feature_extraction.text import TfidfVectorizer

    div_cfg = cfg["divergence"]
    lex_cfg = div_cfg["lexical"]
    n_perm = div_cfg["permutation"]["n_perm"]
    seed = div_cfg["random_seed"]
    gap = div_cfg.get("gap", 1)
    tfidf_max_features = lex_cfg["tfidf_max_features"]
    tfidf_min_df = lex_cfg["tfidf_min_df"]

    df = load_lexical_data(None)
    doc_years = df["year"].values
    all_texts = df["abstract"].tolist()
    min_papers = get_min_papers(cfg=cfg, n_works=len(df))

    # Fit global vectorizer on the entire corpus (consistent with compute_l2_novelty)
    vec = TfidfVectorizer(
        stop_words="english",
        max_features=tfidf_max_features,
        min_df=min(tfidf_min_df, max(1, len(all_texts) - 1)),
        sublinear_tf=True,
    )
    X_all = vec.fit_transform(all_texts)

    # Unique (year, window) pairs from div_df
    year_windows = (
        div_df[["year", "window"]]
        .drop_duplicates()
        .assign(window=lambda d: d["window"].astype(int))
    )

    rows = []
    for _, row in year_windows.iterrows():
        y = int(row["year"])
        w = int(row["window"])

        _, perm_rng = _make_window_rngs(seed, y, w)

        past_mask = (doc_years >= y - w) & (doc_years <= y - gap)
        future_mask = (doc_years >= y + gap) & (doc_years <= y + w)
        year_mask = doc_years == y

        if (
            past_mask.sum() < min_papers
            or future_mask.sum() < min_papers
            or year_mask.sum() == 0
        ):
            rows.append(_nan_row(y, str(w)))
            continue

        # Pre-transform year-y docs (fixed across permutations)
        year_indices = np.where(year_mask)[0]
        year_vecs = [
            _smooth_distribution(np.asarray(X_all[i].todense()).flatten())
            for i in year_indices
        ]

        # Pool past + future
        past_indices = np.where(past_mask)[0]
        future_indices = np.where(future_mask)[0]
        pool_indices = np.concatenate([past_indices, future_indices])
        n_past = len(past_indices)

        def _resonance_from_split(perm_past_idx, perm_future_idx):
            """Compute mean resonance = mean_novelty - mean_transience."""
            past_agg = _smooth_distribution(
                np.asarray(X_all[perm_past_idx].mean(axis=0)).flatten()
            )
            future_agg = _smooth_distribution(
                np.asarray(X_all[perm_future_idx].mean(axis=0)).flatten()
            )
            novelties = []
            transiences = []
            for dv in year_vecs:
                nov = min(float(entropy(dv, past_agg)), 50.0)
                trans = min(float(entropy(dv, future_agg)), 50.0)
                novelties.append(nov)
                transiences.append(trans)
            return float(np.mean(novelties)) - float(np.mean(transiences))

        # Observed resonance
        observed = _resonance_from_split(past_indices, future_indices)

        # Null distribution: shuffle pool assignment
        null_stats = np.empty(n_perm)
        for i in range(n_perm):
            shuffled = perm_rng.permutation(pool_indices)
            perm_past = shuffled[:n_past]
            perm_future = shuffled[n_past:]
            null_stats[i] = _resonance_from_split(perm_past, perm_future)

        nm = float(np.mean(null_stats))
        ns = float(np.std(null_stats))
        if ns > 0:
            z = (observed - nm) / ns
        else:
            z = 0.0
        p = float(np.mean(null_stats >= observed))

        rows.append(_result_row(y, str(w), observed, nm, ns, z, p))
        log.info("  year=%d window=%d z=%.2f p=%.3f [L2]", y, w, z, p)

    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# L1: Jensen-Shannon on TF-IDF
# ---------------------------------------------------------------------------


def _make_lexical_statistic(vectorizer):
    """Return a statistic_fn(texts_before, texts_after) -> float for L1 JS."""
    from _divergence_lexical import _smooth_distribution
    from scipy.spatial.distance import jensenshannon

    def js_fn(texts_before, texts_after):
        X_before = vectorizer.transform(texts_before)
        X_after = vectorizer.transform(texts_after)
        agg_before = np.asarray(X_before.mean(axis=0)).flatten()
        agg_after = np.asarray(X_after.mean(axis=0)).flatten()
        p = _smooth_distribution(agg_before)
        q = _smooth_distribution(agg_after)
        return float(jensenshannon(p, q))

    return js_fn


def _run_lexical_permutations(method_name, div_df, cfg):
    """Permutation test for lexical methods (L1).

    Precomputes TF-IDF for each (year, window) pool once, then permutes
    row indices into the sparse matrix — avoids 2 x n_perm redundant
    vectorizer.transform() calls per window.
    """
    from _divergence_io import fit_lexical_vectorizer, iter_lexical_windows
    from _permutation_accel import precomputed_lexical_permutation

    vectorizer = fit_lexical_vectorizer(cfg)
    n_perm = cfg["divergence"]["permutation"]["n_perm"]

    rows = []
    for y, w, texts_before, texts_after, perm_rng in iter_lexical_windows(div_df, cfg):
        all_texts = texts_before + texts_after
        X_all = vectorizer.transform(all_texts)
        n_before = len(texts_before)

        obs, nm, ns, z, p = precomputed_lexical_permutation(
            X_all, n_before, n_perm, perm_rng
        )
        rows.append(_result_row(y, w, obs, nm, ns, z, p))
        log.info("  year=%d window=%d z=%.2f p=%.3f", y, w, z, p)

    return pd.DataFrame(rows)
