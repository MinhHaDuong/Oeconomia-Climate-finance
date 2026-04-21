"""ELI15 schematic: Bibliographic Coupling Age (G3).

Shows citation-age distributions for two time windows (before/after 2007),
with an exponential decay fit overlaid.  Based on Price (1965) and
Redner (1998) on citation statistics.

Usage::

    uv run python scripts/plot_schematic_G3_coupling_age.py \\
        --output /tmp/test_G3.png
"""

import os
import sys

import matplotlib.pyplot as plt
import numpy as np
from pipeline_io import save_figure
from plot_style import DARK, DPI, FIGWIDTH, FILL, LIGHT, MED, apply_style
from script_io_args import parse_io_args, validate_io
from utils import get_logger

log = get_logger("plot_schematic_G3_coupling_age")
apply_style()

# Schematic windows — display choices, not research params
WINDOW_BEFORE = (2000, 2004)
WINDOW_AFTER = (2007, 2011)
AGE_MIN, AGE_MAX = 0, 30


def _exp_decay(age, A, lam):
    return A * np.exp(-lam * age)


def _load_real_ages():
    """Load real citation data and return age arrays for before/after windows."""
    from pipeline_loaders import load_analysis_corpus, load_refined_citations

    works, _ = load_analysis_corpus(with_embeddings=False)
    citations = load_refined_citations()
    works = works.dropna(subset=["doi"]).copy()

    corpus_dois = set(works["doi"].values)
    doi_to_year = dict(zip(works["doi"], works["year"]))

    mask = citations["source_doi"].isin(corpus_dois) & citations["ref_doi"].isin(
        corpus_dois
    )
    internal = citations.loc[mask, ["source_doi", "ref_doi"]].copy()
    internal["source_year"] = internal["source_doi"].map(doi_to_year)
    internal["ref_year"] = internal["ref_doi"].map(doi_to_year)
    internal = internal.dropna(subset=["source_year", "ref_year"])
    internal["age"] = internal["source_year"] - internal["ref_year"]
    internal = internal[internal["age"].between(AGE_MIN, AGE_MAX)]

    def _window_ages(lo, hi):
        mask_w = internal["source_year"].between(lo, hi)
        return internal.loc[mask_w, "age"].values.astype(int)

    ages_before = _window_ages(*WINDOW_BEFORE)
    ages_after = _window_ages(*WINDOW_AFTER)
    if len(ages_before) < 50 or len(ages_after) < 50:
        raise ValueError("Too few citation edges in windows for real data plot.")
    return ages_before, ages_after


def _synthetic_ages(mean_age, n=4000, seed_offset=0):
    """Draw ages from an exponential with given mean; truncate to [0, AGE_MAX]."""
    # Fixed seed for schematic reproducibility — not a research parameter
    rng = np.random.default_rng(42 + seed_offset)
    ages = rng.exponential(scale=mean_age, size=n * 2).astype(int)
    ages = ages[(ages >= AGE_MIN) & (ages <= AGE_MAX)]
    return ages[:n]


def _fit_exponential(age_array):
    """Fit A * exp(-lam * age) via scipy.optimize.curve_fit; return (A, lam)."""
    from scipy.optimize import curve_fit

    bins = np.arange(AGE_MIN, AGE_MAX + 1)
    counts, _ = np.histogram(age_array, bins=bins)
    ages_mid = bins[:-1].astype(float)

    # Mask empty bins for fitting
    valid = counts > 0
    try:
        popt, _ = curve_fit(
            _exp_decay,
            ages_mid[valid],
            counts[valid].astype(float),
            p0=[counts.max(), 0.2],
            maxfev=2000,
        )
        return float(popt[0]), float(popt[1])
    except Exception as exc:
        log.warning("curve_fit failed (%s) — using mean estimate.", exc)
        lam = 1.0 / max(age_array.mean(), 1.0)
        return float(counts.max()), float(lam)


def _draw_panel(ax, ages, color, window_label, label):
    """Draw age histogram + exponential fit on ax."""
    bins = np.arange(AGE_MIN, AGE_MAX + 2, 1) - 0.5
    counts, edges = np.histogram(ages, bins=bins)
    age_centres = (edges[:-1] + edges[1:]) / 2

    # Grey histogram bars
    ax.bar(
        age_centres,
        counts,
        width=0.8,
        color=FILL,
        edgecolor=LIGHT,
        linewidth=0.3,
        zorder=2,
        label="observed",
    )

    # Exponential fit overlay
    A, lam = _fit_exponential(ages)
    age_fit = np.linspace(0, AGE_MAX, 200)
    ax.semilogy(
        age_fit,
        _exp_decay(age_fit, A, lam),
        color=color,
        linewidth=1.4,
        zorder=3,
        label=rf"$A\,e^{{-\lambda t}}$  ($\lambda$={lam:.2f})",
    )

    # Make y-axis log
    ax.set_yscale("log")
    ax.set_ylim(bottom=0.8)

    mean_age = ages.mean()
    ax.text(
        0.97,
        0.95,
        f"mean age = {mean_age:.1f} yr",
        transform=ax.transAxes,
        ha="right",
        va="top",
        fontsize=6.5,
        color=DARK,
        bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=LIGHT, lw=0.4),
    )

    ax.set_xlabel("Citation age (years)", fontsize=7)
    ax.set_ylabel("Citation count (log scale)", fontsize=7)
    ax.set_title(
        f"{window_label[0]}–{window_label[1]}\n({label})",
        fontsize=7.5,
        color=DARK,
        pad=3,
    )
    ax.legend(frameon=False, fontsize=6, loc="upper right")
    ax.set_xlim(-0.5, AGE_MAX + 0.5)
    return mean_age


def main():
    io_args, _ = parse_io_args()
    validate_io(output=io_args.output)

    using_real = False
    try:
        ages_before, ages_after = _load_real_ages()
        using_real = True
        log.info("Loaded real citation ages.")
    except Exception as exc:
        log.warning("Real data unavailable (%s) — using synthetic ages.", exc)
        ages_before = _synthetic_ages(mean_age=8.0, seed_offset=0)
        ages_after = _synthetic_ages(mean_age=5.5, seed_offset=1)

    fig, (ax_b, ax_a) = plt.subplots(1, 2, figsize=(FIGWIDTH, 3.2), sharey=False)
    plt.subplots_adjust(left=0.11, right=0.97, top=0.78, bottom=0.18, wspace=0.42)

    mean_b = _draw_panel(ax_b, ages_before, "#4477AA", WINDOW_BEFORE, "before")
    mean_a = _draw_panel(ax_a, ages_after, "#CC4444", WINDOW_AFTER, "after")

    g3 = abs(mean_a - mean_b)
    src = "synthetic" if not using_real else "real corpus"
    log.info("mean_before=%.1f yr, mean_after=%.1f yr, G3=%.2f yr", mean_b, mean_a, g3)

    # Arrow between panels showing shift in mean age
    fig.text(
        0.50,
        0.48,
        f"Δ mean age = {g3:.1f} yr",
        ha="center",
        va="center",
        fontsize=7,
        color=DARK,
        bbox=dict(boxstyle="round,pad=0.25", fc="white", ec=LIGHT, lw=0.5),
    )

    # G3 formula box
    fig.text(
        0.5,
        0.01,
        rf"$G3 = \Delta(\text{{mean citation age}}) = {g3:.2f}$ yr"
        f"   [{src} data]",
        ha="center",
        va="bottom",
        fontsize=6.5,
        color=DARK,
        bbox=dict(boxstyle="round,pad=0.3", fc="#F5F5F5", ec=LIGHT, lw=0.5),
    )

    fig.suptitle(
        "Bibliographic Coupling Age: how far back do papers cite?",
        fontsize=8,
        color=DARK,
        y=1.01,
    )
    fig.text(
        0.5,
        0.96,
        "Exponential decay fit (Price 1965) — older = deeper canon; younger = faster-moving field.",
        ha="center",
        va="top",
        fontsize=6.5,
        color=MED,
        style="italic",
    )

    stem = os.path.splitext(io_args.output)[0]
    save_figure(fig, stem, dpi=DPI)
    plt.close(fig)
    log.info("Saved → %s.png", stem)


if __name__ == "__main__":
    sys.exit(main())
