"""Schematic figure: Jensen-Shannon Divergence on TF-IDF.

Illustrates how JS divergence measures vocabulary shift between two time
windows.  Uses real corpus data: abstracts from 2000–2002 (before) and
2009–2011 (after crystallisation).

Usage::

    uv run python scripts/plot_schematic_L1_js.py \\
        --output content/figures/schematic_L1_js.png
"""

import os
import sys

import matplotlib.pyplot as plt
import numpy as np
from pipeline_io import save_figure
from pipeline_loaders import load_analysis_corpus
from plot_style import DARK, DPI, FIGWIDTH, LIGHT, MED, apply_style
from scipy.special import rel_entr
from script_io_args import parse_io_args, validate_io
from sklearn.feature_extraction.text import TfidfVectorizer
from utils import get_logger

log = get_logger("plot_schematic_L1_js")
apply_style()

# --------------------------------------------------------------------------- #
# Configuration                                                                #
# --------------------------------------------------------------------------- #
BEFORE_YEARS = (2000, 2002)
AFTER_YEARS = (2009, 2011)
TOP_N = 15  # number of terms to show in the bar chart
TOP_DIFF = 5  # terms with largest |P-Q| to highlight
MIN_DOCS = 3  # minimum document frequency for vocabulary


def _get_texts(df, year_range: tuple[int, int]) -> list[str]:
    """Collect non-empty abstract strings for the given year range."""
    lo, hi = year_range
    sub = df[(df["year"] >= lo) & (df["year"] <= hi)]
    texts = []
    for _, row in sub.iterrows():
        parts = []
        if isinstance(row.get("title"), str) and row["title"]:
            parts.append(row["title"])
        if isinstance(row.get("abstract"), str) and row["abstract"]:
            parts.append(row["abstract"])
        if parts:
            texts.append(" ".join(parts))
    return texts


def _js_divergence(p: np.ndarray, q: np.ndarray) -> float:
    """Compute JS(P || Q) = 0.5 * KL(P || M) + 0.5 * KL(Q || M)."""
    m = 0.5 * (p + q)
    # rel_entr(a, b) = a * log(a/b) element-wise, 0 when a=0
    kl_pm = np.sum(rel_entr(p, m))
    kl_qm = np.sum(rel_entr(q, m))
    return 0.5 * (kl_pm + kl_qm)


def main() -> None:
    io_args, _extra = parse_io_args()
    validate_io(output=io_args.output)

    log.info("Loading corpus …")
    df, _ = load_analysis_corpus(with_embeddings=False)

    texts_before = _get_texts(df, BEFORE_YEARS)
    texts_after = _get_texts(df, AFTER_YEARS)
    log.info(
        "Before (%d–%d): %d docs  |  After (%d–%d): %d docs",
        *BEFORE_YEARS,
        len(texts_before),
        *AFTER_YEARS,
        len(texts_after),
    )

    if not texts_before or not texts_after:
        log.error("Insufficient documents in one or both windows. Aborting.")
        sys.exit(1)

    # --------------------------------------------------------------------- #
    # TF-IDF on combined corpus                                              #
    # --------------------------------------------------------------------- #
    vectorizer = TfidfVectorizer(
        stop_words="english",
        min_df=MIN_DOCS,
        max_features=500,
        ngram_range=(1, 2),
        sublinear_tf=True,
    )
    all_texts = texts_before + texts_after
    tfidf_matrix = vectorizer.fit_transform(all_texts)
    vocab = vectorizer.get_feature_names_out()

    n_before = len(texts_before)
    mat_before = tfidf_matrix[:n_before]
    mat_after = tfidf_matrix[n_before:]

    # Mean TF-IDF vector per group
    p_raw = np.asarray(mat_before.mean(axis=0)).flatten()
    q_raw = np.asarray(mat_after.mean(axis=0)).flatten()

    # Normalise to sum=1 (probability distributions)
    p = p_raw / p_raw.sum() if p_raw.sum() > 0 else p_raw
    q = q_raw / q_raw.sum() if q_raw.sum() > 0 else q_raw
    m = 0.5 * (p + q)

    # Select TOP_N terms by total TF-IDF weight
    total_weight = p + q
    top_idx = np.argsort(total_weight)[-TOP_N:][::-1]
    top_idx = top_idx[np.argsort(total_weight[top_idx])[::-1]]

    top_terms = vocab[top_idx]
    p_top = p[top_idx]
    q_top = q[top_idx]
    m_top = m[top_idx]

    # Top-DIFF terms by largest absolute difference
    diff = np.abs(p_top - q_top)
    highlight_idx = set(np.argsort(diff)[-TOP_DIFF:])

    js = _js_divergence(p, q)
    log.info("JS divergence: %.4f nats", js)

    # --------------------------------------------------------------------- #
    # Plot                                                                   #
    # --------------------------------------------------------------------- #
    fig, ax = plt.subplots(figsize=(FIGWIDTH, 3.6))

    x = np.arange(TOP_N)
    bar_width = 0.32

    bars_p = ax.bar(
        x - bar_width / 2,
        p_top,
        width=bar_width,
        color="#4477AA",
        alpha=0.75,
        label=f"P  ({BEFORE_YEARS[0]}–{BEFORE_YEARS[1]})",
        zorder=3,
    )
    bars_q = ax.bar(
        x + bar_width / 2,
        q_top,
        width=bar_width,
        color="#CC4444",
        alpha=0.75,
        label=f"Q  ({AFTER_YEARS[0]}–{AFTER_YEARS[1]})",
        zorder=3,
    )

    # M = (P+Q)/2 as grey outline
    ax.bar(
        x - bar_width / 2,
        m_top,
        width=bar_width * 2,
        fc="none",
        ec=MED,
        lw=0.6,
        ls="--",
        label="M = (P+Q)/2",
        zorder=4,
    )

    # Highlight top-DIFF terms with a star marker above the bar pair
    for i in sorted(highlight_idx):
        yval = max(p_top[i], q_top[i])
        ax.plot(x[i], yval + 0.0008, marker="*", ms=5, color=DARK, zorder=5)

    ax.set_xticks(x)
    ax.set_xticklabels(top_terms, rotation=45, ha="right", fontsize=6)

    # Colour tick labels for highlighted terms
    for tick, i in zip(ax.get_xticklabels(), range(TOP_N)):
        if i in highlight_idx:
            tick.set_color(DARK)
            tick.set_fontweight("bold")
        else:
            tick.set_color(MED)

    ax.set_ylabel("Mean TF-IDF weight (normalised)")
    ax.set_title(
        "JS Divergence: how different are the vocabularies?", fontsize=9, color=DARK
    )

    # JS formula + value in legend
    leg = ax.legend(
        loc="upper right",
        fontsize=6.5,
        frameon=True,
        framealpha=0.9,
        edgecolor=LIGHT,
        title=f"JS(P‖Q) = ½KL(P‖M) + ½KL(Q‖M) = {js:.3f}",
        title_fontsize=6.5,
    )

    # Footnote: bold = largest divergence
    ax.text(
        0.01,
        0.99,
        "Bold labels: top 5 terms with largest |P − Q|",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=6,
        color=MED,
        style="italic",
    )

    fig.tight_layout()

    stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, stem, dpi=DPI)
    plt.close(fig)
    log.info("Saved schematic_L1_js to %s.png", stem)


if __name__ == "__main__":
    sys.exit(main())
