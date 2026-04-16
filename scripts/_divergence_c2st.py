"""C2ST (Classifier Two-Sample Test) divergence: implementation functions.

Private module -- no main, no argparse. Called by compute_divergence.py.

Methods:
  C2ST_embedding  Logistic regression on PCA-reduced embeddings
  C2ST_lexical    Logistic regression on TF-IDF features

Reference:
  Lopez-Paz & Oquab (2017) "Revisiting Classifier Two-Sample Tests"

"""

import numpy as np
import pandas as pd
import scipy.sparse as sp
from sklearn.decomposition import PCA
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegressionCV
from sklearn.model_selection import cross_val_score
from utils import get_logger

log = get_logger("_divergence_c2st")


# ── Core classifier ──────────────────────────────────────────────────────


def _c2st_auc(X, Y, *, cv_folds=5, class_weight="balanced", seed):
    """Compute C2ST AUC: train a classifier to distinguish X from Y.

    Labels X as 0, Y as 1.  Returns mean cross-validated ROC AUC.
    AUC near 0.5 means the distributions are indistinguishable;
    AUC near 1.0 means they are clearly different.

    Accepts both dense arrays and sparse matrices (e.g. TF-IDF output).

    Parameters
    ----------
    X, Y : array-like
        Feature matrices (n_samples, n_features). Dense or sparse.
    cv_folds : int
        Number of cross-validation folds.
    class_weight : str
        Class weight strategy for LogisticRegressionCV.
    seed : int
        Random state for classifier reproducibility (required, from config).

    Returns
    -------
    float
        Mean cross-validated ROC AUC.

    """
    if sp.issparse(X) or sp.issparse(Y):
        features = sp.vstack([X, Y])
    else:
        features = np.vstack([X, Y])
    labels = np.concatenate([np.zeros(X.shape[0]), np.ones(Y.shape[0])])

    clf = LogisticRegressionCV(
        class_weight=class_weight,
        cv=cv_folds,
        scoring="roc_auc",
        max_iter=1000,
        random_state=seed,
    )
    scores = cross_val_score(clf, features, labels, cv=cv_folds, scoring="roc_auc")
    return float(np.mean(scores))


# ── C2ST on PCA-reduced embeddings ──────────────────────────────────────


def compute_c2st_embedding(df, emb, cfg):
    """C2ST on PCA-reduced embeddings.

    For each (year, window): extract before/after embeddings via
    _iter_window_pairs, PCA-reduce, then classify.

    Returns DataFrame with columns: year, window, hyperparams, value
    """
    from _divergence_semantic import _get_years_and_params, _iter_window_pairs

    div_cfg = cfg["divergence"]
    c2st_cfg = div_cfg.get("c2st", {})
    pca_dim = c2st_cfg.get("pca_dim", 32)
    cv_folds = c2st_cfg.get("cv_folds", 5)
    class_weight = c2st_cfg.get("class_weight", "balanced")
    seed = div_cfg.get("random_seed", 42)
    rng = np.random.RandomState(seed)

    years, min_papers, max_subsample, windows, equal_n = _get_years_and_params(
        df, emb, cfg
    )
    if not years:
        return pd.DataFrame(columns=["year", "window", "hyperparams", "value"])

    results = []
    last_w = None
    for y, w, X, Y in _iter_window_pairs(
        df,
        emb,
        years,
        windows,
        min_papers,
        max_subsample,
        rng=rng,
        equal_n=equal_n,
    ):
        if last_w is not None and w != last_w:
            log.info("C2ST_embedding window=%d done", last_w)
        last_w = w

        # PCA reduce
        n_components = min(pca_dim, min(len(X), len(Y)) - 1, X.shape[1])
        n_components = max(2, n_components)
        pca = PCA(n_components=n_components, random_state=seed)
        combined = np.vstack([X, Y])
        combined_r = pca.fit_transform(combined)
        X_r = combined_r[: len(X)]
        Y_r = combined_r[len(X) :]

        auc = _c2st_auc(
            X_r, Y_r, cv_folds=cv_folds, class_weight=class_weight, seed=seed
        )
        results.append(
            {
                "year": int(y),
                "window": str(w),
                "hyperparams": f"pca={n_components}",
                "value": auc,
            }
        )

    if last_w is not None:
        log.info("C2ST_embedding window=%d done", last_w)
    return pd.DataFrame(results)


# ── C2ST on TF-IDF features ────────────────────────────────────────────


def compute_c2st_lexical(df, cfg):
    """C2ST on TF-IDF features.

    For each (year, window): extract before/after abstracts, vectorize
    with TF-IDF, then classify.

    Returns DataFrame with columns: year, window, hyperparams, value
    """
    from _divergence_io import get_min_papers

    div_cfg = cfg["divergence"]
    lex_cfg = div_cfg.get("lexical", {})
    c2st_cfg = div_cfg.get("c2st", {})
    cv_folds = c2st_cfg.get("cv_folds", 5)
    class_weight = c2st_cfg.get("class_weight", "balanced")

    windows = div_cfg["windows"]
    min_papers = get_min_papers(len(df), cfg)
    tfidf_max_features = lex_cfg.get("tfidf_max_features", 5000)
    tfidf_min_df = lex_cfg.get("tfidf_min_df", 3)
    equal_n = div_cfg.get("equal_n", False)
    seed = div_cfg.get("random_seed", 42)
    rng = np.random.RandomState(seed) if equal_n else None

    log.info("=== C2ST_lexical ===")
    years = sorted(df["year"].unique())
    all_texts = df["abstract"].tolist()

    # Fit one global vectorizer for consistent vocabulary
    vec = TfidfVectorizer(
        stop_words="english",
        max_features=tfidf_max_features,
        min_df=min(tfidf_min_df, max(1, len(all_texts) - 1)),
        sublinear_tf=True,
    )
    vec.fit(all_texts)

    results = []
    for w in windows:
        log.info("  C2ST_lexical window=%d", w)
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

            auc = _c2st_auc(
                X_before,
                X_after,
                cv_folds=cv_folds,
                class_weight=class_weight,
                seed=seed,
            )
            results.append(
                {
                    "year": int(y),
                    "window": str(w),
                    "hyperparams": f"tfidf_features={tfidf_max_features}",
                    "value": auc,
                }
            )

    log.info("  C2ST_lexical: %d data points", len(results))
    return pd.DataFrame(results)
