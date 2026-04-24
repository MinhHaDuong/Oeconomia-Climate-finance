"""Permutation null model drivers for C2ST methods.

C2ST_embedding — PCA-reduced embeddings + logistic regression AUC
C2ST_lexical   — TF-IDF sparse features + logistic regression AUC

Private module — no main, no argparse.  Called by compute_null_model.py.
"""

import numpy as np
import pandas as pd
from _permutation_io import _result_row, permutation_test
from utils import get_logger

log = get_logger("_permutation_c2st")


def _run_c2st_embedding_permutations(div_df, cfg):
    """Permutation null model for C2ST_embedding.

    For each (year, window): loads raw embeddings via iter_semantic_windows,
    PCA-reduces the combined pool (fit once, same transform for all permutations),
    then calls permutation_test with _c2st_auc as the statistic.

    PCA is fit on the combined pool before permutation so that all permuted
    splits share the same feature space.  n_components is clamped to avoid
    sklearn errors on small smoke windows.
    """
    from _divergence_c2st import _c2st_auc
    from _divergence_io import iter_semantic_windows
    from sklearn.decomposition import PCA

    div_cfg = cfg["divergence"]
    c2st_cfg = div_cfg.get("c2st", {})
    pca_dim = c2st_cfg.get("pca_dim", 32)
    cv_folds = c2st_cfg.get("cv_folds", 5)
    class_weight = c2st_cfg.get("class_weight", "balanced")
    seed = div_cfg["random_seed"]
    n_perm = div_cfg["permutation"]["n_perm"]

    rows = []
    for y, w, X_raw, Y_raw, perm_rng in iter_semantic_windows(div_df, cfg):
        # Clamp n_components as in compute_c2st_embedding (ticket 0068)
        n_components = max(
            2, min(pca_dim, min(len(X_raw), len(Y_raw)) - 1, X_raw.shape[1])
        )
        pca = PCA(n_components=n_components, random_state=seed)
        combined_r = pca.fit_transform(np.vstack([X_raw, Y_raw]))
        X_pca = combined_r[: len(X_raw)]
        Y_pca = combined_r[len(X_raw) :]

        def statistic_fn(X, Y, _seed=seed):
            return _c2st_auc(
                X, Y, cv_folds=cv_folds, class_weight=class_weight, seed=_seed
            )["mean"]

        observed, null_mean, null_std, z, p = permutation_test(
            X_pca, Y_pca, statistic_fn, n_perm, perm_rng
        )
        rows.append(_result_row(y, w, observed, null_mean, null_std, z, p))
        log.info("  C2ST_embedding year=%d window=%d z=%.2f p=%.3f", y, w, z, p)

    return pd.DataFrame(rows)


def _run_c2st_lexical_permutations(div_df, cfg):
    """Permutation null model for C2ST_lexical.

    For each (year, window): vectorizes the combined text pool once, then
    runs a manual permutation loop (sparse-matrix slicing) to build the
    null AUC distribution, calling _c2st_auc directly on sparse row slices.
    permutation_test() is skipped because it calls np.vstack which converts
    sparse matrices to dense, breaking sklearn's sparse-aware path.
    """
    from _divergence_c2st import _c2st_auc
    from _divergence_io import fit_lexical_vectorizer, iter_lexical_windows

    div_cfg = cfg["divergence"]
    c2st_cfg = div_cfg.get("c2st", {})
    cv_folds = c2st_cfg.get("cv_folds", 5)
    class_weight = c2st_cfg.get("class_weight", "balanced")
    seed = div_cfg["random_seed"]
    n_perm = div_cfg["permutation"]["n_perm"]

    vectorizer = fit_lexical_vectorizer(cfg)

    rows = []
    for y, w, texts_before, texts_after, perm_rng in iter_lexical_windows(div_df, cfg):
        all_texts = texts_before + texts_after
        X_all = vectorizer.transform(all_texts)
        n_before = len(texts_before)

        # Observed statistic on un-permuted split
        observed = _c2st_auc(
            X_all[:n_before],
            X_all[n_before:],
            cv_folds=cv_folds,
            class_weight=class_weight,
            seed=seed,
        )["mean"]

        # Manual permutation loop — sparse slicing avoids dense conversion
        null_stats = []
        for i in range(n_perm):
            idx = perm_rng.permutation(X_all.shape[0])
            X_perm_before = X_all[idx[:n_before]]
            X_perm_after = X_all[idx[n_before:]]
            null_auc = _c2st_auc(
                X_perm_before,
                X_perm_after,
                cv_folds=cv_folds,
                class_weight=class_weight,
                seed=seed + i,
            )["mean"]
            null_stats.append(null_auc)

        null_stats_arr = np.array(null_stats)
        null_mean = float(np.mean(null_stats_arr))
        null_std = float(np.std(null_stats_arr))
        z = (observed - null_mean) / null_std if null_std > 0 else 0.0
        p = float(np.mean(null_stats_arr >= observed))

        rows.append(_result_row(y, w, observed, null_mean, null_std, z, p))
        log.info("  C2ST_lexical year=%d window=%d z=%.2f p=%.3f", y, w, z, p)

    return pd.DataFrame(rows)
