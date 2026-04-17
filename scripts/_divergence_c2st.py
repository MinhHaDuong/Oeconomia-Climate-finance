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
from scipy import stats
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from utils import get_logger

log = get_logger("_divergence_c2st")


# ── Core classifier ──────────────────────────────────────────────────────


def _c2st_auc(X, Y, *, cv_folds=5, class_weight="balanced", seed):
    """Compute C2ST AUC with per-fold variance and significance vs chance.

    Labels X as 0, Y as 1. Trains a fixed-C logistic regression per
    Lopez-Paz & Oquab (2017) — the test measures separability, not
    optimizes it. Uses shuffled StratifiedKFold on the concatenated data.

    The per-fold AUCs are the data-derived measure of uncertainty
    (ticket 0068): the K scores are used to report mean ± CI and a
    one-sample t-test against the chance baseline 0.5. C2ST does NOT
    use the shared permutation null model, because its statistic is
    already a hypothesis test.

    Parameters
    ----------
    X, Y : array-like
        Feature matrices (n_samples, n_features). Dense or sparse.
    cv_folds : int
        Number of cross-validation folds.
    class_weight : str
        Class weight strategy for LogisticRegression.
    seed : int
        Random state for classifier reproducibility (required, from config).

    Returns
    -------
    dict
        {"mean", "std", "q025", "q975", "n_folds", "p_value_vs_chance"}
        where q025/q975 are a Student-t CI over the K fold scores and
        p_value_vs_chance is one-sample t-test vs 0.5 (two-sided).

    """
    if sp.issparse(X) or sp.issparse(Y):
        features = sp.vstack([X, Y])
    else:
        features = np.vstack([X, Y])
    labels = np.concatenate([np.zeros(X.shape[0]), np.ones(Y.shape[0])])

    clf = LogisticRegression(
        C=1.0,
        class_weight=class_weight,
        max_iter=1000,
        random_state=seed,
    )
    cv = StratifiedKFold(n_splits=cv_folds, shuffle=True, random_state=seed)
    scores = np.asarray(
        cross_val_score(clf, features, labels, cv=cv, scoring="roc_auc"),
        dtype=float,
    )
    n = int(scores.size)
    mean = float(scores.mean())
    std = float(scores.std(ddof=1)) if n > 1 else 0.0

    if n > 1 and std > 0.0:
        t_crit = float(stats.t.ppf(0.975, df=n - 1))
        se = std / np.sqrt(n)
        q025 = max(0.0, mean - t_crit * se)
        q975 = min(1.0, mean + t_crit * se)
        # C2ST's alternative is directional: a distinguishable pair gives
        # AUC > 0.5. Use one-sided test so that a pathological cluster below
        # 0.5 does not register as "significant" signal.
        p_value = float(stats.ttest_1samp(scores, 0.5, alternative="greater").pvalue)
    else:
        q025 = mean
        q975 = mean
        p_value = float("nan")

    return {
        "mean": mean,
        "std": std,
        "q025": q025,
        "q975": q975,
        "n_folds": n,
        "p_value_vs_chance": p_value,
    }


# ── C2ST on PCA-reduced embeddings ──────────────────────────────────────


def compute_c2st_embedding(df, emb, cfg):
    """C2ST on PCA-reduced embeddings.

    For each (year, window): extract before/after embeddings via
    _iter_window_pairs, PCA-reduce, then classify.

    Returns DataFrame with columns matching C2STDivergenceSchema:
    year, window, hyperparams, value, auc_std, auc_q025, auc_q975,
    n_folds, p_value_vs_chance.
    """
    from _divergence_semantic import _get_years_and_params, _iter_window_pairs

    div_cfg = cfg["divergence"]
    c2st_cfg = div_cfg.get("c2st", {})
    pca_dim = c2st_cfg.get("pca_dim", 32)
    cv_folds = c2st_cfg.get("cv_folds", 5)
    class_weight = c2st_cfg.get("class_weight", "balanced")
    seed = div_cfg["random_seed"]
    rng = np.random.RandomState(seed)

    years_by_window, min_papers, max_subsample, equal_n = _get_years_and_params(
        df, emb, cfg
    )
    if not any(years_by_window.values()):
        return pd.DataFrame(
            columns=[
                "year",
                "window",
                "hyperparams",
                "value",
                "auc_std",
                "auc_q025",
                "auc_q975",
                "n_folds",
                "p_value_vs_chance",
            ]
        )

    results = []
    last_w = None
    for y, w, X, Y in _iter_window_pairs(
        df,
        emb,
        years_by_window,
        min_papers,
        max_subsample,
        rng=rng,
        equal_n=equal_n,
    ):
        if last_w is not None and w != last_w:
            log.info("C2ST_embedding window=%d done", last_w)
        last_w = w

        n_components = min(pca_dim, min(len(X), len(Y)) - 1, X.shape[1])
        n_components = max(2, n_components)
        pca = PCA(n_components=n_components, random_state=seed)
        combined = np.vstack([X, Y])
        combined_r = pca.fit_transform(combined)
        X_r = combined_r[: len(X)]
        Y_r = combined_r[len(X) :]

        r = _c2st_auc(X_r, Y_r, cv_folds=cv_folds, class_weight=class_weight, seed=seed)
        results.append(
            {
                "year": int(y),
                "window": str(w),
                "hyperparams": f"pca={n_components}",
                "value": r["mean"],
                "auc_std": r["std"],
                "auc_q025": r["q025"],
                "auc_q975": r["q975"],
                "n_folds": r["n_folds"],
                "p_value_vs_chance": r["p_value_vs_chance"],
            }
        )

    if last_w is not None:
        log.info("C2ST_embedding window=%d done", last_w)
    return pd.DataFrame(results)


# ── C2ST on TF-IDF features ────────────────────────────────────────────


def compute_c2st_lexical(df, cfg):
    """C2ST on TF-IDF features via shared lexical window iterator.

    Returns DataFrame with columns matching C2STDivergenceSchema:
    year, window, hyperparams, value, auc_std, auc_q025, auc_q975,
    n_folds, p_value_vs_chance.
    """
    from _divergence_lexical import _iter_lexical_window_pairs

    div_cfg = cfg["divergence"]
    c2st_cfg = div_cfg.get("c2st", {})
    cv_folds = c2st_cfg.get("cv_folds", 5)
    class_weight = c2st_cfg.get("class_weight", "balanced")
    seed = div_cfg["random_seed"]
    lex_cfg = div_cfg.get("lexical", {})
    tfidf_max_features = lex_cfg.get("tfidf_max_features", 5000)

    log.info("=== C2ST_lexical ===")
    results = []
    last_w = None
    for y, w, X_before, X_after, _vec in _iter_lexical_window_pairs(df, cfg):
        if last_w is not None and w != last_w:
            log.info("  C2ST_lexical window=%d done", last_w)
        last_w = w

        r = _c2st_auc(
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
                "value": r["mean"],
                "auc_std": r["std"],
                "auc_q025": r["q025"],
                "auc_q975": r["q975"],
                "n_folds": r["n_folds"],
                "p_value_vs_chance": r["p_value_vs_chance"],
            }
        )

    log.info("  C2ST_lexical: %d data points", len(results))
    return pd.DataFrame(results)
