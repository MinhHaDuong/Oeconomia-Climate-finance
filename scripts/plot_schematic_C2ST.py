"""ELI15 schematic: Classifier Two-Sample Test (C2ST).

Shows how a logistic regression classifier trained on paper embeddings can
distinguish papers from 2000–2002 (blue) vs. 2009–2011 (red). Accuracy above
0.5 confirms the two distributions differ.

Loads real embeddings when available; falls back to synthetic 2D Gaussian
clusters otherwise.

Usage::

    uv run python scripts/plot_schematic_C2ST.py \\
        --output /tmp/test_C2ST.png
"""

import os
import sys

import matplotlib.pyplot as plt
import numpy as np
from pipeline_io import save_figure
from plot_style import DARK, DPI, FIGWIDTH, LIGHT, MED, apply_style
from script_io_args import parse_io_args, validate_io
from sklearn.decomposition import PCA
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import StratifiedKFold, cross_val_score
from utils import get_logger

log = get_logger("plot_schematic_C2ST")
apply_style()

# Window definitions — schematic choices, not research parameters
YEARS_BEFORE = (2000, 2002)
YEARS_AFTER = (2009, 2011)
N_SUBSAMPLE = 30
N_CV_FOLDS = 5
# Fixed seed — schematic only, not a research parameter
_SEED = 42


def _load_real_embeddings():
    """Load real embeddings aligned with works; raise FileNotFoundError if absent."""
    from pipeline_loaders import load_analysis_corpus

    works, embeddings = load_analysis_corpus(with_embeddings=True)
    if embeddings is None:
        raise FileNotFoundError("Embeddings not available from load_analysis_corpus.")
    return works, embeddings


def _subsample(X, rng, n):
    """Random subsample of n rows (or all rows if fewer available)."""
    idx = rng.choice(len(X), size=min(n, len(X)), replace=False)
    return X[idx]


def _decision_boundary_line(clf, X_2d, ax):
    """Compute and draw the logistic regression decision boundary in 2D."""
    x_min, x_max = X_2d[:, 0].min() - 0.5, X_2d[:, 0].max() + 0.5
    y_min, y_max = X_2d[:, 1].min() - 0.5, X_2d[:, 1].max() + 0.5

    xx, yy = np.meshgrid(
        np.linspace(x_min, x_max, 300),
        np.linspace(y_min, y_max, 300),
    )
    Z = clf.predict(np.c_[xx.ravel(), yy.ravel()]).reshape(xx.shape)

    # Shade regions
    ax.contourf(
        xx,
        yy,
        Z,
        levels=[-0.5, 0.5, 1.5],
        colors=["#4477AA", "#CC4444"],
        alpha=0.08,
        zorder=0,
    )
    # Decision boundary line
    ax.contour(xx, yy, Z, levels=[0.5], colors=[MED], linewidths=[1.5], zorder=2)

    return x_min, x_max, y_min, y_max


def main():
    io_args, _ = parse_io_args()
    validate_io(output=io_args.output)

    rng = np.random.default_rng(_SEED)
    using_real = False

    # --- Load data ---
    try:
        works, embeddings = _load_real_embeddings()
        mask_before = works["year"].between(*YEARS_BEFORE)
        mask_after = works["year"].between(*YEARS_AFTER)
        emb_before = embeddings[mask_before.values]
        emb_after = embeddings[mask_after.values]
        log.info(
            "Real embeddings: %d before, %d after",
            len(emb_before),
            len(emb_after),
        )
        if len(emb_before) < 5 or len(emb_after) < 5:
            raise ValueError("Too few papers in one window for a meaningful schematic.")
        using_real = True
    except (FileNotFoundError, ValueError) as exc:
        log.warning("Real embeddings unavailable (%s) — using synthetic data.", exc)

    if not using_real:
        # Synthetic: two overlapping Gaussian clusters in high-D, PCA will reveal shift
        dim = 50
        emb_before = rng.normal(loc=0.0, scale=1.0, size=(80, dim))
        emb_after = rng.normal(loc=0.6, scale=1.0, size=(80, dim))

    # Subsample to N_SUBSAMPLE per group
    emb_before_sub = _subsample(emb_before, rng, N_SUBSAMPLE)
    emb_after_sub = _subsample(emb_after, rng, N_SUBSAMPLE)

    X_all = np.vstack([emb_before_sub, emb_after_sub])
    y_all = np.array([0] * len(emb_before_sub) + [1] * len(emb_after_sub), dtype=int)

    # PCA to 2D (fit on all 60 points)
    pca = PCA(n_components=2, random_state=_SEED)
    X_2d = pca.fit_transform(X_all)

    # Logistic regression: fit on all 60 for the boundary visualisation
    clf_vis = LogisticRegression(
        random_state=_SEED,
        max_iter=1000,
        C=1.0,
    )
    clf_vis.fit(X_2d, y_all)

    # 5-fold CV accuracy
    skf = StratifiedKFold(n_splits=N_CV_FOLDS, shuffle=True, random_state=_SEED)
    cv_scores = cross_val_score(clf_vis, X_2d, y_all, cv=skf, scoring="accuracy")
    cv_acc = float(cv_scores.mean())
    log.info(
        "CV accuracy: %.3f ± %.3f (folds: %s)",
        cv_acc,
        cv_scores.std(),
        np.round(cv_scores, 3),
    )

    # --- Figure ---
    fig, ax = plt.subplots(figsize=(FIGWIDTH, 3.8))

    # Decision boundary + shading
    _decision_boundary_line(clf_vis, X_2d, ax)

    # Scatter points
    X_b = X_2d[y_all == 0]
    X_a = X_2d[y_all == 1]
    ax.scatter(
        X_b[:, 0],
        X_b[:, 1],
        c="#4477AA",
        s=30,
        alpha=0.80,
        zorder=3,
        label=f"Before {YEARS_BEFORE[0]}–{YEARS_BEFORE[1]}",
        linewidths=0.3,
        edgecolors="white",
    )
    ax.scatter(
        X_a[:, 0],
        X_a[:, 1],
        c="#CC4444",
        s=30,
        alpha=0.80,
        zorder=3,
        label=f"After {YEARS_AFTER[0]}–{YEARS_AFTER[1]}",
        linewidths=0.3,
        edgecolors="white",
        marker="^",
    )

    ax.set_xlabel(
        f"PC 1  ({pca.explained_variance_ratio_[0]:.0%} variance)", fontsize=8
    )
    ax.set_ylabel(
        f"PC 2  ({pca.explained_variance_ratio_[1]:.0%} variance)", fontsize=8
    )

    # Accuracy annotation
    ax.text(
        0.03,
        0.97,
        f"Accuracy = {cv_acc:.2f}  ({N_CV_FOLDS}-fold CV)",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=8,
        color=DARK,
        fontweight="bold",
        bbox=dict(boxstyle="round,pad=0.3", fc="#F5F5F5", ec=LIGHT, lw=0.5),
    )
    ax.text(
        0.03,
        0.83,
        "Baseline = 0.50 (random guess)",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=7,
        color=MED,
        style="italic",
    )
    ax.axhline(
        y=np.nan, color=MED, linewidth=1.5, linestyle="-", label="Decision boundary"
    )

    # Feature-space note
    ax.text(
        0.97,
        0.04,
        "Works for any feature space\n— here: paper embeddings",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=6.5,
        color=MED,
        style="italic",
    )

    # Formula box
    formula = (
        r"$C2ST$ = CV accuracy of a classifier between before/after" + "\n"
        r"Accuracy $>$ 0.5 $\Rightarrow$ the two distributions differ"
    )
    ax.text(
        0.5,
        -0.18,
        formula,
        transform=ax.transAxes,
        ha="center",
        va="top",
        fontsize=6.5,
        color=DARK,
        bbox=dict(boxstyle="round,pad=0.3", fc="#F5F5F5", ec=LIGHT, lw=0.5),
    )

    ax.legend(loc="upper right", frameon=False, fontsize=7)

    src = "synthetic" if not using_real else "real corpus"
    ax.set_title(
        "C2ST: can a classifier tell 'before' from 'after'?",
        fontsize=8.5,
        color=DARK,
    )
    fig.text(
        0.5,
        0.98,
        f"Accuracy > 0.5 confirms the distributions differ — but not where or why.  [{src} data]",
        ha="center",
        va="top",
        fontsize=6.5,
        color=MED,
        style="italic",
    )

    fig.tight_layout(rect=[0, 0.10, 1, 0.96])

    stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, stem, dpi=DPI)
    plt.close(fig)
    log.info("Saved → %s.png", stem)


if __name__ == "__main__":
    sys.exit(main())
