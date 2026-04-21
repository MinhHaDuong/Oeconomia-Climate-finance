"""Schematic figure: Term Burst Detection.

Illustrates how burst detection identifies years where a term's usage
spikes significantly above its baseline frequency.  Uses real corpus data
to compute annual term frequencies and z-scores, then highlights burst years.

Usage::

    uv run python scripts/plot_schematic_L3_burst.py \\
        --output content/figures/schematic_L3_burst.png
"""

import os
import sys

import matplotlib.pyplot as plt
import numpy as np
from pipeline_io import save_figure
from pipeline_loaders import load_analysis_corpus
from plot_style import DARK, DPI, FIGWIDTH, LIGHT, MED, apply_style
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("plot_schematic_L3_burst")
apply_style()

# --------------------------------------------------------------------------- #
# Configuration                                                                #
# --------------------------------------------------------------------------- #
YEAR_MIN = 1995
YEAR_MAX = 2022
BURST_Z = 2.0  # z-score threshold for declaring a burst
N_TERMS = 3  # number of terms to show
CANDIDATE_TERMS = [
    "green bond",
    "carbon market",
    "climate risk",
    "green finance",
    "carbon price",
    "adaptation finance",
    "climate fund",
    "renewable energy",
]


def _count_term(texts: list[str], term: str) -> dict[int, int]:
    """Count works containing *term* (case-insensitive) by year."""
    return {yr: int(sum(term in t for t in texts[yr])) for yr in texts}


def _build_year_texts(df) -> dict[int, list[str]]:
    """Map year → list of lowercase title+abstract strings."""
    result: dict[int, list[str]] = {}
    for yr in range(YEAR_MIN, YEAR_MAX + 1):
        sub = df[df["year"] == yr]
        texts = []
        for _, row in sub.iterrows():
            parts = []
            if isinstance(row.get("title"), str):
                parts.append(row["title"])
            if isinstance(row.get("abstract"), str):
                parts.append(row["abstract"])
            texts.append(" ".join(parts).lower())
        result[yr] = texts
    return result


def _select_terms(year_texts: dict[int, list[str]]) -> list[tuple[str, np.ndarray]]:
    """Pick N_TERMS candidates with clearest temporal spikes."""
    years = np.arange(YEAR_MIN, YEAR_MAX + 1)
    scored = []
    for term in CANDIDATE_TERMS:
        counts = np.array(
            [_count_term(year_texts, term)[yr] for yr in years], dtype=float
        )
        mu = counts.mean()
        sigma = counts.std()
        if sigma < 0.5:
            continue  # flat signal — skip
        z = (counts - mu) / sigma
        score = z.max()  # peak z-score
        scored.append((score, term, counts))

    scored.sort(reverse=True)
    selected = []
    for _, term, counts in scored[:N_TERMS]:
        selected.append((term, counts))

    if len(selected) < N_TERMS:
        log.warning(
            "Only %d terms had enough signal; wanted %d", len(selected), N_TERMS
        )

    return selected


def main() -> None:
    io_args, _extra = parse_io_args()
    validate_io(output=io_args.output)

    log.info("Loading corpus …")
    df, _ = load_analysis_corpus(with_embeddings=False)
    df = df[(df["year"] >= YEAR_MIN) & (df["year"] <= YEAR_MAX)].copy()
    log.info("Corpus rows in %d–%d: %d", YEAR_MIN, YEAR_MAX, len(df))

    year_texts = _build_year_texts(df)
    terms = _select_terms(year_texts)
    if not terms:
        log.error("No terms with sufficient signal. Aborting.")
        sys.exit(1)

    years = np.arange(YEAR_MIN, YEAR_MAX + 1)
    n = len(terms)

    fig, axes = plt.subplots(
        n,
        1,
        figsize=(FIGWIDTH, 1.8 * n + 0.6),
        sharex=True,
    )
    if n == 1:
        axes = [axes]
    fig.subplots_adjust(hspace=0.55)
    fig.suptitle(
        "Burst Detection: which terms spiked and when?", fontsize=9, color=DARK, y=0.99
    )

    for ax, (term, counts) in zip(axes, terms):
        mu = counts.mean()
        sigma = counts.std() if counts.std() > 0 else 1.0
        z_scores = (counts - mu) / sigma
        threshold = mu + BURST_Z * sigma

        colors = []
        for z in z_scores:
            if z >= BURST_Z:
                colors.append("#CC4444")  # burst year
            else:
                colors.append(LIGHT)

        ax.bar(years, counts, color=colors, width=0.8, zorder=2)

        # Threshold line
        ax.axhline(
            threshold,
            color=DARK,
            lw=0.8,
            ls="--",
            zorder=3,
            label=f"μ + {BURST_Z:g}σ threshold",
        )

        # Mean line
        ax.axhline(mu, color=MED, lw=0.5, ls=":", zorder=3)

        # Annotate burst years
        burst_yrs = years[z_scores >= BURST_Z]
        for yr in burst_yrs:
            idx = yr - YEAR_MIN
            ax.text(
                yr,
                counts[idx] + 0.3,
                str(yr),
                ha="center",
                va="bottom",
                fontsize=5.5,
                color="#CC4444",
                fontweight="bold",
            )

        ax.set_ylabel("Works / year", fontsize=7)
        ax.set_title(f'"{term}"', fontsize=8, color=DARK, pad=2)

        # Legend entry for burst bars
        burst_patch = plt.Rectangle(
            (0, 0), 1, 1, fc="#CC4444", alpha=0.8, label="Burst year (z ≥ 2)"
        )
        normal_patch = plt.Rectangle((0, 0), 1, 1, fc=LIGHT, label="Normal year")
        ax.legend(
            handles=[burst_patch, normal_patch],
            loc="upper left",
            fontsize=5.5,
            frameon=False,
            ncol=2,
        )

    axes[-1].set_xlabel("Year")
    axes[-1].set_xlim(YEAR_MIN - 0.5, YEAR_MAX + 0.5)
    axes[-1].set_xticks(range(YEAR_MIN, YEAR_MAX + 1, 5))

    stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, stem, dpi=DPI)
    plt.close(fig)
    log.info("Saved schematic_L3_burst to %s.png", stem)


if __name__ == "__main__":
    sys.exit(main())
